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


def _write_data(path: Path, rows: int) -> None:
    now = datetime.now(UTC).isoformat()
    first = True
    chunk_size = 100_000
    for start in range(0, rows, chunk_size):
        count = min(chunk_size, rows - start)
        indexes = range(start, start + count)
        frame = pd.DataFrame(
            {
                "order_id": [f"ORD-{index:08d}" for index in indexes],
                "customer_id": [f"CUS-{index:08d}" for index in indexes],
                "order_date": [now] * count,
                "total_amount": [49.95] * count,
                "status": ["paid"] * count,
                "customer_email": [f"customer{index}@example.com" for index in indexes],
            }
        )
        frame.to_csv(path, index=False, mode="w" if first else "a", header=first)
        first = False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a repeatable synthetic Data Contract Monitor benchmark")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--execution-mode", choices=["auto", "memory", "streaming"], default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from data_contract_monitor.engine import validate_files
    from data_contract_monitor.limits import ResourceLimits

    durations: list[float] = []
    peak_rss_kib: list[int] = []
    observed_mode = None
    batches = None
    profile_mode = None
    with tempfile.TemporaryDirectory(prefix="dcm_benchmark_", dir=root / "temp") as directory:
        data_path = Path(directory) / f"customer_orders_{args.rows}.csv"
        _write_data(data_path, args.rows)
        size = data_path.stat().st_size
        limits = ResourceLimits(max_data_bytes=max(50 * 1024 * 1024, size + 1024 * 1024))
        for _ in range(args.trials):
            try:
                import resource
                before_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            except ImportError:
                before_rss = 0
            started = time.perf_counter()
            result = validate_files(
                contract_path=root / "examples" / "contracts" / "customer_orders.yml",
                data_path=data_path,
                record_history=False,
                execution_mode=args.execution_mode,
                limits=limits,
            )
            durations.append(time.perf_counter() - started)
            try:
                import resource
                after_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            except ImportError:
                after_rss = 0
            peak_rss_kib.append(max(before_rss, after_rss))
            observed_mode = result.execution_mode
            batches = result.batches
            profile_mode = result.profile.profiling_mode
            if not result.summary.passed:
                raise RuntimeError(
                    f"Synthetic benchmark unexpectedly failed with {result.summary.findings_total} findings"
                )
    median = statistics.median(durations)
    payload = {
        "schema_version": "2.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "rows": args.rows,
        "columns": 6,
        "csv_bytes": size,
        "trials": args.trials,
        "requested_execution_mode": args.execution_mode,
        "observed_execution_mode": observed_mode,
        "batches": batches,
        "profile_mode": profile_mode,
        "durations_seconds": [round(item, 6) for item in durations],
        "median_seconds": round(median, 6),
        "rows_per_second_median": round(args.rows / median, 2),
        "peak_process_rss_kib": peak_rss_kib,
        "median_peak_process_rss_kib": int(statistics.median(peak_rss_kib)) if peak_rss_kib else None,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "not reported",
        "scope": (
            "CSV read/stream, aggregate profile, bounded privacy sampling, contract checks, "
            "exact disk-backed uniqueness when streaming, SHA-256 hashes, and result construction; "
            "report serialization excluded. Peak RSS is process-level on platforms that expose resource.getrusage."
        ),
    }
    output = args.output or root / "BENCHMARK_RESULTS.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
