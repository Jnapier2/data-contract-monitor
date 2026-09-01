from __future__ import annotations

import hashlib
import json
from pathlib import Path

from data_contract_monitor.release_identity import verify_release


def test_source_mode_does_not_require_manifest(tmp_path: Path) -> None:
    (tmp_path / "VERSION.txt").write_text("0.1.0\n", encoding="utf-8")
    result = verify_release(tmp_path)
    assert result["passed"] is True
    assert result["mode"] == "source"


def test_release_mode_checks_every_managed_hash(tmp_path: Path) -> None:
    (tmp_path / "RELEASE_MODE").write_text("release\n", encoding="utf-8")
    (tmp_path / "VERSION.txt").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "managed.txt").write_text("known\n", encoding="utf-8")
    build_id = "DCM-0.1.0-TEST"
    metadata = {"version": "0.1.0", "build_id": build_id, "managed_file_count": 2}
    (tmp_path / "PACKAGE_METADATA.json").write_text(json.dumps(metadata), encoding="utf-8")
    package_dir = tmp_path / "src" / "data_contract_monitor"
    package_dir.mkdir(parents=True)
    (package_dir / "build_info.json").write_text(
        json.dumps({"version": "0.1.0", "build_id": build_id}), encoding="utf-8"
    )
    managed_hash = hashlib.sha256((tmp_path / "managed.txt").read_bytes()).hexdigest()
    build_info_hash = hashlib.sha256((package_dir / "build_info.json").read_bytes()).hexdigest()
    manifest = {
        "version": "0.1.0",
        "build_id": build_id,
        "managed_files": [
        {
            "path": "managed.txt",
            "sha256": managed_hash,
            "size": (tmp_path / "managed.txt").stat().st_size,
        },
            {
                "path": "src/data_contract_monitor/build_info.json",
                "sha256": build_info_hash,
                "size": (package_dir / "build_info.json").stat().st_size,
            },
        ],
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_hash = hashlib.sha256((tmp_path / "MANIFEST.json").read_bytes()).hexdigest()
    (tmp_path / "MANIFEST.sha256").write_text(f"{manifest_hash}  MANIFEST.json\n", encoding="utf-8")
    passed = verify_release(tmp_path)
    assert passed["passed"] is True
    assert passed["checked_files"] == 2
    (tmp_path / "managed.txt").write_text("changed\n", encoding="utf-8")
    failed = verify_release(tmp_path)
    assert failed["passed"] is False
    assert any("hash mismatch" in error for error in failed["errors"])
