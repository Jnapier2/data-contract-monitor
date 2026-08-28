# Verification Report — Data Contract Monitor 0.1.5

Build: `DCM-0.1.5-B20260828-ACTION1` · August 28, 2026

## Verified source checks

| Check | Observed result |
|---|---|
| Automated suite | Exact-package results and environment are recorded in the accompanying qualification receipt |
| Python compilation | Source, tools, and tests passed |
| TypeScript | Version 5.8.3 compiled successfully |
| Dashboard JavaScript | Compiled output matched the packaged script byte for byte |
| Dependency consistency | `pip check` passed in the exercised Windows environments |
| Windows launcher structure | Seven CRLF BAT files; six stable entrypoints forward to one implementation |
| Synthetic demo | Passing: zero findings. Failing: two critical findings, eight errors, two warnings |

The suite covers contract rules, readers, drift, aggregate profiling, report formats, CLI exit codes, API validation, release integrity, local-port isolation, dashboard assets, redaction, and preservation of user files. Added regressions cover incomplete frontend builds, Windows line endings, dependency-folder exclusion, legacy terminal encodings, brief Windows file locks, exhausted retries, and independent temporary files for concurrent status writers.

## Exact-artifact acceptance

The separate qualification receipt identifies the ZIP SHA-256, wheel SHA-256, complete file count, environment, and outcomes. Acceptance checks extract the ZIP into a new folder, verify every managed file, import the exact bundled wheel, exercise both CLI and API demos, parse HTML/JSON/JUnit/SARIF evidence, rerun the suite, and verify integrity again after testing.

Windows BAT execution and browser interaction are checked separately from the Python suite. Their outcomes belong to the receipt for the exact artifact being delivered; passing unit tests alone do not establish launcher acceptance. The release ZIP and checksum sidecar must remain together.

## What was fixed during review

- Version 0.1.5 fixes two unquoted composite-Action descriptions that made its YAML invalid. Parsing tests now cover every GitHub YAML file, and CI exercises the real Action with both passing and failing datasets in a caller without its own Python lockfile. The Action uses its own dependency lock and keeps runtime output in the caller's workspace.
- The security notice now describes the current alpha support policy, and the Unix launch command works without relying on an executable file permission.
- A partial TypeScript build could hide the complete packaged dashboard.
- An integrity-test fixture assumed Unix line endings.
- Launcher inventory checks could include third-party virtual-environment scripts.
- Some Windows terminal encodings could interrupt an otherwise successful command while printing table borders. The UTF-8 log is now preserved and console text falls back safely.
- Build ordering, dependency-store exclusions, and the Windows terminal dependency pin needed tightening.
- Redundant CMD status writes could emit permission warnings after successful execution; the bootstrap now owns normal status finalization.
- Brief Windows locks on dashboard status files could abort startup. Status updates now use unique same-folder temporary files and bounded replacement retries; persistent failures preserve the previous complete file and still report an error.
- Wide tables could expand the whole page on narrow screens; results now scroll within their panels, with improved dark-theme status readability.
- Ctrl+C could interrupt the launcher before process cleanup and stopped-status finalization. Cancellation now has bounded child cleanup, cannot trigger a crash export, and cannot be overwritten by a late browser-readiness update.
- CLI cancellation and fatal-error exits now return their documented codes without an unhandled wrapper exception.
- An idle Windows output pipe could defer cancellation until another log line arrived. Output now drains in a dedicated worker while the launcher checks the child through short, bounded waits.

The cancellation implementation follows the [Python subprocess signal API](https://docs.python.org/3.13/library/subprocess.html#subprocess.Popen.send_signal) and accounts for [main-thread signal handling](https://docs.python.org/3.13/library/signal.html#execution-of-python-signal-handlers). Windows child groups receive a targeted Ctrl+Break; a bounded fallback only targets the process launched by this command. Native receipts distinguish a clean application stop from the shell's own batch-termination prompt.

These are maintenance changes. The validation engine, synthetic scenarios, stable entrypoints, and Apache-2.0 licensing remain unchanged.

## Boundaries

This review does not claim a new Linux/macOS run, optional Parquet-engine validation, a formal accessibility audit, a dedicated Norton scan, SmartScreen certification, or production service hardening. Windows security settings were not changed. Historical benchmark and accessibility evidence are labeled separately; neither is a new performance or conformance guarantee.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
