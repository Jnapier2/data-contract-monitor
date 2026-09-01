from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


class ResourceLimitError(RuntimeError):
    """Raised when input exceeds a declared local execution budget."""


@dataclass(frozen=True)
class ResourceLimits:
    max_contract_bytes: int = 1 * 1024 * 1024
    max_data_bytes: int = 250 * 1024 * 1024
    max_in_memory_data_bytes: int = 50 * 1024 * 1024
    max_rows: int = 2_000_000
    max_columns: int = 1_000
    max_findings: int = 10_000
    max_runtime_seconds: float = 300.0
    streaming_threshold_bytes: int = 8 * 1024 * 1024
    batch_rows: int = 50_000
    max_field_length: int = 1_000_000
    max_header_length: int = 512
    max_regex_length: int = 512
    max_json_depth: int = 64
    max_excel_sheets: int = 50
    max_report_bytes: int = 25 * 1024 * 1024
    min_free_disk_bytes: int = 100 * 1024 * 1024
    max_profile_distinct_track: int = 100_000
    max_pii_sample_rows: int = 1_000

    def public_dict(self) -> dict[str, int | float]:
        return asdict(self)

    def check_file_sizes(self, contract_path: Path, data_path: Path) -> None:
        contract_size = contract_path.stat().st_size
        data_size = data_path.stat().st_size
        if contract_size > self.max_contract_bytes:
            raise ResourceLimitError(
                f"Contract is {contract_size} bytes; limit is {self.max_contract_bytes} bytes."
            )
        if data_size > self.max_data_bytes:
            raise ResourceLimitError(
                f"Dataset is {data_size} bytes; limit is {self.max_data_bytes} bytes."
            )

    def check_data_file(self, data_path: Path) -> None:
        size = data_path.stat().st_size
        if size > self.max_data_bytes:
            raise ResourceLimitError(
                f"Dataset '{data_path.name}' is {size} bytes; limit is {self.max_data_bytes} bytes."
            )

    def check_shape(self, rows: int, columns: int) -> None:
        if rows > self.max_rows:
            raise ResourceLimitError(f"Dataset has {rows} rows; limit is {self.max_rows}.")
        if columns > self.max_columns:
            raise ResourceLimitError(
                f"Dataset has {columns} columns; limit is {self.max_columns}."
            )

    def check_headers(self, columns: list[str]) -> None:
        if len(columns) > self.max_columns:
            raise ResourceLimitError(
                f"Dataset has {len(columns)} columns; limit is {self.max_columns}."
            )
        too_long = [name for name in columns if len(name) > self.max_header_length]
        if too_long:
            raise ResourceLimitError(
                f"Dataset header exceeds {self.max_header_length} characters: {too_long[0][:80]!r}."
            )

    def check_regex(self, pattern: str) -> None:
        if len(pattern) > self.max_regex_length:
            raise ResourceLimitError(
                f"Regular-expression pattern is {len(pattern)} characters; limit is {self.max_regex_length}."
            )

    def check_free_disk(self, path: Path) -> None:
        probe = path if path.exists() else path.parent
        usage = shutil.disk_usage(probe)
        if usage.free < self.min_free_disk_bytes:
            raise ResourceLimitError(
                f"Free disk space is {usage.free} bytes; minimum is {self.min_free_disk_bytes} bytes."
            )
