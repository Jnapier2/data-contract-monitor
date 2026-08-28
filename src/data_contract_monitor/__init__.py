"""Data Contract Monitor public package.

The package initializer intentionally depends only on the Python standard library so
release verification and bounded support export remain available before optional
runtime dependencies are installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import ValidationResult


def _load_build_info() -> dict[str, Any]:
    path = Path(__file__).with_name("build_info.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    return {"version": "0.1.5", "build_id": "UNPACKAGED"}


_BUILD_INFO = _load_build_info()
__version__ = str(_BUILD_INFO.get("version") or "0.1.5")
__build_id__ = str(_BUILD_INFO.get("build_id") or "UNPACKAGED")


def __getattr__(name: str) -> Any:
    """Lazily expose heavy public models without loading Pydantic at import time."""
    if name == "ValidationResult":
        from .models import ValidationResult

        return ValidationResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ValidationResult", "__build_id__", "__version__"]
