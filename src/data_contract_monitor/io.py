from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


class DataReadError(ValueError):
    """Raised when a dataset cannot be loaded."""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_dataset(path: Path, *, sheet_name: str | int = 0) -> pd.DataFrame:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(path, low_memory=False)
        elif suffix in {".xlsx", ".xlsm"}:
            frame = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
        elif suffix in {".jsonl", ".ndjson"}:
            frame = pd.read_json(path, lines=True)
        elif suffix == ".json":
            frame = pd.read_json(path)
        elif suffix == ".parquet":
            try:
                frame = pd.read_parquet(path)
            except ImportError as exc:
                raise DataReadError(
                    "Parquet support requires the optional 'parquet' dependency: "
                    "pip install 'data-contract-monitor[parquet]'"
                ) from exc
        else:
            raise DataReadError(
                f"Unsupported dataset type '{suffix}'. Supported: CSV, XLSX, XLSM, JSON, JSONL, and optional Parquet."
            )
    except DataReadError:
        raise
    except Exception as exc:
        raise DataReadError(f"Unable to read dataset '{path.name}': {exc}") from exc
    frame.columns = [str(column) for column in frame.columns]
    return frame
