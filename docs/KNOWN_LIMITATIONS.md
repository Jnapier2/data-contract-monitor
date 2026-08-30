# Known Limitations

1. The execution engine is still file-oriented and pandas-backed; CSV/JSONL streaming and disk-backed global rules are architecture targets, not claimed capabilities in 0.2.2.
2. The default dataset budget is 50 MB and pandas can use substantially more memory than the compressed/on-disk file size.
3. Runtime timeout checks are cooperative between validation phases; they do not forcibly interrupt a single long-running pandas operation.
4. Observed logical types are heuristic for mixed object columns.
5. Freshness rules are wall-clock relative, so old fixtures may require regeneration.
6. Privacy detection is advisory and sample-based. It can miss or misclassify fields and is not a legal classification or DLP system.
7. ODCS support is a documented subset, not complete ODCS implementation coverage.
8. The loopback dashboard uses a per-launch local session token but is not a multi-user authentication/authorization/tenancy system and should not be exposed publicly as-is.
9. Validation cancellation is cooperative. A future isolated worker-process profile would provide a harder execution boundary for hostile or very large workloads.
10. The Windows ZIP still requires a supported Python runtime and can require first-run access to the configured package index. A self-contained offline runtime is not yet shipped.
11. Parquet support is optional and depends on a compatible `pyarrow` installation.
12. Accessibility review is internal; no third-party WCAG certification is claimed.
13. Release artifacts use SHA-256 integrity evidence but are not Authenticode-signed in this build.
14. Windows `cmd.exe`, Norton, SmartScreen, and signing are exact-artifact qualification steps that must be performed on Windows; the Linux build environment cannot substitute for them.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
