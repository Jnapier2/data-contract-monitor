# Release Recovery

## Current release

- Version: 0.2.2
- Build: `DCM-0.2.2-B20260829-WINDOWS1`
- Lineage: durable-foundation work merged with v0.1.5's verified composite Action and Windows cancellation safeguards. The v0.2.0 and v0.2.1 artifacts were not promoted.
- Promotion rule: the exact final ZIP, manifest, metadata, wheel, managed hashes, tests, and extracted release gate must agree. Norton, SmartScreen reputation, and signing remain separately scoped evidence and are never inferred from application tests.

## Rollback authority

The public rollback release is Data Contract Monitor v0.1.5. The exact v0.1.2 package remains the deeper Windows launcher-recovery baseline, build `DCM-0.1.2-B20260828-LAUNCHISOLATION1`.

Exact v0.1.5 release SHA-256:

`1bc3294daca89911a5029c2bb0a49a1764463fe5d20c572d7261830115a2b1ee`

Exact v0.1.2 release SHA-256:

`16b53aaa47d406f61b8163faf6b1ea39be504fc8fc11fcec7b8becfbef62fe24`

That build was user-confirmed working on Windows and remains the immediate recovery authority. Do not merge managed BAT, Python, manifest, metadata, or package files across releases. Re-extract the exact rollback ZIP instead.

## Runtime data preservation

When changing versions, preserve only reviewed user/configuration data and approved schema baselines. Runtime databases, reports, logs, diagnostics, and support exports are evidence, not source files. Unknown or user-created files are never silently deleted.

A browser opening is not sufficient promotion evidence. `VERSION.txt`, `PACKAGE_METADATA.json`, `MANIFEST.json`, `MANIFEST.sha256`, the application wheel, and the exact release ZIP must identify the same build.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
