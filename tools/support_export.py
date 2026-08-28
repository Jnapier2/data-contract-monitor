from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a bounded Data Contract Monitor support export")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / "src"))
    try:
        from data_contract_monitor.diagnostics import DiagnosticManager

        path = DiagnosticManager(root).create_manual_export()
    except Exception as exc:
        print(f"[ERROR] Support export failed: {exc}", file=sys.stderr)
        return 4
    if path is None:
        print("[ERROR] Support export could not be created.", file=sys.stderr)
        return 4
    print(f"[OK] Support export created: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
