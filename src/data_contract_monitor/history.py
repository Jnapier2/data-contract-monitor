from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import ValidationResult
from .state_store import StateStore


def default_history_path(contract_path: Path) -> Path:
    return contract_path.parent / ".dcm" / "state" / "dcm_state.sqlite3"


def append_history(path: Path, result: ValidationResult) -> None:
    """Record a validation result.

    SQLite is authoritative. JSONL remains readable/writable only for compatibility with
    older callers that explicitly pass a .jsonl path.
    """
    if path.suffix.lower() == ".jsonl":
        _append_legacy_jsonl(path, result)
        return
    StateStore(path).record_validation(result)


def read_history(path: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return _read_legacy_jsonl(path, limit=limit)
    if not path.exists():
        return []
    return StateStore(path).read_history(limit=limit)


def _append_legacy_jsonl(path: Path, result: ValidationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": result.run_id,
        "dataset_name": result.dataset_name,
        "started_at": result.started_at.isoformat(),
        "duration_ms": result.duration_ms,
        "status": result.summary.status,
        "findings_total": result.summary.findings_total,
        "warnings": result.summary.warnings,
        "errors": result.summary.errors,
        "critical": result.summary.critical,
        "row_count": result.profile.row_count,
        "column_count": result.profile.column_count,
        "contract_sha256": result.contract_sha256,
        "data_sha256": result.data_sha256,
    }
    line = json.dumps(entry, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _read_legacy_jsonl(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries
