from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

from data_contract_monitor.deployment_state import deployment_coherence, retire_stale_generated_identity
from data_contract_monitor.diagnostics import DiagnosticManager
from data_contract_monitor.release_identity import verify_release
from data_contract_monitor.state_store import StateStore
import data_contract_monitor.state_store as state_store_module


def _write_release(root: Path, managed_relatives: list[str]) -> None:
    (root / "RELEASE_MODE").write_text("release\n", encoding="utf-8")
    (root / "VERSION.txt").write_text("0.2.2\n", encoding="utf-8")
    build_id = "DCM-0.2.2-TEST"
    package = root / "src" / "data_contract_monitor"
    package.mkdir(parents=True, exist_ok=True)
    (package / "build_info.json").write_text(
        json.dumps({"version": "0.2.2", "build_id": build_id}), encoding="utf-8"
    )
    files = ["src/data_contract_monitor/build_info.json", *managed_relatives]
    manifest_entries = []
    for relative in files:
        path = root / relative
        manifest_entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
        )
    metadata = {"version": "0.2.2", "build_id": build_id, "managed_file_count": len(files)}
    (root / "PACKAGE_METADATA.json").write_text(json.dumps(metadata), encoding="utf-8")
    manifest = {"version": "0.2.2", "build_id": build_id, "managed_files": manifest_entries}
    (root / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    digest = hashlib.sha256((root / "MANIFEST.json").read_bytes()).hexdigest()
    (root / "MANIFEST.sha256").write_text(f"{digest}  MANIFEST.json\n", encoding="utf-8")


def test_deployment_coherence_marks_stale_generated_identity(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "VERSION.txt").write_text("0.2.2\n", encoding="utf-8")
    (tmp_path / "PACKAGE_METADATA.json").write_text(
        json.dumps({"version": "0.2.2", "build_id": "DCM-0.2.2-TEST"}), encoding="utf-8"
    )
    stale = {"version": "0.1.2", "build_id": "DCM-0.1.2-OLD", "passed": True}
    (tmp_path / "state" / "release_verification.json").write_text(json.dumps(stale), encoding="utf-8")
    (tmp_path / "state" / "runtime_environment.json").write_text(
        json.dumps({"application_version": "0.1.2", "build_id": "DCM-0.1.2-OLD"}), encoding="utf-8"
    )
    result = deployment_coherence(tmp_path)
    assert result["status"] == "stale-generated-identity"
    assert set(result["mismatches"]) == {"cached_release_verification", "runtime_environment"}
    assert result["managed_rehash_performed"] is False


def test_stale_runtime_identity_is_retired_without_touching_user_state(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "VERSION.txt").write_text("0.2.2\n", encoding="utf-8")
    (tmp_path / "PACKAGE_METADATA.json").write_text(
        json.dumps({"version": "0.2.2", "build_id": "DCM-0.2.2-TEST"}), encoding="utf-8"
    )
    (tmp_path / "state" / "runtime_environment.json").write_text(
        json.dumps({"application_version": "0.1.2", "build_id": "DCM-0.1.2-OLD"}), encoding="utf-8"
    )
    (tmp_path / "state" / "dashboard_endpoint.json").write_text(json.dumps({"version": "0.1.2"}), encoding="utf-8")
    (tmp_path / "state" / "dependencies.sha256").write_text("old\n", encoding="utf-8")
    user_state = tmp_path / "state" / "customer_notes.json"
    user_state.write_text('{"keep": true}\n', encoding="utf-8")

    result = retire_stale_generated_identity(tmp_path)
    assert set(result["retired"]) == {
        "state/runtime_environment.json",
        "state/dashboard_endpoint.json",
        "state/dependencies.sha256",
    }
    assert user_state.is_file()
    receipts = list((tmp_path / "backups" / "runtime_identity").glob("*/retirement_receipt.json"))
    assert len(receipts) == 1


def test_release_rejects_unlisted_protected_execution_file(tmp_path: Path) -> None:
    managed = tmp_path / "managed.txt"
    managed.write_text("known\n", encoding="utf-8")
    _write_release(tmp_path, ["managed.txt"])
    passed = verify_release(tmp_path)
    assert passed["passed"] is True

    stale_wheel = tmp_path / "packages" / "data_contract_monitor-0.1.2-py3-none-any.whl"
    stale_wheel.parent.mkdir(parents=True)
    stale_wheel.write_bytes(b"stale")
    failed = verify_release(tmp_path)
    assert failed["passed"] is False
    assert any("Unlisted protected execution file" in error for error in failed["errors"])


def test_release_allows_unknown_user_file_outside_protected_namespaces(tmp_path: Path) -> None:
    managed = tmp_path / "managed.txt"
    managed.write_text("known\n", encoding="utf-8")
    _write_release(tmp_path, ["managed.txt"])
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "customer_evidence.zip").write_bytes(b"user-owned")
    result = verify_release(tmp_path)
    assert result["passed"] is True


def test_support_export_explains_current_vs_cached_identity(tmp_path: Path) -> None:
    for name in ("logs", "state", "reports"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    (tmp_path / "VERSION.txt").write_text("0.2.2\n", encoding="utf-8")
    (tmp_path / "PACKAGE_METADATA.json").write_text(
        json.dumps({"version": "0.2.2", "build_id": "DCM-0.2.2-TEST"}), encoding="utf-8"
    )
    (tmp_path / "state" / "release_verification.json").write_text(
        json.dumps({"version": "0.1.2", "build_id": "DCM-0.1.2-OLD", "passed": True}), encoding="utf-8"
    )
    (tmp_path / "state" / "runtime_environment.json").write_text(
        json.dumps({"application_version": "0.1.2", "build_id": "DCM-0.1.2-OLD"}), encoding="utf-8"
    )
    path = DiagnosticManager(tmp_path).create_manual_export()
    assert path is not None
    with zipfile.ZipFile(path) as archive:
        context = json.loads(archive.read("diagnostics/support_context.json"))
    coherence = context["deployment_coherence"]
    assert coherence["current_release"]["version"] == "0.2.2"
    assert coherence["cached_release_verification"]["version"] == "0.1.2"
    assert coherence["status"] == "stale-generated-identity"
    assert "export action is still running" in context["capture_note"]


def test_state_store_closes_sqlite_connections(tmp_path: Path, monkeypatch) -> None:
    original_connect = state_store_module.sqlite3.connect
    opened = []

    def tracking_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(state_store_module.sqlite3, "connect", tracking_connect)
    store = StateStore(tmp_path / "state" / "dcm_state.sqlite3")
    assert store.health_check()["passed"] is True
    store.read_history(limit=1)
    assert opened
    for connection in opened:
        try:
            connection.execute("SELECT 1")
        except sqlite3.ProgrammingError as exc:
            assert "closed" in str(exc).lower()
        else:
            raise AssertionError("SQLite connection remained open after StateStore operation")
