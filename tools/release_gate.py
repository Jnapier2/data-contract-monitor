from __future__ import annotations

import argparse
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

try:
    from tooling_common import atomic_json
except ModuleNotFoundError:  # imported as tools.* during tests
    from tools.tooling_common import atomic_json


def _capsule(root: Path, errors: list[str], exc: BaseException | None = None) -> None:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "project": "Data Contract Monitor",
        "created_at": datetime.now(UTC).isoformat(),
        "trigger": "runtime-identity-failure",
        "severity": "critical",
        "errors": errors,
        "exception": str(exc) if exc else None,
        "traceback": "".join(traceback.format_exception(exc))[-10000:] if exc else None,
        "export_result": "minimal-crash-capsule",
    }
    atomic_json(root / "diagnostics" / "crash_capsules" / f"identity_failure_{timestamp}.json", payload)


def _write_receipt(root: Path, result: dict[str, object]) -> None:
    payload = {
        "schema_version": "1.0",
        "verified_at": datetime.now(UTC).isoformat(),
        "mode": result.get("mode"),
        "passed": bool(result.get("passed")),
        "version": result.get("version"),
        "build_id": result.get("build_id"),
        "checked_files": int(result.get("checked_files", 0) or 0),
        "errors": [str(item) for item in result.get("errors", [])],
    }
    atomic_json(root / "state" / "release_verification.json", payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / "src"))
    try:
        from data_contract_monitor.release_identity import verify_release

        result = verify_release(root)
        _write_receipt(root, result)
    except Exception as exc:
        try:
            _capsule(root, ["Release verifier or receipt publication crashed"], exc)
        except Exception as capsule_exc:
            print(f"[ERROR] Critical capsule could not be written: {capsule_exc}", file=sys.stderr)
        print(f"[ERROR] Release verification crashed: {exc}", file=sys.stderr)
        return 4
    if not result["passed"]:
        errors = [str(item) for item in result.get("errors", [])]
        _capsule(root, errors)
        print("[ERROR] Release integrity verification failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 4
    print(f"[OK] Release identity: {result['mode']} {result.get('version') or ''} ({result.get('checked_files', 0)} managed files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
