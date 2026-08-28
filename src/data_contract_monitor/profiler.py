from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.api import types as ptypes

from .models import ColumnProfile, DatasetProfile
from .pii import detect_pii


def infer_observed_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "unknown"
    if ptypes.is_bool_dtype(non_null.dtype):
        return "boolean"
    if ptypes.is_integer_dtype(non_null.dtype):
        return "integer"
    if ptypes.is_numeric_dtype(non_null.dtype):
        return "number"
    if ptypes.is_datetime64_any_dtype(non_null.dtype):
        return "datetime"
    sample = non_null.astype(str).head(200)
    parsed = pd.to_datetime(sample, errors="coerce", utc=True, format="mixed")
    if len(sample) and float(parsed.notna().mean()) >= 0.95:
        return "datetime"
    return "string"


def _safe_scalar(value: Any) -> float | str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return str(value)


def profile_dataset(frame: pd.DataFrame, *, include_pii: bool = True) -> DatasetProfile:
    row_count = len(frame)
    profiles: list[ColumnProfile] = []
    for column in frame.columns:
        series = frame[column]
        null_count = int(series.isna().sum())
        distinct_count = int(series.nunique(dropna=True))
        duplicate_count = int(series.dropna().duplicated(keep=False).sum())
        minimum: float | str | None = None
        maximum: float | str | None = None
        mean: float | None = None
        non_null = series.dropna()
        if not non_null.empty:
            if ptypes.is_numeric_dtype(non_null.dtype):
                minimum = _safe_scalar(non_null.min())
                maximum = _safe_scalar(non_null.max())
                mean = round(float(non_null.mean()), 6)
            elif ptypes.is_datetime64_any_dtype(non_null.dtype):
                minimum = str(non_null.min())
                maximum = str(non_null.max())
        profiles.append(
            ColumnProfile(
                name=str(column),
                observed_type=infer_observed_type(series),
                null_count=null_count,
                null_ratio=round(null_count / row_count, 6) if row_count else 0.0,
                distinct_count=distinct_count,
                duplicate_count=duplicate_count,
                minimum=minimum,
                maximum=maximum,
                mean=mean,
            )
        )
    return DatasetProfile(
        row_count=row_count,
        column_count=len(frame.columns),
        columns=profiles,
        pii_signals=detect_pii(frame) if include_pii else [],
    )
