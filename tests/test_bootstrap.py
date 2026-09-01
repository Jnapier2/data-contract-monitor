from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import tools.bootstrap as bootstrap


def test_current_interpreter_is_accepted() -> None:
    supported, reason = bootstrap.supported_interpreter()
    assert supported, reason


def test_resolve_release_wheel_checks_metadata_hash(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    packages.mkdir()
    wheel = packages / "data_contract_monitor-0.2.2-py3-none-any.whl"
    wheel.write_bytes(b"synthetic-wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (tmp_path / "PACKAGE_METADATA.json").write_text(
        json.dumps({"wheel": {"path": wheel.relative_to(tmp_path).as_posix(), "sha256": digest}}),
        encoding="utf-8",
    )
    assert bootstrap.resolve_release_wheel(tmp_path) == wheel
    wheel.write_bytes(b"tampered")
    try:
        bootstrap.resolve_release_wheel(tmp_path)
    except RuntimeError as exc:
        assert "sha-256" in str(exc).lower()
    else:
        raise AssertionError("Tampered wheel should be rejected")


def test_status_and_startup_capsule_are_project_local_and_redacted(tmp_path: Path) -> None:
    (tmp_path / "VERSION.txt").write_text("0.2.2\n", encoding="utf-8")
    (tmp_path / "src" / "data_contract_monitor").mkdir(parents=True)
    (tmp_path / "src" / "data_contract_monitor" / "build_info.json").write_text(
        json.dumps({"version": "0.2.2", "build_id": "DCM-0.2.2-B20260831-FIELDCOHERENCE1"}), encoding="utf-8"
    )
    bootstrap.write_status(tmp_path, state="test", action="doctor", details={"token": "secret-value"})
    status = (tmp_path / "LATEST_LAUNCH_STATUS.txt").read_text(encoding="utf-8")
    assert "State: test" in status
    assert "secret-value" not in status
    status_json = (tmp_path / "state" / "latest_launch_status.json").read_text(encoding="utf-8")
    assert "secret-value" not in status_json
    log_path = tmp_path / "logs" / "bootstrap.log"
    capsule = bootstrap.startup_capsule(
        tmp_path,
        action="serve",
        last_progress="dependency-install",
        exc=RuntimeError("token=secret-value"),
        log_path=log_path,
    )
    assert capsule is not None and capsule.is_file()
    payload = capsule.read_text(encoding="utf-8")
    assert "secret-value" not in payload
    assert "startup_abort_" in capsule.name


def test_verified_windows_wheelhouse_requires_complete_hash_inventory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bootstrap.os, "name", "nt")
    monkeypatch.setattr(bootstrap.sys, "version_info", type("V", (), {"major": 3, "minor": 13})())
    wheelhouse = tmp_path / "packages" / "wheelhouse" / "cp313-win_amd64"
    wheelhouse.mkdir(parents=True)
    wheel = wheelhouse / "example-1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel-bytes")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (wheelhouse / "WHEELHOUSE_MANIFEST.json").write_text(
        json.dumps(
            {
                "target": "cp313-win_amd64",
                "complete": True,
                "files": [{"name": wheel.name, "sha256": digest, "size": wheel.stat().st_size}],
            }
        ),
        encoding="utf-8",
    )
    assert bootstrap.local_wheelhouse(tmp_path) == wheelhouse
    wheel.write_bytes(b"tampered")
    assert bootstrap.local_wheelhouse(tmp_path) is None
