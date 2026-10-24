# GNW Production Readiness and Recovery Checklist

This document is an operator checklist, not a claim that GNW is production-ready.

## Current known state

- The GitHub Actions workflow checks dependency installation, type-checking, tests, and build.
- Railway's last inspected production deployment crashed during startup because required production configuration was absent.
- Do not use `/api/health` alone as evidence of readiness; verify `/api/ready` and a real authenticated DB-backed smoke test.
- Do not run schema changes against production until migrations are versioned, tested against a disposable database/branch, backed up, and reviewed.

## Required Railway configuration

Set values in Railway's Variables UI or another approved secret manager. Never commit secrets or paste them into issue/PR/chat text.

### Application and bootstrap

- `NODE_ENV=production`
- `PORT=8787` (unless the service's configured port differs)
- `SESSION_SECRET`: generate a unique cryptographically random value of at least 32 characters.
- `DATABASE_URL`: PostgreSQL connection URL for the intended GNW database; enforce TLS with certificate verification (the current adapter recognizes `sslmode=require`).
- `OWNER_EMAIL`: the operator-selected bootstrap owner email.
- `OWNER_PASSWORD`: a strong, unique password generated and stored by the operator in a password manager.
- `ALLOW_SELF_REGISTRATION=false`
- `STORAGE_DRIVER=s3`
- `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`; configure `S3_ENDPOINT` only for an S3-compatible non-AWS endpoint and set the matching public base URL only if needed.
- `GNW_REQUIRE_SIGNED_GRANTS=true`
- `GNW_GRANT_ISSUER`, `GNW_GRANT_PRIVATE_KEY_PEM`, `GNW_GRANT_PUBLIC_KEY_PEM`: create a dedicated Ed25519 key pair and store the private key only as a secret.
- `GNW_EXECUTOR_URL`, `GNW_EXECUTOR_SHARED_TOKEN`: required while executor isolation is enabled. Use a private, authenticated service-to-service route and verify the executor implementation before enabling task execution.
- If outbound LLM/provider/webhook/S3 endpoints are configured, set `GNW_ALLOWED_EGRESS_HOSTS` to exact required hostnames; do not use wildcard entries.

Do not copy values from another environment. Do not create a fake or placeholder credential to make startup pass.

## Database gates before production

1. Take and verify a restorable backup/snapshot.
2. Confirm the intended database and schema using a read-only audit.
3. Add versioned, checksum-verified migrations and test forward migration plus rollback/recovery on a disposable Neon branch/database.
4. Reconcile the four schema tables currently missing from the audited database: `council_tasks`, `council_findings`, `council_transitions`, and `council_policy_decisions`. Do not manually create them in production until a reviewed migration exists.
5. Create a dedicated runtime DB role with only the privileges the application needs; it must not own the database and must not have `BYPASSRLS`, `CREATEDB`, or `CREATEROLE`.
6. Design tenant isolation and RLS policies before enabling RLS. Enabling RLS without matching policies can break application access; enabling no policies can also block expected reads/writes.
7. Verify TLS from the deployed application and confirm that the application connects to the intended host/database without printing connection strings.

## Executor and sandbox gates

- The task sandbox is not equivalent to OS/container isolation by itself.
- Keep executor credentials out of task child-process environments.
- Verify private-network routing and service authentication end-to-end.
- Require resource limits, restricted filesystem mounts, non-root execution, network egress restrictions, timeout/cancellation, and an adversarial regression suite before allowing untrusted task code.
- Confirm that interlocks and policy checks are enforced on the actual execution path, not merely available as helper functions.

## Safe rollout sequence

1. Keep the production service unchanged while configuration and migrations are incomplete.
2. Build and test on a non-production environment with separate credentials and disposable data.
3. Run typecheck, unit/integration tests, build, dependency/security checks, and adversarial executor tests.
4. Run DB migration tests, authenticated API smoke tests, readiness checks, and backup/restore rehearsal.
5. Review all changed files and logs for secrets/PII.
6. Deploy only after all gates pass; monitor startup, readiness, error rate, DB connectivity, and executor failures.
7. Have a tested rollback procedure. A green CI run is necessary but does not prove production readiness.
