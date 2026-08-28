"""Standard-library-only atomic status writes shared by setup and runtime."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    """Preserve the previous complete file through brief Windows file locks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(name)
    retry_delays = (0.05, 0.1, 0.2, 0.4, 0.8)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        for attempt in range(len(retry_delays) + 1):
            try:
                os.replace(temporary, path)
                return
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {5, 32, 33}:
                    raise
                if attempt == len(retry_delays):
                    raise
                time.sleep(retry_delays[attempt])
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            # A locked temporary file may remain; never hide the original error.
            pass
