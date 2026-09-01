from __future__ import annotations

import os
from pathlib import Path

from tools import tooling_common


def test_atomic_text_fsyncs_a_writable_descriptor(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "state" / "release_verification.json"
    calls: list[int] = []

    def require_writable_fd(fd: int) -> None:
        # A zero-byte write is harmless but distinguishes a writable descriptor
        # from the read-only descriptor that triggered Windows Errno 9 in v0.3.0.
        os.write(fd, b"")
        calls.append(fd)

    monkeypatch.setattr(tooling_common.os, "fsync", require_writable_fd)
    tooling_common.atomic_text(target, '{"passed": true}\n')

    assert target.read_text(encoding="utf-8") == '{"passed": true}\n'
    assert len(calls) == 1
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))


def test_atomic_text_replaces_existing_file_and_cleans_temp(tmp_path: Path) -> None:
    target = tmp_path / "state" / "receipt.json"
    target.parent.mkdir(parents=True)
    target.write_text("old\n", encoding="utf-8")

    tooling_common.atomic_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "new\n"
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))
