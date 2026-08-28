from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import struct
import subprocess
import sys
import sysconfig
import threading
import traceback
import venv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Setup must use this package's standard-library-only helper before installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from data_contract_monitor.atomic_io import atomic_write_text as atomic_text

SUPPORTED_MIN = (3, 11)
SUPPORTED_MAX = (3, 14)
_SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*[^\s,;]+")
_SECRET_KEY_RE = re.compile(r"(?i)^(api[_-]?key|token|password|secret|authorization)$")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL_CREDENTIAL_RE = re.compile(r"(?i)(https?://)([^/\s:@]+):([^@\s/]+)@")

RUNTIME_DIRS = (
    "config",
    "logs",
    "state",
    "temp",
    "cache",
    "exports",
    "diagnostics",
    "reports",
    "downloads",
)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def redact(value: str) -> str:
    home = str(Path.home())
    redacted = value.replace(home, "[USER_HOME]")
    redacted = _URL_CREDENTIAL_RE.sub(r"\1[REDACTED]@", redacted)
    redacted = _SECRET_RE.sub(r"\1=[REDACTED]", redacted)
    redacted = _IP_RE.sub("[IP_REDACTED]", redacted)
    return redacted[:20_000]


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SECRET_KEY_RE.fullmatch(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value


def console_print(value: str, *, end: str = "\n", stream: Any = None) -> None:
    """Keep legacy Windows output encodings from aborting a healthy command."""
    target = sys.stdout if stream is None else stream
    try:
        print(value, end=end, flush=True, file=target)
    except UnicodeEncodeError:
        encoding = getattr(target, "encoding", None) or "ascii"
        compatible = value.encode(encoding, errors="backslashreplace").decode(encoding)
        print(compatible, end=end, flush=True, file=target)


def log(message: str, path: Path) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {redact(message)}"
    console_print(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_status(root: Path, *, state: str, action: str, details: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "project": "Data Contract Monitor",
        "version": read_version(root),
        "build_id": read_build_id(root),
        "state": state,
        "action": action,
        "updated_at": datetime.now(UTC).isoformat(),
        "project_root": redact(str(root)),
        "python": {
            "executable": redact(sys.executable),
            "version": platform.python_version(),
            "architecture": struct.calcsize("P") * 8,
            "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        },
    }
    if details:
        payload["details"] = redact_value(details)
    lines = [
        "Data Contract Monitor startup status",
        f"State: {state}",
        f"Action: {action}",
        f"Version: {payload['version'] or 'unknown'}",
        f"Build: {payload['build_id'] or 'unknown'}",
        f"Updated: {payload['updated_at']}",
        f"Python: {platform.python_version()} ({struct.calcsize('P') * 8}-bit)",
        f"Project root: {payload['project_root']}",
    ]
    if details:
        safe_details = payload.get("details", {})
        if isinstance(safe_details, dict):
            for key, value in safe_details.items():
                lines.append(f"{key}: {redact(str(value))}")
    atomic_text(root / "LATEST_LAUNCH_STATUS.txt", "\n".join(lines) + "\n")
    atomic_json(root / "state" / "latest_launch_status.json", payload)


def read_version(root: Path) -> str | None:
    try:
        return (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_build_id(root: Path) -> str | None:
    for path in (root / "PACKAGE_METADATA.json", root / "src" / "data_contract_monitor" / "build_info.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("build_id"):
                return str(payload["build_id"])
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def signature(paths: list[Path], *, interpreter: Path) -> str:
    digest = hashlib.sha256()
    digest.update(str(interpreter.resolve()).encode("utf-8", errors="replace"))
    digest.update(platform.python_version().encode())
    digest.update(platform.machine().encode())
    for path in paths:
        digest.update(path.name.encode())
        digest.update(sha256_file(path).encode())
    return digest.hexdigest()


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def supported_interpreter() -> tuple[bool, str]:
    version = sys.version_info[:2]
    if not (SUPPORTED_MIN <= version <= SUPPORTED_MAX):
        return False, "standard CPython 3.11 through 3.14 is required"
    if struct.calcsize("P") != 8:
        return False, "a 64-bit Python runtime is required"
    if bool(sysconfig.get_config_var("Py_GIL_DISABLED")):
        return False, "the free-threaded Python build is not used by this release"
    return True, "compatible"


def remove_tree(path: Path, log_path: Path) -> None:
    def onerror(function: Any, target: str, exc_info: Any) -> None:
        try:
            os.chmod(target, 0o700)
            function(target)
        except OSError:
            raise exc_info[1]

    log(f"Removing package-managed environment: {path}", log_path)
    shutil.rmtree(path, onerror=onerror)


class CommandCancelled(KeyboardInterrupt):
    """A user cancellation after the specific launched process has stopped."""

    def __init__(self, process_id: int, *, forced: bool) -> None:
        super().__init__("Command stopped by user")
        self.process_id = process_id
        self.forced = forced


def stop_owned_process(process: subprocess.Popen[str], log_path: Path) -> bool:
    """Request a graceful stop, then bound cleanup of this child only."""
    forced = False
    if process.poll() is None:
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        except OSError:
            forced = True
            process.terminate()
    try:
        process.wait(timeout=5)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        forced = True
        process.kill()
        process.wait(timeout=3)
    if process.poll() is None:
        raise RuntimeError("The launched process did not stop within the cleanup budget")
    return forced


def finalize_cancelled_endpoint(root: Path, process_id: int) -> None:
    """Do not leave the stopped child's endpoint active or alter another run."""
    path = root / "state" / "dashboard_endpoint.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict) or payload.get("service_id") != "data-contract-monitor":
        return
    if payload.get("process_id") != process_id or payload.get("build_id") != read_build_id(root):
        return
    payload.update(state="stopped", browser_status="closed", updated_at=datetime.now(UTC).isoformat())
    atomic_json(path, payload)


def stream_command(
    command: list[str],
    *,
    root: Path,
    env: dict[str, str],
    log_path: Path,
    check: bool = True,
) -> int:
    printable = subprocess.list2cmdline(command) if os.name == "nt" else " ".join(command)
    log("RUN " + printable, log_path)
    process = subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )
    assert process.stdout is not None
    output_errors: list[BaseException] = []

    def relay_output() -> None:
        try:
            with log_path.open("a", encoding="utf-8") as output:
                for line in process.stdout:
                    safe_line = redact(line)
                    output.write(safe_line)
                    output.flush()
                    console_print(safe_line, end="")
        except BaseException as exc:
            output_errors.append(exc)

    # A blocking Windows pipe read can defer the main thread's Ctrl+C handler.
    # Drain output in one worker; keep the main thread on short, bounded waits.
    reader = threading.Thread(target=relay_output, name="dcm-command-output", daemon=True)
    reader.start()
    try:
        while True:
            if output_errors:
                raise output_errors[0]
            try:
                return_code = process.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        reader.join(timeout=2)
        if reader.is_alive():
            raise RuntimeError("Command output did not close within the cleanup budget")
        if output_errors:
            raise output_errors[0]
    except KeyboardInterrupt:
        log("Cancellation requested; stopping the launched command", log_path)
        forced = stop_owned_process(process, log_path)
        reader.join(timeout=2)
        raise CommandCancelled(process.pid, forced=forced) from None
    except Exception:
        stop_owned_process(process, log_path)
        reader.join(timeout=2)
        raise
    finally:
        if not reader.is_alive():
            process.stdout.close()
    if check and return_code:
        raise RuntimeError(f"Command failed with exit code {return_code}; see {log_path}")
    return return_code


def resolve_release_wheel(root: Path) -> Path:
    metadata_path = root / "PACKAGE_METADATA.json"
    if metadata_path.is_file():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        wheel_info = payload.get("wheel")
        if not isinstance(wheel_info, dict) or not isinstance(wheel_info.get("path"), str):
            raise RuntimeError("PACKAGE_METADATA.json does not identify the release wheel")
        wheel = (root / wheel_info["path"]).resolve()
        try:
            wheel.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("Release wheel path escapes the project root") from exc
        if not wheel.is_file():
            raise RuntimeError(f"Release wheel is missing: {wheel}")
        expected = str(wheel_info.get("sha256") or "").lower()
        if expected and sha256_file(wheel) != expected:
            raise RuntimeError("Release wheel SHA-256 does not match PACKAGE_METADATA.json")
        return wheel
    wheels = sorted((root / "packages").glob("data_contract_monitor-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one local application wheel, found {len(wheels)}")
    return wheels[0]


def environment_valid(python: Path, *, version: str, build_id: str | None) -> bool:
    if not python.is_file():
        return False
    code = r'''
import importlib
import sys
required = [
    "data_contract_monitor", "pandas", "numpy", "fastapi", "httpx", "jinja2",
    "openpyxl", "pydantic", "yaml", "rich", "typer", "uvicorn", "multipart",
]
for name in required:
    importlib.import_module(name)
import data_contract_monitor as dcm
expected_version = sys.argv[1]
expected_build = sys.argv[2]
if dcm.__version__ != expected_version:
    raise SystemExit(11)
if expected_build and dcm.__build_id__ != expected_build:
    raise SystemExit(12)
'''
    completed = subprocess.run(
        [str(python), "-c", code, version, build_id or ""],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    return completed.returncode == 0


def ensure_environment(root: Path, *, include_tests: bool, force: bool, log_path: Path) -> Path:
    compatible, reason = supported_interpreter()
    if not compatible:
        raise RuntimeError(reason)

    venv_dir = root / ".venv"
    python = venv_python(venv_dir)
    if force and venv_dir.exists():
        try:
            Path(sys.executable).resolve().relative_to(venv_dir.resolve())
        except ValueError:
            remove_tree(venv_dir, log_path)
        else:
            raise RuntimeError(
                "Repair must be launched with an external Python runtime; the active .venv cannot delete itself"
            )
    if python.exists():
        probe = subprocess.run(
            [
                str(python),
                "-c",
                "import struct,sys,sysconfig; v=sys.version_info[:2]; raise SystemExit(0 if (3,11)<=v<=(3,14) and struct.calcsize('P')==8 and not bool(sysconfig.get_config_var('Py_GIL_DISABLED')) else 1)",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if probe.returncode:
            remove_tree(venv_dir, log_path)

    if not python.exists():
        log(f"Creating project-local virtual environment with {sys.executable}", log_path)
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=False).create(venv_dir)
    if not python.is_file():
        raise RuntimeError(f"Virtual environment creation did not produce {python}")

    root.joinpath("state").mkdir(parents=True, exist_ok=True)
    wheel = resolve_release_wheel(root)
    lock_paths = [root / "requirements.lock", root / "pyproject.toml", wheel]
    if include_tests:
        lock_paths.append(root / "requirements-test.lock")
    missing = [str(path) for path in lock_paths if not path.is_file()]
    if missing:
        raise RuntimeError("Required installation files are missing: " + ", ".join(missing))

    expected = signature(lock_paths, interpreter=python)
    stamp = root / "state" / ("test_dependencies.sha256" if include_tests else "dependencies.sha256")
    current = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else ""
    version = read_version(root) or "unknown"
    build_id = read_build_id(root)

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_CACHE_DIR": str(root / "cache" / "pip"),
            "PIP_DEFAULT_TIMEOUT": "45",
            "TEMP": str(root / "temp"),
            "TMP": str(root / "temp"),
            "TMPDIR": str(root / "temp"),
            "DCM_HOME": str(root),
            "DCM_PROJECT_ROOT": str(root),
        }
    )

    if current == expected and environment_valid(python, version=version, build_id=build_id):
        log("Existing project-local environment passed import and release checks", log_path)
        return python

    stamp.unlink(missing_ok=True)
    pip_base = [
        str(python),
        "-m",
        "pip",
        "install",
        "--no-input",
        "--only-binary=:all:",
        "--prefer-binary",
        "--retries",
        "4",
        "--timeout",
        "45",
        "--progress-bar",
        "off",
    ]
    stream_command(
        [*pip_base, "--requirement", str(root / "requirements.lock")],
        root=root,
        env=env,
        log_path=log_path,
    )
    if include_tests:
        stream_command(
            [*pip_base, "--requirement", str(root / "requirements-test.lock")],
            root=root,
            env=env,
            log_path=log_path,
        )
    stream_command(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-input",
            "--no-deps",
            "--force-reinstall",
            str(wheel),
        ],
        root=root,
        env=env,
        log_path=log_path,
    )
    if not environment_valid(python, version=version, build_id=build_id):
        raise RuntimeError("Installed environment failed its import/version/build verification")

    stamp.write_text(expected + "\n", encoding="utf-8")
    runtime_state = {
        "schema_version": "1.0",
        "verified_at": datetime.now(UTC).isoformat(),
        "python_executable": redact(str(python)),
        "python_version": platform.python_version(),
        "architecture_bits": struct.calcsize("P") * 8,
        "application_version": version,
        "build_id": build_id,
        "dependency_signature": expected,
        "tests_included": include_tests,
        "wheel": wheel.relative_to(root).as_posix(),
    }
    atomic_json(root / "state" / "runtime_environment.json", runtime_state)
    log("Dependency and application installation verified", log_path)
    return python


def startup_capsule(root: Path, *, action: str, last_progress: str, exc: BaseException, log_path: Path) -> Path | None:
    try:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = root / "diagnostics" / "crash_capsules" / f"startup_abort_{timestamp}.json"
        payload = {
            "schema_version": "1.0",
            "project": "Data Contract Monitor",
            "created_at": datetime.now(UTC).isoformat(),
            "trigger": "logged-startup-abort",
            "severity": "critical",
            "action": action,
            "last_progress": last_progress,
            "version": read_version(root),
            "build_id": read_build_id(root),
            "exception_type": type(exc).__name__,
            "exception_message": redact(str(exc)),
            "traceback": redact("".join(traceback.format_exception(exc))[-20_000:]),
            "python": {
                "executable": redact(sys.executable),
                "version": platform.python_version(),
                "architecture_bits": struct.calcsize("P") * 8,
                "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
            },
            "log_path": redact(str(log_path)),
            "export_result": "capsule-written",
        }
        atomic_json(path, payload)
        return path
    except Exception:
        return None


def attempt_support_export(root: Path, log_path: Path) -> str | None:
    command = [sys.executable, str(root / "tools" / "support_export.py"), "--root", str(root)]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            check=False,
        )
        output = completed.stdout.strip()
        if output:
            log("Support export attempt: " + redact(output), log_path)
        return output or f"exit code {completed.returncode}"
    except Exception as export_exc:
        log("Support export attempt failed: " + redact(str(export_exc)), log_path)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Data Contract Monitor root-relative bootstrap")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--action", choices=["serve", "doctor", "test", "demo", "export"], default="serve")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = args.root.resolve()
    for relative in RUNTIME_DIRS:
        (root / relative).mkdir(parents=True, exist_ok=True)
    log_path = root / "logs" / "bootstrap.log"
    last_progress = "bootstrap-started"
    write_status(root, state="starting", action=args.action)
    try:
        compatible, reason = supported_interpreter()
        if not compatible:
            raise RuntimeError(reason)
        last_progress = "environment-preparation"
        python = ensure_environment(
            root,
            include_tests=args.action == "test",
            force=args.repair,
            log_path=log_path,
        )
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "TEMP": str(root / "temp"),
                "TMP": str(root / "temp"),
                "TMPDIR": str(root / "temp"),
                "DCM_HOME": str(root),
                "DCM_PROJECT_ROOT": str(root),
            }
        )
        if args.action == "serve":
            command = [str(python), "-m", "data_contract_monitor.cli", "serve", "--host", args.host, "--port", str(args.port)]
        elif args.action == "doctor":
            command = [str(python), "-m", "data_contract_monitor.cli", "doctor"]
        elif args.action == "test":
            command = [str(python), "-m", "pytest", str(root / "tests"), "--basetemp", str(root / "temp" / "pytest")]
        elif args.action == "demo":
            command = [str(python), "-m", "data_contract_monitor.cli", "demo", "--scenario", "bad"]
        else:
            command = [str(python), "-m", "data_contract_monitor.cli", "export-support"]
        last_progress = f"starting-{args.action}"
        write_status(
            root,
            state="running",
            action=args.action,
            details={"runtime_python": redact(str(python)), "log": redact(str(log_path))},
        )
        return_code = stream_command(command, root=root, env=env, log_path=log_path, check=False)
        if args.action == "demo" and return_code == 2:
            log("The intentionally invalid demo failed its contract as expected", log_path)
            write_status(root, state="completed", action=args.action, details={"result": "expected contract failure demonstrated"})
            return 0
        if return_code == 0:
            write_status(root, state="completed", action=args.action, details={"exit_code": 0})
        elif return_code == 130:
            write_status(root, state="stopped-by-user", action=args.action, details={"exit_code": 130})
        else:
            write_status(root, state="failed", action=args.action, details={"exit_code": return_code, "log": redact(str(log_path))})
        return return_code
    except KeyboardInterrupt as exc:
        details: dict[str, Any] = {"exit_code": 130, "reason": "user cancellation"}
        if isinstance(exc, CommandCancelled):
            details["forced_stop"] = exc.forced
            if args.action == "serve":
                finalize_cancelled_endpoint(root, exc.process_id)
        write_status(root, state="stopped-by-user", action=args.action, details=details)
        log("Stopped by user", log_path)
        return 130
    except Exception as exc:
        message = redact(str(exc))
        log("ERROR " + message, log_path)
        capsule = startup_capsule(root, action=args.action, last_progress=last_progress, exc=exc, log_path=log_path)
        export_result = attempt_support_export(root, log_path)
        write_status(
            root,
            state="startup-failed",
            action=args.action,
            details={
                "error": message,
                "last_progress": last_progress,
                "bootstrap_log": redact(str(log_path)),
                "crash_capsule": redact(str(capsule)) if capsule else "not created",
                "support_export": export_result or "not created",
            },
        )
        console_print(f"[ERROR] {message}", stream=sys.stderr)
        console_print(f"[ERROR] Review {root / 'LATEST_LAUNCH_STATUS.txt'}", stream=sys.stderr)
        console_print(f"[ERROR] Review {log_path}", stream=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
