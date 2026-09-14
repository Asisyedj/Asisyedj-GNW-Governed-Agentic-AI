import { randomUUID } from "node:crypto";
import type { Db } from "./db/index.js";
import { ENV, type Env } from "./env.js";
import { appendAudit } from "./audit.js";
import { authorizeArtifactStorage, governanceService, rehydrateGrant, sha256 } from "./orchestrator.js";
import { notifyOwner } from "./notify.js";
import * as repo from "./repo.js";
import { storagePut } from "./storage.js";
import { assertFinalInterlock, executeExternal, executeFencedExternal, ExecutionDenied } from "./execution.js";
import { governedFetch } from "./security.js";
import type { SessionUser } from "./auth.js";

export type SubmitResult =
  | { ok: true; jobId: number; providerJobId: string; status: string }
  | { ok: false; status: "DENY" | "STOP"; reason: string };

/**
 * The only path to an external side effect. It requires an approved, unexpired,
 * unreplayed approval whose action digest matches the frozen grant. Anything
 * else returns an explicit structured denial.
 */
export async function submitApprovedVideoJob(db: Db, user: SessionUser, approvalId: number, env: Env = ENV): Promise<SubmitResult> {
  await repo.expireApprovals(db);
  const approval = await repo.getApproval(db, approvalId);
  if (!approval) return { ok: false, status: "DENY", reason: "approval_not_found" };
  const task = await repo.getTaskForUser(db, approval.task_id, user.workspaceId);
  if (!task) return { ok: false, status: "DENY", reason: "tenant_binding" };
  if (approval.status !== "approved") return deny(db, user, approval.task_id, approvalId, "approval_required");
  if (Number(approval.expires_at) <= Date.now()) return deny(db, user, approval.task_id, approvalId, "approval_expired");
  if (!approval.grant_json) return deny(db, user, approval.task_id, approvalId, "approval_binding");
  if (!approval.video_job_id) return deny(db, user, approval.task_id, approvalId, "approval_binding");

  const grant = rehydrateGrant(approval.grant_json, env.grantTtlMs);
  if (grant.expiresAt > Number(approval.expires_at)) return deny(db, user, approval.task_id, approvalId, "grant_expiry_exceeds_approval");
  const decision = await governanceService(db, env).authorize(grant, {
    approvalId: approval.id,
    requestId: grant.requestId,
    actionDigest: approval.action_digest,
    tenant: user.tenantKey,
    status: "approved",
    approverId: approval.reviewed_by ?? undefined,
    approverRole: user.role,
    requestedBy: approval.requested_by,
    expiresAt: Number(approval.expires_at),
    nonce: approval.nonce,
  });

  await appendAudit(db, {
    taskId: approval.task_id,
    actorUserId: user.id,
    eventType: "provider_submission_admission",
    decision: decision.status,
    reason: decision.reason,
    payload: { approvalId, videoJobId: approval.video_job_id, actionDigest: decision.actionDigest },
  });

  if (!decision.allowed) {
    // A refused retry must never roll a finished job backwards.
    const current = await repo.getVideoJob(db, approval.video_job_id);
    const terminal = current && ["completed", "failed", "stopped"].includes(current.status);
    if (!terminal) {
      await repo.updateVideoJob(db, approval.video_job_id, { status: decision.status === "STOP" ? "stopped" : "awaiting_approval", errorMessage: decision.reason });
    }
    await repo.createMessage(db, { taskId: approval.task_id, role: "system", agentName: "video_producer", content: `Provider submission denied by governance: ${decision.reason}` });
    if (decision.status === "STOP") {
      await notifyOwner(db, { title: "GNW safety interlock engaged", body: `Provider submission for task ${approval.task_id} was stopped (${decision.reason}).`, taskId: approval.task_id, userId: user.id }, env);
    }
    return { ok: false, status: decision.status === "STOP" ? "STOP" : "DENY", reason: decision.reason };
  }

  const jobId = approval.video_job_id;
  const job = await repo.getVideoJob(db, jobId);
  if (!job) return deny(db, user, approval.task_id, approvalId, "video_job_not_found");
  const frozen = grant.normalizedParameters ?? {};
  const endpoint = env.videoProviderUrl || "stub://local";
  if (String(frozen.briefDigest) !== sha256(job.brief ?? "") || String(frozen.scriptDigest) !== sha256(job.script ?? "") || String(frozen.storyboardDigest) !== sha256(job.storyboard ?? "") || String(frozen.provider) !== env.videoProvider || String(frozen.endpointDigest) !== sha256(endpoint)) return deny(db, user, approval.task_id, approvalId, "action_binding_mismatch");
  await repo.updateVideoJob(db, jobId, { status: "approved" });

  try {
    await repo.updateVideoJob(db, jobId, { status: "queued", startedAt: Date.now() });
    const tenant = user.tenantKey;
    const effectKey = `video-provider:${tenant}:${jobId}`;
    const idempotencyKey = sha256(`GNW-PROVIDER-IDEMPOTENCY-V1|${tenant}|${jobId}|${decision.actionDigest}`);
    const fenced = await executeFencedExternal({ db, env, taskId: approval.task_id, actorUserId: user.id, tenant, eventType: "provider_submission", actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease!, capability: "video.provider_job", provider: env.videoProvider, effectKey, idempotencyKey, effect: (fenceToken, providerIdempotencyKey, generation) => submitToProvider({ jobId, brief: job.brief ?? "", script: job.script ?? "", storyboard: job.storyboard ?? "" }, env, { fenceToken, idempotencyKey: providerIdempotencyKey, generation }) });
    if (fenced.status === "PENDING_RECONCILIATION") {
      await repo.updateVideoJob(db, jobId, { status: "queued", errorMessage: "provider_submission_pending_reconciliation" });
      return { ok: false, status: "DENY", reason: "provider_submission_pending_reconciliation" };
    }
    const submission = fenced.result ?? (fenced.providerEffectId ? { providerJobId: fenced.providerEffectId, provider: env.videoProvider, completesImmediately: false } : null);
    if (!submission) {
      await repo.updateVideoJob(db, jobId, { status: "queued", errorMessage: "provider_effect_completed_without_effect_id" });
      return { ok: false, status: "DENY", reason: "provider_effect_completed_without_effect_id" };
    }
    await repo.updateVideoJob(db, jobId, { status: "generating", providerJobId: submission.providerJobId, errorMessage: null });
    await repo.createMessage(db, { taskId: approval.task_id, role: "system", agentName: "video_producer", content: `Provider job ${submission.providerJobId} submitted after human approval. Status: generating.` });
    await appendAudit(db, { taskId: approval.task_id, actorUserId: user.id, eventType: "provider_job_submitted", decision: "ALLOW", reason: "approved_submission", payload: { jobId, providerJobId: submission.providerJobId, provider: submission.provider } });

    if (submission.completesImmediately) {
      await completeVideoJob(db, user, jobId, submission.providerJobId, env);
    }
    const settled = await repo.getVideoJob(db, jobId);
    return { ok: true, jobId, providerJobId: submission.providerJobId, status: settled?.status ?? "generating" };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    await repo.updateVideoJob(db, jobId, { status: "failed", errorMessage: detail.slice(0, 500), completedAt: Date.now() });
    await appendAudit(db, { taskId: approval.task_id, actorUserId: user.id, eventType: "provider_job_failed", decision: "DENY", reason: "provider_error", payload: { jobId, detail } });
    await notifyOwner(db, { title: "GNW video job failed", body: `Video job ${jobId} failed: ${detail}`, taskId: approval.task_id, userId: user.id }, env);
    return { ok: false, status: "DENY", reason: "provider_error" };
  }
}

