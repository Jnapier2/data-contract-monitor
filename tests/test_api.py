from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from data_contract_monitor.api import _is_known_windows_proactor_reset, create_app
from data_contract_monitor.demo import write_demo_dataset


def _wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    for _ in range(100):
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["state"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("job did not reach a terminal state")



def test_current_ui_is_no_store_version_qualified_and_has_no_retired_demo_data_dependency(project_root: Path, monkeypatch) -> None:
    monkeypatch.setenv("DCM_HOME", str(project_root))
    with TestClient(create_app()) as client:
        root_response = client.get("/?build=DCM-0.3.3-B20260831-WINDOWSFRESHNESS1")
        assert root_response.status_code == 200
        assert root_response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert root_response.headers["pragma"] == "no-cache"
        html = root_response.text
        assert "/assets/styles.css?v=0.3.3" in html
        assert "/assets/app.js?v=0.3.3" in html
        assert "demo-data.json" not in html

        asset = client.get("/assets/app.js?v=0.3.3")
        assert asset.status_code == 200
        assert asset.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert "demo-data.json" not in asset.text

        # The field-observed path is not a current application dependency. Keeping
        # it absent makes stale browser state obvious rather than inventing a fake
        # data contract around another application's old asset.
        assert client.get("/demo-data.json").status_code == 404


def test_windows_proactor_reset_filter_is_narrow() -> None:
    benign = ConnectionResetError(10054, "forcibly closed by remote host")
    assert _is_known_windows_proactor_reset({
        "message": "Exception in callback _ProactorBasePipeTransport._call_connection_lost()",
        "exception": benign,
    })
    assert not _is_known_windows_proactor_reset({
        "message": "Exception in callback unrelated_handler()",
        "exception": benign,
    })
    assert not _is_known_windows_proactor_reset({
        "message": "Exception in callback _ProactorBasePipeTransport._call_connection_lost()",
        "exception": RuntimeError("real failure"),
    })


def test_api_health_and_builtin_demos(project_root: Path, monkeypatch) -> None:
    monkeypatch.setenv("DCM_HOME", str(project_root))
    monkeypatch.setenv("DCM_LAUNCH_ID", "test-launch-identity")
    with TestClient(create_app()) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        payload = health.json()
        assert payload["local_only_default"] is True
        assert payload["service_id"] == "data-contract-monitor"
        assert payload["name"] == "Data Contract Monitor"
        assert payload["version"] == "0.3.3"
        assert payload["build_id"] == "DCM-0.3.3-B20260831-WINDOWSFRESHNESS1"
        assert payload["launch_id"] == "test-launch-identity"
        assert payload["state"]["passed"] is True
        assert client.get("/").status_code == 200  # establishes the SameSite local session
        good = client.post("/api/demo/good")
        bad = client.post("/api/demo/bad")
        assert good.status_code == 200 and good.json()["summary"]["passed"] is True
        assert bad.status_code == 200 and bad.json()["summary"]["passed"] is False


def test_api_modifying_requests_require_local_session(project_root: Path, monkeypatch) -> None:
    monkeypatch.setenv("DCM_HOME", str(project_root))
    with TestClient(create_app()) as client:
        response = client.post("/api/demo/good")
        assert response.status_code == 403


def test_api_upload_validation_uses_bounded_job(project_root: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DCM_HOME", str(project_root))
    data = write_demo_dataset(tmp_path / "good.csv", valid=True)
    with TestClient(create_app()) as client:
        assert client.get("/").status_code == 200
        with (project_root / "examples" / "contracts" / "customer_orders.yml").open("rb") as contract_handle, data.open("rb") as data_handle:
            response = client.post(
                "/api/jobs/validate",
                files={
                    "contract": ("customer_orders.yml", contract_handle, "application/yaml"),
                    "data": ("good.csv", data_handle, "text/csv"),
                },
            )
        assert response.status_code == 202
        job = _wait_for_job(client, response.json()["job_id"])
        assert job["state"] == "completed"
        result = job["result"]
        assert result["summary"]["passed"] is True
        assert result["contract_label"].startswith("contract")
        assert result["data_label"].startswith("dataset")
        assert job["artifact_dir"].startswith("reports/runs/")


def test_api_reference_dataset_and_history_compare(project_root: Path, monkeypatch) -> None:
    monkeypatch.setenv("DCM_HOME", str(project_root))
    contract_path = project_root / "examples" / "contracts" / "orders_reference_check.yml"
    data_path = project_root / "examples" / "data" / "orders_reference_check.csv"
    reference_path = project_root / "examples" / "data" / "customers_reference.csv"
    with TestClient(create_app()) as client:
        assert client.get("/").status_code == 200
        with contract_path.open("rb") as contract_handle, data_path.open("rb") as data_handle, reference_path.open("rb") as reference_handle:
            response = client.post(
                "/api/jobs/validate?execution_mode=streaming",
                files=[
                    ("contract", (contract_path.name, contract_handle, "application/yaml")),
                    ("data", (data_path.name, data_handle, "text/csv")),
                    ("references", (reference_path.name, reference_handle, "text/csv")),
                ],
            )
        assert response.status_code == 202
        job = _wait_for_job(client, response.json()["job_id"])
        assert job["state"] == "completed"
        result = job["result"]
        assert result["execution_mode"] == "streaming"
        reference_findings = [
            item for item in result["findings"] if item["category"] == "referential_integrity"
        ]
        assert len(reference_findings) == 1
        assert reference_findings[0]["affected_rows"] == 1

        # Add a second run so the API comparison/trend surfaces are grounded in durable state.
        good = client.post("/api/demo/good")
        assert good.status_code == 200
        history = client.get("/api/history?limit=10").json()
        assert len(history) >= 2
        newer, older = history[0]["run_id"], history[1]["run_id"]
        comparison = client.get(f"/api/runs/compare/{older}/{newer}")
        assert comparison.status_code == 200
        trend = client.get("/api/history/trend?limit=10")
        assert trend.status_code == 200
        assert trend.json()["run_count"] >= 2
