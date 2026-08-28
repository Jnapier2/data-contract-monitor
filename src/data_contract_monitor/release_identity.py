"""Dependency-free release identity verification used by the launcher and package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def find_root(start: Path) -> Path | None:
    candidate = start.resolve()
    for parent in [candidate, *candidate.parents]:
        if (parent / "VERSION.txt").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    return None


def verify_release(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not (root / "RELEASE_MODE").exists():
        version_path = root / "VERSION.txt"
        return {
            "mode": "source",
            "passed": True,
            "version": version_path.read_text(encoding="utf-8").strip() if version_path.exists() else None,
            "build_id": None,
            "checked_files": 0,
            "errors": [],
        }

    errors: list[str] = []
    required = [
        "VERSION.txt",
        "PACKAGE_METADATA.json",
        "MANIFEST.json",
        "MANIFEST.sha256",
        "src/data_contract_monitor/build_info.json",
    ]
    for name in required:
        if not (root / name).is_file():
            errors.append(f"Missing release identity file: {name}")
    if errors:
        return {"mode": "release", "passed": False, "version": None, "build_id": None, "checked_files": 0, "errors": errors}

    version = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    try:
        metadata = json.loads((root / "PACKAGE_METADATA.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
        build_info = json.loads(
            (root / "src" / "data_contract_monitor" / "build_info.json").read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        return {"mode": "release", "passed": False, "version": version, "build_id": None, "checked_files": 0, "errors": [f"Invalid release JSON: {exc}"]}

    expected_manifest_hash = (root / "MANIFEST.sha256").read_text(encoding="utf-8").split()[0].lower()
    if sha256_file(root / "MANIFEST.json") != expected_manifest_hash:
        errors.append("MANIFEST.json hash does not match MANIFEST.sha256")
    if metadata.get("version") != version:
        errors.append("PACKAGE_METADATA.json version does not match VERSION.txt")
    if manifest.get("version") != version:
        errors.append("MANIFEST.json version does not match VERSION.txt")
    if metadata.get("build_id") != manifest.get("build_id"):
        errors.append("Build ID disagreement between package metadata and manifest")
    if build_info.get("version") != version:
        errors.append("Running package version does not match VERSION.txt")
    if build_info.get("build_id") != metadata.get("build_id"):
        errors.append("Running package build ID does not match PACKAGE_METADATA.json")
    if metadata.get("managed_file_count") != len(manifest.get("managed_files", [])):
        errors.append("Managed-file count disagreement between package metadata and manifest")

    checked = 0
    seen: set[str] = set()
    for entry in manifest.get("managed_files", []):
        relative = entry.get("path")
        expected = str(entry.get("sha256", "")).lower()
        if not isinstance(relative, str) or not relative:
            errors.append("Manifest contains an empty path")
            continue
        normalized = Path(relative)
        if normalized.is_absolute() or ".." in normalized.parts or relative in seen:
            errors.append(f"Unsafe or duplicate manifest path: {relative!r}")
            continue
        seen.add(relative)
        path = root / normalized
        if not path.is_file():
            errors.append(f"Managed file missing: {relative}")
            continue
        checked += 1
        expected_size = entry.get("size")
        if isinstance(expected_size, int) and path.stat().st_size != expected_size:
            errors.append(f"Managed file size mismatch: {relative}")
        if sha256_file(path) != expected:
            errors.append(f"Managed file hash mismatch: {relative}")
    return {
        "mode": "release",
        "passed": not errors,
        "version": version,
        "build_id": metadata.get("build_id"),
        "checked_files": checked,
        "errors": errors,
    }
