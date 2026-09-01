# Release Checklist

## Code and behavior

- [ ] Version is identical in package, `VERSION.txt`, dashboard, API, and metadata.
- [ ] Native and ODCS example contracts load.
- [ ] Contract lint/normalize/diff commands pass and stable contract ID/version are recorded in history.
- [ ] Forced streaming CSV/JSONL tests preserve exact uniqueness/reference semantics across batch boundaries.
- [ ] SQLite state migrations create an integrity-checked backup and land on schema v3.
- [ ] Passing demo returns exit code `0`.
- [ ] Failing demo returns exit code `2` and the expected finding counts.
- [ ] API health, bounded upload/reference, demo, history, trend, run-comparison, and artifact endpoints pass.
- [ ] HTML, JSON, JUnit, and SARIF outputs parse successfully.
- [ ] Reports contain no raw demo values.
- [ ] Schema baseline create and compare pass.
- [ ] Manual support export has no false Critical capsule.
- [ ] Critical capture is bounded and deduplicated.

## User experience

- [ ] TypeScript compiles with no errors.
- [ ] Keyboard flow, focus visibility, 320-pixel layout, dark mode, and reduced motion are reviewed.
- [ ] Screenshots match the release.
- [ ] README quick start matches the actual launcher.
- [ ] All BAT files use CRLF and pass the automated launch-contract test.
- [ ] Each root BAT detects an incomplete/unextracted ZIP and preserves a visible error.
- [ ] Python 3.13 is preferred and standard 64-bit Python 3.11–3.14 remains supported.
- [ ] Startup failure writes persistent status, logs, and a bounded diagnostic capsule/export attempt.
- [ ] Known limitations are current.

## Packaging

- [ ] Tests pass from source.
- [ ] Wheel builds and installs into an isolated environment with source checkout excluded.
- [ ] If a Windows wheelhouse is distributed, every wheel hash matches `WHEELHOUSE_MANIFEST.json` and bootstrap uses `--no-index`.
- [ ] Installed CLI runs its bundled demo.
- [ ] Source release ZIP passes integrity test.
- [ ] `SBOM.spdx.json` and third-party notices are current.
- [ ] `PACKAGE_METADATA.json` and `MANIFEST.json` are generated last.
- [ ] Every managed-file SHA-256 verifies in release mode.
- [ ] Exact release ZIP is scanned with normal endpoint protection before public distribution.
- [ ] Real repository URLs replace documentation placeholders only after publication.
- [ ] Hosted CI matrix and CodeQL complete on the published repository; local workflow presence is not treated as execution evidence.

## Publication

- [ ] Tag matches semantic version.
- [ ] Release notes summarize outcomes, changes, limitations, and upgrade steps.
- [ ] Demonstration video is no longer than 90 seconds.
- [ ] Screenshots include captions and alt text.
- [ ] Public issue templates do not request private datasets or secrets.
