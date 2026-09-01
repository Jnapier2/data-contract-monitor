from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STALE_WHEEL_RE = re.compile(r"^data_contract_monitor-[A-Za-z0-9_.+-]+-py3-none-any\.whl$", re.I)
_REQUIRED_SELF_MANAGED = (
    "tools/maintenance_preflight.py",
    "tools/launch.bat",
    "tools/release_gate.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path.name}")
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _manifest_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("managed_files")
    if not isinstance(entries, list):
        raise RuntimeError("MANIFEST.json managed_files is missing or invalid")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise RuntimeError("MANIFEST.json contains an invalid managed-file entry")
        relative = str(entry["path"])
        if relative in result:
            raise RuntimeError(f"MANIFEST.json contains duplicate path: {relative}")
        result[relative] = entry
    return result


def verify_recovery_authority(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], str]:
    required = [
        root / "RELEASE_MODE",
        root / "VERSION.txt",
        root / "PACKAGE_METADATA.json",
        root / "MANIFEST.json",
        root / "MANIFEST.sha256",
    ]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Recovery preflight requires a complete release: " + ", ".join(missing))

    expected_manifest = (root / "MANIFEST.sha256").read_text(encoding="utf-8").split()[0].lower()
    actual_manifest = _sha256(root / "MANIFEST.json")
    if not expected_manifest or actual_manifest != expected_manifest:
        raise RuntimeError("MANIFEST.json does not match MANIFEST.sha256; no automatic maintenance was performed")

    metadata = _load_json(root / "PACKAGE_METADATA.json")
    manifest = _load_json(root / "MANIFEST.json")
    version = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    if not version or metadata.get("version") != version or manifest.get("version") != version:
        raise RuntimeError("Release version identity disagrees; no automatic maintenance was performed")
    if metadata.get("build_id") != manifest.get("build_id"):
        raise RuntimeError("Release build identity disagrees; no automatic maintenance was performed")

    entries = _manifest_map(manifest)
    for relative in _REQUIRED_SELF_MANAGED:
        entry = entries.get(relative)
        path = root / relative
        if entry is None or not path.is_file():
            raise RuntimeError(f"Recovery authority file is missing from the release: {relative}")
        if _sha256(path) != str(entry.get("sha256", "")).lower():
            raise RuntimeError(f"Recovery authority file hash mismatch: {relative}")

    wheel_info = metadata.get("wheel")
    if not isinstance(wheel_info, dict) or not isinstance(wheel_info.get("path"), str):
        raise RuntimeError("PACKAGE_METADATA.json does not identify the current application wheel")
    current_relative = str(wheel_info["path"])
    current_entry = entries.get(current_relative)
    current_wheel = root / current_relative
    if current_entry is None or not current_wheel.is_file():
        raise RuntimeError("Current application wheel is missing from the release manifest")
    expected_wheel_hash = str(wheel_info.get("sha256") or current_entry.get("sha256") or "").lower()
    if not expected_wheel_hash or _sha256(current_wheel) != expected_wheel_hash:
        raise RuntimeError("Current application wheel hash mismatch; no automatic maintenance was performed")

    return metadata, manifest, entries, current_relative


def retire_stale_application_wheels(root: Path) -> dict[str, Any]:
    metadata, _manifest, _entries, current_relative = verify_recovery_authority(root)
    packages = root / "packages"
    candidates: list[Path] = []
    if packages.is_dir():
        for path in packages.glob("data_contract_monitor-*.whl"):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative == current_relative:
                continue
            if _STALE_WHEEL_RE.fullmatch(path.name):
                candidates.append(path)

    if not candidates:
        return {
            "schema_version": "1.0",
            "status": "clean",
            "version": metadata.get("version"),
            "build_id": metadata.get("build_id"),
            "current_wheel": current_relative,
            "retired": [],
        }

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = root / "backups" / "retired_packages" / timestamp
    destination.mkdir(parents=True, exist_ok=True)
    retired: list[dict[str, Any]] = []
    for path in sorted(candidates, key=lambda item: item.name.casefold()):
        before = {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "size": path.stat().st_size,
        }
        target = destination / path.name
        if target.exists():
            raise RuntimeError(f"Retirement destination already exists: {target}")
        os.replace(path, target)
        before["backup_path"] = target.relative_to(root).as_posix()
        retired.append(before)

    receipt = {
        "schema_version": "1.0",
        "project": "Data Contract Monitor",
        "created_at": datetime.now(UTC).isoformat(),
        "action": "retire-stale-application-wheels",
        "version": metadata.get("version"),
        "build_id": metadata.get("build_id"),
        "current_wheel": current_relative,
        "retired": retired,
        "destructive_delete_performed": False,
        "note": "Only recognized prior-version Data Contract Monitor wheels were moved. Unknown/user files were not modified.",
    }
    _atomic_json(destination / "retirement_receipt.json", receipt)
    return {**receipt, "status": "reconciled"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded pre-release maintenance for Data Contract Monitor")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        result = retire_stale_application_wheels(root)
    except Exception as exc:
        print(f"[ERROR] Maintenance preflight failed safely: {exc}", file=sys.stderr)
        return 4
    retired = result.get("retired") or []
    if retired:
        print(f"[OK] Retired {len(retired)} recognized stale application wheel(s) to project-local backups.")
        for item in retired:
            print(f"  - {item['path']} -> {item['backup_path']}")
    else:
        print("[OK] Maintenance preflight: no stale application wheels found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
