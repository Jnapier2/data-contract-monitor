# Known-Good / Recovery State

## Current candidate

- Version: 0.3.3
- Build: `DCM-0.3.3-B20260831-WINDOWSFRESHNESS1`
- Status: source maintenance candidate; exact-artifact qualification pending final archive construction.
- Immediate predecessor: exact v0.3.2 maintenance-preflight release with physical Windows startup/readiness evidence.
- Earlier Windows-confirmed rollback authority: v0.1.2 exact ZIP SHA-256 `16b53aaa47d406f61b8163faf6b1ea39be504fc8fc11fcec7b8becfbef62fe24`.

## Physical Windows evidence inherited from v0.3.2

The 2026-08-31 v0.3.2 run retired recognized v0.3.0/v0.3.1 wheels to project-local backups, passed 144/144 release identity, installed CPython 3.13.15 dependencies and the exact v0.3.2 application wheel, selected port 8766 around an unrelated 8765 listener, completed Uvicorn startup, and returned `/api/health` HTTP 200. The remaining symptoms were a non-terminal WinError 10054 Proactor callback traceback and a stale `/demo-data.json` request.

## v0.3.3 maintenance delta

Validation/data behavior and SQLite state schema 3 are unchanged. v0.3.3 adds build-qualified browser launch, no-store current UI responses, version-qualified static asset references, and a narrowly matched Windows Proactor WinError 10054 callback filter. It deliberately leaves `/demo-data.json` absent because current Data Contract Monitor code has no dependency on that retired/stale path.

## Recovery rule

Do not overlay managed BAT, Python, wheel, manifest, or metadata files across releases. Prefer a fresh extraction. Copy only reviewed user configuration, approved baselines, durable validation history, and desired reports/exports. The v0.3.2 maintenance preflight remains the bounded recovery path for recognized stale Data Contract Monitor wheels and never deletes unknown/user files.

Release mode remains fail-closed when version/build/package/manifest/managed hashes disagree. Read-only support export remains available after an integrity failure.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
