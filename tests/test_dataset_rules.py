from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_contract_monitor.engine import validate_files


def test_dataset_and_column_rules(tmp_path: Path) -> None:
    contract = tmp_path / "rules.yml"
    contract.write_text(
        """
dataset:
  name: rule_matrix
  required_columns: [code, quantity, note, status, approval]
  allow_extra_columns: true
rules:
  code:
    type: string
    min_length: 3
    max_length: 5
    pattern: '^[A-Z]+$'
  quantity:
    type: integer
    minimum: 1
    maximum: 10
  status:
    allowed_values: [approved, pending]
dataset_rules:
  - name: exact_rows
    type: row_count
    minimum: 4
    maximum: 4
  - name: composite_key
    type: unique_combination
    columns: [code, status]
  - name: notes_complete
    type: null_ratio
    column: note
    max_ratio: 0.20
  - name: approval_required
    type: conditional_not_null
    when_column: status
    when_equals: approved
    then_column: approval
privacy:
  detect_pii: false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    data = tmp_path / "rules.csv"
    pd.DataFrame(
        {
            "code": ["A", "TOOLONG", "abc", "abc"],
            "quantity": [0, 11, 2.5, 2.5],
            "note": [None, None, "ok", "ok"],
            "status": ["approved", "other", "pending", "pending"],
            "approval": [None, "x", "x", "x"],
        }
    ).to_csv(data, index=False)
    result = validate_files(contract_path=contract, data_path=data, record_history=False)
    rule_ids = {finding.rule_id for finding in result.findings}
    assert {
        "column.min_length",
        "column.max_length",
        "column.pattern",
        "column.type",
        "column.minimum",
        "column.maximum",
        "column.allowed_values",
        "dataset.unique_combination.composite_key",
        "dataset.null_ratio.notes_complete",
        "dataset.conditional_not_null.approval_required",
    } <= rule_ids
    assert "dataset.row_count.exact_rows" not in rule_ids
