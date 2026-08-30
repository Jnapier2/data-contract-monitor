# Changelog

All notable changes are documented here. The project follows semantic versioning after the first public release.

## 0.2.2 — 2026-08-29

- Repaired Windows atomic status writes and made temporary-file replacement resilient to brief antivirus and file-indexing locks.
- Restored bounded Ctrl+C handling so cancellation stops only the launched child process, records a clean stopped state, and does not create a Critical export.
- Restored legacy Windows console fallback so Unicode progress output remains visible without corrupting UTF-8 logs.
- Restored the caller-independent composite Action installation path and pinned the setup action by commit.
- Corrected cross-platform newline accounting and release-inventory exclusions discovered during native Windows qualification.
- Expanded the merged regression suite from 49 to 72 tests, including public Action, shutdown, launcher, and release-inventory safeguards.

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
