from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a repeatable synthetic Data Contract Monitor benchmark")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from data_contract_monitor.engine import validate_files

    now = datetime.now(UTC)
    frame = pd.DataFrame(
        {
            "order_id": [f"ORD-{index:07d}" for index in range(args.rows)],
            "customer_id": [f"CUS-{index:07d}" for index in range(args.rows)],
            "order_date": [now.isoformat()] * args.rows,
            "total_amount": [49.95] * args.rows,
            "status": ["paid"] * args.rows,
            "customer_email": [f"customer{index}@example.com" for index in range(args.rows)],
        }
    )
    durations: list[float] = []
    with tempfile.TemporaryDirectory(prefix="dcm_benchmark_", dir=root / "temp") as directory:
        data_path = Path(directory) / "customer_orders_100k.csv"
        frame.to_csv(data_path, index=False)
        size = data_path.stat().st_size
        for _ in range(args.trials):
            started = time.perf_counter()
            result = validate_files(
                contract_path=root / "examples" / "contracts" / "customer_orders.yml",
                data_path=data_path,
                record_history=False,
            )
            durations.append(time.perf_counter() - started)
            if not result.summary.passed:
                raise RuntimeError(f"Synthetic benchmark unexpectedly failed with {result.summary.findings_total} findings")
    payload = {
        "schema_version": "1.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "rows": args.rows,
        "columns": len(frame.columns),
        "csv_bytes": size,
        "trials": args.trials,
        "durations_seconds": [round(item, 6) for item in durations],
        "median_seconds": round(statistics.median(durations), 6),
        "rows_per_second_median": round(args.rows / statistics.median(durations), 2),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "not reported",
        "scope": "CSV read, aggregate profile, privacy sample, contract checks, SHA-256 hashes, and result construction; report serialization excluded.",
    }
    output = args.output or root / "BENCHMARK_RESULTS.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
