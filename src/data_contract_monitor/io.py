from __future__ import annotations

from pathlib import Path

import pandas as pd

from .atomic import sha256_file
from .limits import ResourceLimits
from .readers import ReaderError, open_dataset_reader


class DataReadError(ValueError):
    """Raised when a dataset cannot be loaded."""


def read_dataset(path: Path, *, sheet_name: str | int = 0) -> pd.DataFrame:
    try:
        reader = open_dataset_reader(
            path,
            limits=ResourceLimits(),
            sheet_name=sheet_name,
            execution_mode="memory",
        )
        batch = next(reader.iter_batches())
        return batch.frame
    except (ReaderError, StopIteration) as exc:
        raise DataReadError(str(exc)) from exc


__all__ = ["DataReadError", "read_dataset", "sha256_file"]
