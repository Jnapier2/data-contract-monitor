from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data_contract_monitor.io import DataReadError, read_dataset
from data_contract_monitor.profiler import profile_dataset


def test_csv_jsonl_and_excel_inputs(tmp_path: Path) -> None:
    frame = pd.DataFrame({"id": [1, 2], "when": ["2026-08-27T00:00:00Z", "2026-08-28T00:00:00Z"]})
    csv = tmp_path / "data.csv"
    jsonl = tmp_path / "data.jsonl"
    xlsx = tmp_path / "data.xlsx"
    frame.to_csv(csv, index=False)
    frame.to_json(jsonl, orient="records", lines=True)
    frame.to_excel(xlsx, index=False)
    assert read_dataset(csv).shape == (2, 2)
    assert read_dataset(jsonl).shape == (2, 2)
    assert read_dataset(xlsx).shape == (2, 2)


def test_unsupported_input_has_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(DataReadError, match="Unsupported dataset type"):
        read_dataset(path)


def test_profile_uses_aggregate_statistics_only() -> None:
    frame = pd.DataFrame(
        {
            "customer_email": ["private.one@example.com", "private.two@example.com"],
            "amount": [10.0, 20.0],
        }
    )
    profile = profile_dataset(frame)
    payload = profile.model_dump_json()
    assert profile.row_count == 2
    assert profile.columns[1].mean == 15.0
    assert "private.one@example.com" not in payload
    assert any(signal.category == "email" for signal in profile.pii_signals)
