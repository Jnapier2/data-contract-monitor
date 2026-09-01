from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import yaml

from data_contract_monitor.artifacts import publish_run_artifacts
from data_contract_monitor.contract_loader import load_contract
from data_contract_monitor.contract_tools import diff_contracts, lint_contract, normalized_contract_text
from data_contract_monitor.engine import validate_files
from data_contract_monitor.limits import ResourceLimits
from data_contract_monitor.state_store import SCHEMA_VERSION, StateStore


def _write_contract(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_streaming_uniqueness_is_exact_across_batches(tmp_path: Path) -> None:
    contract = _write_contract(
        tmp_path / "contract.yml",
        {
            "contract_version": "2.0",
            "dataset": {
                "name": "orders",
                "contract_id": "orders-contract",
                "required_columns": ["order_id", "amount"],
            },
            "rules": {
                "order_id": {"type": "integer", "nullable": False, "unique": True},
                "amount": {"type": "number", "minimum": 0},
            },
            "privacy": {"detect_pii": False},
        },
    )
    data = tmp_path / "orders.csv"
    pd.DataFrame(
        {"order_id": [1, 2, 3, 1, 5, 2], "amount": [1, 2, 3, 4, 5, 6]}
    ).to_csv(data, index=False)
    result = validate_files(
        contract_path=contract,
        data_path=data,
        execution_mode="streaming",
        limits=ResourceLimits(batch_rows=2, streaming_threshold_bytes=1),
        record_history=False,
    )
    assert result.execution_mode == "streaming"
    assert result.batches == 3
    assert result.rows_scanned == 6
    finding = next(item for item in result.findings if item.rule_id == "column.unique")
    assert finding.affected_rows == 4
    assert finding.sample_rows == [1, 2, 4, 6]
    assert result.exactness["uniqueness"] == "exact_disk_backed"


def test_streaming_referential_integrity_is_exact(tmp_path: Path) -> None:
    pd.DataFrame({"customer_id": [10, 20, 30]}).to_csv(tmp_path / "customers.csv", index=False)
    pd.DataFrame({"order_id": [1, 2, 3, 4], "customer_id": [10, 99, 20, 88]}).to_csv(
        tmp_path / "orders.csv", index=False
    )
    contract = _write_contract(
        tmp_path / "contract.yml",
        {
            "contract_version": "2.0",
            "dataset": {
                "name": "orders",
                "contract_id": "orders-contract",
                "required_columns": ["order_id", "customer_id"],
            },
            "rules": {
                "order_id": {"type": "integer", "nullable": False, "unique": True},
                "customer_id": {"type": "integer", "nullable": False},
            },
            "dataset_rules": [
                {
                    "name": "customer_fk",
                    "type": "reference_exists",
                    "column": "customer_id",
                    "reference_dataset": "customers.csv",
                    "reference_column": "customer_id",
                    "severity": "error",
                }
            ],
            "privacy": {"detect_pii": False},
        },
    )
    result = validate_files(
        contract_path=contract,
        data_path=tmp_path / "orders.csv",
        execution_mode="streaming",
        limits=ResourceLimits(batch_rows=2, streaming_threshold_bytes=1),
        record_history=False,
    )
    finding = next(item for item in result.findings if item.rule_id == "dataset.reference_exists.customer_fk")
    assert finding.affected_rows == 2
    assert finding.sample_rows == [2, 4]
    assert result.exactness["referential_integrity"] == "exact_disk_backed"


def test_contract_lint_normalize_and_semantic_diff(tmp_path: Path) -> None:
    older_path = _write_contract(
        tmp_path / "old.yml",
        {
            "contract_version": "1.0",
            "dataset": {
                "name": "orders",
                "contract_id": "orders-contract",
                "owner": "Data Operations",
                "required_columns": ["order_id"],
            },
            "rules": {"order_id": {"type": "integer", "nullable": True}},
        },
    )
    newer_path = _write_contract(
        tmp_path / "new.yml",
        {
            "contract_version": "2.0",
            "dataset": {
                "name": "orders",
                "contract_id": "orders-contract",
                "owner": "Data Operations",
                "required_columns": ["order_id", "customer_id"],
            },
            "rules": {
                "order_id": {"type": "integer", "nullable": False},
                "customer_id": {"type": "integer", "nullable": False},
            },
        },
    )
    lint = lint_contract(newer_path)
    assert lint["passed"] is True
    normalized = normalized_contract_text(load_contract(newer_path))
    assert "contract_id: orders-contract" in normalized
    comparison = diff_contracts(load_contract(older_path), load_contract(newer_path))
    assert comparison["classification"] == "breaking"
    assert any(change["path"] == "rules.order_id.nullable" for change in comparison["changes"])


def test_state_schema_two_run_comparison_trends_and_artifacts(tmp_path: Path) -> None:
    contract = _write_contract(
        tmp_path / "contract.yml",
        {
            "dataset": {"name": "orders", "contract_id": "orders-contract", "required_columns": ["id"]},
            "rules": {"id": {"type": "integer", "unique": True}},
            "privacy": {"detect_pii": False},
        },
    )
    state_path = tmp_path / "runtime" / "state" / "dcm_state.sqlite3"
    state_path.parent.mkdir(parents=True)
    # Seed schema v1 to prove the migration path is real and backup-protected.
    conn = sqlite3.connect(state_path)
    conn.executescript(
        """
        CREATE TABLE validation_runs(run_id TEXT PRIMARY KEY,dataset_name TEXT NOT NULL,started_at TEXT NOT NULL,completed_at TEXT NOT NULL,duration_ms INTEGER NOT NULL,status TEXT NOT NULL,findings_total INTEGER NOT NULL,warnings INTEGER NOT NULL,errors INTEGER NOT NULL,critical INTEGER NOT NULL,row_count INTEGER NOT NULL,column_count INTEGER NOT NULL,contract_sha256 TEXT NOT NULL,data_sha256 TEXT NOT NULL,result_json TEXT NOT NULL);
        CREATE TABLE findings(run_id TEXT NOT NULL,finding_index INTEGER NOT NULL,finding_id TEXT NOT NULL,severity TEXT NOT NULL,category TEXT NOT NULL,rule_id TEXT NOT NULL,column_name TEXT,PRIMARY KEY(run_id,finding_index));
        CREATE TABLE jobs(job_id TEXT PRIMARY KEY,state TEXT NOT NULL,progress INTEGER NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,run_id TEXT,result_json TEXT,artifact_dir TEXT,error TEXT);
        PRAGMA user_version=1;
        """
    )
    conn.close()
    store = StateStore(state_path)
    assert store.health_check()["schema_version"] == SCHEMA_VERSION
    assert list((tmp_path / "runtime" / "backups").glob("state_schema_1_before_3_*.sqlite3"))

    data1 = tmp_path / "one.csv"
    pd.DataFrame({"id": [1, 2]}).to_csv(data1, index=False)
    first = validate_files(contract_path=contract, data_path=data1, history_path=state_path)
    data2 = tmp_path / "two.csv"
    pd.DataFrame({"id": [1, 1, 3]}).to_csv(data2, index=False)
    second = validate_files(contract_path=contract, data_path=data2, history_path=state_path)
    comparison = store.compare_runs(first.run_id, second.run_id)
    assert comparison["finding_count_delta"] > 0
    trend = store.trend(dataset_name="orders", limit=10)
    assert trend["run_count"] == 2
    check = sqlite3.connect(state_path)
    try:
        contract_row = check.execute(
            "SELECT contract_id,contract_version FROM contract_versions WHERE contract_sha256=?",
            (second.contract_sha256,),
        ).fetchone()
    finally:
        check.close()
    assert contract_row == ("orders-contract", "1.0")
    assert second.contract_id == "orders-contract"
    assert second.contract_version == "1.0"

    runtime = tmp_path / "runtime"
    for name in ("temp", "reports"):
        (runtime / name).mkdir(parents=True, exist_ok=True)
    publish_run_artifacts(second, root=runtime)
    assert store.artifacts_for_run(second.run_id)


def test_state_schema_two_migrates_to_three_with_contract_identity_column(tmp_path: Path) -> None:
    state_path = tmp_path / "runtime" / "state" / "dcm_state.sqlite3"
    state_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(state_path)
    try:
        conn.executescript(
            """
            CREATE TABLE contract_versions (
                contract_sha256 TEXT PRIMARY KEY,
                dataset_name TEXT NOT NULL,
                contract_version TEXT,
                source_format TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            PRAGMA user_version=2;
            """
        )
    finally:
        conn.close()
    StateStore(state_path)
    check = sqlite3.connect(state_path)
    try:
        columns = {row[1] for row in check.execute("PRAGMA table_info(contract_versions)")}
        version = check.execute("PRAGMA user_version").fetchone()[0]
    finally:
        check.close()
    assert version == 3
    assert "contract_id" in columns
    assert list((tmp_path / "runtime" / "backups").glob("state_schema_2_before_3_*.sqlite3"))
