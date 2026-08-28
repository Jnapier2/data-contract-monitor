from __future__ import annotations

import io
import os
from pathlib import Path
import sys

from tools.bootstrap import console_print, stream_command


def test_console_output_falls_back_without_losing_message(monkeypatch) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stream)
        console_print("Doctor: \u250f PASS \u2513")
    stream.flush()
    assert "PASS" in buffer.getvalue().decode("cp1252")
    assert "\\u250f" in buffer.getvalue().decode("cp1252")


def test_command_unicode_is_preserved_in_utf8_log_with_legacy_console(monkeypatch, tmp_path: Path) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
    log_path = tmp_path / "bootstrap.log"
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stream)
        code = stream_command(
            [sys.executable, "-c", "print(chr(0x250f) + ' PASS ' + chr(0x2513))"],
            root=tmp_path, env=environment, log_path=log_path,
        )
    stream.flush()
    assert code == 0
    assert "\u250f PASS \u2513" in log_path.read_text(encoding="utf-8")
    assert "PASS" in buffer.getvalue().decode("cp1252")
