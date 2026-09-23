# GNW V4 Deep Execution Evidence — 2026-09-10 Pass 01

## Status
CONTROLLED-STAGING / SECURITY-VALIDATED-SUBSET / NOT PRODUCTION-CERTIFIED

## Evidence rule
UNPROVEN != PASS. BLOCKED != PASS. Design/source inspection != runtime proof.

## Environment observed
- Node.js: v22.16.0
- npm: 10.9.2
- Docker: unavailable (`docker` command absent)
- PostgreSQL client/server binaries: unavailable (`psql`, `postgres` absent)
- npm cache entries: 0
- Registry resolution is unavailable in this sandbox; `npm ci --ignore-scripts` timed out.

## Executed checks

### E-001 Clean dependency install
Command: `npm ci --ignore-scripts`
Result: BLOCKED. The command timed out because the environment cannot obtain the required packages. No installed dependency tree was accepted as evidence.

### E-002 Typecheck
Command: `tsc --noEmit`
Result: BLOCKED. Global TypeScript ran but required `node` and `vitest/globals` type definitions are unavailable in the current incomplete dependency tree.

### E-003 Security sink scan
Command: `node scripts/security-sink-scan.mjs`
Result: PASS.
Observed: `raw_fetch_sinks=0; governed_fetch_sinks=4; execution_boundary_modules=4`.

### E-004 100-control evidence validator
Command: `node scripts/validate-100-evidence.mjs`
Result: STRUCTURAL PASS / RELEASE BLOCKED.
Observed: 100 records present; PASS=0, FAIL=0, BLOCKED=0, UNPROVEN=100.

### E-005 Capability cryptographic harness
The current source modules were transpiled in isolation using the installed global TypeScript compiler (with unrelated missing-type diagnostics). The emitted capability/security modules were then executed with Node.
Results:
- valid Ed25519 capability accepted
- actionDigest tampering rejected
- tenant tampering rejected
- nonce tampering rejected
- expiry tampering rejected
- capability tampering rejected
- destination tampering rejected
- TTL measured exactly 60,000 ms in the harness

This is component-level execution evidence, not full application evidence.

### E-006 Capability consumption concurrency model
A 20-thread SQLite concurrency harness executed the same conditional update pattern used by the repository:
`UPDATE ... SET consumed_at ... WHERE lease_id=? AND consumed_at IS NULL AND expires_at>?`
Observed: 1 winner, 19 denials.
This validates the conditional-consume pattern under SQLite locking, but is NOT a PostgreSQL production concurrency proof.

### E-007 Egress helper execution
Current `security.ts` was executed directly with Node TypeScript stripping.
Observed:
- HTTPS URL parsing accepted for `https://example.com`.
- private/local host classifier rejected localhost, loopback, RFC1918, link-local and ::1 examples.
- real `governedFetch('https://example.com')` was attempted; DNS failed with `EAI_AGAIN`, so live network behavior remains unproven.

### E-008 Source review finding and hardening
A race window was identified in `executeExternal`: the final interlock was checked before audit-admission work, allowing the interlock state to change during that work. A second `assertFinalInterlock()` was inserted immediately before the irreversible `effect()` call. Security sink scan remained PASS after the change.

## Artifact identity
Pre-pass RC2 SHA-256:
`9282e02b88bd41d79ab81fb4ca16bf0de5c37eeede1e8a1998803baf8a453df6`

The source was modified after that hash by the final-interlock hardening above. Therefore the old artifact hash must NOT be used for a release claim after this change.

## Not yet proven
1. Clean reproducible npm installation.
2. Full typecheck/build/test suite.
3. PostgreSQL 15 real multi-session concurrency.
4. Multi-instance replay and budget races.
5. Real controlled HTTPS provider/redirect/DNS-rebinding tests.
6. Backup/restore anti-resurrection.
7. Distributed kill-switch fencing and in-flight cancellation.
8. Secret/signing-key rotation and revocation.
9. Docker build/runtime execution.
10. Vulnerability scan with advisory database.
11. SBOM completeness.
12. Build provenance verification.
13. Artifact signature verification.
14. Reproducible artifact build.
15. Full IRS-001 through IRS-100 adversarial execution with effect/audit evidence.
16. Independent release review.

## Certification decision
NOT PRODUCTION-CERTIFIED.

The current evidence supports a hardened staging candidate with several directly executed component-level controls. It does not support a 100% production certification claim.
