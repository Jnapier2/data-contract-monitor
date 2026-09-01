from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Callable, Iterator, Literal, Protocol

import pandas as pd

from .limits import ResourceLimitError, ResourceLimits


class ReaderError(ValueError):
    """Raised when a dataset reader cannot safely inspect or iterate an input."""


@dataclass(frozen=True)
class DatasetBatch:
    frame: pd.DataFrame
    start_row: int


class DatasetReader(Protocol):
    mode: Literal["memory", "streaming"]

    def inspect_columns(self) -> list[str]: ...

    def iter_batches(self) -> Iterator[DatasetBatch]: ...


ReaderFactory = Callable[[Path, ResourceLimits, str | int, Literal["memory", "streaming"]], DatasetReader]
_REGISTRY: dict[str, ReaderFactory] = {}
_PLUGINS_DISCOVERED = False


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame.columns = [str(column) for column in frame.columns]
    return frame


def _validate_text_signature(path: Path) -> None:
    head = path.read_bytes()[:8192]
    if b"\x00" in head:
        raise ReaderError(f"Text dataset '{path.name}' contains NUL bytes and does not match its extension.")
    try:
        head.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ReaderError(
            f"Text dataset '{path.name}' is not valid UTF-8/UTF-8-SIG near the beginning of the file."
        ) from exc


def _validate_json_depth(value: object, *, maximum: int, depth: int = 0) -> None:
    if depth > maximum:
        raise ReaderError(f"JSON nesting exceeds the configured depth limit of {maximum}.")
    if isinstance(value, dict):
        for item in value.values():
            _validate_json_depth(item, maximum=maximum, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _validate_json_depth(item, maximum=maximum, depth=depth + 1)


def validate_content_signature(path: Path, limits: ResourceLimits) -> None:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".jsonl", ".ndjson", ".json"}:
        _validate_text_signature(path)
    if suffix in {".xlsx", ".xlsm"}:
        with path.open("rb") as handle:
            if handle.read(4) != b"PK\x03\x04":
                raise ReaderError(f"Spreadsheet '{path.name}' does not have an XLSX/ZIP signature.")
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                    raise ReaderError(f"Spreadsheet '{path.name}' is not a valid XLSX workbook.")
        except zipfile.BadZipFile as exc:
            raise ReaderError(f"Spreadsheet '{path.name}' is not a valid XLSX workbook.") from exc
    elif suffix == ".parquet":
        with path.open("rb") as handle:
            head = handle.read(4)
            handle.seek(max(path.stat().st_size - 4, 0))
            tail = handle.read(4)
        if head != b"PAR1" or tail != b"PAR1":
            raise ReaderError(f"Parquet dataset '{path.name}' does not have a valid Parquet signature.")
    elif suffix == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ReaderError(f"JSON dataset '{path.name}' is not valid JSON: {exc}") from exc
        _validate_json_depth(value, maximum=limits.max_json_depth)


class PandasReader:
    def __init__(
        self,
        path: Path,
        limits: ResourceLimits,
        sheet_name: str | int,
        mode: Literal["memory", "streaming"],
    ) -> None:
        self.path = path
        self.limits = limits
        self.sheet_name = sheet_name
        self.mode = mode
        self.suffix = path.suffix.lower()
        validate_content_signature(path, limits)
        if self.suffix in {".xlsx", ".xlsm"}:
            try:
                with pd.ExcelFile(path, engine="openpyxl") as workbook:
                    sheet_count = len(workbook.sheet_names)
                if sheet_count > limits.max_excel_sheets:
                    raise ResourceLimitError(
                        f"Workbook has {sheet_count} sheets; limit is {limits.max_excel_sheets}."
                    )
            except ResourceLimitError:
                raise
            except Exception as exc:
                raise ReaderError(f"Unable to inspect workbook '{path.name}': {exc}") from exc

    def inspect_columns(self) -> list[str]:
        try:
            if self.suffix == ".csv":
                frame = pd.read_csv(self.path, nrows=0)
            elif self.suffix in {".jsonl", ".ndjson"}:
                iterator = pd.read_json(self.path, lines=True, chunksize=1)
                frame = next(iter(iterator), pd.DataFrame())
            elif self.suffix in {".xlsx", ".xlsm"}:
                frame = pd.read_excel(
                    self.path, sheet_name=self.sheet_name, nrows=0, engine="openpyxl"
                )
            elif self.suffix == ".json":
                frame = pd.read_json(self.path)
            elif self.suffix == ".parquet":
                try:
                    frame = pd.read_parquet(self.path)
                except ImportError as exc:
                    raise ReaderError(
                        "Parquet support requires the optional 'parquet' dependency: "
                        "pip install 'data-contract-monitor[parquet]'"
                    ) from exc
            else:
                raise ReaderError(f"Unsupported dataset type '{self.suffix}'.")
        except ReaderError:
            raise
        except Exception as exc:
            raise ReaderError(f"Unable to inspect dataset '{self.path.name}': {exc}") from exc
        columns = [str(column) for column in frame.columns]
        self.limits.check_headers(columns)
        return columns

    def _read_all(self) -> pd.DataFrame:
        try:
            if self.suffix == ".csv":
                frame = pd.read_csv(self.path, low_memory=False)
            elif self.suffix in {".xlsx", ".xlsm"}:
                frame = pd.read_excel(self.path, sheet_name=self.sheet_name, engine="openpyxl")
            elif self.suffix in {".jsonl", ".ndjson"}:
                frame = pd.read_json(self.path, lines=True)
            elif self.suffix == ".json":
                frame = pd.read_json(self.path)
            elif self.suffix == ".parquet":
                try:
                    frame = pd.read_parquet(self.path)
                except ImportError as exc:
                    raise ReaderError(
                        "Parquet support requires the optional 'parquet' dependency: "
                        "pip install 'data-contract-monitor[parquet]'"
                    ) from exc
            else:
                raise ReaderError(f"Unsupported dataset type '{self.suffix}'.")
        except ReaderError:
            raise
        except Exception as exc:
            raise ReaderError(f"Unable to read dataset '{self.path.name}': {exc}") from exc
        return _normalize_frame(frame)

    def iter_batches(self) -> Iterator[DatasetBatch]:
        if self.mode == "memory" or self.suffix not in {".csv", ".jsonl", ".ndjson"}:
            yield DatasetBatch(self._read_all(), 1)
            return
        start_row = 1
        try:
            if self.suffix == ".csv":
                iterator = pd.read_csv(
                    self.path,
                    low_memory=False,
                    chunksize=self.limits.batch_rows,
                )
            else:
                iterator = pd.read_json(
                    self.path,
                    lines=True,
                    chunksize=self.limits.batch_rows,
                )
            for frame in iterator:
                normalized = _normalize_frame(frame)
                yield DatasetBatch(normalized, start_row)
                start_row += len(normalized)
        except Exception as exc:
            raise ReaderError(f"Unable to stream dataset '{self.path.name}': {exc}") from exc


