# Windows Startup Troubleshooting

Use a fresh extraction of the complete `Data_Contract_Monitor_v0.2.2` ZIP. Do not run BAT files from Windows compressed-folder preview and do not overlay managed files onto an older extraction.

The normal entrypoint is `START_DATA_CONTRACT_MONITOR.bat`. Every root BAT is a three-line logic-free forwarder to the single backend `tools\launch.bat`, so a startup failure should be investigated through the shared evidence rather than by maintaining separate launcher implementations.

If startup fails, review `LATEST_LAUNCH_STATUS.txt`, `logs\launcher.log`, `logs\bootstrap.log`, and `logs\python_detection.txt`. `CREATE_SUPPORT_EXPORT.bat` remains a read-only recovery action and writes its final ZIP only to root `exports\`.

The launcher supports standard non-free-threaded 64-bit CPython 3.11–3.14 and prefers 3.13. It clears inherited `PYTHONPATH` and `PYTHONHOME`, derives root from the launcher location, and creates/repairs the project-local environment. First environment creation can require access to the configured Python package index.

Port 8765 is only a preference. The launcher reserves a socket before browser launch, tries the bounded fallback range through 8785, then can use an operating-system-assigned loopback port. The browser opens only after the endpoint returns the exact service ID, version, build, and per-launch identity. This preserves the v0.1.2 fix that prevented an unrelated local dashboard from appearing when it owned port 8765.

An old v0.1.1 folder may still contain historical `diagnostics\exports`. v0.2.2 does not use or recreate that location and does not silently delete old evidence. Current support/Critical ZIPs belong only in root `exports\`; staging occurs under root `temp\`.

If release identity fails, do not repair by mixing files. Re-extract the exact release ZIP. The immediate rollback authority remains v0.1.2 with SHA-256 `16b53aaa47d406f61b8163faf6b1ea39be504fc8fc11fcec7b8becfbef62fe24`.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
