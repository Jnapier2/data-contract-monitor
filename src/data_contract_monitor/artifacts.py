from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable

from .atomic import atomic_write_json, sha256_file
from .limits import ResourceLimits
from .models import ValidationResult
from .state_store import StateStore
from .reporters import write_reports

DEFAULT_REPORT_FORMATS = ("html", "json", "junit", "sarif")


def publish_run_artifacts(
    result: ValidationResult,
    *,
    root: Path,
    formats: Iterable[str] = DEFAULT_REPORT_FORMATS,
    limits: ResourceLimits | None = None,
) -> Path:
    root = root.resolve()
    effective_limits = limits or ResourceLimits()
    runs_root = root / "reports" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    destination = runs_root / result.run_id
    if destination.exists():
        raise FileExistsError(f"Run artifact directory already exists: {destination}")

    temp_root = root / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"dcm_run_{result.run_id[:12]}_", dir=temp_root))
    try:
        written = write_reports(result, staging, list(formats))
        manifest_entries = []
        for path in written:
            manifest_entries.append(
                {"path": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)}
            )
        total_report_bytes = sum(path.stat().st_size for path in written)
        if total_report_bytes > effective_limits.max_report_bytes:
            raise RuntimeError(
                f"Generated reports total {total_report_bytes} bytes; limit is {effective_limits.max_report_bytes}."
            )
        atomic_write_json(
            staging / "artifact_manifest.json",
            {
                "schema_version": "1.0",
                "run_id": result.run_id,
                "dataset_name": result.dataset_name,
                "status": result.summary.status,
                "files": manifest_entries,
            },
        )
        for entry in manifest_entries:
            path = staging / str(entry["path"])
            if path.stat().st_size != entry["size"] or sha256_file(path) != entry["sha256"]:
                raise RuntimeError(f"Artifact verification failed for {path.name}")
        os.replace(staging, destination)
        state_store = StateStore(root / "state" / "dcm_state.sqlite3")
        if state_store.get_result(result.run_id) is None:
            state_store.record_validation(result)
        state_store.record_artifacts(result.run_id, manifest_entries)
        atomic_write_json(
            root / "state" / "latest_completed_run.json",
            {
                "run_id": result.run_id,
                "dataset_name": result.dataset_name,
                "status": result.summary.status,
                "completed_at": result.completed_at.isoformat(),
                "artifact_dir": destination.relative_to(root).as_posix(),
            },
        )
        return destination
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
