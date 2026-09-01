# Changelog

## 0.3.4 — 2026-09-01

- Validated artifact run identifiers before resolving report paths and retained an explicit containment check under the managed run directory.
- Replaced database exception details in the public health response with a stable, non-sensitive failure message.
- Added bounded retries for transient Windows file locks during atomic state replacement.
- Added regression coverage for noncanonical artifact identifiers.
- Preserved the v0.3.3 validation engine, Windows freshness controls, state schema, and release/rollback behavior.

## 0.3.3 — 2026-08-31

- Preserved v0.3.2 maintenance-preflight behavior proven by physical Windows startup evidence.
- Added exact-build browser launch URLs after health identity verification.
- Added no-store/no-cache headers for current root UI and static assets plus version-qualified CSS/JavaScript references.
- Confirmed current Data Contract Monitor UI has no `/demo-data.json` dependency; stale requests remain 404 for diagnosability.
- Narrowly filters only Windows Proactor `_call_connection_lost` `ConnectionResetError` WinError/errno 10054 callbacks; unrelated asyncio errors remain visible.
- Added regression coverage for browser freshness and narrow transport-noise matching.

## 0.3.2 — 2026-08-31

- Added bounded pre-release maintenance reconciliation for recognized stale prior-version application wheels.
- Repair and normal launch can now recover from a stale `packages/data_contract_monitor-*.whl` overlay without weakening the strict release gate.
- Stale wheels are moved to project-local `backups/retired_packages/` with SHA-256 receipts; no automatic deletion is performed.
- Support export deliberately bypasses the strict gate and selects external Python so a broken project virtual environment cannot block diagnostics.
- Preserved v0.3.1 Windows atomic-write durability repair and all v0.3.0 Scalable Assurance capabilities.

## 0.3.1 — 2026-08-31

- Fixed Windows startup failure in `tools/tooling_common.atomic_text`: temporary files are now opened writable, flushed, and `fsync`ed before close and atomic replacement.
- Added a regression test that fails if the tooling helper attempts durability sync through a read-only descriptor.
- Hardened `tools/release_gate.py` so receipt/capsule write failures fail closed with concise diagnostics instead of escaping as an unhandled traceback.
- Preserved all v0.3.0 scalable-assurance validation, streaming, contract-governance, reporting, and Export20 behavior.

## 0.3.0 — 2026-08-31

### Added
- Bounded CSV/JSONL/NDJSON streaming with exact disk-backed global uniqueness and referential-integrity checks.
- Reader plugin registry, contract lint/normalize/diff, stable contract identity/version history, run comparison/trends, and artifact inventory.
- SQLite state schema v3 with migration backup/integrity receipts.
- Contract-declared reference uploads in the local dashboard/API.
- Target-specific Windows wheelhouse builder and verified offline-bootstrap consumption when a wheelhouse is present.
- Expanded CI matrix and CodeQL workflow definitions.

### Changed
- Total dataset budget increased to 250 MB while non-streamable/in-memory input remains capped at 50 MB.
- Streaming high-cardinality profile counts are explicitly labeled as bounded lower bounds; enforcement remains exact.
- Validation result schema is 1.3 and carries execution/exactness plus stable contract ID/version.

### Fixed
- Durable contract history now records the true contract version instead of the contract filename.
- API reference-file staging preserves declared safe relative layouts inside the isolated job workspace.
- Excel inspection and SQLite verification paths close file/database handles deterministically.

All notable changes are documented here. The project follows semantic versioning after the first public release.

## 0.2.2 — 2026-08-31

- Reconciled the August 31 Windows support export: canonical v0.2.1 identity files matched exactly while cached runtime/endpoint state still identified v0.1.2.
- Added standard-library deployment-coherence reporting to support and Critical diagnostics without managed-file rehashing during export.
- Added project-local backup/retirement for known stale generated runtime identity before normal environment preparation.
- Added protected execution namespace checks for unlisted BAT/CMD/PowerShell files, package files, and application wheels.
- Added case-collision protection to release manifest validation.
- Added `backups/` to launcher runtime directories and preserved unknown/user files outside protected namespaces.
- Expanded automated coverage for stale-state reconciliation, overlay safety, support evidence semantics, and user-file preservation.

