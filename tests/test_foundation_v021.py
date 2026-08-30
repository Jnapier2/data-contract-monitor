from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
import yaml

from data_contract_monitor.artifacts import publish_run_artifacts
from data_contract_monitor.contract_plan import ContractPlanError, compile_contract
from data_contract_monitor.demo import write_demo_dataset
from data_contract_monitor.engine import ValidationExecutionError, validate_files
from data_contract_monitor.limits import ResourceLimits
from data_contract_monitor.models import Contract
from data_contract_monitor.state_store import StateStore


def test_sqlite_state_and_atomic_run_artifacts(project_root: Path, tmp_path: Path) -> None:
    data = write_demo_dataset(tmp_path / "good.csv", valid=True)
    state_path = tmp_path / "state" / "dcm_state.sqlite3"
    result = validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        history_path=state_path,
    )
    store = StateStore(state_path)
    history = store.read_history(limit=5)
    assert history[0]["run_id"] == result.run_id
    assert store.health_check()["passed"] is True

    runtime = tmp_path / "runtime"
    for name in ("state", "temp", "reports"):
        (runtime / name).mkdir(parents=True, exist_ok=True)
    destination = publish_run_artifacts(result, root=runtime)
    assert destination.name == result.run_id
    manifest = json.loads((destination / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 4
    pointer = json.loads((runtime / "state" / "latest_completed_run.json").read_text(encoding="utf-8"))
    assert pointer["run_id"] == result.run_id


def test_state_health_does_not_expose_database_exception(
    project_root: Path, monkeypatch
) -> None:
    store = StateStore(project_root / "state" / "health-test.sqlite3")

    def fail_connection() -> None:
        raise sqlite3.OperationalError("private path C:/sensitive/state.sqlite3")

    monkeypatch.setattr(store, "_connect", fail_connection)
    health = store.health_check()

    assert health == {
        "passed": False,
        "error": "state_database_unavailable",
        "schema_version": None,
        "runs": None,
    }


def test_resource_limit_rejects_before_reporting(project_root: Path, tmp_path: Path) -> None:
    data = write_demo_dataset(tmp_path / "good.csv", valid=True)
    with pytest.raises(ValidationExecutionError, match="rows; limit is 1"):
        validate_files(
            contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
            data_path=data,
            record_history=False,
            limits=ResourceLimits(max_rows=1),
        )


def test_safe_aggregate_reconciliation(tmp_path: Path) -> None:
    contract_payload = {
        "contract_version": "1.0",
        "dataset": {"name": "invoice", "required_columns": ["total", "subtotal", "tax"]},
        "rules": {},
        "dataset_rules": [
            {
                "name": "invoice_math",
                "type": "aggregate_reconciliation",
                "left_column": "total",
                "right_expression": "subtotal + tax",
                "tolerance": 0.01,
                "severity": "error",
            }
        ],
        "privacy": {"detect_pii": False},
    }
    contract = tmp_path / "contract.yml"
    contract.write_text(yaml.safe_dump(contract_payload, sort_keys=False), encoding="utf-8")
    data = tmp_path / "data.csv"
    pd.DataFrame(
        [
            {"total": 10.5, "subtotal": 10.0, "tax": 0.5},
            {"total": 9.0, "subtotal": 10.0, "tax": 0.5},
        ]
    ).to_csv(data, index=False)
    result = validate_files(contract_path=contract, data_path=data, record_history=False)
    matches = [item for item in result.findings if item.category == "reconciliation"]
    assert len(matches) == 1
    assert matches[0].affected_rows == 1
    assert result.summary.passed is False


def test_compiled_plan_rejects_duplicate_dataset_rule_names() -> None:
    contract = Contract.model_validate(
        {
            "dataset": {"name": "demo"},
            "dataset_rules": [
                {"name": "same", "type": "row_count", "minimum": 1},
                {"name": "same", "type": "row_count", "maximum": 10},
            ],
        }
    )
    with pytest.raises(ContractPlanError, match="Duplicate dataset rule name"):
        compile_contract(contract)
