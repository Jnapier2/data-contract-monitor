from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

try:
    from tooling_common import atomic_text, sha256_file
except ModuleNotFoundError:  # imported as tools.* during tests
    from tools.tooling_common import atomic_text, sha256_file


EXCLUDED_ROOTS = {
    ".git",
    ".github-cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "backups",
    "build",
    "cache",
    "diagnostics",
    "dist",
    "downloads",
    "exports",
    "logs",
    "node_modules",
    "pnpm-store",
    "reports",
    "state",
    "temp",
}
EXCLUDED_NAMES = {
    ".coverage",
    "LATEST_LAUNCH_STATUS.txt",
    "PACKAGE_METADATA.json.tmp",
    "MANIFEST.json.tmp",
    "MANIFEST.sha256.tmp",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp"}
IDENTITY_FILES = {"MANIFEST.json", "MANIFEST.sha256"}
ROOT_BATCH_ACTIONS = {
    "START_DATA_CONTRACT_MONITOR.bat": "serve",
    "VERIFY_RELEASE.bat": "doctor",
    "RUN_DEMO.bat": "demo",
    "RUN_TESTS.bat": "test",
    "REPAIR_INSTALLATION.bat": "repair",
    "CREATE_SUPPORT_EXPORT.bat": "export",
}


def should_include(root: Path, path: Path) -> bool:
    relative = path.relative_to(root)
    if not path.is_file() or path.name in IDENTITY_FILES or path.name in EXCLUDED_NAMES:
        return False
    if any(part in EXCLUDED_ROOTS or part == "__pycache__" or part.endswith(".egg-info") for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return True


def collect_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if should_include(root, path)),
        key=lambda path: path.relative_to(root).as_posix().lower(),
    )


