# Release Checklist

## Code and behavior

- [ ] Version is identical in package, `VERSION.txt`, dashboard, API, and metadata.
- [ ] Native and ODCS example contracts load.
- [ ] Passing demo returns exit code `0`.
- [ ] Failing demo returns exit code `2` and the expected finding counts.
- [ ] API health, upload, demo, and history endpoints pass.
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
- [ ] Wheel builds and installs into a clean virtual environment.
- [ ] Installed CLI runs its bundled demo.
- [ ] Source release ZIP passes integrity test.
- [ ] `SBOM.spdx.json` and third-party notices are current.
- [ ] `PACKAGE_METADATA.json` and `MANIFEST.json` are generated last.
- [ ] Every managed-file SHA-256 verifies in release mode.
- [ ] Exact release ZIP is scanned with normal endpoint protection before public distribution.
- [ ] Real repository URLs replace documentation placeholders only after publication.

## Publication

- [ ] Tag matches semantic version.
- [ ] Release notes summarize outcomes, changes, limitations, and upgrade steps.
- [ ] Demonstration video is no longer than 90 seconds.
- [ ] Screenshots include captions and alt text.
- [ ] Public issue templates do not request private datasets or secrets.
