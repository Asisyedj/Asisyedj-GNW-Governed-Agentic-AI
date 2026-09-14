import "dotenv/config";
import { generateKeyPairSync, randomBytes } from "node:crypto";

const devEphemeralKeys = generateKeyPairSync("ed25519", {
  privateKeyEncoding: { type: "pkcs8", format: "pem" },
  publicKeyEncoding: { type: "spki", format: "pem" },
});

export type Readiness = "ok" | "missing" | "degraded";

export type ReadinessReport = {
  ready: boolean;
  checks: Record<string, Readiness>;
  notes: Record<string, string>;
};

function bool(value: string | undefined, fallback = false) {
  if (value === undefined) return fallback;
  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

function int(value: string | undefined, fallback: number) {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function councilMode(value: string | undefined): "disabled" | "shadow" {
  const mode = (value ?? "disabled").trim().toLowerCase();
  if (mode !== "disabled" && mode !== "shadow") throw new Error("GNW_COUNCIL_MODE must be disabled or shadow");
  return mode;
}

export function loadEnv(source: NodeJS.ProcessEnv = process.env) {
  const nodeEnv = source.NODE_ENV ?? "development";
  const isProduction = nodeEnv === "production";
  return {
    nodeEnv,
    isProduction,
    isTest: nodeEnv === "test",
    port: int(source.PORT, 8787),
    sessionSecret: source.SESSION_SECRET ?? (isProduction ? "" : "dev-insecure-secret-do-not-use-in-production"),
    databaseUrl: source.DATABASE_URL ?? "file:./data/gnw.db",
    postgresSslRequired: bool(source.GNW_POSTGRES_SSL_REQUIRED, isProduction),
    ownerEmail: (source.OWNER_EMAIL ?? "").trim().toLowerCase(),
    ownerPassword: source.OWNER_PASSWORD ?? "",
    allowSelfRegistration: bool(source.ALLOW_SELF_REGISTRATION, false),
    llmBaseUrl: (source.LLM_BASE_URL ?? "https://api.openai.com/v1").replace(/\/$/, ""),
    llmApiKey: source.LLM_API_KEY ?? "",
    llmModel: source.LLM_MODEL ?? "gpt-4o-mini",
    llmTimeoutMs: int(source.LLM_TIMEOUT_MS, 45_000),
    storageDriver: (source.STORAGE_DRIVER ?? "local") as "local" | "s3",
    artifactDir: source.ARTIFACT_DIR ?? "./data/artifacts",
    s3: {
      bucket: source.S3_BUCKET ?? "",
      region: source.S3_REGION ?? "",
      endpoint: source.S3_ENDPOINT ?? "",
      accessKeyId: source.S3_ACCESS_KEY_ID ?? "",
      secretAccessKey: source.S3_SECRET_ACCESS_KEY ?? "",
      publicBaseUrl: source.S3_PUBLIC_BASE_URL ?? "",
    },
    videoProvider: source.VIDEO_PROVIDER ?? "stub",
    videoProviderUrl: source.VIDEO_PROVIDER_URL ?? "",
    videoProviderApiKey: source.VIDEO_PROVIDER_API_KEY ?? "",
    videoProviderIdempotencyRequired: bool(source.VIDEO_PROVIDER_IDEMPOTENCY_REQUIRED, isProduction),
    videoProviderFencingRequired: bool(source.VIDEO_PROVIDER_FENCING_REQUIRED, isProduction),
    notifyWebhookUrl: source.NOTIFY_WEBHOOK_URL ?? "",
    // "none" is required only when the client is served from a different origin
    // than the API; it forces Secure and therefore HTTPS.
    cookieSameSite: ((source.COOKIE_SAME_SITE ?? "lax").toLowerCase() as "lax" | "strict" | "none"),
    corsOrigin: source.CORS_ORIGIN ?? "",
    // Returns the signed session token in the auth response so a client behind
    // a cookie-stripping proxy can send it as a bearer token. Off by default.
    sessionTokenInBody: bool(source.SESSION_TOKEN_IN_BODY, false),
    maxBudgetTokens: int(source.MAX_BUDGET_TOKENS, 100_000),
    maxBudgetBytes: int(source.MAX_BUDGET_BYTES, 50_000_000),
    grantTtlMs: int(source.GRANT_TTL_MS, 600_000),
    approvalTtlMs: int(source.APPROVAL_TTL_MS, 900_000),
    grantIssuer: source.GNW_GRANT_ISSUER ?? "gnw-local-issuer",
    grantPrivateKeyPem: source.GNW_GRANT_PRIVATE_KEY_PEM ?? (isProduction ? "" : devEphemeralKeys.privateKey),
    grantPublicKeyPem: source.GNW_GRANT_PUBLIC_KEY_PEM ?? (isProduction ? "" : devEphemeralKeys.publicKey),
    requireSignedGrants: bool(source.GNW_REQUIRE_SIGNED_GRANTS, isProduction),
    allowedEgressHosts: (source.GNW_ALLOWED_EGRESS_HOSTS ?? "").split(",").map(v => v.trim().toLowerCase()).filter(Boolean),
    maxArtifactBytes: int(source.MAX_ARTIFACT_BYTES, 20_000_000),
    maxProviderResponseBytes: int(source.MAX_PROVIDER_RESPONSE_BYTES, 1_000_000),
    maxGrantTtlMs: int(source.MAX_GRANT_TTL_MS, 600_000),
    capabilityLeaseTtlMs: int(source.GNW_CAPABILITY_LEASE_TTL_MS, 60_000),
    executorUrl: (source.GNW_EXECUTOR_URL ?? "").replace(/\/$/, ""),
    executorSharedToken: source.GNW_EXECUTOR_SHARED_TOKEN ?? "",
    executorRequired: bool(source.GNW_EXECUTOR_REQUIRED, isProduction),
    councilMode: councilMode(source.GNW_COUNCIL_MODE),
  };
}

export type Env = ReturnType<typeof loadEnv>;

export const ENV: Env = loadEnv();

export function readinessReport(env: Env = ENV): ReadinessReport {
  const checks: Record<string, Readiness> = {
    session_secret: env.sessionSecret && env.sessionSecret.length >= 32 ? "ok" : "missing",
    database: env.databaseUrl ? "ok" : "missing",
    owner_bootstrap: env.ownerEmail && env.ownerPassword ? "ok" : "degraded",
    llm: env.llmApiKey ? "ok" : "degraded",
    storage: env.storageDriver === "s3" ? (env.s3.bucket && env.s3.accessKeyId ? "ok" : "missing") : "degraded",
    video_provider: env.videoProviderUrl ? "ok" : "degraded",
    notifications: env.notifyWebhookUrl ? "ok" : "degraded",
    grant_signing: env.requireSignedGrants && env.grantPrivateKeyPem && env.grantPublicKeyPem ? "ok" : env.requireSignedGrants ? "missing" : "degraded",
  };
  const notes: Record<string, string> = {
    owner_bootstrap: checks.owner_bootstrap === "ok" ? "Owner account seeded from environment." : "No OWNER_EMAIL/OWNER_PASSWORD: create the first account through /register.",
    llm: checks.llm === "ok" ? "OpenAI-compatible endpoint configured." : "Governed offline mode: specialists return deterministic planning output and make no external call.",
    storage: checks.storage === "ok" ? "External object storage configured." : env.storageDriver === "local" ? "Local artifact directory: single-node only, not durable on serverless." : "S3 driver selected but incomplete.",
    video_provider: checks.video_provider === "ok" ? "Provider endpoint configured." : "Stub provider: the approval and job lifecycle runs, no external generation is performed.",
    notifications: checks.notifications === "ok" ? "Webhook configured." : "Notifications are persisted and logged only.",
    grant_signing: checks.grant_signing === "ok" ? "Ed25519 grant issuer configured." : "Production requires signed grants with a trusted issuer key pair.",
  };
  // Only hard failures ("missing") block readiness. Degraded is a documented,
  // safe operating mode and is surfaced to operators instead of hidden.
  const ready = Object.values(checks).every(value => value !== "missing");
  return { ready, checks, notes };
}

/** Fail fast at startup in production rather than serving a half-configured control plane. */
export function assertProductionEnvironment(env: Env = ENV) {
  if (!env.isProduction) return;
  const failures: string[] = [];
  if (!env.sessionSecret || env.sessionSecret.length < 32) failures.push("SESSION_SECRET must be set to at least 32 characters");
  if (!env.databaseUrl) failures.push("DATABASE_URL must be set");
  if (env.databaseUrl.startsWith("file:")) failures.push("SQLite is not an accepted production database; set a postgres:// DATABASE_URL");
  if ((env.databaseUrl.startsWith("postgres://") || env.databaseUrl.startsWith("postgresql://")) && env.postgresSslRequired && !/sslmode=verify-full/i.test(env.databaseUrl)) failures.push("Production PostgreSQL requires sslmode=verify-full");
  if (!env.ownerEmail || !env.ownerPassword) failures.push("OWNER_EMAIL and OWNER_PASSWORD are required in production bootstrap");
  if (env.allowSelfRegistration) failures.push("ALLOW_SELF_REGISTRATION must be false in production");
  if (env.storageDriver !== "s3") failures.push("Production requires durable S3-compatible object storage; set STORAGE_DRIVER=s3");
  if (env.storageDriver === "s3" && !(env.s3.bucket && env.s3.accessKeyId && env.s3.secretAccessKey)) failures.push("S3 storage selected but S3_BUCKET/S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY are incomplete");
  if (!env.requireSignedGrants) failures.push("GNW_REQUIRE_SIGNED_GRANTS must be true in production");
  if (env.requireSignedGrants && !(env.grantIssuer && env.grantPrivateKeyPem && env.grantPublicKeyPem)) failures.push("Signed grant issuer keys are required in production");
  if (env.grantTtlMs <= 0 || env.grantTtlMs > env.maxGrantTtlMs) failures.push("GRANT_TTL_MS must be positive and <= MAX_GRANT_TTL_MS");
  if (env.capabilityLeaseTtlMs <= 0 || env.capabilityLeaseTtlMs > env.grantTtlMs) failures.push("GNW_CAPABILITY_LEASE_TTL_MS must be positive and <= GRANT_TTL_MS");
  if (env.llmApiKey && env.allowedEgressHosts.length === 0) failures.push("Configured LLM requires GNW_ALLOWED_EGRESS_HOSTS");
  if (env.videoProviderUrl && env.allowedEgressHosts.length === 0) failures.push("Configured provider requires GNW_ALLOWED_EGRESS_HOSTS");
  if (env.videoProviderUrl && !env.videoProviderIdempotencyRequired) failures.push("Configured provider requires VIDEO_PROVIDER_IDEMPOTENCY_REQUIRED=true in production");
  if (env.videoProviderUrl && !env.videoProviderFencingRequired) failures.push("Configured provider requires VIDEO_PROVIDER_FENCING_REQUIRED=true in production");
  if (env.notifyWebhookUrl && env.allowedEgressHosts.length === 0) failures.push("Configured notification webhook requires GNW_ALLOWED_EGRESS_HOSTS");
  if (env.s3.endpoint && env.allowedEgressHosts.length === 0) failures.push("Configured S3 endpoint requires GNW_ALLOWED_EGRESS_HOSTS");
  if (env.allowedEgressHosts.some(host => host === "*" || host.startsWith("*.*"))) failures.push("Wildcard egress host policy is not permitted");
  if (env.executorRequired && (!env.executorUrl || !env.executorSharedToken)) failures.push("GNW_EXECUTOR_URL and GNW_EXECUTOR_SHARED_TOKEN are required when executor isolation is enabled");
  if (failures.length) throw new Error(`Production environment is not ready:\n - ${failures.join("\n - ")}`);
}

export function generateSecret() {
  return randomBytes(48).toString("hex");
}
