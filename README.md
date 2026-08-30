# Data Contract Monitor

**Executable data contracts with durable evidence for files, local review, and CI.**

Data Contract Monitor validates CSV, Excel, JSON, JSON Lines, and optional Parquet datasets against readable YAML contracts. It produces accessible HTML plus JSON, JUnit XML, and SARIF evidence, records durable run history, detects schema drift and privacy-field signals, and gives CI a clear distinction between “the data failed its contract” and “the program failed.”

The project is local-first and includes generated passing/failing demonstrations that require no credentials or private data.

![Data Contract Monitor dashboard](docs/assets/dashboard.png)

## Windows quick start

Extract the complete ZIP first; do not run a BAT from Windows compressed-folder preview. Open the extracted `Data_Contract_Monitor_v0.2.2` folder and double-click:

```text
START_DATA_CONTRACT_MONITOR.bat
```

All six root BAT files are stable, logic-free action forwarders. `tools\launch.bat` is the single Windows BAT implementation backend. It derives the project root from its own location, clears inherited Python path/home overrides, verifies release identity before normal release startup, selects a standard non-free-threaded 64-bit CPython 3.11–3.14 runtime (3.13 preferred), and starts the loopback dashboard.

Port `8765` is preferred. If another local service already owns it, the launcher reserves another port rather than opening the unrelated service. The browser opens only after the responding health endpoint proves the exact Data Contract Monitor service, version, build, and per-launch identity.

Other Windows actions are `VERIFY_RELEASE.bat`, `RUN_DEMO.bat`, `RUN_TESTS.bat`, `REPAIR_INSTALLATION.bat`, and `CREATE_SUPPORT_EXPORT.bat`.

Linux/macOS source launch:

```bash
./tools/start.sh
```

## What 0.2.2 adds

Version 0.2.2 adds a versioned SQLite state store, bounded background validation jobs, progress and cooperative cancellation, immutable per-run report sets, atomic report publication, a compiled rule plan, declared input/resource budgets, and safe aggregate reconciliation. It also hardens Windows atomic writes, cancellation, legacy-console output, and composite Action portability. Modifying dashboard API requests use a random per-launch local session cookie and loopback Origin/Host checks.

A completed run publishes to:

```text
reports/runs/<run_id>/
```

Only after the complete report set is hashed and verified does the application atomically update:

```text
state/latest_completed_run.json
```

SQLite is authoritative runtime history at `state/dcm_state.sqlite3`. Legacy JSONL history remains readable only for explicit compatibility workflows; new project-root runs use SQLite.

## One export destination

Support and automatic Critical diagnostic ZIPs finalize only under:

```text
exports/
```

Temporary ZIP staging occurs under project `temp/`; crash capsules stay under `diagnostics/crash_capsules/`. The obsolete `diagnostics/exports/` path is not created or used.

## Contract capabilities

| Area | Implemented controls |
|---|---|
| Schema | Required/unexpected columns, logical types, observed nullability, approved baselines and drift |
| Column quality | Nullability, uniqueness, range, length, pattern, approved values, freshness |
| Dataset quality | Row-count bounds, composite uniqueness, null-ratio limits, conditional completeness |
| Reconciliation | Safe arithmetic aggregate reconciliation with numeric tolerance |
| Privacy review | Heuristic field-name and bounded sampled-pattern signals; no raw cell values in normal reports |
| Interfaces | Shared Python engine behind CLI, FastAPI, TypeScript dashboard, Python package, and composite GitHub Action |
| CI evidence | Exit codes, JSON, JUnit XML, and SARIF 2.1.0 |
| Reliability | SQLite state, bounded jobs, atomic artifacts, release identity, project-local diagnostics |

## Example contract

```yaml
dataset:
  name: customer_orders
  required_columns: [order_id, customer_id, order_date, total_amount]
  allow_extra_columns: false

rules:
  order_id:
    type: string
    nullable: false
    unique: true
    pattern: '^ORD-[0-9]{4,}$'
    severity: critical
  total_amount:
    type: number
    nullable: false
    minimum: 0
  order_date:
    type: datetime
    maximum_age_hours: 48

privacy:
  detect_pii: true
  allowed_categories: [account_identifier]
  fail_on_unapproved: false
```

