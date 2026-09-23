# Deployment

One codebase, three supported targets. The database adapter chooses its dialect from `DATABASE_URL`: anything starting with `postgres://` or `postgresql://` uses the `pg` pool, anything else is treated as a SQLite file path.

## Environment variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `SESSION_SECRET` | yes | — | 32+ characters. Boot is refused in production if it is short or a known placeholder. |
| `DATABASE_URL` | no | `file:./data/gnw.db` | Postgres URL, a SQLite path, or `file::memory:` for tests. Postgres is mandatory for production and serverless. |
| `PORT` | no | `8787` | Ignored on Vercel. |
| `NODE_ENV` | no | `development` | Set `production` on every real deployment. |
| `OWNER_EMAIL` / `OWNER_PASSWORD` | no | — | Seeds the administrator at boot instead of open registration. |
| `ALLOW_SELF_REGISTRATION` | no | `false` | The first account always succeeds; later ones need this flag. |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | no | — | Any OpenAI-compatible endpoint. Unset means governed offline mode. |
| `LLM_TIMEOUT_MS` | no | `45000` | Request timeout for the model call. |
| `VIDEO_PROVIDER_URL` / `VIDEO_PROVIDER_API_KEY` | no | — | Unset means the provider call is stubbed and clearly labelled. |
| `STORAGE_DRIVER` | no | `local` | `local` or `s3`. |
| `ARTIFACT_DIR` | no | `./data/artifacts` | Local driver only; point it at a mounted volume. |
| `S3_BUCKET` / `S3_REGION` / `S3_ENDPOINT` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | if `s3` | — | Incomplete S3 configuration refuses to boot in production. |
| `NOTIFY_WEBHOOK_URL` | no | — | Owner notifications are always persisted; the webhook is an extra channel. |
| `MAX_BUDGET_TOKENS` / `MAX_BUDGET_BYTES` | no | `100000` / `50000000` | Ceilings the gateway enforces on every grant. |
| `GRANT_TTL_MS` / `APPROVAL_TTL_MS` | no | `600000` / `900000` | Lifetime of a grant and of an approval window. |
| `COOKIE_SAME_SITE` | no | `lax` | Set `none` only when the browser app is served from a different origin than the API; it forces `Secure`, so HTTPS is required. |
| `CORS_ORIGIN` | no | — | Comma-separated explicit origins. Wildcard `*` is not accepted for credentialed production sessions. |
| `SESSION_TOKEN_IN_BODY` | no | `false` | Optional bearer transport for controlled clients. Prefer the HTTP-only session cookie. |
| `GNW_GRANT_ISSUER` / `GNW_GRANT_PRIVATE_KEY_PEM` / `GNW_GRANT_PUBLIC_KEY_PEM` | yes in production | — | Ed25519 issuer identity and key pair used to sign and verify frozen capability grants. |
| `GNW_ALLOWED_EGRESS_HOSTS` | yes when external provider is enabled | — | Explicit HTTPS host allowlist. Private/local destinations are blocked. |
| `GNW_EXECUTOR_URL` / `GNW_EXECUTOR_SHARED_TOKEN` | yes when `GNW_EXECUTOR_REQUIRED=true` | — | HTTPS endpoint and transport token for the separate executor; the token is not a substitute for lease verification. |
| `EXECUTOR_GRANT_ISSUER` / `EXECUTOR_GRANT_PUBLIC_KEY_PEM` | yes on the executor | — | The executor independently verifies the Ed25519 capability lease. Missing trust configuration causes every execution request to fail closed. |
| `MAX_ARTIFACT_BYTES` / `MAX_PROVIDER_RESPONSE_BYTES` | no | 20MB / 1MB | Hard byte ceilings at storage/provider boundaries. |

### Cross-origin hosting

The default deployment serves the built UI and the API from one origin, so the
`gnw_session` cookie is the only session channel and nothing above is needed. If
you host the static bundle separately, build it with `VITE_API_BASE=https://api.example.com`
and set `COOKIE_SAME_SITE=none` plus `CORS_ORIGIN` on the API. Where an
intermediary strips cookies entirely, additionally set `SESSION_TOKEN_IN_BODY=true`:
the same signed, expiring token is then also accepted as a bearer header and the
client keeps it in `sessionStorage` for the tab's lifetime.

