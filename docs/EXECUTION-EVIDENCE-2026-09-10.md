# GNW V4 — Execution Evidence Report — 2026-09-10

## Release verdict

**NOT PRODUCTION-READY / RELEASE BLOCKED.**

No production certification is claimed. This report records only evidence actually executed in the available environment.

## Environment

- Node: v22.16.0
- npm: 10.9.2
- Docker: unavailable (`docker: command not found`)
- PostgreSQL client/server: unavailable (`psql: command not found`; no `postgres` binary)
- Internet/DNS to npm registry: unavailable (`registry.npmjs.org` did not resolve)

## Executed successfully

1. **Source syntax validation**
   - 36 TypeScript/TSX files inspected with the TypeScript parser.
   - Result: `36 files / 0 syntax failures`.

2. **Ed25519 grant/canonicalization harness**
   - Valid signature accepted.
   - Tampered action rejected.
   - HTTPS/private/local destination checks rejected unsafe targets.
   - IPv4/IPv6 localhost and metadata addresses rejected.

3. **Capability lease cryptographic harness**
   - Valid lease accepted.
   - Expired lease rejected.
   - Action-digest tampering rejected.

4. **Security sink scan**
   - Raw network sinks: `0`.
   - Governed egress sinks: `4`.
   - External modules checked: LLM, video, notification, storage.
   - Result: PASS.

5. **Independent-review matrix validator**
   - IRS-001 through IRS-100 present, ordered and unique.
   - 10 domains × 10 subjects.
   - Evidence schema present.
   - Result: PASS for matrix structure only.

6. **100-evidence validator**
   - 100 records structurally valid.
   - PASS=0, FAIL=0, BLOCKED=0, UNPROVEN=100.
   - Correctly blocks release.

7. **Package-lock root version consistency**
   - package.json: 4.0.0
   - package-lock root: 4.0.0
   - Result: PASS.

## Blocked execution

### Clean dependency installation

`npm ci --offline` failed because required package tarballs were not cached. Online registry access also failed because `registry.npmjs.org` could not be resolved.

Therefore these could not be truthfully executed:

- npm ci
- typecheck with project dependencies
- Vitest suite
- production Vite/esbuild build
- npm audit

The local `node_modules` directory is not treated as a valid clean-install substitute.

### Docker/container staging

Blocked because Docker is not installed/available.

Therefore unproven:

- image build
- non-root runtime execution
- read-only root filesystem
- capability drop
- no-new-privileges
- seccomp enforcement
- healthcheck
- container resource limits

### Real PostgreSQL concurrency

Blocked because PostgreSQL binaries/server are unavailable.

Therefore unproven:

- concurrent capability consumption
- aggregate budget reservation
- multi-instance replay protection
- audit append serialization
- failover behavior
- row-lock correctness under contention

### Real external egress/provider testing

Blocked because no controlled provider endpoint and no network staging environment are available.

The code was strengthened so provider/storage/webhook paths use the governed HTTPS egress helper with DNS-address pinning, allowlist checks, private-address blocking and manual redirect handling, but live network evidence is still required.

### Backup/restore

No real Postgres/object-store backup environment is available. Anti-resurrection behavior therefore remains UNPROVEN.

### Kill-switch/failover

The application contains durable interlock state and final interlock checks, but distributed kill-switch propagation, fencing and failover have not been demonstrated across real instances. They remain UNPROVEN.

### Secret/key rotation

No KMS/HSM or production secret-management environment is available. Rotation evidence remains UNPROVEN.

### 100 adversarial cases

The 100-case ledger is intentionally left UNPROVEN. Existing unit/integration tests do not constitute execution of all 100 adversarial subjects.

## Code changes made during this execution pass

- Corrected `package-lock.json` root version to match package version 4.0.0.
- Fixed production gate self-matching its own forbidden-install grep.
- Removed Vitest Jest-style `--runInBand` argument from the production gate.
- Strengthened `security-sink-scan.mjs` so it detects governed egress sinks rather than passing vacuously when raw `fetch()` calls disappear.
- Added a DNS-pinned `governedFetch()` implementation that resolves all addresses, rejects unsafe/private destinations, and connects to the vetted IP while preserving TLS SNI/Host semantics.
- Routed LLM, video provider, webhook and S3 egress through the governed egress helper.
- Added production Compose hardening: read-only root filesystem, no-new-privileges, dropped capabilities, tmpfs for temporary paths, PID limit and memory limit.

## Remaining production gates

All of the following must produce real evidence before certification:

1. Clean `npm ci`.
2. Full typecheck.
3. Full Vitest suite.
4. Production build.
5. Dependency vulnerability scan.
6. Real Docker build and hardened runtime inspection.
7. Real PostgreSQL concurrency tests.
8. Multi-instance replay/budget/failover tests.
9. Controlled egress/provider tests including DNS rebinding and redirect attacks.
10. Backup/restore anti-resurrection test.
11. Kill-switch propagation and fencing test.
12. Secret/KMS key rotation tests.
13. SBOM generation and artifact/provenance/signature verification.
14. Reproducibility/rebuild comparison.
15. Execution of IRS-001 through IRS-100 with retained evidence.
16. Independent release review.

## Certification rule

`DESIGN != EXECUTION EVIDENCE`

`UNPROVEN != PASS`

`BLOCKED != PASS`

The release gate must remain closed until every required P0 control has executable evidence and no unexplained critical blocker remains.
