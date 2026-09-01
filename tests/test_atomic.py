from __future__ import annotations

import os
from pathlib import Path

from data_contract_monitor.atomic import atomic_write_text


def test_atomic_write_retries_transient_windows_file_lock(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "state" / "latest.json"
    original_replace = os.replace
    attempts = 0

    def transient_replace(source: str | bytes | os.PathLike[str] | os.PathLike[bytes], target: str | bytes | os.PathLike[str] | os.PathLike[bytes]) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "simulated transient file lock")
        original_replace(source, target)

    monkeypatch.setattr(os, "replace", transient_replace)
    atomic_write_text(destination, "ready\n")

    assert attempts == 3
    assert destination.read_text(encoding="utf-8") == "ready\n"
