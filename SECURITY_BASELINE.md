# GNW v3 Security Baseline

## Non-negotiable invariants

1. Model output never creates authority.
2. Every privileged effect crosses the PEP/PDP and execution gateway.
3. Approval is bound to the exact canonical action digest.
4. Grants are short-lived and signed by a trusted issuer in production.
5. Nonces are durable and unique across instances.
6. Aggregate task budgets are reserved atomically.
7. The kill switch/circuit breaker is rechecked at the effect boundary.
8. External destinations are HTTPS and explicitly allowlisted; private/local destinations are denied.
9. Artifact keys are normalized and path-contained; byte ceilings are enforced.
10. Audit event hashing uses the exact persisted reason and serialized payload digest; append is serialized.
11. Sessions are durable and revocable; logout invalidates the presented token.
12. Global audit verification is admin-only; task audit is tenant-bound.

## Production dependencies outside the app

- TLS termination and secure headers
- Postgres HA/backups/PITR
- managed secret/KMS storage
- network egress proxy or equivalent DNS-aware policy enforcement
- object storage with server-side encryption and lifecycle controls
- centralized logs/SIEM and alerting
- image signing/SBOM/dependency scanning
- CI adversarial release gates
- disaster-recovery restore drills


## Current verification boundary (2026-09-09)

The core policy/cryptographic layer has been exercised with 100 executable adversarial unit-level cases in an isolated Node harness: 100 passed, 0 failed. This is evidence for the policy core only; it is not evidence of full application or infrastructure production readiness.

The full npm test/typecheck/build/migration suite could not be executed in the current sandbox because the repository dependency tree is incomplete and the package registry/cache was unavailable. A production release MUST obtain a clean `npm ci`, then pass typecheck, unit/integration tests, build, dependency/security scanning, Postgres concurrency tests, staging deployment, backup/restore, and egress/kill-switch tests before the production gate can change to PASS.

A production kill switch is not treated as mathematically atomic with an already-in-flight external network request. The final application interlock must therefore be paired with an external egress proxy/network enforcement layer for hard-stop semantics.
