# Windows Startup Troubleshooting

Use a fresh extraction of the complete `Data_Contract_Monitor_v0.3.4` ZIP. Do not run BAT files from Windows compressed-folder preview and do not overlay managed files onto an older extraction.

The normal entrypoint is `START_DATA_CONTRACT_MONITOR.bat`. Every root BAT remains a logic-free forwarder to the single backend `tools\launch.bat`. Review `LATEST_LAUNCH_STATUS.txt`, `logs\launcher.log`, `logs\bootstrap.log`, and `logs\python_detection.txt` after a failure. `CREATE_SUPPORT_EXPORT.bat` remains a read-only recovery action whose final ZIP belongs only in root `exports\`.

## Port and browser identity

Port 8765 is a preference. The launcher reserves a socket before browser launch, falls forward through the bounded range, and can use an OS-assigned loopback port. The browser opens only after exact service/version/build/per-launch health identity. v0.3.4 opens `/?build=DCM-0.3.4-B20260901-SECURITY1` and serves `/` plus `/assets/*` with no-store/no-cache headers. Current HTML uses version-qualified CSS/JavaScript assets.

The current Data Contract Monitor UI does **not** use `/demo-data.json`. If a browser still asks for it, the 404 is evidence of stale browser/external document state; v0.3.3 intentionally does not fabricate compatibility data. Close that stale tab and use the build-qualified URL recorded in `state\dashboard_endpoint.json` or `LATEST_LAUNCH_STATUS.txt`.

## Windows Proactor reset noise

A reset loopback client can cause Python's Windows Proactor transport to surface `ConnectionResetError: [WinError 10054]` from `_ProactorBasePipeTransport._call_connection_lost` after the useful request already completed. v0.3.3 suppresses only that exact callback signature on Windows. Invalid HTTP warnings and unrelated asyncio exceptions are not broadly hidden.

## Stale prior-version wheel recovery

The v0.3.2 bounded maintenance preflight is preserved. After verifying its recovery authority, it may move only recognized old `packages\data_contract_monitor-*.whl` files to `backups\retired_packages\<timestamp>\` with SHA-256 evidence. It never deletes them or moves unrelated/unknown user files. The strict release gate then runs unchanged. Repair and Export use external Python so a stale project `.venv` cannot block recovery evidence.

If release identity fails for anything outside that recognized stale-wheel case, re-extract the exact release rather than mixing files. The earlier confirmed rollback remains v0.1.2 SHA-256 `16b53aaa47d406f61b8163faf6b1ea39be504fc8fc11fcec7b8becfbef62fe24`.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
