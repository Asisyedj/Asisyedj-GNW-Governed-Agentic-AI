# GNW Step 5 — Secrets and Key-Management Boundary

**Status:** Step 5 code boundary implemented and unit-verified. External KMS/Secrets Manager rotation evidence remains pending until a provider and staging credentials are supplied.

## Decision

GNW must not pass long-lived secret values to agents, models, browser tools, or sandbox processes. The control plane issues a short-lived, tenant-bound, task-bound, action-digest-bound lease. A provider-side adapter resolves the value only at the approved destination and only after the lease is validated.

The repository contains no production secret values. Environment variables remain bootstrap references for local development and process startup; production deployment must source them from a managed secret system and must not commit them to images, logs, artifacts, or evidence bundles.

## Implemented controls

| Control | Implementation | Evidence |
|---|---|---|
| Provider-neutral contract | `src/server/secrets.ts` defines `SecretProvider` | Typecheck and focused tests |
| Short-lived access | Lease TTL is bounded by `SecretBroker.maxTtlMs` | Invalid and expired TTL tests |
| Exact scope | Lease binds tenant, task, action digest, host, path, and method | Binding and destination mismatch tests |
| Integrity | Lease digest detects modification | Tamper test |
| Revocation | Provider version changes and explicit lease revocation invalidate old leases | Rotation and revocation tests |
| No value disclosure | `secretReference()` returns a broker marker, not a secret | Non-disclosure test |

## What this proves

The GNW-side contract no longer requires exposing a raw secret to a governed tool. A stale, revoked, expired, modified, cross-tenant, cross-task, wrong-action, or wrong-destination lease fails closed.

## What this does not prove

The memory provider is a test double. It does not prove KMS policy enforcement, provider audit logs, HSM protection, multi-instance revocation propagation, secret version destruction, network proxy enforcement, or zero-downtime rotation in a real deployment. Those require a selected provider, staging environment, credentials, and an independent reviewer.

## Required external evidence

1. Provision one managed secret service with least-privilege workload identity and audit logging.
2. Store database, session, grant-signing, OIDC, provider, executor, and object-storage credentials there.
3. Run a staging rotation rehearsal with overlap and explicit expiry for old versions.
4. Prove that old provider credentials, old signing keys, revoked sessions, and stale leases fail across two application instances.
5. Capture provider/version, timestamps, artifact digest, test worker count, logs, cleanup result, and reviewer identity.
6. Repeat the exercise during a restore drill and confirm that revocation state does not resurrect.

## Release decision

This step is accepted as a **code-boundary hardening step**, not as production certification. The overall release remains **DENY** until external secret-manager, PostgreSQL, sandbox, egress, recovery, dependency, supply-chain, and independent-review gates pass on the same artifact digest.

**Next step:** Step 6 — external egress and interlock enforcement, including DNS rebinding, redirect, private-address, response-limit, and distributed kill-switch evidence.

## References

[1]: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html "OWASP Secrets Management Cheat Sheet"
[2]: https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final "NIST Special Publication 800-57 Part 1 Revision 5"
