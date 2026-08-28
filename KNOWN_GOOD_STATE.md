# Release and Recovery Baselines

## Maintenance package

- Product: Data Contract Monitor
- Version: 0.1.5
- Build: `DCM-0.1.5-B20260828-ACTION1`
- Channel: portfolio alpha
- Source checks: recorded in the exact-package qualification receipt; native shutdown acceptance is recorded separately.
- Acceptance authority: the exact ZIP's checksum and separate qualification receipt, not a version label or an open browser window.

## Retained rollback

Version 0.1.2 (`DCM-0.1.2-B20260828-LAUNCHISOLATION1`) remains the prior field-confirmed Windows save state. The separately reviewed v0.1.3 package retains its recorded cancellation/status limitation. The v0.1.4 `SHUTDOWN2` and `PUBLIC1` packages retain their exact Windows acceptance evidence. The v0.1.4 public release has a documented invalid composite-Action YAML limitation; v0.1.5 fixes that integration without changing local validation or Windows startup behavior. Earlier archives are not overwritten.

## Release invariants

- Managed source, package metadata, manifest, wheel, version, and build identity must agree before launch.
- The Windows entrypoint resolves the project folder from its own location.
- The browser opens only after the endpoint proves the expected service, version, build, and per-launch identity.
- Occupied local ports must not open another application's page.
- Runtime logs, state, reports, and support exports remain separate from managed release files.
- Support exports finalize in root `exports/`; unknown and user-created ZIPs are preserved.

## Recovery

Re-extract the complete release ZIP into a new folder. Do not overlay individual BAT, Python, manifest, metadata, or wheel files from another version. Retain the old folder until the new one has passed verification, then copy only reviewed configuration and reports.

A failed integrity check is a reason to restore a complete package, not to disable the check. A separate local support export remains available for diagnosis.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