The complete native example is `examples/contracts/customer_orders.yml`. A documented subset of Open Data Contract Standard v3.1 is also supported.

## CLI

Install from source:

```bash
python -m pip install .
```

Validate:

```bash
data-contract-monitor validate \
  --contract examples/contracts/customer_orders.yml \
  --data path/to/customer_orders.csv \
  --formats html,json,junit,sarif \
  --fail-on error
```

Useful commands include `demo`, `profile`, `baseline create`, `baseline compare`, `doctor`, and `export-support`.

Exit codes are `0` pass, `2` contract/data-quality failure at the selected threshold, `3` input/configuration failure, `4` internal/startup/release-integrity failure, and `130` cancellation.

## Local API and dashboard

```bash
data-contract-monitor serve --host 127.0.0.1 --port 8765
```

The dashboard submits validation to a bounded job queue instead of performing the entire validation inside the HTTP request. Job state and progress are queryable, cancellation is cooperative, and completed results are durable. The service is designed for a trusted local workstation; it is not a public multi-user service.

Default resource budgets include a 1 MB contract limit, 50 MB dataset limit, 2,000,000 rows, 1,000 columns, 10,000 retained findings, and a cooperative 300-second validation budget checked between stages. These are safety budgets rather than throughput promises.

## GitHub Action

After publishing a real repository, a consumer can use the included composite action, for example:

```yaml
- uses: Jnapier2/data-contract-monitor@v0.2.2
  with:
    contract: contracts/customer_orders.yml
    data: data/customer_orders.csv
    fail-on: error
    formats: json,junit,sarif
```

The Action installs the repository's pinned dependency set and remains independent of the calling repository's cache layout.

## Release integrity and project organization

Release mode fails closed when `VERSION.txt`, `PACKAGE_METADATA.json`, `MANIFEST.json`, `MANIFEST.sha256`, managed-file SHA-256 values, and installed application identity disagree. Read-only support export remains available after an integrity failure.

`tools/project_index.py` inventories retained files and rejects an unexpected BAT/CMD or unapproved exact duplicate during release preparation. The active implementation map and the one intentional demo-resource boundary duplicate are documented in `docs/PROJECT_STRUCTURE.md`.

Version 0.2.2 merges the durable-foundation work with the proven public Action and Windows cancellation safeguards from v0.1.5. The unqualified v0.2.0 and v0.2.1 artifacts were never promoted. v0.1.5 remains the public rollback release; do not combine managed files from releases.

## Verification and limits

The source suite contains 72 tests spanning data rules, APIs, persistence, diagnostics, release identity, the composite Action, and Windows lifecycle behavior. The release pipeline also performs Python compilation, TypeScript compilation/equivalence, schema/SBOM regeneration, launcher/consolidation checks, wheel build/version checks, manifest verification, and ZIP integrity/path checks. The external verification receipt distributed beside the final ZIP records exact artifact hashes and counts.

The v0.2.2 release is built and regression-tested on Windows with CPython 3.12. Exact native launcher, integrity, demo, and extracted-package results are recorded in the release receipt. Norton, SmartScreen reputation, and Authenticode are reported separately and are never inferred from application tests. See `VERIFICATION_REPORT.md`, `docs/KNOWN_LIMITATIONS.md`, and `docs/RELEASE_CHECKLIST.md`.

## Documentation

Architecture: `docs/ARCHITECTURE.md` · project structure: `docs/PROJECT_STRUCTURE.md` · contract reference: `docs/CONTRACT_REFERENCE.md` · reviewer guide: `docs/RECRUITER_REVIEW.md` · release recovery: `docs/RELEASE_RECOVERY.md` · security/privacy: `docs/SECURITY_AND_PRIVACY.md` · Windows troubleshooting: `docs/WINDOWS_STARTUP_TROUBLESHOOTING.md`.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
