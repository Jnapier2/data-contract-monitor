# Launcher Repair Report — Data Contract Monitor 0.1.2

**Workstream:** Professional Portfolio — Data Contract Monitor  
**Build:** `DCM-0.1.2-B20260828-LAUNCHISOLATION1`  
**Repair date:** August 28, 2026

## Evidence reviewed

Two v0.1.1 manual support packages were reviewed:

| Package timestamp | SHA-256 | Items |
|---|---|---:|
| 2026-08-28 15:23:07 UTC | `b43c4454c0b2f4c03517b0af422c5ae4d4b9f1e4e8f7d0f27ce31768a480089b` | 10 |
| 2026-08-28 15:23:42 UTC | `e5cbe711211d1a3f37ad0471d36a1af6239a191c329081646a65b360ff0cd59e` | 10 |

Both packages identified Data Contract Monitor v0.1.1, build `DCM-0.1.1-B20260828-STARTUPREPAIR1`, on Windows with Python 3.13.15. Release identity passed. The packages did not include `logs/launcher.log`, `logs/bootstrap.log`, `logs/python_detection.txt`, `LATEST_LAUNCH_STATUS.txt`, or a selected-endpoint record, so they could not identify the process already listening on the preferred port.

## Root causes

### 1. Unrelated local page could open

The v0.1.1 server always constructed `http://127.0.0.1:8765`, scheduled the browser to open that URL after one second, and only then attempted to bind Uvicorn to the port. It did not prove which application answered the address. When another local application already owned port 8765, the browser could display that application while Data Contract Monitor failed to bind.

A complete source scan found no BTC, miner, CKPool, or stratum implementation in Data Contract Monitor. The observed miner page is therefore consistent with a loopback-port collision rather than miner code being launched by this project.

### 2. Duplicate export directories

The v0.1.1 runtime created both root `exports/` and `diagnostics/exports/`, while the diagnostic manager finalized support and Critical ZIPs in the nested directory. That contradicted the project-local directory policy and created two apparent export destinations.

## Repair

Version 0.1.2:

- reserves the selected socket before server startup;
- falls back safely when the preferred port is occupied;
- hands the reserved socket directly to Uvicorn;
- opens the browser only after exact service, version, build, and per-launch identity verification;
- records the actual endpoint for recovery and diagnosis;
- clears inherited Python environment redirection variables;
- uses only root `exports/` for support and Critical ZIPs;
- keeps `diagnostics/` for capsules and internal diagnostic state;
- adds the missing startup evidence to Export20;
- preserves unknown and user-created ZIPs during retention.

## Recovery boundary

Use a fresh v0.1.2 extraction. Do not copy the repaired BAT or Python files over the v0.1.1 folder. The old nested export directory may be retained as historical evidence; v0.1.2 will not create or use it.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
