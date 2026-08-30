# Data Contract Monitor 0.2.2 — Windows-Qualified Durable Foundation

**Build:** `DCM-0.2.2-B20260829-WINDOWS1`  
**Release date:** 2026-08-29

Version 0.2.2 combines the durable data-governance foundation with the proven public Action and Windows lifecycle safeguards from v0.1.5. The unqualified v0.2.0 and v0.2.1 artifacts were not promoted.

## Foundation changes

The release adds a transactional SQLite runtime state store, bounded validation jobs, cooperative cancellation and progress, immutable per-run evidence, atomic report publication, a compiled rule plan, declared resource budgets, and a safe aggregate-reconciliation rule. The local dashboard now submits validation jobs rather than executing long validation work directly in the request thread.

Local modifying API requests require a random per-launch HttpOnly session cookie and pass trusted-host/origin checks. Loopback remains the default service boundary. The origin parser validates the actual hostname rather than using an unsafe string-prefix comparison.

Support and Critical Export20 ZIPs have one final destination, root `exports/`. Temporary ZIPs stage under root `temp/`, pass ZIP integrity/uniqueness/count checks, and then finalize atomically. The obsolete `diagnostics/exports` path does not return.

## Consolidation changes

All six root BAT files are logic-free action forwarders to the sole Windows BAT backend, `tools/launch.bat`. Build/bootstrap atomic and hash helpers are centralized in `tools/tooling_common.py`; application-side atomic behavior remains centralized in `src/data_contract_monitor/atomic.py`. `tools/project_index.py` indexes every retained release file and fails release preparation if an unexpected BAT/CMD or unapproved exact duplicate appears.

The only approved exact source-content duplicate is the customer-orders demo contract at the human-readable example boundary and installed-package resource boundary. It is retained deliberately so an isolated wheel can run its demo without relying on the source checkout.

## Windows qualification repairs

Native Windows testing identified and corrected two issues that were invisible in the Linux-generated v0.2.1 receipt: atomic status writes attempted to flush a read-only Windows descriptor, and one test assumed Linux newline byte counts. The merged pass also restored bounded child-process cancellation, legacy-console output fallback, caller-independent Action installation, and project-local test staging. The 72-test suite now exercises those behaviors directly.

## Compatibility and recovery

Use a fresh extraction for 0.2.2. Do not overlay it on an earlier release. Public rollback remains v0.1.5. The exact Windows-confirmed v0.1.2 package remains the deeper launcher-recovery baseline.

The Windows launcher still supports standard non-free-threaded 64-bit CPython 3.11–3.14 and prefers Python 3.13. A self-contained offline Windows runtime remains a future publication enhancement; this release does not claim one.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
