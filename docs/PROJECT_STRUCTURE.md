# Project Structure and Active-Implementation Map

Data Contract Monitor follows the Gateway v2.17.13 rule that every capability has one active implementation. User-facing action BAT files are stable, logic-free forwarders. They do not duplicate bootstrap, release-gate, repair, test, or export behavior.

| Action | Stable Windows entrypoint | Active BAT backend | Application/tool backend |
|---|---|---|---|
| Start dashboard | `START_DATA_CONTRACT_MONITOR.bat` | `tools/launch.bat` | `tools/bootstrap.py` -> installed `data-contract-monitor serve` |
| Verify/Doctor | `VERIFY_RELEASE.bat` | `tools/launch.bat` | `tools/release_gate.py`, then installed Doctor |
| Demo | `RUN_DEMO.bat` | `tools/launch.bat` | installed `data-contract-monitor demo` |
| Tests | `RUN_TESTS.bat` | `tools/launch.bat` | pytest through the project environment |
| Repair | `REPAIR_INSTALLATION.bat` | `tools/launch.bat` | `tools/bootstrap.py --repair` |
| Support export | `CREATE_SUPPORT_EXPORT.bat` | `tools/launch.bat` | `tools/support_export.py` / diagnostic manager |

Application atomic-write and hash behavior is centralized in `src/data_contract_monitor/atomic.py`. Pre-install build/bootstrap tools use the standard-library-only `tools/tooling_common.py`, which is intentionally a separate execution boundary because those tools must work before the application package is importable.

The only approved exact source-content duplication is the generated/maintained demo contract boundary:

- `examples/contracts/customer_orders.yml` — human-facing source example.
- `src/data_contract_monitor/resources/contracts/customer_orders.yml` — package resource used by an isolated installed wheel.

`tools/project_index.py` fails release preparation if an unexpected BAT/CMD file or an unapproved exact duplicate returns. Runtime-generated state, reports, diagnostics, caches, environments, and exports are excluded from the managed release inventory.

Runtime directories are project-local: `config/`, `logs/`, `state/`, `temp/`, `cache/`, `exports/`, `diagnostics/`, `reports/`, `downloads/`, and `backups/`. Support and Critical ZIPs finalize only under root `exports/`; temporary ZIP staging occurs under root `temp/`.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
