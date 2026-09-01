"""Dependency-free release identity verification used by the launcher and package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .atomic import sha256_file



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
    seen_casefold: set[str] = set()
    for entry in manifest.get("managed_files", []):
        relative = entry.get("path")
        expected = str(entry.get("sha256", "")).lower()
        if not isinstance(relative, str) or not relative:
            errors.append("Manifest contains an empty path")
            continue
        normalized = Path(relative)
        folded = relative.casefold()
        if normalized.is_absolute() or ".." in normalized.parts or relative in seen or folded in seen_casefold:
            errors.append(f"Unsafe, duplicate, or case-colliding manifest path: {relative!r}")
            continue
        seen.add(relative)
        seen_casefold.add(folded)
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

    # Reject unlisted files only inside protected execution namespaces. Unknown/user files
    # elsewhere remain untouched and do not block release verification.
    protected_candidates: set[Path] = set()
    for suffix in ("*.bat", "*.cmd", "*.ps1"):
        protected_candidates.update(root.glob(suffix))
        tools = root / "tools"
        if tools.is_dir():
            protected_candidates.update(tools.rglob(suffix))
    package_root = root / "src" / "data_contract_monitor"
    if package_root.is_dir():
        protected_candidates.update(
            path for path in package_root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}
        )
    packages_root = root / "packages"
    if packages_root.is_dir():
        protected_candidates.update(packages_root.glob("data_contract_monitor-*.whl"))

    for path in sorted(protected_candidates, key=lambda item: item.as_posix().casefold()):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative not in seen:
            errors.append(f"Unlisted protected execution file: {relative}")

    return {
        "mode": "release",
        "passed": not errors,
        "version": version,
        "build_id": metadata.get("build_id"),
        "checked_files": checked,
        "errors": errors,
    }
