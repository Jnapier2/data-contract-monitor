from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from data_contract_monitor.api import create_app
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
        assert payload["version"] == "0.2.2"
        assert payload["build_id"] == "DCM-0.2.2-B20260829-WINDOWS1"
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
