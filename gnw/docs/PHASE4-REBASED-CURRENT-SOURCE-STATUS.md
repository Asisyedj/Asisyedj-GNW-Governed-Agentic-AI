# GNW Phase 4 Rebased Current-Source Status — 2026-09-14

## Release decision

**PRODUCTION DENIED.** This branch is a current-source Phase 4 reconstruction candidate, not a production release.

## Base identity

- Base branch: `remediation/phase3-executor-fencing-skill-bypass-2026-09-14`
- Base commit: `e901ba86354dc81c299f336065f9cf87687f67d7`
- Base tree: `2761d66ee248feb3f54d8d2816fd84e806b77e42`
- Reconstruction branch: `remediation/phase4-rebased-current-2026-09-14`

## Reconstructed controls

The Phase 4 patch was not applied blindly because its original context did not match the current source. Its effect-fence semantics were reconstructed on the current source. The branch now contains a durable `effect_fences` table, unique effect and idempotency identities, generation-checked claim transitions, provider idempotency/fence headers for video, LLM and notification POST sinks, fenced artifact storage, pending-reconciliation state, and a PostgreSQL row lock for interlock-generation updates. The branch also adds production PostgreSQL `sslmode=verify-full` enforcement and fail-closed handling for unexpected migration errors.

The local fence tests cover one-winner concurrent claim behavior, stale-generation rejection, pending reconciliation, and a reference provider contract. These tests do not prove that an arbitrary real provider will enforce the headers.

## Executed evidence

| Check | Result |
|---|---|
| `npm ci` | PASS |
| `npm run typecheck` | PASS |
| `npm test` | PASS; 20 files, 122 tests |
| `npm run build` | PASS |
| `npm audit --omit=dev` | PASS |
| Phase 4 targeted fence/provider tests | PASS |
| Python OpenClaw smoke tests | PASS |
| Static sink scan | PASS for raw-fetch policy |
| Phase 1 fenced sink contract scan | PASS for video, LLM, notification and artifact storage sinks |
| Phase 2 PostgreSQL tenant context/RLS gate | PASS; scoped visibility and cross-tenant insert denial |
| PostgreSQL tenant tables | PASS; `relrowsecurity=true`, `relforcerowsecurity=true` |
| 100-case validator | BLOCKED; 100 UNPROVEN |
| Release evidence validator | BLOCKED |
| PostgreSQL two-instance fence claim | PASS; exactly one winner |
| PostgreSQL `tasks` RLS | PASS in fresh test database |

## Remaining mandatory blockers

The branch now has local Phase 1/2 implementation and executable evidence. It does not claim arbitrary real-provider enforcement until a real provider contract test is run, and it does not claim distributed kill-switch race proof, backup/restore anti-resurrection, secret rotation, signed SBOM/provenance, LIET-01 through LIET-26 execution evidence, independent security review, or accredited certification. Those require a real deployment/provider and independent evidence; they cannot be honestly converted to PASS by local unit tests.

The release manifest remains fail-closed and production remains denied until every mandatory gate has evidence-complete PASS status.