Generate a secret with `node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"`.

## Target 1 — Node host with SQLite

Suitable for a single instance with a persistent disk: Render, Fly, Railway, or a VPS behind nginx.

```bash
npm ci
npm run build
DATABASE_URL=[REDACTED]
ARTIFACT_DIR=/var/lib/gnw/artifacts \
SESSION_SECRET=… NODE_ENV=production \
npm run migrate && npm start
```

The disk must be persistent and the app must run as a single instance — SQLite gives no cross-instance locking. Mount the volume at `/var/lib/gnw` and back it up; it holds the audit chain.

## Target 2 — Docker and docker-compose with Postgres

```bash
export SESSION_SECRET=$(node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))")
export OWNER_EMAIL=you@example.com OWNER_PASSWORD='a long passphrase'
docker compose up --build
```

The image is a multi-stage build ending on a non-root user with a healthcheck against `/api/health`. `/data` is a named volume for artifacts; Postgres has its own volume. Migrations run at boot, so a rolling restart is enough.

The separate executor is not optional when `GNW_EXECUTOR_REQUIRED=true`. Deploy `Dockerfile.executor` as a distinct service over HTTPS, set `EXECUTOR_SHARED_TOKEN`, `EXECUTOR_GRANT_ISSUER`, and `EXECUTOR_GRANT_PUBLIC_KEY_PEM`, and configure the app with the executor HTTPS URL. Do not run the executor over plaintext HTTP in production. The executor independently verifies the signed lease, task, actor, tenant, capability, and action digest before starting a sandbox process.

For a registry deployment:

```bash
docker build -t gnw-governed-agent:3.0.0 .
docker run -p 8787:8787 --env-file .env -v gnw-data:/data gnw-governed-agent:3.0.0
```

## Target 3 — Vercel serverless with external Postgres

The serverless filesystem is ephemeral and per-instance, so `assertProductionEnvironment` refuses to boot with SQLite there. Provision Postgres first (Neon, Supabase, Vercel Postgres or RDS).

```bash
vercel link
vercel env add SESSION_SECRET production
vercel env add DATABASE_URL production      # postgres://…?sslmode=require
vercel env add OWNER_EMAIL production
vercel env add OWNER_PASSWORD production
vercel deploy --prod
```

`vercel.json` builds the client to `dist/public`, serves it from the CDN, and routes `/api/*` to `api/index.ts`. The handler is created once per warm instance, so the pool and migration are not repeated per request. Use `STORAGE_DRIVER=s3` on this target — there is no writable local disk for artifacts.

## Migrations

`migrate()` is idempotent and runs automatically at boot on every target. Run it standalone with `npm run migrate`. It creates tables only; it never drops or rewrites a column, so a rollback to the previous image is always safe.

## Operations

- **Health**: `GET /api/health` is unauthenticated and cheap — use it for the load balancer.
- **Readiness**: `GET /api/ready` returns per-check state (`session_secret`, `database`, `owner_bootstrap`, `llm`, `storage`, `video_provider`, `notifications`) and returns 503 when a required check is missing.
- **Stop everything**: engage the kill switch in Controls, or `UPDATE system_controls SET value = 'true' WHERE key = 'kill_switch';`. It is persisted, so every instance honours it immediately and it survives a restart.
- **Verify evidence**: `GET /api/audit/verify` recomputes the whole hash chain and reports the first broken row.
- **Backups**: back up the database. It holds the audit chain, approvals and nonces; artifacts live in the object store or the mounted volume.

## Production security gate

The service is designed to fail closed when signed grant verification, database access, or the safety interlock cannot be evaluated. Production must use Postgres, durable object storage, a managed secret store, explicit egress allowlists, TLS, backups, monitoring, and a deployment process that executes the adversarial release suite. The application alone cannot prove provider/network safety; those controls must also exist in the network and infrastructure layers.

Generate an Ed25519 key pair with `node scripts/generate-grant-keys.mjs`.
