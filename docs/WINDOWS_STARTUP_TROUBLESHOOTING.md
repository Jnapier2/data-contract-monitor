# Windows Startup Troubleshooting

## Correct launch sequence

1. Right-click the downloaded release ZIP and select **Extract All**.
2. Open the complete extracted Data Contract Monitor folder.
3. Double-click `START_DATA_CONTRACT_MONITOR.bat`.
4. Allow the first-run dependency installation to finish. Port `8765` is preferred. If another local program already owns it, Data Contract Monitor reserves the next available port through `8785`; if that bounded range is full, the operating system assigns another available loopback port. The verified selected address opens instead.

Do not launch the BAT from Windows Explorer's compressed-folder preview. A BAT opened inside the ZIP cannot reliably access the rest of the project.

## Supported Python runtimes

The Windows launcher accepts a standard, non-free-threaded, 64-bit CPython runtime from 3.11 through 3.14. It prefers Python 3.13, then 3.14, 3.12, and 3.11. An already verified project-local `.venv` is reused first.

Python does not need to be on `PATH` when it is discoverable through the Windows Python launcher or a standard per-user installation path.

## Persistent evidence

A failed launch no longer disappears without evidence. Review these project-local files:

```text
LATEST_LAUNCH_STATUS.txt
logs\launcher.log
logs\bootstrap.log
logs\python_detection.txt
state\dashboard_endpoint.json
```

A terminal startup abort also attempts to create:

```text
diagnostics\crash_capsules\startup_abort_*.json
exports\Data_Contract_Monitor_*_Support.zip
```

The diagnostic collector is bounded, read-only with respect to application data, and redacts common secret, home-directory, and IP-address signals. All support and Critical ZIPs use the single canonical `exports` directory; `diagnostics` is reserved for capsules and diagnostic state.

An old v0.1.1 extraction may still contain `diagnostics\exports`. Keep it only as historical evidence or move reviewed ZIPs manually. Version 0.1.2 does not use that location and does not silently delete prior files.

## A different local application appeared

Version 0.1.1 opened the preferred address before proving that Data Contract Monitor owned it. When another local service—such as a miner dashboard—already used port `8765`, the browser could show that unrelated service while Data Contract Monitor failed to bind. Version 0.1.2 reserves an available socket first and opens the browser only after `/api/health` returns the exact Data Contract Monitor service ID, version, build, and per-launch identity.

The selected address is recorded in:

```text
LATEST_LAUNCH_STATUS.txt
state\dashboard_endpoint.json
```

## Recovery order

1. Close any prior Data Contract Monitor console window.
2. Run `VERIFY_RELEASE.bat`.
3. When release integrity passes but environment setup fails, run `REPAIR_INSTALLATION.bat` once.
4. When release integrity fails, do not copy replacement BATs into the old folder. Run `CREATE_SUPPORT_EXPORT.bat`, then extract a fresh release ZIP to a new folder.
5. When Python is not found, install a standard 64-bit CPython 3.13 or 3.14 runtime and rerun the start BAT.

`REPAIR_INSTALLATION.bat` removes only the package-managed project-local `.venv` and installation stamps before rebuilding them. It does not delete contracts, datasets, reports, or user configuration.

## Common first-run causes

- The BAT was opened directly inside the ZIP.
- Only the BAT files were copied instead of extracting the full release.
- Python 3.14 was selected with a dependency lock that lacked matching Windows wheels in v0.1.0.
- Package-index access was blocked during the first dependency installation.
- The extracted folder was altered after release creation, causing the integrity gate to fail closed.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