## 0.2.1 — 2026-08-29

- Rebased the durable-foundation work on the exact v0.1.2 Windows-confirmed rollback authority; the blocked v0.2.0 delivery is not used as a release baseline.
- Added transactional SQLite run/job state, versioned migration backup, immutable per-run artifacts, bounded background validation jobs, progress/cancellation, resource budgets, compiled rule planning, and aggregate reconciliation.
- Added per-launch local API session protection and strict loopback Origin parsing for modifying requests.
- Consolidated six root BATs into logic-free action forwarders backed by one active `tools/launch.bat` implementation.
- Consolidated application atomic/hash helpers and pre-install tooling helpers within their required execution boundaries.
- Added full retained-file indexing and release-time rejection of unexpected BAT/CMD files or unapproved exact duplicates.
- Moved Export20 temporary ZIP staging to project `temp/` while preserving root `exports/` as the only final ZIP destination.
- Removed stale runtime residue, empty package placeholders, and the stale v0.1.2 wheel from source preparation.
- Updated release identity metadata to Gateway shared defaults v2.17.13.

## 0.1.2 — 2026-08-28

### Fixed

- Prevented the browser from opening an unrelated loopback application when port 8765 is already occupied.
- Reserved the selected socket before server startup and handed that socket directly to Uvicorn, removing the prior check-and-bind race.
- Required exact service, version, build, and per-launch health identity before opening the browser.
- Disabled proxy use and redirects for local launcher health verification.
- Consolidated manual support and automatic Critical ZIPs into the root `exports/` directory.
- Removed runtime creation of `diagnostics/exports/`; diagnostics now retains only capsules and diagnostic state.
- Added launcher, bootstrap, Python-detection, endpoint, and launch-status evidence to the bounded support package.
- Prevented inherited `PYTHONPATH` and `PYTHONHOME` values from redirecting Windows startup.
- Restricted export retention to recognized generated filenames so unknown and user-owned ZIPs are preserved.

### Added

- Bounded fallback-port selection through `8785`, followed by an operating-system-assigned loopback port when needed.
- Persistent selected-endpoint evidence in `state/dashboard_endpoint.json` and `LATEST_LAUNCH_STATUS.txt`.
- Automated occupied-port, exact-port, wrong-service, wrong-version/build/launch-ID, canonical-export, evidence-redaction, and unknown-file-retention tests.
- A launcher repair report documenting the v0.1.1 support-export findings and v0.1.2 recovery boundary.

## 0.1.1 — 2026-08-28

### Fixed

- Replaced the shared Windows bootstrap used by all BAT entrypoints.
- Corrected Python 3.14 dependency compatibility by updating pandas from 2.2.3 to 2.3.3.
- Preferred Python 3.13 while retaining standard 64-bit Python 3.11–3.14 support.
- Installed the included application wheel rather than an editable checkout.
- Preserved visible installer output and persistent startup evidence.
- Added unextracted-ZIP detection and visible failure pauses.
- Corrected support-export return-code handling.
- Normalized BAT files to CRLF and added automated launch-contract tests.

### Added

- `LATEST_LAUNCH_STATUS.txt` and JSON startup state.
- Python discovery diagnostics.
- Atomic startup-abort crash capsules and bounded support-export attempts.
- Windows startup troubleshooting guide.

## 0.1.0 — 2026-08-28

### Added

- Strict native YAML data contracts
- Partial Open Data Contract Standard v3.1 adapter
- CSV, Excel, JSON, JSON Lines, and optional Parquet readers
- Column and dataset-level quality rules
- Aggregate profiling and heuristic privacy-field signals
- Schema baselines and drift findings
- HTML, JSON, JUnit XML, and SARIF 2.1.0 reports
- CLI, Python API, FastAPI service, TypeScript dashboard, and composite GitHub Action
- Credential-free passing and failing demos
- Windows root-relative launcher and idempotent environment repair
- Release identity verification with managed-file SHA-256 checks
- Bounded redacted Critical diagnostics and manual Export20 support package
- Automated test suite and reviewer documentation
