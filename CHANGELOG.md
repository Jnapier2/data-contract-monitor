# Changelog

## 0.1.5 — 2026-08-28

- Fixed invalid YAML in the reusable GitHub Action's input descriptions.
- Removed the Action's caller-dependent cache setup and installed its reviewed dependency lock before the application. This also avoids a setup-python cache-glob failure when a local Action path contains `/./`.
- Kept Action runtime output inside the caller's workspace.
- Added YAML parsing regressions and a real composite-Action CI job covering passing and intentionally failing datasets from a caller without its own Python lockfile.

The local validation engine and Windows startup behavior are unchanged. Version 0.1.4 remains available with its integration limitation documented; use v0.1.5 for new automation integrations.

## 0.1.4 — 2026-08-28

- Corrected the alpha security-support notice and documented a Unix launch command that does not depend on executable file permissions. The publication build is `DCM-0.1.4-B20260828-PUBLIC1`; the tested `SHUTDOWN2` package remains retained separately.

- Windows cancellation stops the launched process within a bounded cleanup budget and records stopped status instead of leaving the dashboard marked running.
- Delayed browser-readiness checks cannot overwrite stopped status; cancelled checks do not open a browser.
- Setup and runtime share one standard-library-only atomic status writer, including bounded handling of brief Windows file locks.
- Normal cancellation does not trigger critical crash exports. CLI error and cancellation exits no longer produce an unhandled wrapper exception.
- Added regression coverage for cancellation, bounded cleanup, ownership checks, late readiness, shared file writes, and CLI exit handling.

Native and exact-package results are recorded in the separate acceptance receipts. The prior v0.1.3 package remains available for comparison and rollback.

All notable changes are documented here. The project follows semantic versioning after the first public release.

## 0.1.3 — 2026-08-28

### Fixed

- Prevented legacy Windows terminal encodings from interrupting successful verification or demo commands.
- Removed redundant Windows wrapper writes to the status file already finalized by the bootstrap.
- Made dashboard status replacement resilient to brief Windows file locks, with bounded retries and independent temporary files; persistent failures keep the prior complete status.
- Kept wide results tables inside independently scrollable panels on narrow screens.
- Improved dark-theme status and skip-link readability.
- Pinned GitHub Actions dependencies to immutable commits and retained read-only workflow permissions.
- Corrected release finalization so generated schemas, dependency evidence, metadata, and the wheel are covered by the exact manifest before tests run.
- Corrected CI checks to compare only the JavaScript that the TypeScript build produces.
- Kept the dashboard available when a local TypeScript build contains JavaScript but no HTML or stylesheet.
- Made the integrity fixture portable across Windows and Unix line endings and excluded virtual-environment activation scripts from the first-party launcher inventory.
- Pinned the Windows terminal dependency and excluded dependency stores from release packaging.
- Kept build temporary files and caches within the project folder.
- Preserved the v0.1.2 rollback archive, Apache-2.0 license, stable Windows entrypoints, and synthetic demonstrations.

See `VERIFICATION_REPORT.md` for checks and platform limitations.

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
