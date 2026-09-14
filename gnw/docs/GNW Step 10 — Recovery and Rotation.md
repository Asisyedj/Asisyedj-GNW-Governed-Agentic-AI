# GNW Step 10 — Recovery and Rotation

**Status:** Durable session revocation, nonce consumption, interlocks, and secret-version invalidation exist in code. A real backup/restore and zero-downtime rotation rehearsal remains pending.

## Required recovery proof

Restore PostgreSQL and object storage into a clean environment. Verify audit-chain integrity, consumed approvals, consumed nonces, revoked sessions, disabled controls, engaged interlock state, artifact digests, and no resurrection of previously consumed authority.

## Required rotation proof

Rotate database credentials, session secret, OIDC secret, provider key, executor token, object-storage key, and grant-signing keys. Signing-key rotation must use an explicit overlap window followed by old-key expiry. Old credentials and old sessions must fail across every application instance.

## Current code boundary

The session table supports revocation. The secret broker binds leases to versions and rejects stale or revoked versions. The production environment gate requires external durable services. These controls are necessary but do not constitute a completed restore drill.

**Decision:** implementation boundary documented; release remains DENY pending provider-backed evidence.

**Next step:** Step 11 — supply-chain release.
