from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from data_contract_monitor.api import create_app
from data_contract_monitor.demo import write_demo_dataset


def test_partial_frontend_build_cannot_hide_packaged_dashboard(monkeypatch, tmp_path: Path) -> None:
    from data_contract_monitor.api import _web_root

    monkeypatch.setenv("DCM_HOME", str(tmp_path))
    partial = tmp_path / "frontend" / "dist"
    partial.mkdir(parents=True)
    (partial / "app.js").write_text("// compiled script only", encoding="utf-8")
    selected = _web_root()
    assert selected != partial
    assert (selected / "index.html").is_file()
    assert (selected / "styles.css").is_file()


def test_complete_frontend_build_remains_supported(monkeypatch, tmp_path: Path) -> None:
    from data_contract_monitor.api import _web_root

    monkeypatch.setenv("DCM_HOME", str(tmp_path))
    complete = tmp_path / "frontend" / "dist"
    complete.mkdir(parents=True)
    for name in ("index.html", "app.js", "styles.css"):
        (complete / name).write_text("fixture", encoding="utf-8")
    assert _web_root() == complete


def test_api_health_and_builtin_demos(project_root: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DCM_HOME", str(project_root))
    monkeypatch.setenv("DCM_LAUNCH_ID", "test-launch-identity")
    client = TestClient(create_app())
    health = client.get("/api/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["local_only_default"] is True
    assert payload["service_id"] == "data-contract-monitor"
    assert payload["name"] == "Data Contract Monitor"
    assert payload["version"] == "0.1.5"
    assert payload["build_id"].startswith("DCM-0.1.5-")
    assert payload["launch_id"] == "test-launch-identity"
    good = client.post("/api/demo/good")
    bad = client.post("/api/demo/bad")
    assert good.status_code == 200 and good.json()["summary"]["passed"] is True
    assert bad.status_code == 200 and bad.json()["summary"]["passed"] is False


def test_api_upload_validation(project_root: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DCM_HOME", str(project_root))
    client = TestClient(create_app())
    data = write_demo_dataset(tmp_path / "good.csv", valid=True)
    with (project_root / "examples" / "contracts" / "customer_orders.yml").open("rb") as contract_handle, data.open("rb") as data_handle:
        response = client.post(
            "/api/validate",
            files={
                "contract": ("customer_orders.yml", contract_handle, "application/yaml"),
                "data": ("good.csv", data_handle, "text/csv"),
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["passed"] is True
    assert payload["contract_label"] == "customer_orders.yml"
    assert payload["data_label"] == "good.csv"
