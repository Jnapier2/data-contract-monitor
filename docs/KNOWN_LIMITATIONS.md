# Known Limitations

1. **File-oriented first release.** The engine validates files loaded into memory. Direct warehouse, object-storage, and streaming connectors are not included.
2. **Memory bound.** pandas must materialize the dataset. The FastAPI upload limit is 50 MB by default, but memory use can exceed file size.
3. **Heuristic observed types.** Mixed object columns may be classified as strings even when some values are numeric or datetime-like.
4. **Freshness is wall-clock relative.** Replaying old fixtures can fail a freshness rule unless the data is regenerated or the rule is adjusted.
5. **Privacy detection is advisory.** It samples up to 200 values per column and can miss or misclassify fields.
6. **ODCS support is partial.** One schema object and selected quality fields are adapted. Unmapped fields are documented, not silently enforced.
7. **No multi-user security.** The local dashboard has no authentication, authorization, tenancy, or public-service hardening.
8. **No automatic remediation.** The tool identifies failures but never edits source data, changes a contract, or approves drift.
9. **No distributed execution.** Validation runs in one process and does not partition large files across workers.
10. **Windows launcher requires Python and first-run package access.** The ZIP is not a standalone native executable. It accepts standard non-free-threaded 64-bit CPython 3.11–3.14 and requests binary wheels only; a blocked package index can prevent the first environment build.
11. **Parquet is optional.** It requires the `parquet` extra and a compatible `pyarrow` installation.
12. **Accessibility review is internal.** No formal third-party WCAG certification has been completed.
13. **Release artifacts are unsigned.** SHA-256 receipts support integrity checking but do not replace code signing or a trusted publication channel.

These limits are intentionally explicit so a reviewer can distinguish implemented behavior from a roadmap claim.
