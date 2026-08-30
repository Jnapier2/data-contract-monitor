from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .models import DatasetProfile, DriftChange, DriftSummary, Severity


class BaselineError(ValueError):
    """Raised when a baseline cannot be parsed."""


def snapshot_from_profile(dataset_name: str, profile: DatasetProfile) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "dataset_name": dataset_name,
        "created_at": datetime.now(UTC).isoformat(),
        "columns": [
            {
                "name": column.name,
                "observed_type": column.observed_type,
                "nullable_observed": column.null_count > 0,
            }
            for column in profile.columns
        ],
    }


def write_baseline(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BaselineError(f"Unable to read baseline: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("columns"), list):
        raise BaselineError("Baseline must contain a columns list")
    return cast(dict[str, Any], payload)


def compare_profile(profile: DatasetProfile, baseline: dict[str, Any], path: Path) -> DriftSummary:
    before = {item["name"]: item for item in baseline.get("columns", []) if "name" in item}
    after = {
        item.name: {
            "observed_type": item.observed_type,
            "nullable_observed": item.null_count > 0,
        }
        for item in profile.columns
    }
    changes: list[DriftChange] = []
    for name in sorted(after.keys() - before.keys()):
        changes.append(
            DriftChange(change_type="added", column=name, after=after[name]["observed_type"], severity=Severity.WARNING)
        )
    for name in sorted(before.keys() - after.keys()):
        changes.append(
            DriftChange(change_type="removed", column=name, before=before[name].get("observed_type"), severity=Severity.ERROR)
        )
    for name in sorted(before.keys() & after.keys()):
        if before[name].get("observed_type") != after[name]["observed_type"]:
            changes.append(
                DriftChange(
                    change_type="type_changed",
                    column=name,
                    before=before[name].get("observed_type"),
                    after=after[name]["observed_type"],
                    severity=Severity.ERROR,
                )
            )
        if not bool(before[name].get("nullable_observed")) and bool(after[name]["nullable_observed"]):
            changes.append(
                DriftChange(
                    change_type="nullability_changed",
                    column=name,
                    before=False,
                    after=True,
                    severity=Severity.WARNING,
                )
            )
    return DriftSummary(baseline_used=True, baseline_path=path.name, changes=changes)
