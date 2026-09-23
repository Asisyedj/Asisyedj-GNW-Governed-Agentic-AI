# GNW v3 Hardened — Verification Record

Date: 2026-09-09

## Executed in the current sandbox

| Gate | Result | Evidence |
|---|---|---|
| TypeScript transpile/syntax check | PASS | 16 production source files transpiled with zero diagnostics |
| Core security adversarial harness | PASS | 100/100 executed, 0 failed |
| Ed25519 signature verification | PASS | valid signature accepted; nonce/time/identity/action tampering rejected |
| Policy fail-closed tests | PASS | context, classification, tool/scope, time, budget, approval, replay, interlock |
| Egress policy tests | PASS | HTTPS, allowlist, private/local destination rejection |
| Production environment gate | PASS | incomplete production config rejected; complete configuration accepted |
| Grant-key generator | PASS | Ed25519 key pair generated successfully |
| Full `npm test` | BLOCKED | Vitest executable unavailable because dependency installation could not complete |
| Full `npm run typecheck` | BLOCKED | required local type packages unavailable |
| Full `npm run build` | BLOCKED | Vite/esbuild executables unavailable |
| DB migration | BLOCKED | `tsx` executable unavailable |
| Docker build | BLOCKED | Docker is not installed in the current sandbox |
| Postgres multi-instance concurrency | UNPROVEN | no live Postgres deployment in the current sandbox |
| Real provider/network integration | UNPROVEN | deliberately not executed against external side effects |
| Windows/UNC/reparse filesystem tests | UNPROVEN | current sandbox is Linux and no production filesystem was used |
| Disaster recovery/backup restore | UNPROVEN | no production database/object store available |

## Important hardening changes

1. Grant signatures now cover the complete grant except the signature field, including nonce and validity timestamps.
2. Production `GovernanceService` is wired to the trusted issuer public key.
3. Provider approval stores the complete signed grant; submission no longer regenerates nonce/time.
4. Approval review and policy evaluation both enforce separation of duties.
5. Grant TTL is bounded by `MAX_GRANT_TTL_MS`.
6. Postgres aggregate budget reservation locks the task row with `FOR UPDATE`.
7. Interlock updates use an atomic upsert transaction.
8. LLM, provider, webhook and custom S3 egress are HTTPS/allowlist checked.
9. Direct artifact storage paths pass through the execution boundary and final interlock.
10. Production refuses SQLite, self-registration, unsigned grants, missing owner bootstrap, and incomplete durable storage configuration.
11. Specialist execution stops immediately after a STOP decision.
12. Video completion verifies tenant and provider-job binding before storage.

## Production decision

**NOT YET PRODUCTION-READY / RELEASE BLOCKED.**

The core governance/security layer is substantially hardened and has executable local evidence, but a production claim requires the blocked full dependency/build/test pipeline plus live staging evidence for Postgres concurrency, network egress, backup/restore, secret rotation, container security, and the real execution sinks.

`UNPROVEN` is not `PASS`.
`BLOCKED` is not `PASS`.
