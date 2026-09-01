from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    from tooling_common import atomic_json, sha256_file
except ModuleNotFoundError:
    from tools.tooling_common import atomic_json, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a hash-inventoried Windows x64 wheelhouse for offline Data Contract Monitor bootstrap."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--python-version", choices=("311", "312", "313", "314"), default="313")
    parser.add_argument("--include-tests", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    target_tag = f"cp{args.python_version}-win_amd64"
    destination = root / "packages" / "wheelhouse" / target_tag
    staging = root / "temp" / f"wheelhouse_{target_tag}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    requirement_files = [root / "requirements.lock"]
    if args.include_tests:
        requirement_files.append(root / "requirements-test.lock")
    for path in requirement_files:
        if not path.is_file():
            raise RuntimeError(f"Missing requirement file: {path}")

    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--only-binary=:all:",
        "--platform",
        "win_amd64",
        "--implementation",
        "cp",
        "--python-version",
        args.python_version,
        "--abi",
        f"cp{args.python_version}",
        "--dest",
        str(staging),
    ]
    for requirements in requirement_files:
        command.extend(["--requirement", str(requirements)])
    completed = subprocess.run(command, cwd=root, check=False)
    if completed.returncode:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError(
            "Windows wheelhouse download failed. No incomplete wheelhouse was promoted. "
            "Run again where package-index access is available."
        )

    wheels = sorted(staging.glob("*.whl"), key=lambda path: path.name.lower())
    if not wheels:
        raise RuntimeError("Wheelhouse download returned no wheels")
    manifest = {
        "schema_version": "1.0",
        "target": target_tag,
        "complete": True,
        "include_tests": bool(args.include_tests),
        "created_at": datetime.now(UTC).isoformat(),
        "requirements": [path.name for path in requirement_files],
        "files": [
            {"name": path.name, "sha256": sha256_file(path), "size": path.stat().st_size}
            for path in wheels
        ],
    }
    atomic_json(staging / "WHEELHOUSE_MANIFEST.json", manifest)
    shutil.rmtree(destination, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
