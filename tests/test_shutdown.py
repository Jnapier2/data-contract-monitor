from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

import data_contract_monitor.cli as cli
import data_contract_monitor.local_server as local_server
from data_contract_monitor.atomic import atomic_write_text as runtime_atomic_text
import tools.bootstrap as bootstrap


def prepare_root(root: Path) -> None:
    (root / "VERSION.txt").write_text("0.2.2\n", encoding="utf-8")
    (root / "PACKAGE_METADATA.json").write_text(
        json.dumps({"build_id": "shutdown-test"}), encoding="utf-8"
    )
    (root / "state").mkdir(exist_ok=True)


def write_endpoint(root: Path, pid: int = 123) -> Path:
    path = root / "state" / "dashboard_endpoint.json"
    path.write_text(json.dumps({
        "service_id": "data-contract-monitor", "build_id": "shutdown-test",
        "process_id": pid, "state": "running", "browser_status": "opened",
    }), encoding="utf-8")
    return path


def forbid_export(*args, **kwargs):
    raise AssertionError("User cancellation must not produce a critical export")


@pytest.mark.parametrize("during_setup", [True, False])
def test_bootstrap_cancellation_records_stopped_without_crash_export(
    tmp_path: Path, monkeypatch, during_setup: bool
) -> None:
    prepare_root(tmp_path)
    endpoint = write_endpoint(tmp_path)
    monkeypatch.setattr(sys, "argv", ["bootstrap", "--root", str(tmp_path), "--action", "serve"])
    monkeypatch.setattr(bootstrap, "supported_interpreter", lambda: (True, "compatible"))
    monkeypatch.setattr(bootstrap, "startup_capsule", forbid_export)
    monkeypatch.setattr(bootstrap, "attempt_support_export", forbid_export)

    def cancel(*args, **kwargs):
        if during_setup:
            raise KeyboardInterrupt
        raise bootstrap.CommandCancelled(123, forced=False)

    monkeypatch.setattr(bootstrap, "ensure_environment", cancel if during_setup else lambda *a, **k: Path(sys.executable))
    monkeypatch.setattr(bootstrap, "stream_command", cancel)
    assert bootstrap.main() == 130
    status = json.loads((tmp_path / "state" / "latest_launch_status.json").read_text())
    assert status["state"] == "stopped-by-user"
    assert status["details"]["exit_code"] == 130
    expected = "running" if during_setup else "stopped"
    assert json.loads(endpoint.read_text())["state"] == expected
    assert not list((tmp_path / "diagnostics").rglob("*.zip"))


