# Data Contract Monitor Benchmark Report

These measurements are local engineering evidence, not universal performance guarantees. They include dataset read/streaming, contract evaluation, aggregate profiling, privacy sampling, exact uniqueness enforcement, SHA-256 hashing, and result construction. Report serialization is excluded.

## 100,000-row in-memory benchmark

- Rows: 100,000
- Columns: 6
- CSV size: 9,588,957 bytes
- Execution mode: memory
- Trials: 3
- Median validation time: 0.553449 seconds
- Median throughput: 180,684.98 rows/second
- Profile mode: exact
- Median observed process peak RSS: 198,884 KiB

See `BENCHMARK_RESULTS.json` for the exact machine-readable evidence.

## 1,000,000-row streaming benchmark

- Rows: 1,000,000
- Columns: 6
- CSV size: 96,888,957 bytes
- Execution mode: streaming
- Batches: 20 × up to 50,000 rows
- Trial count: 1
- Validation time: 29.694255 seconds
- Throughput: 33,676.55 rows/second
- Profile mode: bounded
- Observed process peak RSS: 216,528 KiB
- Rule uniqueness exactness: exact, disk-backed

The bounded profile mode is intentional: validation rules remain exact, while high-cardinality profile distinct/duplicate counts may become lower bounds once the declared profile-cardinality memory budget is reached. This distinction is reported explicitly in validation output and is never silently represented as exact.

See `BENCHMARK_RESULTS_1M_STREAMING.json` for exact evidence.

## Interpretation

The in-memory path remains faster for modest datasets. The streaming path trades throughput for bounded working memory and exact disk-backed global rule enforcement, allowing substantially larger CSV/JSONL inputs without requiring the full dataset to reside in memory.

Peak RSS is process-level evidence from `resource.getrusage` on the exercised Linux environment and can include allocator high-water marks from setup and prior operations. It should not be interpreted as a cross-platform service-level guarantee.
