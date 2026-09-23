# GNW Security Remediation Status — 12 September 2026

## Release decision

**Production Ready:** NO  
**International Certification Ready:** NO  
**Security Gate:** FAIL  
**Overall Release Decision:** DENY  
**Risk Classification:** CRITICAL  
**Current classification:** Hardened Staging Candidate / Controlled Security-Validated Subset

This report records fresh source changes and executable verification. It does not authorize deployment or certification.

## Remediations applied

### Guest-admin path

`POST /api/auth/guest` no longer creates or elevates a user. It returns HTTP `410` with `guest_access_disabled`. The previous `ensureGuestUser` admin-session path is no longer reachable from the API.

### Google authentication

The previous implementation decoded an unverified JWT payload and trusted a caller-supplied email, then provisioned or elevated an admin user. That behavior has been removed. `POST /api/auth/google` now returns HTTP `503` with `google_oidc_verifier_not_configured` until a real OIDC verifier with issuer, audience, signature, nonce, and claim validation is implemented and configured.

This is a fail-closed mitigation, not a completed Google/OIDC feature.

### Memory tenant isolation

In-memory vector records now carry `tenantKey`. Store-side supersession invalidates only records belonging to the authenticated tenant. Query-side scanning skips every record from another tenant. Store and query also reject a capability lease whose tenant does not equal the authenticated user tenant.

### Executor egress

Remote executor calls now use `assertEgressUrl` and `governedFetch` rather than raw `fetch`. The executor endpoint must be HTTPS, must be allowlisted, must resolve without unsafe private/local addresses, uses manual redirect handling, and is subject to the governed response-size limit.

## Fresh executable evidence

| Check | Result |
|---|---:|
| `npm run typecheck` | Pass |
| Targeted auth and memory tests | **35/35 pass** |
| Full Vitest suite | **92/92 pass; 10/10 files** |
| `npm run build` | Pass |
| Security sink scan | Pass: `raw_fetch_sinks=0`, `governed_fetch_sinks=7` |
| Clean `npm ci` | Pass |
| Non-breaking `npm audit fix` | Applied |
| Final `npm audit --audit-level=high` | **Fail: 6 vulnerabilities remain** |

## Remaining blockers

The current dependency graph still reports four moderate, one high, and one critical vulnerability. The remaining advisory chain includes Vitest/Vite/esbuild issues that require breaking upgrades to the current major versions; these were not applied automatically because they require compatibility review and a fresh full regression run.

Real Google/OIDC verification is not yet implemented; the endpoint is disabled rather than certified. A hostile-code sandbox has not been independently proven against the required adversarial corpus. RLS and multi-instance PostgreSQL adversarial evidence remain incomplete. SSRF redirect/DNS-rebinding evidence, distributed kill-switch fencing, audit-failure interlock, backup/restore anti-resurrection, secret rotation, SBOM, provenance, signing, reproducible build, LIET-01→26 executable ledger, IRS-001→100 execution ledger, and independent release reviews remain pending.

## Decision

> **Fresh remediation evidence is positive for four P0 fail-closed controls and the current regression suite, but the artifact is not production-ready or certification-ready. Release remains DENY until the remaining blockers have fresh executable evidence on the same artifact digest.**
