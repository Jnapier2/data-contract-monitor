# Data Contract Monitor

**Executable data contracts with scalable, exact validation evidence for files, local review, and CI.**

Data Contract Monitor validates CSV, Excel, JSON, JSON Lines, and optional Parquet datasets against readable YAML contracts. It produces accessible HTML plus JSON, JUnit XML, and SARIF evidence; records durable run history; detects schema drift and privacy-field signals; compares contract and run evolution; and gives CI a clear distinction between “the data failed its contract” and “the program failed.”

The project is local-first and includes passing/failing demonstrations that require no credentials or private data.

![Data Contract Monitor dashboard](docs/assets/dashboard.png)

## Windows quick start

Extract the complete ZIP first; do not run a BAT from Windows compressed-folder preview. Open the extracted `Data_Contract_Monitor_v0.3.3` folder and double-click:

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

## What 0.3.3 repairs and preserves

Version 0.3.3 is the **Windows Freshness & Transport Noise** maintenance release. It preserves the v0.3.2 field-proven maintenance preflight, the v0.3.1 atomic-write repair, and the v0.3.0 Scalable Assurance capability set. The v0.3.2 Windows field run proved stale-wheel retirement, all 144 managed hashes, dependency/application installation, fallback-port launch, and HTTP health. v0.3.3 narrows the remaining field polish to browser freshness and the known benign Windows Proactor reset callback.

Field hardening in v0.3.3:

- the browser opens a build-qualified URL (`/?build=<exact-build-id>`) only after exact health identity succeeds;
- `/` and `/assets/*` are served with `no-store`/`no-cache` response headers;
- current stylesheet/script URLs are version-qualified;
- the current UI has no `/demo-data.json` dependency, so a stale request remains a visible 404 rather than silently serving unrelated compatibility data;
- only the exact Windows Proactor `_call_connection_lost` `ConnectionResetError` / WinError 10054 callback is suppressed; unrelated asyncio failures remain visible.

Before the strict release gate, a small dependency-free maintenance preflight verifies the manifest sidecar, version/build agreement, its own managed hash, the launcher and release-gate hashes, and the exact current application wheel. Only after that recovery authority passes may it move recognized prior-version `packages/data_contract_monitor-*.whl` files into `backups/retired_packages/<timestamp>/` with SHA-256 receipts. Files are moved, never deleted; unknown/user files are not touched. The strict release gate then runs unchanged.

Support export remains available even when strict release verification fails and deliberately selects an external Python runtime so a stale or damaged project `.venv` cannot block recovery. Repair also uses external Python before rebuilding the project-local environment.

The release preserves:

- `auto`, `memory`, and bounded `streaming` execution modes;
- batch streaming for CSV, JSONL, and NDJSON;
- exact disk-backed single-column uniqueness, composite uniqueness, and cross-dataset referential integrity across batches;
- bounded high-cardinality profiling that labels lower-bound counts rather than presenting them as exact;
- reader-plugin discovery through `data_contract_monitor.readers` entry points;
- contract lint, canonical normalization, semantic diff classification, stable contract IDs, and exact contract-version history;
- SQLite state schema v3 with migration backup/integrity evidence;
- run-to-run finding/metric comparison, quality trends, drift history, and artifact inventory;
- optional reference-file upload in the local dashboard/API with isolated path mapping;
- stricter content-signature, field/header, JSON-depth, report-size, free-disk, row/column, finding, and runtime budgets;
- a target-specific, hash-inventoried Windows wheelhouse builder and offline-bootstrap consumption when such a wheelhouse is present;
- expanded Python 3.11–3.14 Windows/Linux CI plus CodeQL workflow definitions.

A completed run publishes to:

```text
reports/runs/<run_id>/
```

Only after the complete report set is hashed and verified does the application atomically update:

```text
state/latest_completed_run.json
```

SQLite is authoritative runtime history at `state/dcm_state.sqlite3`.

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
| Column quality | Nullability, exact uniqueness, range, length, pattern, approved values, freshness |
| Dataset quality | Row-count bounds, exact composite uniqueness, null-ratio limits, conditional completeness |
| Reconciliation | Safe arithmetic aggregate reconciliation with numeric tolerance |
| Relationships | Exact disk-backed `reference_exists` checks against declared reference datasets |
| Contract lifecycle | Stable contract ID/version, lint, normalized YAML, semantic change classification |
| History | Durable runs, artifact inventory, run comparison, pass-rate and drift trends |
| Privacy review | Heuristic field-name and bounded sampled-pattern signals; no raw cell values in normal reports |
| Interfaces | Shared Python engine behind CLI, FastAPI, TypeScript dashboard, package, GitHub Action, and container definition |
| CI evidence | Exit codes, JSON, JUnit XML, SARIF 2.1.0, multi-version/multi-OS workflow definitions |
| Reliability | SQLite migrations, bounded jobs, atomic artifacts, release identity, project-local diagnostics |

## Example contract

```yaml
contract_version: "2.1"
effective_date: "2026-08-31"
compatibility_policy: strict

dataset:
  name: customer_orders
  contract_id: customer-orders
  owner: Data Operations
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

Cross-dataset rules can require that a local key exists in a declared reference file:

```yaml
dataset_rules:
  - name: customer_fk
    type: reference_exists
    column: customer_id
    reference_dataset: ../data/customers_reference.csv
    reference_column: customer_id
    severity: error
