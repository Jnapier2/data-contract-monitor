from __future__ import annotations

from pathlib import Path

from data_contract_monitor.demo import write_demo_dataset
from data_contract_monitor.engine import validate_files
from data_contract_monitor.models import Severity


def test_good_demo_passes_without_findings(project_root: Path, tmp_path: Path) -> None:
    data = write_demo_dataset(tmp_path / "good.csv", valid=True)
    result = validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        record_history=False,
    )
    assert result.summary.passed is True
    assert result.summary.findings_total == 0
    assert result.profile.row_count == 3
    assert result.contract_label == "customer_orders.yml"
    assert result.data_label == "good.csv"


def test_bad_demo_finds_expected_issues_without_raw_values(project_root: Path, tmp_path: Path) -> None:
    data = write_demo_dataset(tmp_path / "bad.csv", valid=False)
    result = validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        record_history=False,
    )
    rules = {finding.rule_id for finding in result.findings}
    assert result.summary.passed is False
    assert result.summary.critical == 2
    assert result.summary.errors == 8
    assert result.summary.warnings == 2
    assert {
        "column.nullable",
        "column.unique",
        "column.type",
        "column.minimum",
        "column.allowed_values",
        "column.maximum_age_hours",
        "dataset.null_ratio.customer_id_completeness",
        "privacy.unapproved_pii_signal",
        "schema.extra_column",
    } <= rules
    serialized = result.model_dump_json()
    assert "123-45-6789" not in serialized
    assert "987-65-4321" not in serialized
    assert result.privacy_note.startswith("Reports contain aggregate")


def test_warning_threshold_can_fail_a_pipeline(project_root: Path, tmp_path: Path) -> None:
    data = write_demo_dataset(tmp_path / "bad.csv", valid=False)
    result = validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        fail_on=Severity.WARNING,
        record_history=False,
    )
    assert result.summary.fail_on == Severity.WARNING
    assert result.summary.passed is False


def test_findings_are_deterministic_for_same_rule_and_data(project_root: Path, tmp_path: Path) -> None:
    data = write_demo_dataset(tmp_path / "bad.csv", valid=False)
    first = validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        record_history=False,
    )
    second = validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        record_history=False,
    )
    assert [item.id for item in first.findings] == [item.id for item in second.findings]
