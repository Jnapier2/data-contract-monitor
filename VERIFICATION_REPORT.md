# Verification Report — Data Contract Monitor 0.3.4

**Build:** `DCM-0.3.4-B20260901-SECURITY1`  
**Status:** exact-package qualification is produced beside the release ZIP.

## Source qualification targets

- full pytest suite with `ResourceWarning` promoted to an error;
- Python compilation;
- TypeScript compile and packaged JavaScript equivalence;
- noncanonical artifact-identifier rejection and report-root containment;
- non-sensitive database-health failure response;
- bounded retry behavior for transient Windows file locks during atomic replacement;
- browser freshness, local-session, maintenance-preflight, release-gate, and recovery regressions;
- schema/SBOM regeneration, wheel identity, manifest verification, ZIP integrity/path checks, installed-wheel demonstrations, Export20 checks, and deliberate tamper tests.

## Preserved behavior

Validation semantics, data-contract behavior, state schema 3, resource limits, report formats, and Windows startup behavior are unchanged from v0.3.3. Existing scalability and physical-Windows evidence remain regression context rather than new performance or native-environment claims.

## Native qualification boundary

Hosted GitHub Actions and CodeQL provide independent source verification. Physical-Windows `cmd.exe`, Norton, SmartScreen, Authenticode, and optional wheelhouse acceptance remain separate native checks for the exact package.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
