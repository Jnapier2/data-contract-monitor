# Verification Report — Data Contract Monitor 0.2.2

**Build:** `DCM-0.2.2-B20260829-WINDOWS1`  
**Verification scope:** merged source, Windows regression suite, release pipeline, and fresh exact-artifact qualification.

The source regression suite contains 72 tests. Coverage includes contract loading, rule behavior, readers/profiling, drift/history, SQLite state, immutable run artifacts, resource limits, aggregate reconciliation, FastAPI local-session protection and asynchronous jobs, reporters, CLI behavior, release identity, diagnostics, occupied-port isolation, exact-service readiness, composite Action portability, bounded cancellation, legacy-console output, and Windows launcher structure.

Release preparation additionally enforces one expected BAT/CMD filename per action plus one shared BAT backend, strict CRLF on Windows BAT files, no unexpected exact source duplicates, Python byte-code compilation, schema regeneration, supply-chain regeneration, TypeScript compilation equivalence, wheel/version matching, managed-file hashing, release identity, ZIP path safety, uniqueness, and ZIP CRC integrity.

The exact final release receipt distributed beside the ZIP is the authority for the final ZIP SHA-256, ZIP size, manifest SHA-256, managed-file count, and wheel hash. Those values are intentionally not embedded here because changing this file would itself change the release hash.

## Environment and publication boundary

The release is built and regression-tested on Windows with CPython 3.12. The external release receipt records exact native launcher, integrity, demo, extracted-wheel, API, and test results. Norton, SmartScreen reputation, and Authenticode signing are separate checks; absence of a warning is not treated as publisher authentication. v0.1.5 remains the public rollback release, while v0.1.2 remains the user-confirmed deeper Windows launcher baseline.

## Security/privacy boundary

The application is local-first. Report evidence does not intentionally include raw cell values. Diagnostic exports redact common credential assignments, user-home paths, IP addresses, and latest-result filenames. Export20 is bounded to at most 20 items and uses project-local staging/finalization. Privacy-field detection remains heuristic rather than a legal or data-loss-prevention determination.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
