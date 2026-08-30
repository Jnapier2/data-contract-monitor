# Benchmark Report

## Result

A repeatable synthetic run validated **100,000 rows across six columns** in a median of **0.474686 seconds**, equivalent to **210,665.54 rows per second** on the exercised environment.

| Measure | Verified value |
|---|---:|
| Rows | 100,000 |
| Columns | 6 |
| CSV size | 9,388,957 bytes |
| Trials | 3 |
| Trial durations | 0.474686 s, 0.470189 s, 0.496843 s |
| Median | 0.474686 s |
| Median throughput | 210,665.54 rows/s |
| Python | 3.13.5 |
| Operating system | Linux 6.18.35 x86_64, glibc 2.41 |

The benchmark scope includes CSV parsing, aggregate profiling, the bounded privacy sample, contract checks, SHA-256 calculation, and result construction. It excludes report serialization and dashboard rendering.

## Method

The script `tools/benchmark.py` generates current, conforming customer-order data in a project-local temporary directory. Every trial invokes the same public `validate_files` engine used by the command line, API, dashboard, and GitHub Action. A trial is rejected if the generated dataset produces any finding.

Reproduce it from a prepared environment:

```bash
python tools/benchmark.py --rows 100000 --trials 3 --output BENCHMARK_RESULTS.json
```

The machine-readable evidence is [BENCHMARK_RESULTS.json](BENCHMARK_RESULTS.json).

## Interpretation

This is one bounded local measurement, not a universal performance claim. Results will vary with storage, processor, Python and pandas versions, data types, rule complexity, privacy signals, and file format. The first release loads the full dataset into memory and is intended for file-oriented validation rather than distributed or streaming workloads.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
