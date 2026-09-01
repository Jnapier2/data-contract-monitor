# Known limitations

1. Streaming execution currently applies to CSV, JSONL, and NDJSON. Excel, JSON arrays/objects, and optional Parquet use bounded in-memory execution and are subject to the stricter in-memory byte cap.
2. High-cardinality profile distinct/duplicate statistics may become bounded lower bounds. Exactness flags make this explicit; validation uniqueness rules remain exact.
3. Streaming exact global rules use a temporary SQLite hash index and therefore trade disk I/O for bounded memory. Free-disk checks apply before validation but cannot guarantee another process will not consume disk during a run.
4. Runtime timeout checks are cooperative between validation stages/batches; validation is not yet isolated in a killable worker process.
5. Observed logical types are heuristic for mixed object columns.
6. Freshness rules are wall-clock relative, so old fixtures may require regeneration.
7. Privacy detection is advisory and sampled on streaming/high-volume inputs. It can miss or misclassify fields and is not a legal classification or data-loss-prevention system.
8. ODCS support is a documented subset, not complete Open Data Contract Standard implementation coverage.
9. The loopback dashboard uses per-launch local session protection but is not a multi-user authentication/authorization/tenancy system and should not be exposed publicly as-is. The supplied container is a packaging surface, not a hardened public service profile.
10. Validation cancellation is cooperative. A future isolated worker-process profile would provide a harder boundary for hostile workloads or native-library stalls.
11. Parquet support is optional and depends on a compatible `pyarrow` installation.
12. The reader plugin entry-point API is intentionally narrow and pre-stable in v0.3.4; third-party readers remain responsible for obeying resource/security contracts.
13. A project-local Windows wheelhouse can be generated and verified, but no complete wheelhouse is bundled in this release because the build environment lacked package-index network access. A supported Python runtime is still required.
14. Accessibility review is internal; no third-party WCAG certification is claimed.
15. Release artifacts use SHA-256 integrity evidence but are not Authenticode-signed in this build.
16. Windows `cmd.exe`, Norton, SmartScreen, hosted GitHub Actions/CodeQL, signing, and actual Windows offline-wheelhouse bootstrap are exact-artifact qualification steps that cannot be substituted by the Linux build environment.
17. Cloud warehouse/object-store connectors, dbt/OpenLineage emitters, organization-level roles, and AI-assisted contract authoring are not included in v0.3.4; the reader/plugin and contract lifecycle boundaries are intended to support later additions without coupling them to the core validator.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
