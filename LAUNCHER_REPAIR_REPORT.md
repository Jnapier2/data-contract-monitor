# Launcher Repair Report — Data Contract Monitor 0.1.2

**Workstream:** Professional Portfolio — Data Contract Monitor  
**Build:** `DCM-0.1.2-B20260828-LAUNCHISOLATION1`  
**Repair date:** August 28, 2026

## Historical review

This note describes the v0.1.2 repair. Current verification is recorded in `VERIFICATION_REPORT.md`. Earlier Windows startup evidence showed that release identity alone could not establish which local service answered the preferred dashboard port.

## Root causes

### 1. Unrelated local page could open

The v0.1.1 server always constructed `http://127.0.0.1:8765`, scheduled the browser to open that URL after one second, and only then attempted to bind Uvicorn to the port. It did not prove which application answered the address. When another local application already owned port 8765, the browser could display that application while Data Contract Monitor failed to bind.

The fix checks the responding service identity instead of assuming that an open port belongs to this application.

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
