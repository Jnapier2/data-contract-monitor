# Security and Privacy

## Default posture

The service binds to loopback by default. The Windows launcher reserves a socket before server startup and opens a browser only after the exact Data Contract Monitor service/version/build/per-launch identity responds. Modifying API requests require a random per-launch HttpOnly SameSite-strict session cookie, and supplied Origin headers are parsed and restricted to loopback hostnames.

No application feature uploads datasets to an external service. Temporary uploaded files are project-local and removed after job completion/cancellation. Reports contain filenames, hashes, aggregates, rule messages, and bounded row numbers rather than raw cell values.

## Input controls

Contracts and datasets are untrusted. File types and upload sizes are allow-listed/bounded; contract models reject unknown keys. Aggregate-reconciliation expressions use a restricted AST evaluator that allows numeric column names/constants and basic arithmetic only. Function calls, imports, attributes, subscripts, and arbitrary evaluation are rejected.

Regular expressions are still user-supplied Python regular expressions and are not sandboxed. Untrusted pathological expressions can consume excessive CPU; this remains a known limitation.

## State and evidence

SQLite stores durable run/job history locally. Report sets are staged under project `temp/`, hashed and verified, and atomically finalized into immutable per-run folders. The latest-run pointer updates only after successful publication.

Automatic diagnostics are reserved for terminal Critical conditions. A minimal capsule is written first, then one bounded Export20 may be attempted. Export20 performs no network call, repair, recursive export, project rescan, or managed-file rehash. Temporary ZIPs stage under root `temp/`; only integrity-tested final ZIPs appear under root `exports/`. Unknown/user ZIP files are not deleted by retention.

Diagnostic text redacts common credential assignments, the user-home path, IP addresses, and latest-result filenames. Redaction is best-effort and is not a substitute for reviewing a support package before public sharing.

## Release integrity

Normal release startup is blocked unless `VERSION.txt`, `PACKAGE_METADATA.json`, `MANIFEST.json`, `MANIFEST.sha256`, the managed-file hashes, and installed package identity agree. Support export remains read-only recovery evidence after an identity failure.

SHA-256 sidecars detect change only when obtained through a trusted channel; they do not provide publisher authentication. Authenticode signing is not claimed for 0.2.2.

## Deployment boundary

This release is intended for a trusted local workstation or controlled CI runner. Do not bind it publicly or place it behind a public reverse proxy without adding a deployment-specific authentication, authorization, TLS, rate/concurrency controls, proxy/origin configuration, audit policy, and threat model.

The first Windows environment build can contact the configured Python package index. Organizations should use a trusted index/mirror and their normal dependency-review controls.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
