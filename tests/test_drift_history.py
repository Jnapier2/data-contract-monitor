from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_contract_monitor.demo import write_demo_dataset
from data_contract_monitor.drift import compare_profile, load_baseline, snapshot_from_profile, write_baseline
from data_contract_monitor.engine import validate_files
from data_contract_monitor.history import read_history
from data_contract_monitor.io import read_dataset
from data_contract_monitor.profiler import profile_dataset


def test_schema_baseline_detects_added_removed_and_type_changes(tmp_path: Path) -> None:
    before = profile_dataset(pd.DataFrame({"id": [1, 2], "name": ["a", "b"]}), include_pii=False)
    baseline_path = tmp_path / "baseline.json"
    write_baseline(baseline_path, snapshot_from_profile("sample", before))
    after = profile_dataset(pd.DataFrame({"id": ["a", "b"], "new": [1, 2]}), include_pii=False)
    drift = compare_profile(after, load_baseline(baseline_path), baseline_path)
    kinds = {(change.change_type, change.column) for change in drift.changes}
    assert ("removed", "name") in kinds
    assert ("added", "new") in kinds
    assert ("type_changed", "id") in kinds
    assert drift.baseline_path == "baseline.json"


def test_validation_history_is_compact_and_contains_no_paths(project_root: Path, tmp_path: Path) -> None:
    history = tmp_path / "history.jsonl"
    data = write_demo_dataset(tmp_path / "good.csv", valid=True)
    validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        history_path=history,
    )
    entries = read_history(history)
    assert len(entries) == 1
    assert entries[0]["status"] == "passed"
    assert "data_label" not in entries[0]
    assert str(tmp_path) not in history.read_text(encoding="utf-8")


def test_packaged_schema_drift_example_is_reproducible(project_root: Path) -> None:
    baseline_path = project_root / "examples" / "baselines" / "customer_orders.schema.json"
    data_path = project_root / "examples" / "data" / "customer_orders_schema_drift.csv"
    profile = profile_dataset(read_dataset(data_path), include_pii=False)
    drift = compare_profile(profile, load_baseline(baseline_path), baseline_path)
    changes = {(item.change_type, item.column, item.severity.value) for item in drift.changes}
    assert changes == {
        ("added", "sales_channel", "warning"),
        ("removed", "status", "error"),
    }
