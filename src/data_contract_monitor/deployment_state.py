"""Deployment-state coherence helpers.

This module is intentionally standard-library-only. It distinguishes immutable release
identity from generated runtime evidence so overlay upgrades cannot make stale state look
current. Only known first-party generated state files may be retired automatically.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic import atomic_write_json

_GENERATED_IDENTITY_FILES = (
    "state/runtime_environment.json",
    "state/dashboard_endpoint.json",
    "state/dependencies.sha256",
    "state/test_dependencies.sha256",
)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def current_release_identity(root: Path) -> dict[str, Any]:
    root = root.resolve()
    version: str | None = None
    build_id: str | None = None
    try:
        version = (root / "VERSION.txt").read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    metadata = _read_json(root / "PACKAGE_METADATA.json") or {}
    if isinstance(metadata.get("build_id"), str):
        build_id = metadata["build_id"]
    return {"version": version, "build_id": build_id}


def _identity_from_payload(payload: dict[str, Any] | None, *, runtime: bool = False) -> dict[str, Any] | None:
    if not payload:
        return None
    version_key = "application_version" if runtime else "version"
    return {
        "version": payload.get(version_key),
        "build_id": payload.get("build_id"),
        "passed": payload.get("passed") if not runtime else None,
    }


def deployment_coherence(root: Path) -> dict[str, Any]:
    """Compare current release metadata with cached generated identity without rehashing files."""
    root = root.resolve()
    current = current_release_identity(root)
    cached = _identity_from_payload(_read_json(root / "state" / "release_verification.json"))
    runtime = _identity_from_payload(_read_json(root / "state" / "runtime_environment.json"), runtime=True)
    endpoint = _identity_from_payload(_read_json(root / "state" / "dashboard_endpoint.json"))

    mismatches: list[str] = []
    for label, item in (("cached_release_verification", cached), ("runtime_environment", runtime), ("dashboard_endpoint", endpoint)):
        if not item:
            continue
        if item.get("version") != current.get("version") or item.get("build_id") != current.get("build_id"):
            mismatches.append(label)

    if not current.get("version") or not current.get("build_id"):
        status = "current-release-identity-incomplete"
    elif mismatches:
        status = "stale-generated-identity"
    else:
        status = "coherent"

    return {
        "schema_version": "1.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "status": status,
        "current_release": current,
        "cached_release_verification": cached,
        "runtime_environment": runtime,
        "dashboard_endpoint": endpoint,
        "mismatches": mismatches,
        "managed_rehash_performed": False,
        "note": "Generated runtime identity is compared to current static release metadata only; support collection does not rehash managed files.",
    }


def retire_stale_generated_identity(root: Path) -> dict[str, Any]:
    """Move only known stale generated identity files into project-local backups.

    Validation history, reports, configuration, user files, and unknown files are never moved.
    """
    root = root.resolve()
    coherence = deployment_coherence(root)
    current = coherence["current_release"]
    runtime = coherence.get("runtime_environment")
    if not runtime or (
        runtime.get("version") == current.get("version")
        and runtime.get("build_id") == current.get("build_id")
    ):
        return {"retired": [], "reason": "runtime identity already current or absent", "coherence": coherence}

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_root = root / "backups" / "runtime_identity" / stamp
    retired: list[str] = []
    for relative in _GENERATED_IDENTITY_FILES:
        source = root / relative
        if not source.is_file():
            continue
        destination = backup_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        retired.append(relative)

    receipt = {
        "schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "reason": "stale generated runtime identity from an earlier release",
        "current_release": current,
        "previous_runtime_environment": runtime,
        "retired": retired,
    }
    if retired:
        atomic_write_json(backup_root / "retirement_receipt.json", receipt)
    return {"retired": retired, "reason": receipt["reason"] if retired else "no generated identity files found", "coherence": coherence}
