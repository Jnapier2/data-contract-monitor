from __future__ import annotations

from pathlib import Path


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


def test_root_batch_entrypoints_are_logic_free_forwarders(project_root: Path) -> None:
    for name, action in ROOT_WRAPPERS.items():
        path = project_root / name
        assert path.is_file(), name
        _assert_crlf(path)
        text = path.read_text(encoding="ascii")
        assert text.splitlines() == [
            "@echo off",
            f'call "%~dp0tools\\launch.bat" {action}',
            "exit /b %ERRORLEVEL%",
        ]
        assert "%CD%" not in text
        assert "Desktop" not in text
        assert "Downloads" not in text
        assert "bootstrap.py" not in text
        assert "release_gate.py" not in text


def test_shared_windows_launcher_contract(project_root: Path) -> None:
    path = project_root / "tools" / "launch.bat"
    _assert_crlf(path)
    text = path.read_text(encoding="ascii")
    assert 'for %%I in ("%~dp0..") do set "ROOT=%%~fI"' in text
    assert 'tools\\bootstrap.py' in text
    assert 'tools\\release_gate.py' in text
    assert 'tools\\maintenance_preflight.py' in text
    assert 'tools\\support_export.py' in text
    assert 'LATEST_LAUNCH_STATUS.txt' in text
    assert 'logs\\launcher.log' in text
    assert 'logs\\python_detection.txt' in text
    assert 'if /I "%ACTION%"=="export" goto :run_export' in text
    assert text.index('if /I "%ACTION%"=="export" goto :run_export') < text.index('tools\\maintenance_preflight.py')
    assert text.index('tools\\maintenance_preflight.py') < text.index('tools\\release_gate.py')
    assert 'set "PYTHONPATH="' in text
    assert 'set "PYTHONHOME="' in text
    assert ':probe_python' in text
    assert 'if /I "%ACTION%"=="repair" goto :external_python' in text
    assert 'if /I "%ACTION%"=="export" goto :external_python' in text
    assert text.index('call :probe_python py -3.13') < text.index('call :probe_python py -3.14')
    for version in ('3.11', '3.12', '3.13', '3.14'):
        assert f'py -{version}' in text
    assert "Py_GIL_DISABLED" in text
    assert "struct.calcsize('P') == 8" in text
    assert 'if /I not "%DCM_NO_PAUSE%"=="1" pause' in text
    assert "%CD%" not in text
    assert "Desktop" not in text
    assert "Downloads" not in text


def test_batch_files_have_one_backend_and_one_filename_per_action(project_root: Path) -> None:
    batch_files = sorted(project_root.rglob("*.bat"))
    assert {path.name for path in batch_files} == {*ROOT_WRAPPERS, "launch.bat"}
    assert len(batch_files) == len(ROOT_WRAPPERS) + 1
    for path in batch_files:
        if path.name != "launch.bat":
            text = path.read_text(encoding="ascii")
            assert text.count("call ") == 1
