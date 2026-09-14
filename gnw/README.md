# GNW Governed Agent — v4.0.0

A production-ready, self-contained rebuild of the Gigantic Wrecking Crew governed multi-agent workspace: a policy gateway that admits or refuses every agent action, a human approval queue for anything that touches the outside world, and a tamper-evident audit chain that records both.

Nothing here depends on a proprietary scaffold. `npm install && npm run dev` is the whole setup.

## What it does

An orchestrator plans; it never holds capability. Each specialist run is issued a single-use, time-boxed grant that binds subject, tenant, role, purpose, classification, operation, resource, agent, tool, scope and budgets. The gateway evaluates that grant and returns `ALLOW`, `DENY` or `STOP`. Sensitive operations — provider submissions, restricted data, provider tooling — cannot be admitted at all until a human reviewer approves the exact action digest.

Five specialists: research, analysis, engineering, QA, video producer. Each is confined to its own tool scope; a grant asking for a tool outside that scope is refused as `tool_not_allowed`.

## Quick start

```bash
cp .env.example .env          # set SESSION_SECRET (32+ chars)
npm install
npm run dev                   # API on :8787, client on :5173
```

The first account you register becomes the workspace administrator. Without `LLM_API_KEY` the app runs in **governed offline mode**: deterministic specialist output, clearly labelled, with the full governance, approval and audit path exercised end to end. Set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` for any OpenAI-compatible provider to enable live generation.

## Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | API and client with hot reload |
| `npm run build` | Client bundle to `dist/public`, server bundle to `dist/server` |
| `npm start` | Run the built server |
| `npm run migrate` | Apply schema migrations (idempotent) |
| `npm run typecheck` | Strict TypeScript check |
| `npm test` | Vitest: governance matrix, audit chain, HTTP routes |

## Deployment

Three supported targets, one codebase — see [DEPLOYMENT.md](DEPLOYMENT.md).

1. **Node host** (Render, Fly, Railway, a VPS) with embedded SQLite.
2. **Docker / docker-compose** with Postgres.
3. **Vercel serverless** with external Postgres (Neon, Supabase, RDS).

`assertProductionEnvironment` refuses to boot on a weak session secret, on SQLite under a serverless runtime, or on an incomplete S3 configuration. `GET /api/ready` returns a per-check readiness report that the Controls screen renders.

## Security posture

- Sessions are HMAC-signed HTTP-only cookies; passwords use scrypt with per-user salts.
- Mutations require the `x-gnw-client: web` header, which blocks cross-site form posts.
- Failed logins are rate-limited per email and IP.
- Tenancy is checked on every read and write; approvals are bound to the tenant that requested them.
- Separation of duties: a non-admin requester cannot approve their own action.
- Nonces for grants and approvals are stored in the database with a uniqueness constraint, so replay protection survives restarts and holds across multiple instances.
- Kill switch and circuit breaker are persisted, so a stop holds across restarts and instances.
- Artifacts are stored in the filesystem or S3; the database keeps only key, digest and size.

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) — the three targets, environment variables, migrations, rollback.
- [ARCHITECTURE.md](ARCHITECTURE.md) — trust boundaries, grant lifecycle, audit chain, data model.
- [ACCEPTANCE.md](ACCEPTANCE.md) — the live acceptance checklist to run against a deployed instance.
- `docs/inherited/` — the original architecture pack, findings and controls, adversarial test matrix, release gates, and the Python reference implementation this rebuild preserves.
- `docs/diagrams/` — system context, governance authority, multi-agent trust, execution gateway, audit sequence.

## GNW v3 hardened security plane

This release hardens the original control-plane design with:

- canonical action envelopes and exact parameter/content digests;
- optional-but-required-in-production Ed25519-signed grants with a trusted issuer;
- durable, revocable sessions;
- atomic audit-chain append serialization;
- exact persisted-reason hashing (fixes the historical truncation/hash mismatch);
- aggregate task budget reservations;
- final kill-switch/circuit-breaker recheck at the external effect boundary;
- HTTPS + explicit egress host allowlisting with local/private destination blocking;
- storage-key containment and byte ceilings;
- admin-only global audit verification and mandatory separation of approval duties;
- a 100-case adversarial release manifest and production security baseline.

**Important:** code hardening is not the same as production certification. Production status remains blocked until CI, Postgres concurrency, provider/network sandboxing, backups/restore, secret rotation, dependency scanning, and the adversarial release suite are executed with evidence.
