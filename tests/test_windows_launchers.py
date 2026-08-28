from __future__ import annotations

from pathlib import Path

from tools.build_release import collect_files


ROOT_WRAPPERS = {
    "START_DATA_CONTRACT_MONITOR.bat": "serve",
    "VERIFY_RELEASE.bat": "doctor",
    "RUN_DEMO.bat": "demo",
    "RUN_TESTS.bat": "test",
    "REPAIR_INSTALLATION.bat": "repair",
    "CREATE_SUPPORT_EXPORT.bat": "export",
}


def _assert_crlf(path: Path) -> None:
    payload = path.read_bytes()
    assert b"\r\n" in payload
    assert b"\n" not in payload.replace(b"\r\n", b"")
    assert b"\x00" not in payload


def test_root_batch_entrypoints_are_crlf_and_forward_once(project_root: Path) -> None:
    for name, action in ROOT_WRAPPERS.items():
        path = project_root / name
        assert path.is_file(), name
        _assert_crlf(path)
        text = path.read_text(encoding="ascii")
        assert 'set "ROOT=%~dp0"' in text
        assert 'tools\\launch.bat' in text
        assert f'call "%LAUNCHER%" {action}' in text
        assert ':not_extracted' in text
        assert 'launching directly inside the downloaded ZIP' in text
        assert 'pause' in text.lower()
        assert '%CD%' not in text
        assert 'Desktop' not in text
        assert 'Downloads' not in text


def test_shared_windows_launcher_contract(project_root: Path) -> None:
    path = project_root / "tools" / "launch.bat"
    _assert_crlf(path)
    text = path.read_text(encoding="ascii")
    assert 'for %%I in ("%~dp0..") do set "ROOT=%%~fI"' in text
    assert 'tools\\bootstrap.py' in text
    assert 'tools\\release_gate.py' in text
    assert 'tools\\support_export.py' in text
    assert 'LATEST_LAUNCH_STATUS.txt' in text
    assert 'logs\\launcher.log' in text
    assert 'logs\\python_detection.txt' in text
    assert 'if /I "%ACTION%"=="export" goto :run_export' in text
    assert 'set "PYTHONPATH="' in text
    assert 'set "PYTHONHOME="' in text
    assert ':probe_python' in text
    assert 'if /I not "%ACTION%"=="repair" (' in text
    assert text.index('call :probe_python py -3.13') < text.index('call :probe_python py -3.14')
    for version in ('3.11', '3.12', '3.13', '3.14'):
        assert f'py -{version}' in text
    assert "Py_GIL_DISABLED" in text
    assert "struct.calcsize('P') == 8" in text
    assert '%CD%' not in text
    assert 'Desktop' not in text
    assert 'Downloads' not in text
    assert 'echo State: locating-compatible-python' not in text
    assert 'echo State: completed' not in text


def test_batch_files_have_no_duplicate_implementations(project_root: Path) -> None:
    batch_files = [path for path in collect_files(project_root) if path.suffix == '.bat']
    assert {path.name for path in batch_files} == {*ROOT_WRAPPERS, 'launch.bat'}
    for path in batch_files:
        if path.name != 'launch.bat':
            text = path.read_text(encoding='ascii')
            assert 'bootstrap.py' not in text
            assert 'release_gate.py' not in text