def run(command: list[str], root: Path, *, extra_env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    environment = os.environ.copy()
    if extra_env:
        environment.update(extra_env)
    completed = subprocess.run(command, cwd=root, env=environment, check=False)
    if completed.returncode:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def create_zip(root: Path, files: Iterable[Path], output: Path, *, prefix: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if not prefix or "/" in prefix or "\\" in prefix or prefix in {".", ".."}:
        raise RuntimeError(f"Unsafe release ZIP root: {prefix!r}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=f"{prefix}/{path.relative_to(root).as_posix()}")
    with zipfile.ZipFile(temporary, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP integrity test failed at {bad}")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("ZIP contains duplicate archive paths")
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise RuntimeError("ZIP contains an unsafe archive path")
    os.replace(temporary, output)


def _assert_crlf(path: Path) -> None:
    payload = path.read_bytes()
    if b"\r\n" not in payload or b"\n" in payload.replace(b"\r\n", b""):
        raise RuntimeError(f"Windows launcher is not strict CRLF: {path}")
    if b"\x00" in payload:
        raise RuntimeError(f"Windows launcher contains a NUL byte: {path}")


def validate_windows_launchers(root: Path) -> None:
    batch_files = sorted(path for path in collect_files(root) if path.suffix.casefold() == ".bat")
    expected_names = {*ROOT_BATCH_ACTIONS, "launch.bat"}
    found_names = {path.name for path in batch_files}
    if found_names != expected_names or len(batch_files) != len(expected_names):
        raise RuntimeError(
            f"Unexpected BAT inventory. Expected {sorted(expected_names)}, found {[p.relative_to(root).as_posix() for p in batch_files]}"
        )
    for name, action in ROOT_BATCH_ACTIONS.items():
        path = root / name
        _assert_crlf(path)
        text = path.read_text(encoding="ascii")
        expected_lines = [
            "@echo off",
            f'call "%~dp0tools\\launch.bat" {action}',
            "exit /b %ERRORLEVEL%",
        ]
        if text.splitlines() != expected_lines:
            raise RuntimeError(f"{name} must remain a logic-free forwarder to tools/launch.bat")
        if any(value in text for value in ("%CD%", "Desktop", "Downloads", "bootstrap.py", "release_gate.py")):
            raise RuntimeError(f"{name} contains non-forwarder or unstable path logic")
    launch = root / "tools" / "launch.bat"
    _assert_crlf(launch)
    text = launch.read_text(encoding="ascii")
    required = [
        'for %%I in ("%~dp0..") do set "ROOT=%%~fI"',
        "tools\\bootstrap.py",
        "tools\\release_gate.py",
        "tools\\support_export.py",
        "LATEST_LAUNCH_STATUS.txt",
        "logs\\launcher.log",
        "logs\\python_detection.txt",
        'set "PYTHONPATH="',
        'set "PYTHONHOME="',
        ':probe_python',
        "Py_GIL_DISABLED",
        "struct.calcsize('P') == 8",
    ]
    missing = [value for value in required if value not in text]
    if missing:
        raise RuntimeError(f"tools/launch.bat is missing launch contract elements: {missing}")
    if text.index("call :probe_python py -3.13") > text.index("call :probe_python py -3.14"):
        raise RuntimeError("Python 3.13 must be preferred before Python 3.14")
    for version in ("3.11", "3.12", "3.13", "3.14"):
        if f"py -{version}" not in text:
            raise RuntimeError(f"tools/launch.bat does not probe Python {version}")
    if any(value in text for value in ("%CD%", "Desktop", "Downloads")):
        raise RuntimeError("tools/launch.bat contains an unstable external path")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a release-mode Data Contract Monitor ZIP")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--build-id")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--reuse-wheel", action="store_true", help="Use the single existing wheel in packages/")
    args = parser.parse_args()
    root = args.source_root.resolve()
    output_dir = args.output_dir.resolve()
    version = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError("VERSION.txt is empty")
    if args.build_id:
        build_id = args.build_id
    else:
        try:
            current_build = json.loads(
                (root / "src" / "data_contract_monitor" / "build_info.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            current_build = {}
        build_id = (
            str(current_build.get("build_id"))
            if current_build.get("version") == version and current_build.get("build_id")
            else f"DCM-{version}-B20260829-RELEASE1"
        )

    build_info = {"version": version, "build_id": build_id}
    atomic_text(
        root / "src" / "data_contract_monitor" / "build_info.json",
        json.dumps(build_info, indent=2, sort_keys=True) + "\n",
    )
    atomic_text(root / "RELEASE_MODE", "release\n")

    validate_windows_launchers(root)
    run([sys.executable, "tools/project_index.py", "--root", str(root), "--check-only"], root)
    run([sys.executable, "tools/generate_schemas.py"], root)
    run([sys.executable, "tools/generate_supply_chain.py"], root)
    run([sys.executable, "-m", "compileall", "-q", "src", "tools", "tests"], root)
    if not args.skip_tests:
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        source_pythonpath = str(root / "src")
        if existing_pythonpath:
            source_pythonpath += os.pathsep + existing_pythonpath
        run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--basetemp",
                str(root / "temp" / "pytest-release"),
            ],
            root,
            extra_env={"PYTHONPATH": source_pythonpath},
        )

    packages = root / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    if not args.reuse_wheel:
        for prior in packages.glob("data_contract_monitor-*.whl"):
            prior.unlink()
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                ".",
                "--wheel-dir",
                str(packages),
            ],
            root,
        )
    wheels = sorted(packages.glob("data_contract_monitor-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one wheel, found {len(wheels)}")
    wheel = wheels[0]
    expected_wheel_prefix = f"data_contract_monitor-{version.replace('-', '_')}-"
    if not wheel.name.startswith(expected_wheel_prefix):
        raise RuntimeError(f"Wheel filename does not match version {version}: {wheel.name}")

    metadata = {
        "schema_version": "1.2",
        "project": "Data Contract Monitor",
        "display_name": "Data Contract Monitor",
        "package_name": "data-contract-monitor",
        "version": version,
        "build_id": build_id,
        "release_date": "2026-08-29",
        "release_channel": "portfolio-alpha",
        "license": "Apache-2.0",
        "publisher": "Gateway Information Group LLC",
        "copyright": "Copyright © 2026 Gateway Information Group LLC. All rights reserved.",
        "stable_entrypoint": "START_DATA_CONTRACT_MONITOR.bat",
        "minimum_python": "3.11",
        "maximum_python": "3.14",
        "python_runtime_policy": "standard non-free-threaded 64-bit CPython; 3.13 preferred on Windows",
        "dependency_install_policy": "locked binary wheels only for Windows bootstrap",
        "lineage": {
            "source_authority": "v0.2.1 durable foundation merged with v0.1.5 public Action and Windows lifecycle safeguards",
            "rollback_release_sha256": "1bc3294daca89911a5029c2bb0a49a1764463fe5d20c572d7261830115a2b1ee",
            "blocked_intermediate": "v0.2.0 and v0.2.1 artifacts were not promoted; v0.2.2 repairs the Windows qualification failures",
        },
        "canonical_export_directory": "exports",
        "dashboard_port_policy": "reserve preferred port 8765; bounded fallback through 8785; OS-assigned loopback fallback if the bounded range is full; browser opens only after exact service/version/build/per-launch health identity",
        "windows_launcher_verification": "CRLF, automated static launch-contract verification, local port-collision isolation, and exact-service browser-readiness tests; cmd.exe execution pending",
        "execution_qualified_environment": f"{sys.platform}; CPython {sys.version.split()[0]}",
        "tested_windows_computers": [],
        "execution_namespace": "DataContractMonitor",
        "runtime_output_roots": ["config", "logs", "state", "temp", "cache", "exports", "diagnostics", "reports", "downloads", "backups"],
        "one_active_launcher_policy": "six stable logic-free action BATs -> one active BAT backend tools/launch.bat; unexpected BAT/CMD return fails release preparation",
        "action_map": {
            name: {"action": action, "forwarder": name, "bat_backend": "tools/launch.bat"}
            for name, action in ROOT_BATCH_ACTIONS.items()
        },
        "approved_exact_duplicate_exceptions": [
            {
                "paths": ["examples/contracts/customer_orders.yml", "src/data_contract_monitor/resources/contracts/customer_orders.yml"],
                "reason": "human-readable source example plus isolated installed-wheel resource",
            }
        ],
        "wheel": {
            "path": wheel.relative_to(root).as_posix(),
            "sha256": sha256_file(wheel),
            "size": wheel.stat().st_size,
        },
        "managed_file_count": 0,
    }
    metadata_path = root / "PACKAGE_METADATA.json"
    atomic_text(metadata_path, json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    count = len(collect_files(root))
    metadata["managed_file_count"] = count
    atomic_text(metadata_path, json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    managed_paths = collect_files(root)
    if len(managed_paths) != count:
        raise RuntimeError("Managed-file count changed while finalizing metadata")
    manifest = {
        "schema_version": "1.2",
        "project": "Data Contract Monitor",
        "version": version,
        "build_id": build_id,
        "created_at": datetime.now(UTC).isoformat(),
        "hash_algorithm": "SHA-256",
        "managed_file_count": len(managed_paths),
        "managed_files": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
            for path in managed_paths
        ],
    }
    manifest_path = root / "MANIFEST.json"
    atomic_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    manifest_hash = sha256_file(manifest_path)
    atomic_text(root / "MANIFEST.sha256", f"{manifest_hash}  MANIFEST.json\n")

    sys.path.insert(0, str(root / "src"))
    from data_contract_monitor.release_identity import verify_release

    verification = verify_release(root)
    if not verification["passed"]:
        raise RuntimeError("Release identity failed: " + "; ".join(verification["errors"]))

    release_name = f"Data_Contract_Monitor_v{version}_Portfolio_Release.zip"
    output = output_dir / release_name
    archive_files = [*managed_paths, manifest_path, root / "MANIFEST.sha256"]
    create_zip(
        root,
        archive_files,
        output,
        prefix=f"Data_Contract_Monitor_v{version}",
    )
    zip_hash = sha256_file(output)
    atomic_text(output.with_suffix(output.suffix + ".sha256.txt"), f"{zip_hash}  {output.name}\n")
    receipt = {
        "schema_version": "1.2",
        "project": "Data Contract Monitor",
        "version": version,
        "build_id": build_id,
        "created_at": datetime.now(UTC).isoformat(),
        "release_zip": output.name,
        "release_zip_sha256": zip_hash,
        "release_zip_size": output.stat().st_size,
        "managed_file_count": len(managed_paths),
        "manifest_sha256": manifest_hash,
        "wheel": metadata["wheel"],
        "release_identity": verification,
        "zip_integrity": "passed",
        "windows_batch_contract": "passed-static",
        "local_port_collision_isolation": "passed",
        "canonical_export_directory": "exports",
        "windows_cmd_execution": "pending exact-artifact qualification after finalization",
    }
    receipt_name = f"Data_Contract_Monitor_v{version}_Verification_Receipt.json"
    atomic_text(output_dir / receipt_name, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"Built {output}")
    print(f"SHA-256 {zip_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