```

The complete examples are under `examples/contracts/` and `examples/data/`. A documented subset of Open Data Contract Standard v3.1 is also supported.

## CLI

Install from source:

```bash
python -m pip install .
```

Validate with automatic execution selection:

```bash
data-contract-monitor validate \
  --contract examples/contracts/customer_orders.yml \
  --data path/to/customer_orders.csv \
  --execution-mode auto \
  --formats html,json,junit,sarif \
  --fail-on error
```

Contract lifecycle:

```bash
data-contract-monitor contract lint --contract contracts/orders.yml
data-contract-monitor contract normalize --contract contracts/orders.yml --output normalized.yml
data-contract-monitor contract diff --older contracts/orders-v1.yml --newer contracts/orders-v2.yml
```

Durable run analysis:

```bash
data-contract-monitor history trend --dataset customer_orders
data-contract-monitor history compare <older_run_id> <newer_run_id>
```

Other commands include `demo`, `profile`, `baseline create`, `baseline compare`, `doctor`, and `export-support`.

Exit codes are `0` pass, `2` contract/data-quality failure at the selected threshold, `3` input/configuration failure, `4` internal/startup/release-integrity failure, and `130` cancellation.

## Local API and dashboard

```bash
data-contract-monitor serve --host 127.0.0.1 --port 8765
```

The dashboard submits validation to a bounded job queue rather than performing the entire validation inside the HTTP request. It supports execution-mode selection, optional contract-declared reference datasets, job progress/cancellation, durable history, run comparison, and report downloads. The service is designed for a trusted local workstation; it is not a public multi-user service.

Default resource budgets include a 1 MB contract limit, 250 MB total dataset-file limit, 50 MB in-memory input cap, 2,000,000 rows, 1,000 columns, 10,000 retained findings, and a cooperative 300-second validation budget. CSV/JSONL can stream above the in-memory threshold. These are safety budgets rather than performance guarantees.

## Exactness and performance

Streaming rule enforcement does not silently become approximate. Uniqueness, composite uniqueness, referential integrity, and supported row/column rules remain exact. High-cardinality *profile statistics* may become bounded lower bounds and explicitly carry `*_exact=false` metadata.

A local Linux qualification run processed a synthetic **1,000,000-row / 6-column / ~96.9 MB CSV** in streaming mode in **29.694 seconds** of validator time across 20 batches, with about **216,528 KiB peak process RSS** in that exercised environment. This is benchmark evidence for one machine/runtime, not a universal throughput promise. See `BENCHMARK_REPORT.md`.

## GitHub Action

After publishing a real repository, a consumer can use the included composite action, for example:

```yaml
- uses: your-org/data-contract-monitor@v0.3.3
  with:
    contract: contracts/customer_orders.yml
    data: data/customer_orders.csv
    fail-on: error
    execution-mode: auto
    formats: json,junit,sarif
```

`your-org` remains a placeholder until an actual repository is published.

## Offline Windows dependency preparation

Normal Windows bootstrap can use a verified project-local wheelhouse when one exists at `packages/wheelhouse/cpXY-win_amd64/`. Create one on a networked build machine with:

```bash
python tools/build_windows_wheelhouse.py --root . --python-version 313
```

The builder stages under project `temp/`, promotes only after download completion, and writes a SHA-256 inventory. This build environment could not reach the package index, so no Windows wheelhouse is falsely claimed as bundled or Windows-qualified in v0.3.3.

## Release integrity and project organization

Release mode fails closed when `VERSION.txt`, `PACKAGE_METADATA.json`, `MANIFEST.json`, `MANIFEST.sha256`, managed-file SHA-256 values, and installed application identity disagree. Read-only support export remains available after an integrity failure.

`tools/project_index.py` inventories retained files and rejects an unexpected BAT/CMD or unapproved exact duplicate during release preparation. The active implementation map and intentional source/package resource boundary are documented in `docs/PROJECT_STRUCTURE.md`.

v0.3.3 branches from the exact v0.3.2 maintenance-preflight candidate plus physical Windows evidence showing v0.3.2 reached healthy readiness. The exact v0.1.2 ZIP remains the earlier user-confirmed rollback authority until v0.3.3 receives visible Windows browser acceptance. Do not combine managed files from releases.

## Verification and limits

The v0.3.3 source suite contains **69 passing tests** with `ResourceWarning` promoted to an error before exact-artifact packaging. Release qualification also performs Python compilation, TypeScript compilation/equivalence, schema/SBOM regeneration, launcher/consolidation checks, wheel build/version checks, manifest verification, ZIP integrity/path checks, installed-wheel demos, Export20 checks, and deliberate tamper tests.

Windows `cmd.exe`, Norton, SmartScreen, Authenticode, hosted GitHub Actions/CodeQL, and the optional Windows wheelhouse cannot be truthfully executed in this Linux build environment and remain field/publication qualification steps for v0.3.3. See `VERIFICATION_REPORT.md`, `docs/KNOWN_LIMITATIONS.md`, and `docs/RELEASE_CHECKLIST.md`.

## Documentation

Architecture: `docs/ARCHITECTURE.md` · scalable execution: `docs/SCALABLE_EXECUTION.md` · reader plugins: `docs/READER_PLUGINS.md` · contract reference: `docs/CONTRACT_REFERENCE.md` · recruiter review: `docs/RECRUITER_REVIEW.md` · security/privacy: `docs/SECURITY_AND_PRIVACY.md` · Windows troubleshooting: `docs/WINDOWS_STARTUP_TROUBLESHOOTING.md`.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
