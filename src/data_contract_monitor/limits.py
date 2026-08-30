from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


class ResourceLimitError(RuntimeError):
    """Raised when input exceeds a declared local execution budget."""


@dataclass(frozen=True)
class ResourceLimits:
    max_contract_bytes: int = 1 * 1024 * 1024
    max_data_bytes: int = 50 * 1024 * 1024
    max_rows: int = 2_000_000
    max_columns: int = 1_000
    max_findings: int = 10_000
    max_runtime_seconds: float = 300.0

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

    def check_shape(self, rows: int, columns: int) -> None:
        if rows > self.max_rows:
            raise ResourceLimitError(f"Dataset has {rows} rows; limit is {self.max_rows}.")
        if columns > self.max_columns:
            raise ResourceLimitError(
                f"Dataset has {columns} columns; limit is {self.max_columns}."
            )
