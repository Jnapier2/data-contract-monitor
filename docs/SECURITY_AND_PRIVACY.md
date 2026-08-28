# Security and Privacy

## Default posture

- The web service binds to `127.0.0.1` by default. The launcher reserves the socket before startup and opens a browser only after the exact service/version/build health identity is confirmed.
- No application feature uploads datasets to an external service.
- Temporary API uploads are deleted at the end of each request.
- Reports contain filenames, file hashes, aggregate measurements, finding messages, and bounded row numbers—not raw cell values.
- Manual and automatic diagnostic exports redact common credentials, the user-home path, IP addresses, and uploaded filenames in the latest result.
- Release mode verifies every managed file against `MANIFEST.json` before normal startup.
- The release ZIP and manifest are hash-verified but not digitally signed; the sidecar hash detects accidental change only when obtained through a trusted channel and cannot authenticate a coordinated replacement of the ZIP and its sidecars.

## Threat model

The first release is intended for a trusted local workstation, CI runner, or isolated internal service. It does not provide multi-tenant authentication, authorization, network isolation, malware scanning, content-disarm, secrets management, or regulated-data certification.

Treat contracts and datasets as untrusted input. The application limits file types and request sizes, rejects unknown contract fields, and avoids evaluating expressions from the contract. Regular expressions are compiled but are not sandboxed; reviewers should avoid pathological patterns supplied by unknown parties.

## Privacy detector boundary

Privacy-field detection is a review aid. False positives and false negatives are expected. It does not inspect every value in a large column: sampling is intentionally bounded to protect performance and minimize processing. Do not use a signal alone to determine legal classification, retention, disclosure, or deletion.

## Service exposure

Do not bind to `0.0.0.0` or expose the FastAPI service through a public reverse proxy without adding, at minimum:

- authentication and authorization;
- TLS termination;
- request and concurrency limits;
- trusted-origin and proxy configuration;
- malware/content scanning appropriate to the environment;
- centralized audit logging and retention rules;
- a reviewed deployment threat model.

## Dependency installation

The application itself does not transmit datasets. The first Windows launch installs locked Python packages using the configured `pip` package index, which is a network action unless packages are already cached or supplied by an internal mirror. Organizations should use a trusted package index and their normal dependency-review process.

## Diagnostics

Automatic collection is reserved for terminal Critical events such as an uncaught fatal exception or runtime identity failure. Normal validation failures, handled warnings, cancellation, and transient request errors do not trigger an automatic package.

The collector:

- writes an atomic minimal capsule first;
- attempts one full export only when time and storage budgets permit;
- adds no more than 20 items and 5 MB of source material;
- uses a same-computer exporter lock;
- performs no network calls, repair, project rescan, or managed-file rehash;
- retains only its own bounded diagnostic ZIPs in the canonical project-local `exports/` directory.

## Reporting a vulnerability

Follow [SECURITY.md](../SECURITY.md). Do not include private datasets, credentials, or unredacted diagnostics in a public issue.