def test_cancellation_never_changes_another_process_endpoint(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    endpoint = write_endpoint(tmp_path, pid=456)
    before = endpoint.read_bytes()
    bootstrap.finalize_cancelled_endpoint(tmp_path, 123)
    assert endpoint.read_bytes() == before


class InterruptedOutput:
    closed = False

    def __iter__(self):
        raise KeyboardInterrupt

    def close(self):
        self.closed = True


class FakeProcess:
    pid = 123

    def __init__(self, *, time_out=False):
        self.stdout = InterruptedOutput()
        self.returncode = None
        self.signals = []
        self.killed = False
        self.time_out = time_out

    def poll(self):
        return self.returncode

    def send_signal(self, value):
        self.signals.append(value)

    def wait(self, timeout):
        if (timeout == 0.2 or self.time_out) and not self.killed:
            raise subprocess.TimeoutExpired("synthetic child", timeout)
        self.returncode = 130
        return self.returncode

    def kill(self):
        self.killed = True

    def terminate(self):
        self.killed = True


@pytest.mark.parametrize("time_out", [False, True])
def test_stream_cancellation_stops_only_its_child_and_closes_output(
    tmp_path: Path, monkeypatch, time_out: bool
) -> None:
    process = FakeProcess(time_out=time_out)
    options = {}

    def popen(*args, **kwargs):
        options.update(kwargs)
        return process

    monkeypatch.setattr(bootstrap.subprocess, "Popen", popen)
    with pytest.raises(bootstrap.CommandCancelled) as interrupted:
        bootstrap.stream_command(["synthetic child"], root=tmp_path, env={}, log_path=tmp_path / "test.log")
    assert interrupted.value.process_id == process.pid
    assert interrupted.value.forced is time_out
    assert process.killed is time_out
    assert process.stdout.closed
    assert process.poll() == 130
    expected_signal = signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT
    assert process.signals == [expected_signal]
    expected_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    assert options["creationflags"] == expected_flags
    assert options["start_new_session"] is (os.name != "nt")


def test_idle_output_does_not_delay_main_thread_cancellation(tmp_path: Path, monkeypatch) -> None:
    reading = threading.Event()
    stopped = threading.Event()

    class IdleOutput:
        closed = False

        def __iter__(self):
            reading.set()
            assert stopped.wait(2), "Owned child was not stopped while its output was idle"
            return iter(["Shutdown complete.\n"])

        def close(self):
            self.closed = True

    class IdleProcess(FakeProcess):
        def __init__(self):
            super().__init__()
            self.stdout = IdleOutput()

        def wait(self, timeout):
            if timeout == 0.2:
                assert reading.wait(2)
                raise KeyboardInterrupt
            self.returncode = 130
            return self.returncode

        def send_signal(self, value):
            super().send_signal(value)
            stopped.set()

    process = IdleProcess()
    monkeypatch.setattr(bootstrap.subprocess, "Popen", lambda *a, **k: process)
    with pytest.raises(bootstrap.CommandCancelled) as interrupted:
        bootstrap.stream_command(["idle child"], root=tmp_path, env={}, log_path=tmp_path / "test.log")
    assert not interrupted.value.forced
    assert process.stdout.closed
    assert "Shutdown complete." in (tmp_path / "test.log").read_text()


def test_bootstrap_and_runtime_atomic_writers_are_windows_safe(tmp_path: Path) -> None:
    tooling_path = tmp_path / "tooling.txt"
    runtime_path = tmp_path / "runtime.txt"
    bootstrap.atomic_text(tooling_path, "tooling\n")
    runtime_atomic_text(runtime_path, "runtime\n")
    assert tooling_path.read_bytes() == b"tooling\n"
    assert runtime_path.read_bytes() == b"runtime\n"


@pytest.mark.parametrize("cancel_after_health", [False, True])
def test_cancelled_readiness_never_opens_a_browser(cancel_after_health: bool) -> None:
    cancelled = threading.Event()
    calls = []
    if not cancel_after_health:
        cancelled.set()

    def health(url):
        calls.append("health")
        cancelled.set()
        return {"service_id": local_server.SERVICE_ID, "version": "test", "build_id": "test"}

    opened = local_server.open_browser_when_ready(
        "http://127.0.0.1:8765", expected_version="test", expected_build_id="test",
        health_reader=health, browser_opener=lambda url: calls.append("browser"),
        cancelled=cancelled.is_set,
    )
    assert not opened
    assert calls == (["health"] if cancel_after_health else [])


@pytest.mark.parametrize("exception, expected_code, expected_exports", [
    (KeyboardInterrupt(), 130, 0), (RuntimeError("synthetic failure"), 4, 1),
])
def test_cli_exit_paths_do_not_raise_unhandled_typer_exits(
    monkeypatch, exception, expected_code, expected_exports
) -> None:
    captures = []
    manager = SimpleNamespace(capture_critical=lambda *a: captures.append(a))
    monkeypatch.setattr(cli, "DiagnosticManager", lambda: manager)
    monkeypatch.setattr(cli, "install_exception_hooks", lambda manager: None)

    def fail():
        raise exception

    monkeypatch.setattr(cli, "app", fail)
    with pytest.raises(SystemExit) as exited:
        cli.main()
    assert exited.value.code == expected_code
    assert len(captures) == expected_exports


def test_late_browser_worker_cannot_overwrite_stopped_state(tmp_path: Path, monkeypatch) -> None:
    prepare_root(tmp_path)
    ready = threading.Event()
    release_worker = threading.Event()
    workers = []
    real_thread = threading.Thread
    closed = []
    endpoint = local_server.ReservedEndpoint("127.0.0.1", 8765, 8766, SimpleNamespace(close=lambda: closed.append(True)))
    monkeypatch.setattr(cli, "runtime_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "verify_release_integrity", lambda root: SimpleNamespace(mode="development", passed=True))
    monkeypatch.setattr(cli, "reserve_endpoint", lambda *a, **k: endpoint)

    def start_thread(*args, **kwargs):
        worker = real_thread(*args, **kwargs)
        workers.append(worker)
        return worker

    def wait_for_health(*args, **kwargs):
        ready.set()
        assert release_worker.wait(2)
        return True

    class Server:
        def __init__(self, config):
            pass

        def run(self, sockets):
            assert ready.wait(2)
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.threading, "Thread", start_thread)
    monkeypatch.setattr(cli, "open_browser_when_ready", wait_for_health)
    monkeypatch.setattr(cli.uvicorn, "Server", Server)
    try:
        with pytest.raises(KeyboardInterrupt):
            cli.serve_command(host="127.0.0.1", port=8765, port_search_limit=20, open_browser=True)
    finally:
        release_worker.set()
        for worker in workers:
            worker.join(timeout=2)
    assert closed == [True]
    assert all(not worker.is_alive() for worker in workers)
    payload = json.loads((tmp_path / "state" / "dashboard_endpoint.json").read_text())
    assert payload["state"] == "stopped"
    assert payload["browser_status"] == "closed"
