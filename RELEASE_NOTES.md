# Data Contract Monitor 0.3.3 — Windows Freshness & Transport Noise

**Build:** `DCM-0.3.3-B20260831-WINDOWSFRESHNESS1`  
**Date:** 2026-08-31

## Purpose

Version 0.3.3 is a focused Windows field-maintenance release built from exact v0.3.2. It does not change validation semantics, data-contract behavior, state schema, or resource-limit policy. It preserves the field-proven v0.3.2 maintenance preflight and addresses the two non-terminal symptoms remaining in the physical Windows run.

## Field evidence reconciled

The v0.3.2 Windows run retired recognized v0.3.0 and v0.3.1 wheels, passed 144/144 managed release identity, installed locked dependencies and the exact v0.3.2 wheel under CPython 3.13.15, fell forward from occupied port 8765 to 8766, completed application startup, and returned `/api/health` HTTP 200. The server remained healthy after the observed warning/traceback.

The remaining evidence was:

1. a Windows asyncio Proactor `_call_connection_lost` `ConnectionResetError` / WinError 10054 after an invalid/reset loopback request;
2. a browser request for `/demo-data.json` returning 404 even though the current Data Contract Monitor HTML and JavaScript do not reference that path.

## Repair

- Browser launch now uses a build-qualified URL after exact health identity.
- Root HTML and `/assets/*` use `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`, `Pragma: no-cache`, and `Expires: 0`.
- Current HTML references version-qualified CSS and JavaScript assets.
- No fake `/demo-data.json` response was added; a stale request remains a 404 so stale external/browser state stays diagnosable.
- On Windows only, the event loop suppresses exactly the known Proactor `_call_connection_lost` connection-reset callback with WinError/errno 10054. Other asyncio exceptions continue through the existing/default handler.

## Recovery and rollback

v0.3.2 is the immediate field-started predecessor. v0.1.2 remains the earlier Windows-confirmed rollback authority until this exact v0.3.3 release receives visible Windows browser acceptance.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
