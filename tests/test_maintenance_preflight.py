from __future__ import annotations

import hashlib
import json
from pathlib import Path

from data_contract_monitor.release_identity import verify_release
from tools.maintenance_preflight import retire_stale_application_wheels, verify_recovery_authority


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_release(tmp_path: Path, project_root: Path) -> tuple[Path, Path]:
    version = "0.3.3"
    build_id = "DCM-0.3.3-TEST"
    for relative in ("tools/maintenance_preflight.py", "tools/launch.bat", "tools/release_gate.py"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((project_root / relative).read_bytes())
    package = tmp_path / "src" / "data_contract_monitor"
    package.mkdir(parents=True)
    (package / "build_info.json").write_text(
        json.dumps({"version": version, "build_id": build_id}), encoding="utf-8"
    )
    packages = tmp_path / "packages"
    packages.mkdir()
    current = packages / "data_contract_monitor-0.3.3-py3-none-any.whl"
    current.write_bytes(b"current-wheel")
    (tmp_path / "VERSION.txt").write_text(version + "\n", encoding="utf-8")
    (tmp_path / "RELEASE_MODE").write_text("release\n", encoding="utf-8")

    managed = [
        "VERSION.txt",
        "RELEASE_MODE",
        "tools/maintenance_preflight.py",
        "tools/launch.bat",
        "tools/release_gate.py",
        "src/data_contract_monitor/build_info.json",
        "packages/data_contract_monitor-0.3.3-py3-none-any.whl",
    ]
    entries = []
    for relative in managed:
        path = tmp_path / relative
        entries.append({"path": relative, "sha256": _sha(path), "size": path.stat().st_size})
    metadata = {
        "version": version,
        "build_id": build_id,
        "managed_file_count": len(managed),
        "wheel": {"path": current.relative_to(tmp_path).as_posix(), "sha256": _sha(current), "size": current.stat().st_size},
    }
    (tmp_path / "PACKAGE_METADATA.json").write_text(json.dumps(metadata), encoding="utf-8")
    # metadata must also be a managed file in a real release; append after its bytes are final.
    entries.append({
        "path": "PACKAGE_METADATA.json",
        "sha256": _sha(tmp_path / "PACKAGE_METADATA.json"),
        "size": (tmp_path / "PACKAGE_METADATA.json").stat().st_size,
    })
    metadata["managed_file_count"] = len(entries)
    (tmp_path / "PACKAGE_METADATA.json").write_text(json.dumps(metadata), encoding="utf-8")
    entries[-1] = {
        "path": "PACKAGE_METADATA.json",
        "sha256": _sha(tmp_path / "PACKAGE_METADATA.json"),
        "size": (tmp_path / "PACKAGE_METADATA.json").stat().st_size,
    }
    manifest = {"version": version, "build_id": build_id, "managed_files": entries}
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "MANIFEST.sha256").write_text(_sha(tmp_path / "MANIFEST.json") + "  MANIFEST.json\n", encoding="utf-8")
    return tmp_path, current


def test_preflight_retires_only_recognized_stale_wheel(tmp_path: Path, project_root: Path) -> None:
    root, current = _make_release(tmp_path, project_root)
    stale = root / "packages" / "data_contract_monitor-0.3.0-py3-none-any.whl"
    stale.write_bytes(b"old-wheel")
    unrelated = root / "packages" / "customer_plugin-1.0-py3-none-any.whl"
    unrelated.write_bytes(b"user-package")

    assert verify_release(root)["passed"] is False
    result = retire_stale_application_wheels(root)
    assert result["status"] == "reconciled"
    assert len(result["retired"]) == 1
    assert not stale.exists()
    assert current.is_file()
    assert unrelated.read_bytes() == b"user-package"
    backup = root / result["retired"][0]["backup_path"]
    assert backup.read_bytes() == b"old-wheel"
    assert (backup.parent / "retirement_receipt.json").is_file()
    assert verify_release(root)["passed"] is True


def test_preflight_refuses_to_modify_when_manifest_hash_is_bad(tmp_path: Path, project_root: Path) -> None:
    root, _current = _make_release(tmp_path, project_root)
    stale = root / "packages" / "data_contract_monitor-0.3.0-py3-none-any.whl"
    stale.write_bytes(b"old-wheel")
    (root / "MANIFEST.sha256").write_text("0" * 64 + "  MANIFEST.json\n", encoding="utf-8")
    try:
        retire_stale_application_wheels(root)
    except RuntimeError as exc:
        assert "MANIFEST.json does not match" in str(exc)
    else:
        raise AssertionError("Preflight should have failed closed")
    assert stale.read_bytes() == b"old-wheel"
    assert not (root / "backups").exists()


def test_recovery_authority_refuses_modified_preflight(tmp_path: Path, project_root: Path) -> None:
    root, _current = _make_release(tmp_path, project_root)
    (root / "tools" / "maintenance_preflight.py").write_text("tampered\n", encoding="utf-8")
    try:
        verify_recovery_authority(root)
    except RuntimeError as exc:
        assert "Recovery authority file hash mismatch" in str(exc)
    else:
        raise AssertionError("Modified maintenance code must not be trusted")