def register_reader(suffix: str, factory: ReaderFactory) -> None:
    normalized = suffix.lower()
    if not normalized.startswith("."):
        normalized = "." + normalized
    _REGISTRY[normalized] = factory


def _discover_plugins() -> None:
    global _PLUGINS_DISCOVERED
    if _PLUGINS_DISCOVERED:
        return
    _PLUGINS_DISCOVERED = True
    try:
        points = metadata.entry_points(group="data_contract_monitor.readers")
    except TypeError:  # pragma: no cover - older importlib.metadata compatibility
        points = metadata.entry_points().get("data_contract_monitor.readers", [])
    for point in points:
        try:
            plugin = point.load()
            suffixes = getattr(plugin, "suffixes", ())
            factory = getattr(plugin, "create_reader", None)
            if callable(factory):
                for suffix in suffixes:
                    register_reader(str(suffix), factory)
        except Exception:
            # Optional third-party plugins must never break built-in readers.
            continue


def _pandas_factory(
    path: Path,
    limits: ResourceLimits,
    sheet_name: str | int,
    mode: Literal["memory", "streaming"],
) -> DatasetReader:
    return PandasReader(path, limits, sheet_name, mode)


for _suffix in (".csv", ".xlsx", ".xlsm", ".json", ".jsonl", ".ndjson", ".parquet"):
    register_reader(_suffix, _pandas_factory)


def choose_execution_mode(
    path: Path,
    requested: Literal["auto", "memory", "streaming"],
    limits: ResourceLimits,
) -> Literal["memory", "streaming"]:
    suffix = path.suffix.lower()
    streamable = suffix in {".csv", ".jsonl", ".ndjson"}
    if requested == "memory":
        return "memory"
    if requested == "streaming":
        if not streamable:
            raise ReaderError(
                f"Streaming mode is currently supported for CSV and JSON Lines, not '{suffix}'."
            )
        return "streaming"
    if streamable and path.stat().st_size >= limits.streaming_threshold_bytes:
        return "streaming"
    return "memory"


def open_dataset_reader(
    path: Path,
    *,
    limits: ResourceLimits,
    sheet_name: str | int = 0,
    execution_mode: Literal["auto", "memory", "streaming"] = "auto",
) -> DatasetReader:
    _discover_plugins()
    suffix = path.suffix.lower()
    factory = _REGISTRY.get(suffix)
    if factory is None:
        raise ReaderError(
            f"Unsupported dataset type '{suffix}'. Supported built-ins: CSV, XLSX, XLSM, JSON, JSONL, and optional Parquet."
        )
    mode = choose_execution_mode(path, execution_mode, limits)
    if mode == "memory" and path.stat().st_size > limits.max_in_memory_data_bytes:
        raise ReaderError(
            f"Dataset '{path.name}' is {path.stat().st_size} bytes; in-memory readers are capped at "
            f"{limits.max_in_memory_data_bytes} bytes. Use CSV/JSONL streaming or reduce the file."
        )
    return factory(path, limits, sheet_name, mode)
