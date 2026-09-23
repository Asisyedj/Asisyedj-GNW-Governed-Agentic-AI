# GNW v4 Hardening Record — 2026-09-09

## Executed changes

1. **Signed execution capability lease** added. A governance ALLOW can mint a short-lived Ed25519-signed lease bound to request, action digest, subject, tenant, task, actor, capability and optional destination.
2. **Execution gateway enforcement** now requires a capability lease, verifies its signature and exact capability/action/task/actor binding, atomically consumes the lease, then performs the final interlock check immediately before the effect.
3. **Audit integrity defect fixed.** The audit hash now uses the exact persisted `reason`; payload digesting uses canonical serialization. The prior 180-character truncation mismatch is removed.
4. **LLM egress** is routed through the execution gateway when live provider access is enabled.
5. **Webhook egress** is fail-closed unless a capability lease is supplied; without a lease, notifications remain persisted/logged only.
6. **Provider polling** is now governed by a fresh signed, short-lived poll grant and execution capability lease instead of a direct network path.
7. **Artifact storage** is admitted through a dedicated `artifact.storage` capability and the same execution boundary.
8. **Private/local IPv6 and RFC1918/link-local destinations** are rejected by the egress helper in addition to the previous local/private checks.
9. **Capability lease TTL** is explicit configuration and is required to be positive and no longer than the grant TTL in production.
10. **Security sink CI gate** added. Network sink files must import the execution boundary; production gate also checks that the S3 SDK is explicitly declared.

## Verification executed in the current sandbox

- Server TypeScript transpile/syntax: **18 files, 0 syntax failures**.
- Capability lease cryptographic harness: **PASS** — valid lease accepted; capability tampering rejected; expiry tampering rejected.
- Audit hash regression harness: **PASS** — 181-character reason and 180-character reason produce different hashes.
- Full npm/Vitest/typecheck/build/migration: **BLOCKED** because dependencies were not installed in the sandbox.
- Docker build: **BLOCKED** because Docker is unavailable.
- S3 dependency declaration: **FAIL/BLOCKED** — `@aws-sdk/client-s3` is still absent from `package.json`; network access to npm registry is unavailable, so the lockfile cannot be safely regenerated here.
- Live Postgres concurrency: **UNPROVEN**.
- Real provider/network integration: **UNPROVEN**.
- KMS/HSM signing: **UNPROVEN**.
- Backup/restore: **UNPROVEN**.

## Security interpretation

This hardening materially closes the previously identified execution-boundary gap, but it does **not** justify a production-ready claim. In particular, the S3 dependency/lockfile issue and missing live infrastructure evidence remain release blockers.

`UNPROVEN != PASS` and `BLOCKED != PASS`.