async function deny(db: Db, user: SessionUser, taskId: number, approvalId: number, reason: string): Promise<SubmitResult> {
  await appendAudit(db, { taskId, actorUserId: user.id, eventType: "provider_submission_admission", decision: "DENY", reason, payload: { approvalId } });
  return { ok: false, status: "DENY", reason };
}

type Submission = { providerJobId: string; provider: string; completesImmediately: boolean };

async function submitToProvider(job: { jobId: number; brief: string; script: string; storyboard: string }, env: Env, fence: { fenceToken: string; idempotencyKey: string; generation: number }): Promise<{ result: Submission; providerEffectId?: string | null; responseDigest?: string | null }> {
  if (!env.videoProviderUrl) {
    // Stub provider: the governed lifecycle runs end to end and no external
    // generation is claimed. Swap in a real endpoint with VIDEO_PROVIDER_URL.
    const providerJobId = `stub-${randomUUID()}`;
    return { result: { providerJobId, provider: "stub", completesImmediately: true }, providerEffectId: providerJobId, responseDigest: sha256(JSON.stringify({ providerJobId, fence: fence.fenceToken, idempotencyKey: fence.idempotencyKey })) };
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await governedFetch(env.videoProviderUrl, {
      method: "POST",
      headers: { "content-type": "application/json", "idempotency-key": fence.idempotencyKey, "x-gnw-fence-generation": String(fence.generation), "x-gnw-fence-token": fence.fenceToken, ...(env.videoProviderApiKey ? { authorization: `Bearer ${env.videoProviderApiKey}` } : {}) },
      body: JSON.stringify({ reference: `gnw-video-${job.jobId}`, brief: job.brief, script: job.script, storyboard: job.storyboard }),
      redirect: "manual",
      signal: controller.signal,
      __allowedHosts: env.allowedEgressHosts,
    } as RequestInit & { __allowedHosts: readonly string[] }, env.maxProviderResponseBytes);
    if (!response.ok) throw new Error(`provider_http_${response.status}: ${(await response.text()).slice(0, 300)}`);
    if (env.videoProviderIdempotencyRequired && response.headers.get("x-gnw-idempotency-key") !== fence.idempotencyKey) throw new Error("provider_idempotency_contract_not_confirmed");
    if (env.videoProviderFencingRequired && response.headers.get("x-gnw-fence-token") !== fence.fenceToken) throw new Error("provider_fence_contract_not_confirmed");
    const contentLength = Number(response.headers.get("content-length") ?? 0);
    if (contentLength > env.maxProviderResponseBytes) throw new Error("provider_response_too_large");
    const raw = await response.text();
    if (Buffer.byteLength(raw, "utf8") > env.maxProviderResponseBytes) throw new Error("provider_response_too_large");
    const payload = JSON.parse(raw) as { id?: string; job_id?: string; status?: string };
    const providerJobId = payload.id ?? payload.job_id;
    if (!providerJobId) throw new Error("provider_response_missing_job_id");
    const responseDigest = sha256(raw);
    return { result: { providerJobId, provider: env.videoProvider, completesImmediately: payload.status === "completed" }, providerEffectId: providerJobId, responseDigest };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Completion registers a controlled external storage reference for the media
 * manifest — the database keeps the key, digest and size, never the bytes.
 */
export async function completeVideoJob(db: Db, user: SessionUser, jobId: number, providerJobId: string, env: Env = ENV) {
  await assertFinalInterlock(db);
  const job = await repo.getVideoJob(db, jobId);
  if (!job) return;
  const task = await repo.getTaskForUser(db, job.task_id, user.workspaceId);
  if (!task) throw new ExecutionDenied("tenant_binding");
  if (!job || !["generating", "queued", "approved"].includes(job.status)) return;
  if (!job.provider_job_id || job.provider_job_id !== providerJobId) throw new ExecutionDenied("provider_job_binding");
  const manifest = JSON.stringify(
    {
      videoJobId: jobId,
      taskId: job.task_id,
      providerJobId,
      provider: job.provider,
      brief: job.brief,
      script: job.script,
      storyboard: job.storyboard,
      completedAt: new Date().toISOString(),
    },
    null,
    2,
  );
  const digest = sha256(manifest);
  const storageDecision = await authorizeArtifactStorage(db, user, job.task_id, task.classification, digest, env);
  if (!storageDecision.allowed || !storageDecision.capabilityLease) throw new ExecutionDenied(storageDecision.reason || "storage_capability_denied", storageDecision.status === "STOP");
  const stored = await executeExternal({
    db, env, taskId: job.task_id, actorUserId: user.id, eventType: "artifact_storage", actionDigest: storageDecision.actionDigest, capabilityLease: storageDecision.capabilityLease, capability: "artifact.storage",
    effect: () => storagePut(`tasks/${job.task_id}/video/${jobId}/${digest}.json`, manifest, "application/json", env),
  });
  await repo.createArtifact(db, {
    taskId: job.task_id,
    videoJobId: jobId,
    kind: "video",
    storageKey: stored.key,
    storageUrl: stored.url,
    contentType: "application/json",
    byteSize: stored.byteSize,
    sha256: digest,
    createdBy: user.id,
  });
  await repo.updateVideoJob(db, jobId, { status: "completed", completedAt: Date.now(), errorMessage: null });
  await repo.updateTaskStatus(db, job.task_id, "completed");
  await repo.createMessage(db, { taskId: job.task_id, role: "system", agentName: "video_producer", content: `Video job ${jobId} completed. Manifest stored at ${stored.key} (sha256 ${digest.slice(0, 16)}…).` });
  await appendAudit(db, { taskId: job.task_id, actorUserId: user.id, eventType: "video_job_completed", decision: "ALLOW", reason: "artifact_registered", payload: { jobId, storageKey: stored.key, sha256: digest, driver: stored.driver } });
  await notifyOwner(db, { title: "GNW video job completed", body: `Video job ${jobId} for task ${job.task_id} completed and its artifact reference was registered.`, taskId: job.task_id, userId: user.id }, env);
}

/** Polls a real provider for a job that is still generating. */
export async function pollVideoJob(db: Db, user: SessionUser, jobId: number, env: Env = ENV) {
  const job = await repo.getVideoJob(db, jobId);
  if (!job || job.status !== "generating" || !job.provider_job_id || !env.videoProviderUrl) return job;
  const url = `${env.videoProviderUrl.replace(/\/$/, "")}/${encodeURIComponent(job.provider_job_id)}`;
  try {
    const pollGrant = rehydrateGrant(JSON.stringify({
      requestId: randomUUID(), subject: String(user.id), tenant: user.tenantKey, role: user.role,
      purpose: "approved_provider_poll", classification: "internal", operation: "provider_poll",
      resource: `task:${job.task_id}/video:${job.id}/provider:${job.provider_job_id}`,
      agent: "video_producer", tool: "video.storyboard", scope: "video.storyboard", capability: "provider.poll",
      budgetTokens: 1, budgetBytes: env.maxProviderResponseBytes, issuedAt: Date.now() - 1,
      expiresAt: Date.now() + Math.min(env.grantTtlMs, 60_000), nonce: randomUUID(),
      normalizedParameters: { jobId: job.id, providerJobId: job.provider_job_id, endpointDigest: sha256(url) },
      inputDigest: sha256(url), outputConstraints: { maxBytes: env.maxProviderResponseBytes },
    }), env.grantTtlMs);
    if (env.requireSignedGrants) {
      const { signGrant } = await import("./security.js");
      const signed = signGrant(pollGrant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      pollGrant.issuer = signed.issuer; pollGrant.signature = signed.signature;
    }
    const pollDecision = await governanceService(db, env).authorize(pollGrant);
    if (!pollDecision.allowed || !pollDecision.capabilityLease) throw new ExecutionDenied(pollDecision.reason || "provider_poll_denied", pollDecision.status === "STOP");
    const response = await executeExternal({ db, env, taskId: job.task_id, actorUserId: user.id, eventType: "provider_poll", actionDigest: pollDecision.actionDigest, capabilityLease: pollDecision.capabilityLease, capability: "provider.poll", destination: url, effect: () => governedFetch(url, { redirect: "manual", headers: env.videoProviderApiKey ? { authorization: `Bearer ${env.videoProviderApiKey}` } : {}, __allowedHosts: env.allowedEgressHosts } as RequestInit & { __allowedHosts: readonly string[] }, env.maxProviderResponseBytes) });
    if (!response.ok) return job;
    const raw = await response.text();
    if (Buffer.byteLength(raw, "utf8") > env.maxProviderResponseBytes) return job;
    const payload = JSON.parse(raw) as { status?: string; error?: string };
    if (payload.status === "completed") await completeVideoJob(db, user, jobId, job.provider_job_id, env);
    if (payload.status === "failed") await repo.updateVideoJob(db, jobId, { status: "failed", errorMessage: (payload.error ?? "provider_failed").slice(0, 500), completedAt: Date.now() });
    return repo.getVideoJob(db, jobId);
  } catch (error) { if (error instanceof ExecutionDenied && error.stop) return job; return job; }
}
