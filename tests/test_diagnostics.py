from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from data_contract_monitor.diagnostics import DiagnosticManager, redact


def _prepare_root(root: Path) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "state").mkdir(parents=True, exist_ok=True)
    (root / "VERSION.txt").write_text("0.2.2\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("test\n", encoding="utf-8")
    (root / "LATEST_LAUNCH_STATUS.txt").write_text(
        f"Project root: {Path.home()}\nDashboard URL: http://192.168.1.9:8765\n",
        encoding="utf-8",
    )
    (root / "logs" / "launcher.log").write_text(
        f"token=private-value home={Path.home()} host=192.168.1.9\n",
        encoding="utf-8",
    )
    (root / "logs" / "bootstrap.log").write_text(
        "bootstrap ready password=bootstrap-private\n", encoding="utf-8"
    )
    (root / "logs" / "python_detection.txt").write_text(
        "CPython 3.13.15 AMD64\n", encoding="utf-8"
    )
    (root / "state" / "dashboard_endpoint.json").write_text(
        json.dumps({"service_id": "data-contract-monitor", "selected_port": 8766}),
        encoding="utf-8",
    )
    (root / "state" / "runtime_environment.json").write_text(
        json.dumps({"python_version": "3.13.15", "application_version": "0.2.2"}),
        encoding="utf-8",
    )
    run_dir = root / "reports" / "runs" / "test-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(
        json.dumps({"contract_label": "private.yml", "data_label": "secret.csv", "summary": {"passed": False}}),
        encoding="utf-8",
    )
    (root / "state" / "latest_completed_run.json").write_text(
        json.dumps({"run_id": "test-run", "artifact_dir": "reports/runs/test-run"}),
        encoding="utf-8",
    )


def test_redaction_removes_common_secret_and_location_signals() -> None:
    value = redact(f"api_key=abcdef password=hunter2 host=192.168.1.9 home={Path.home()}")
    assert "abcdef" not in value
    assert "hunter2" not in value
    assert "192.168.1.9" not in value
    assert str(Path.home()) not in value


def test_manual_export_is_not_recorded_as_critical(tmp_path: Path) -> None:
    _prepare_root(tmp_path)
    manager = DiagnosticManager(tmp_path)
    path = manager.create_manual_export()
    assert path is not None and path.is_file()
    assert path.parent == tmp_path / "exports"
    assert "Support" in path.name
    assert not (tmp_path / "diagnostics" / "exports").exists()
    assert not list((tmp_path / "diagnostics" / "crash_capsules").glob("*.json"))
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.infolist()) <= 20
        context = json.loads(archive.read("diagnostics/support_context.json"))
        latest = json.loads(archive.read("reports/latest_result.redacted.json"))
        launcher_log = archive.read("logs/launcher.log").decode("utf-8")
        bootstrap_log = archive.read("logs/bootstrap.log").decode("utf-8")
        python_detection = archive.read("logs/python_detection.txt").decode("utf-8")
        launch_status = archive.read("LATEST_LAUNCH_STATUS.txt").decode("utf-8")
        names = set(archive.namelist())
    assert context["severity"] == "support"
    assert "private-value" not in launcher_log
    assert "bootstrap-private" not in bootstrap_log
    assert "CPython 3.13.15 AMD64" in python_detection
    assert str(Path.home()) not in launcher_log
    assert "192.168.1.9" not in launcher_log
    assert str(Path.home()) not in launch_status
    assert latest["contract_label"] == "[REDACTED_FILENAME]"
    assert latest["data_label"] == "[REDACTED_FILENAME]"
    assert {
        "logs/bootstrap.log",
        "logs/python_detection.txt",
        "state/dashboard_endpoint.json",
        "state/runtime_environment.json",
    }.issubset(names)


def test_critical_capture_deduplicates_same_fingerprint(tmp_path: Path) -> None:
    _prepare_root(tmp_path)
    manager = DiagnosticManager(tmp_path)
    first = manager.capture_critical("test-crash", RuntimeError("token=secret-value"))
    second = manager.capture_critical("test-crash", RuntimeError("token=secret-value"))
    assert first is not None
    assert second is None
    capsules = list((tmp_path / "diagnostics" / "crash_capsules").glob("*.json"))
    assert len(capsules) == 1
    payload = json.loads(capsules[0].read_text(encoding="utf-8"))
    assert "secret-value" not in json.dumps(payload)
    suppression = json.loads((tmp_path / "diagnostics" / "suppression_counts.json").read_text(encoding="utf-8"))
    assert next(iter(suppression.values()))["count"] == 1


def test_retention_never_deletes_unknown_or_user_zip(tmp_path: Path) -> None:
    _prepare_root(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    user_zip = export_dir / "customer_evidence.zip"
    user_zip.write_bytes(b"user-owned")
    malformed_dcm_zip = export_dir / "Data_Contract_Monitor_unrecognized.zip"
    malformed_dcm_zip.write_bytes(b"unknown")

    manager = DiagnosticManager(tmp_path)
    for index in range(7):
        generated = export_dir / (
            f"Data_Contract_Monitor_Support_202608{index + 1:02d}T120000Z_"
            f"{index:020x}.zip"
        )
        generated.write_bytes(b"generated")
        os.utime(generated, (1_800_000_000 + index, 1_800_000_000 + index))

    manager._retention()

    assert user_zip.read_bytes() == b"user-owned"
    assert malformed_dcm_zip.read_bytes() == b"unknown"
    retained_generated = [
        item
        for item in export_dir.glob("Data_Contract_Monitor_*.zip")
        if item.name != malformed_dcm_zip.name
    ]
    assert len(retained_generated) == 5


def test_diagnostics_import_without_third_party_dependencies(project_root: Path) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root / "src")
    code = (
        "import sys; "
        "import data_contract_monitor; "
        "from data_contract_monitor.diagnostics import DiagnosticManager; "
        "assert not any(k == 'pydantic' or k.startswith('pydantic.') for k in sys.modules); "
        "print(data_contract_monitor.__version__, DiagnosticManager.__name__)"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", code],
        cwd=project_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "0.3.4 DiagnosticManager" in completed.stdout
