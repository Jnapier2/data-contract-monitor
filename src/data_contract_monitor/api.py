from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __build_id__, __version__
from .artifacts import publish_run_artifacts
from .contract_loader import ContractLoadError, load_contract
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


def _is_known_windows_proactor_reset(context: dict[str, Any]) -> bool:
    """Match only the benign Windows Proactor disconnect observed in field evidence.

    A browser or local client can reset a loopback connection after Uvicorn has
    already completed the useful request. Windows' Proactor transport may then
    surface WinError 10054 from ``_call_connection_lost`` as an event-loop
    callback exception even though the server remains healthy. Other asyncio
    exceptions are deliberately not suppressed.
    """

    exc = context.get("exception")
    if not isinstance(exc, ConnectionResetError):
        return False
    winerror = getattr(exc, "winerror", None)
    errno_value = getattr(exc, "errno", None)
    if winerror != 10054 and errno_value != 10054:
        return False
    signature = "_ProactorBasePipeTransport._call_connection_lost"
    return signature in str(context.get("message", "")) or signature in str(context.get("handle", ""))


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
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()
        installed_handler = None
        if os.name == "nt":
            def windows_loop_handler(active_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
                if _is_known_windows_proactor_reset(context):
                    return
                if previous_handler is not None:
                    previous_handler(active_loop, context)
                else:
                    active_loop.default_exception_handler(context)

            installed_handler = windows_loop_handler
            loop.set_exception_handler(installed_handler)
        try:
            yield
        finally:
            manager.shutdown()
            if installed_handler is not None and loop.get_exception_handler() is installed_handler:
                loop.set_exception_handler(previous_handler)

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
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

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
            "execution_modes": ["auto", "memory", "streaming"],
            "streaming_data": ["csv", "jsonl"],
            "report_formats": ["json", "html", "junit", "sarif"],
            "privacy": "Raw cell values are not included in validation results.",
            "limits": limits.public_dict(),
        }

    @app.post("/api/jobs/validate", status_code=202)
    async def queue_validation(
        contract: Annotated[UploadFile, File(description="YAML data contract")],
        data: Annotated[UploadFile, File(description="Dataset")],
        references: Annotated[list[UploadFile] | None, File(description="Optional reference datasets named as used by the contract")] = None,
        fail_on: Severity = Severity.ERROR,
        execution_mode: str = "auto",
    ) -> dict[str, object]:
        if execution_mode not in {"auto", "memory", "streaming"}:
            raise HTTPException(status_code=422, detail="execution_mode must be auto, memory, or streaming")
        temp_parent = root / "temp"
        work = Path(tempfile.mkdtemp(prefix="dcm_job_", dir=temp_parent))
        contract_suffix = Path(contract.filename or "contract.yml").suffix or ".yml"
        data_suffix = Path(data.filename or "data.csv").suffix or ".csv"
        contract_path = work / "contracts" / f"contract{contract_suffix}"
        data_path = work / "data" / f"dataset{data_suffix}"
        try:
            await _save_upload(contract, contract_path, limits.max_contract_bytes)
            await _save_upload(data, data_path, limits.max_data_bytes)
            try:
                loaded_contract = load_contract(contract_path)
            except ContractLoadError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            expected_references: dict[str, Path] = {}
            for rule in loaded_contract.dataset_rules:
                if rule.type != "reference_exists" or not rule.reference_dataset:
                    continue
                relative = Path(rule.reference_dataset)
                if relative.is_absolute():
                    raise HTTPException(status_code=422, detail="reference_dataset must be relative")
                destination = (contract_path.parent / relative).resolve()
                if work.resolve() != destination and work.resolve() not in destination.parents:
                    raise HTTPException(
                        status_code=422,
                        detail=f"reference_dataset escapes the isolated upload workspace: {rule.reference_dataset}",
                    )
                basename = relative.name
                prior = expected_references.get(basename)
                if prior is not None and prior != destination:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Ambiguous reference basename in contract: {basename}",
                    )
                expected_references[basename] = destination
            seen_reference_names: set[str] = set()
            for reference in references or []:
                name = Path(reference.filename or "reference.csv").name
                if name in seen_reference_names:
                    raise HTTPException(status_code=422, detail=f"Duplicate reference filename: {name}")
                destination = expected_references.get(name)
                if destination is None:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Uploaded reference '{name}' is not declared by the contract.",
                    )
                seen_reference_names.add(name)
                await _save_upload(reference, destination, limits.max_data_bytes)
            missing_reference_uploads = sorted(set(expected_references) - seen_reference_names)
            if missing_reference_uploads:
                raise HTTPException(
                    status_code=422,
                    detail="Missing uploaded reference dataset(s): " + ", ".join(missing_reference_uploads),
                )
            job_id = manager.submit(
                contract_path=contract_path,
                data_path=data_path,
                fail_on=fail_on,
                cleanup_dir=work,
                execution_mode=execution_mode,
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
            publish_run_artifacts(result, root=root, limits=limits)
            return result.model_dump(mode="json")

    @app.get("/api/history")
    def history(limit: int = 20) -> list[dict[str, object]]:
        return store.read_history(limit=min(max(limit, 1), 100))

    @app.get("/api/history/trend")
    def history_trend(dataset: str | None = None, limit: int = 20) -> dict[str, object]:
        return store.trend(dataset_name=dataset, limit=min(max(limit, 2), 500))

    @app.get("/api/runs/compare/{older_run_id}/{newer_run_id}")
    def compare_runs(older_run_id: str, newer_run_id: str) -> dict[str, object]:
        try:
            return store.compare_runs(older_run_id, newer_run_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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
        if name not in allowed or len(run_id) != 32 or any(
            character not in "0123456789abcdef" for character in run_id
        ):
            raise HTTPException(status_code=404, detail="Artifact not found")
        runs_root = (root / "reports" / "runs").resolve()
        path = (runs_root / run_id / name).resolve()
        try:
            path.relative_to(runs_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="Artifact not found") from None
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path)

    return app


app = create_app()
