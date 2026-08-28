from pathlib import Path

from tools.build_release import collect_files


def test_managed_inventory_ignores_virtual_environment_launchers(tmp_path: Path) -> None:
    for name in ("START_DATA_CONTRACT_MONITOR.bat", ".venv/Scripts/activate.bat", "temp/test/helper.bat", "pnpm-store/cached.bat", "frontend/node_modules/package/script.bat"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("@echo off\n", encoding="ascii")
    assert [p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path)] == ["START_DATA_CONTRACT_MONITOR.bat"]


def test_managed_inventory_retains_unexpected_source_launchers(tmp_path: Path) -> None:
    path = tmp_path / "tools" / "unexpected.bat"
    path.parent.mkdir()
    path.write_text("@echo off\n", encoding="ascii")
    assert path in collect_files(tmp_path)
