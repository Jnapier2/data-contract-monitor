# Field Review — 2026-08-31

Support evidence SHA-256: `f4f5ef027b94d9e009a2b04e26aaf8d7a27426a084d7844aac50ad8cecc6f0fe`

The 16-entry Windows support ZIP passed CRC, duplicate-path, and path-safety checks. `VERSION.txt`, `PACKAGE_METADATA.json`, `MANIFEST.json`, `MANIFEST.sha256`, `KNOWN_GOOD_STATE.md`, and `CHANGELOG.md` matched the canonical v0.2.1 release byte-for-byte.

Generated state did not match that immutable identity: cached release verification, runtime environment, latest launch status, dashboard endpoint, and diagnostic runtime identity still identified v0.1.2. The physical project path also retained its original v0.1.0-era folder name. The folder name is non-authoritative; the stale generated identity is the material issue.

v0.2.2 resolves the ambiguity by reporting static-vs-cached coherence in diagnostics, retiring only known stale generated runtime identity on normal startup, invalidating stale dependency stamps, and rejecting unlisted protected execution files that can remain after overlay upgrades. Unknown/user files are preserved.
