from __future__ import annotations

from pathlib import Path

import pytest

from data_contract_monitor.contract_loader import ContractLoadError, load_contract


def test_load_native_contract(project_root: Path) -> None:
    contract = load_contract(project_root / "examples" / "contracts" / "customer_orders.yml")
    assert contract.dataset.name == "customer_orders"
    assert contract.source_format == "native"
    assert contract.rules["order_id"].unique is True
    assert contract.rules["total_amount"].minimum == 0
    assert "customer_email" in contract.dataset.required_columns


def test_load_odcs_contract(project_root: Path) -> None:
    contract = load_contract(project_root / "examples" / "contracts" / "customer_orders.odcs.yaml")
    assert contract.source_format == "odcs"
    assert contract.source_standard_version == "v3.1.0"
    assert contract.dataset.owner == "data-operations-owner"
    assert contract.rules["order_id"].unique is True
    assert contract.rules["order_id"].nullable is False
    assert contract.dataset_rules[0].type == "row_count"
    assert contract.adapter_notes


def test_invalid_regex_is_rejected_at_contract_load(tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text(
        """
contract_version: '1.0'
dataset:
  name: invalid_regex
rules:
  value:
    pattern: '[broken'
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractLoadError, match="invalid regular-expression"):
        load_contract(path)


def test_unknown_contract_key_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "unknown.yml"
    path.write_text(
        """
dataset:
  name: strict_contract
unexpected_setting: true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractLoadError, match="unexpected_setting"):
        load_contract(path)
