# Data Contract Monitor 0.3.4 — Artifact and Health Boundary Hardening

**Build:** `DCM-0.3.4-B20260901-SECURITY1`  
**Date:** 2026-09-01

## Purpose

Version 0.3.4 is a focused security-maintenance release built from exact v0.3.3. It does not change validation semantics, data-contract behavior, state schema, resource limits, or Windows startup behavior.

## Security improvements

- Artifact downloads accept only canonical 32-character hexadecimal run identifiers.
- Resolved artifact paths must remain under the managed `reports/runs` directory before any file check or response.
- The public health endpoint returns a stable database-health failure message without exposing internal exception text.
- Atomic state updates retry bounded transient Windows file locks before failing.
- Regression coverage confirms noncanonical artifact identifiers fail closed.

## Preserved foundations

The release retains the scalable v0.3.0 validation engine, v0.3.2 maintenance recovery, v0.3.3 browser-freshness controls, one active Windows launcher backend, exact manifest/wheel identity, bounded local runtime, and recovery diagnostics.

## Recovery and rollback

v0.3.3 is the immediate rollback release. v0.1.2 remains the earlier physical-Windows-confirmed rollback authority. Do not mix managed files between versions; recover from a complete verified archive.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
