from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __build_id__, __version__
from .demo import write_demo_dataset
from .engine import validate_files
from .history import read_history
from .identity import find_project_root, verify_release_integrity
from .local_server import SERVICE_ID
from .runtime import bundled_demo_contract, ensure_runtime_directories, runtime_root
from .models import Severity

MAX_CONTRACT_BYTES = 1 * 1024 * 1024
MAX_DATA_BYTES = 50 * 1024 * 1024


def _root() -> Path:
    return ensure_runtime_directories(runtime_root())


def _web_root() -> Path:
    root = _root()
    release_web = root / "frontend" / "dist"
    if all((release_web / name).is_file() for name in ("index.html", "app.js", "styles.css")):
        return release_web
    return Path(__file__).resolve().parent / "web"


async def _save_upload(upload: UploadFile, destination: Path, maximum: int) -> None:
    size = 0
    with destination.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > maximum:
                raise HTTPException(status_code=413, detail=f"Upload exceeds {maximum // (1024 * 1024)} MB limit")
            handle.write(chunk)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Data Contract Monitor API",
        version=__version__,
        description="Local-first data contract validation. Uploaded files remain on the local process and are deleted after each request.",
    )
    web_root = _web_root()
    startup_integrity = verify_release_integrity(_root())
    launch_id = os.environ.get("DCM_LAUNCH_ID")
    if web_root.exists():
        app.mount("/assets", StaticFiles(directory=web_root), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(web_root / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "service_id": SERVICE_ID,
            "name": "Data Contract Monitor",
            "status": "ok" if startup_integrity.passed else "degraded",
            "version": __version__,
            "build_id": __build_id__,
            "launch_id": launch_id,
            "integrity": startup_integrity.model_dump(mode="json"),
            "local_only_default": True,
        }

    @app.get("/api/about")
    def about() -> dict[str, object]:
        return {
            "name": "Data Contract Monitor",
            "version": __version__,
            "supported_data": ["csv", "xlsx", "xlsm", "json", "jsonl", "parquet-optional"],
            "report_formats": ["json", "html", "junit", "sarif"],
            "privacy": "Raw cell values are not included in validation results.",
        }

    @app.post("/api/validate")
    async def validate(
        contract: Annotated[UploadFile, File(description="YAML data contract")],
        data: Annotated[UploadFile, File(description="Dataset")],
        fail_on: Severity = Severity.ERROR,
    ) -> dict[str, object]:
        root = _root()
        temp_parent = root / "temp"
        temp_parent.mkdir(parents=True, exist_ok=True)
        contract_suffix = Path(contract.filename or "contract.yml").suffix or ".yml"
        data_suffix = Path(data.filename or "data.csv").suffix or ".csv"
        with tempfile.TemporaryDirectory(prefix="dcm_api_", dir=temp_parent) as directory:
            work = Path(directory)
            contract_path = work / f"contract{contract_suffix}"
            data_path = work / f"dataset{data_suffix}"
            await _save_upload(contract, contract_path, MAX_CONTRACT_BYTES)
            await _save_upload(data, data_path, MAX_DATA_BYTES)
            try:
                result = validate_files(
                    contract_path=contract_path,
                    data_path=data_path,
                    fail_on=fail_on,
                    history_path=root / "state" / "history.jsonl",
                )
            except Exception as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            payload = result.model_dump(mode="json")
            payload["contract_label"] = Path(contract.filename or "contract.yml").name
            payload["data_label"] = Path(data.filename or "dataset").name
            latest = root / "reports" / "latest_result.json"
            latest.parent.mkdir(parents=True, exist_ok=True)
            latest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return payload

    @app.post("/api/demo/{scenario}")
    def demo(scenario: str) -> dict[str, object]:
        if scenario not in {"good", "bad"}:
            raise HTTPException(status_code=404, detail="Scenario must be 'good' or 'bad'")
        root = _root()
        temp_parent = root / "temp"
        temp_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="dcm_demo_", dir=temp_parent) as directory:
            data_path = write_demo_dataset(Path(directory) / f"customer_orders_{scenario}.csv", valid=scenario == "good")
            result = validate_files(
                contract_path=bundled_demo_contract(),
                data_path=data_path,
                history_path=root / "state" / "history.jsonl",
            )
            return result.model_dump(mode="json")

    @app.get("/api/history")
    def history(limit: int = 20) -> list[dict[str, object]]:
        return read_history(_root() / "state" / "history.jsonl", limit=min(max(limit, 1), 100))

    return app


app = create_app()
