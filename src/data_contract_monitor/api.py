from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __build_id__, __version__
from .artifacts import publish_run_artifacts
from .demo import write_demo_dataset
from .engine import validate_files
from .identity import verify_release_integrity
from .jobs import JobQueueFull, ValidationJobManager
from .limits import ResourceLimits
from .local_server import SERVICE_ID
from .models import Severity
from .runtime import bundled_demo_contract, ensure_runtime_directories, runtime_root
from .state_store import StateStore

SESSION_COOKIE = "dcm_session"
MODIFYING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SAFE_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _safe_local_origin(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.hostname in SAFE_ORIGIN_HOSTS


def _root() -> Path:
    return ensure_runtime_directories(runtime_root())


def _web_root() -> Path:
    root = _root()
    release_web = root / "frontend" / "dist"
    if (release_web / "index.html").is_file():
        return release_web
    return Path(__file__).resolve().parent / "web"


async def _save_upload(upload: UploadFile, destination: Path, maximum: int) -> None:
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds {maximum // (1024 * 1024)} MB limit",
                    )
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def create_app() -> FastAPI:
    root = _root()
    limits = ResourceLimits()
    manager = ValidationJobManager(root, limits=limits)
    store = StateStore(root / "state" / "dcm_state.sqlite3")
    web_root = _web_root()
    startup_integrity = verify_release_integrity(root)
    launch_id = os.environ.get("DCM_LAUNCH_ID")
    api_token = os.environ.get("DCM_API_TOKEN") or secrets.token_hex(32)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(
        title="Data Contract Monitor API",
        version=__version__,
        description=(
            "Local-first data contract validation with bounded jobs, durable history, "
            "and verified per-run artifacts."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )

    @app.middleware("http")
    async def local_write_guard(request: Request, call_next):
        if request.method in MODIFYING_METHODS and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and not _safe_local_origin(origin):
                return JSONResponse(status_code=403, content={"detail": "Cross-origin modifying requests are blocked."})
            if request.cookies.get(SESSION_COOKIE) != api_token:
                return JSONResponse(status_code=403, content={"detail": "Local session token is missing or invalid."})
        return await call_next(request)

    if web_root.exists():
        app.mount("/assets", StaticFiles(directory=web_root), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        response = FileResponse(web_root / "index.html")
        response.set_cookie(
            SESSION_COOKIE,
            api_token,
            httponly=True,
            samesite="strict",
            secure=False,
        )
        return response

    @app.get("/api/health")
    def health() -> dict[str, object]:
        state_health = store.health_check()
        healthy = startup_integrity.passed and bool(state_health.get("passed"))
        return {
            "service_id": SERVICE_ID,
            "name": "Data Contract Monitor",
            "status": "ok" if healthy else "degraded",
            "version": __version__,
            "build_id": __build_id__,
            "launch_id": launch_id,
            "integrity": startup_integrity.model_dump(mode="json"),
            "state": state_health,
            "local_only_default": True,
            "job_policy": {"workers": 1, "queued": 4},
        }

    @app.get("/api/about")
    def about() -> dict[str, object]:
        return {
            "name": "Data Contract Monitor",
            "version": __version__,
            "supported_data": ["csv", "xlsx", "xlsm", "json", "jsonl", "parquet-optional"],
            "report_formats": ["json", "html", "junit", "sarif"],
            "privacy": "Raw cell values are not included in validation results.",
            "limits": limits.public_dict(),
        }

    @app.post("/api/jobs/validate", status_code=202)
    async def queue_validation(
        contract: Annotated[UploadFile, File(description="YAML data contract")],
        data: Annotated[UploadFile, File(description="Dataset")],
        fail_on: Severity = Severity.ERROR,
    ) -> dict[str, object]:
        temp_parent = root / "temp"
        work = Path(tempfile.mkdtemp(prefix="dcm_job_", dir=temp_parent))
        contract_suffix = Path(contract.filename or "contract.yml").suffix or ".yml"
        data_suffix = Path(data.filename or "data.csv").suffix or ".csv"
        contract_path = work / f"contract{contract_suffix}"
        data_path = work / f"dataset{data_suffix}"
        try:
            await _save_upload(contract, contract_path, limits.max_contract_bytes)
            await _save_upload(data, data_path, limits.max_data_bytes)
            job_id = manager.submit(
                contract_path=contract_path,
                data_path=data_path,
                fail_on=fail_on,
                cleanup_dir=work,
            )
        except JobQueueFull as exc:
            shutil.rmtree(work, ignore_errors=True)
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise
        return {
            "job_id": job_id,
            "state": "queued",
            "contract_label": Path(contract.filename or "contract.yml").name,
            "data_label": Path(data.filename or "dataset").name,
        }

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict[str, object]:
        record = manager.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return record

    @app.get("/api/jobs")
    def jobs(limit: int = 20) -> list[dict[str, object]]:
        return manager.list(limit=min(max(limit, 1), 100))

    @app.delete("/api/jobs/{job_id}")
    def cancel_job(job_id: str) -> dict[str, object]:
        if manager.get(job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
        accepted = manager.cancel(job_id)
        return {"job_id": job_id, "cancellation_requested": accepted}

    @app.post("/api/demo/{scenario}")
    def demo(scenario: str) -> dict[str, object]:
        if scenario not in {"good", "bad"}:
            raise HTTPException(status_code=404, detail="Scenario must be 'good' or 'bad'")
        with tempfile.TemporaryDirectory(prefix="dcm_demo_", dir=root / "temp") as directory:
            data_path = write_demo_dataset(
                Path(directory) / f"customer_orders_{scenario}.csv", valid=scenario == "good"
            )
            result = validate_files(
                contract_path=bundled_demo_contract(),
                data_path=data_path,
                history_path=store.path,
                limits=limits,
            )
            publish_run_artifacts(result, root=root)
            return result.model_dump(mode="json")

    @app.get("/api/history")
    def history(limit: int = 20) -> list[dict[str, object]]:
        return store.read_history(limit=min(max(limit, 1), 100))

    @app.get("/api/runs/{run_id}")
    def run_result(run_id: str) -> dict[str, object]:
        result = store.get_result(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result

    @app.get("/api/runs/{run_id}/artifacts/{name}")
    def run_artifact(run_id: str, name: str) -> FileResponse:
        allowed = {
            "data_contract_report.json",
            "data_contract_report.html",
            "data_contract_report.xml",
            "data_contract_report.sarif",
            "artifact_manifest.json",
        }
        if name not in allowed:
            raise HTTPException(status_code=404, detail="Artifact not found")
        path = root / "reports" / "runs" / run_id / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path)

    return app


app = create_app()
