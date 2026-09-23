import { createHash, randomUUID } from "node:crypto";
import type { Db } from "./db/index.js";
import { ENV, type Env } from "./env.js";
import { appendAudit } from "./audit.js";
import { GovernanceService, digestRequest, type GovernanceRequest } from "./governance.js";
import { signGrant } from "./security.js";
import { invokeLLM } from "./llm.js";
import { notifyOwner } from "./notify.js";
import * as repo from "./repo.js";
import type { SessionUser } from "./auth.js";
import { DEFAULT_AGENT_TOOL, type Classification, type SpecialistAgent } from "../shared/types.js";
import { buildShadowEnvelope, runCouncilShadow } from "./council/index.js";

/**
 * The orchestrator is untrusted: it may only choose *which* specialist to ask.
 * It cannot grant capability, approve an action, or reach a provider. Every
 * step below is admitted by the policy gateway first or it does not run.
 */
export const AGENT_INSTRUCTIONS: Record<SpecialistAgent, string> = {
  research: "You are the Research specialist. Produce evidence-first findings, separate fact from inference, and state uncertainty. Never claim to have browsed or accessed any source that was not supplied to you.",
  analysis: "You are the Analysis specialist. Compare options, state assumptions explicitly, quantify risk where possible, and perform no side effects.",
  engineering: "You are the Engineering specialist. Produce implementation plans, review notes, and safe technical steps. Never execute code, commands, or migrations.",
  qa: "You are the QA specialist. Find failure modes, propose concrete test cases, and return a pass or block decision with the evidence behind it.",
  video_producer: "You are the Video Producer specialist. Produce a concise production brief, a script, and a shot-by-shot storyboard. You may never submit anything to a provider; submission requires an explicit human approval.",
};

const GOVERNANCE_FOOTER = "Governance status: admitted under a scoped, time-bound grant. You may only produce analysis and structured planning. You may not call tools, fetch external data, or perform side effects.";

export function titleFromPrompt(prompt: string) {
  return prompt.trim().replace(/\s+/g, " ").slice(0, 80) || "Untitled governed task";
}

export function sha256(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

export function governanceService(db: Db, env: Env = ENV) {
  return new GovernanceService(
    {
      claimNonce: (kind, nonce, taskId) => repo.claimNonce(db, kind, nonce, taskId),
      reserveBudget: (taskId, grantNonce, tokens, bytes) => repo.reserveBudget(db, taskId, grantNonce, tokens, bytes),
      getInterlock: () => repo.getInterlock(db),
      persistCapabilityLease: (lease) => repo.createCapabilityLease(db, lease),
    },
    { maxBudgetTokens: env.maxBudgetTokens, maxBudgetBytes: env.maxBudgetBytes, maxGrantTtlMs: env.maxGrantTtlMs },
    Date.now,
    env.requireSignedGrants ? { issuer: env.grantIssuer, publicKeyPem: env.grantPublicKeyPem } : undefined,
    env.grantPrivateKeyPem ? { issuer: env.grantIssuer, privateKeyPem: env.grantPrivateKeyPem, ttlMs: env.capabilityLeaseTtlMs } : undefined,
  );
}

export function buildGrant(input: {
  user: SessionUser; taskId: number; agent: SpecialistAgent; tool: string; operation: string;
  purpose: string; classification: Classification; budgetTokens: number; budgetBytes: number; reservationTokens?: number; reservationBytes?: number;
  requestId?: string; ttlMs?: number; capability?: string; env?: Env;
}): GovernanceRequest {
  const env = input.env ?? ENV;
  const issuedAt = Date.now() - 1;
  return {
    requestId: input.requestId ?? randomUUID(),
    subject: String(input.user.id),
    tenant: input.user.tenantKey,
    role: input.user.role,
    purpose: input.purpose,
    classification: input.classification,
    operation: input.operation,
    resource: `task:${input.taskId}`,
    taskId: input.taskId,
    agent: input.agent,
    tool: input.tool,
    scope: input.tool,
    capability: input.capability,
    provenance: {
      tenant: { value: input.user.tenantKey, source: "AUTHORITY", trust: "AUTHORITY_VERIFIED" },
      actor: { value: input.user.id, source: "AUTHORITY", trust: "AUTHORITY_VERIFIED" },
      purpose: { value: input.purpose, source: "CLIENT", trust: "CLIENT_ASSERTED" },
      classification: { value: input.classification, source: "GNW", trust: "GNW_DERIVED" },
    },
    budgetTokens: input.budgetTokens,
    budgetBytes: input.budgetBytes,
    budgetReservationTokens: input.reservationTokens,
    budgetReservationBytes: input.reservationBytes,
    issuedAt,
    expiresAt: issuedAt + (input.ttlMs ?? env.grantTtlMs),
    nonce: randomUUID(),
  };
}

export type SpecialistResult = { agent: SpecialistAgent; status: "ALLOW" | "DENY" | "STOP"; reason: string; output: string; mode?: "live" | "offline" };

export async function authorizeArtifactStorage(db: Db, user: SessionUser, taskId: number, classification: Classification, artifactDigest: string, env: Env = ENV) {
  const grant = buildGrant({ user, taskId, agent: "video_producer", tool: "video.brief", operation: "artifact_store", purpose: "artifact_storage_continuation", classification, budgetTokens: 1, budgetBytes: 1, capability: "artifact.storage", env });
  grant.inputDigest = artifactDigest;
  grant.normalizedParameters = { taskId, artifactDigest };
  grant.outputConstraints = { maxBytes: env.maxArtifactBytes };
  if (env.requireSignedGrants) {
    const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
    grant.issuer = signed.issuer;
    grant.signature = signed.signature;
  }
  return governanceService(db, env).authorize(grant);
}


export async function runSpecialist(db: Db, params: {
  user: SessionUser; taskId: number; agent: SpecialistAgent; prompt: string; purpose: string;
  classification: Classification; budgetTokens: number; budgetBytes: number; reservationTokens?: number; reservationBytes?: number; tool?: string; label?: string; env?: Env;
}): Promise<SpecialistResult> {
  const env = params.env ?? ENV;
  const tool = params.tool ?? DEFAULT_AGENT_TOOL[params.agent];
  const grant = buildGrant({ ...params, tool, operation: "analysis", env });
  grant.inputDigest = sha256(params.prompt);
  grant.normalizedParameters = { taskId: params.taskId, promptDigest: sha256(params.prompt), labelDigest: sha256(params.label ?? ""), tool, operation: "analysis" };
  grant.capability = "llm.chat";
  grant.outputConstraints = { maxBytes: params.budgetBytes, format: "text" };
  if (env.requireSignedGrants) {
    const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
    grant.issuer = signed.issuer;
    grant.signature = signed.signature;
  }
  const actionDigest = digestRequest(grant);
  const runId = await repo.createAgentRun(db, {
    taskId: params.taskId,
    agentName: params.agent,
    requestId: grant.requestId,
    inputDigest: sha256(params.prompt),
    actionDigest,
  });

  const decision = await governanceService(db, env).authorize(grant);
  await appendAudit(db, {
    taskId: params.taskId,
    actorUserId: params.user.id,
    eventType: "agent_admission",
    decision: decision.status,
    reason: decision.reason,
    payload: { agent: params.agent, tool, requestId: grant.requestId, actionDigest },
  });

  if (!decision.allowed) {
    const message = `Action denied by governance: ${decision.reason}`;
    await repo.completeAgentRun(db, runId, { status: decision.status === "STOP" ? "stopped" : "denied", decision: decision.status, reason: decision.reason, errorCode: decision.reason });
    await repo.createMessage(db, { taskId: params.taskId, role: "system", agentName: params.agent, content: message });
    if (decision.status === "STOP") {
      await notifyOwner(db, { title: "GNW safety interlock engaged", body: `Task ${params.taskId} was stopped by the governance interlock (${decision.reason}).`, taskId: params.taskId, userId: params.user.id }, env);
    }
    return { agent: params.agent, status: decision.status, reason: decision.reason, output: message };
  }

  try {
    const result = await invokeLLM({
      messages: [
        { role: "system", content: `${AGENT_INSTRUCTIONS[params.agent]} ${GOVERNANCE_FOOTER}` },
        { role: "user", content: params.label ? `${params.label}\n\n${params.prompt}` : params.prompt },
      ],
      env, db, taskId: params.taskId, actorUserId: params.user.id, actionDigest, capabilityLease: decision.capabilityLease,
    });
    await repo.completeAgentRun(db, runId, { status: "completed", decision: "ALLOW", reason: "result_recorded", output: result.text });
    await repo.createMessage(db, { taskId: params.taskId, role: "agent", agentName: params.agent, content: result.text });
    await appendAudit(db, {
      taskId: params.taskId,
      actorUserId: params.user.id,
      eventType: "agent_result",
      decision: "ALLOW",
      reason: "result_recorded",
      payload: { agent: params.agent, mode: result.mode, model: result.model, outputDigest: sha256(result.text) },
    });
    return { agent: params.agent, status: "ALLOW", reason: "result_recorded", output: result.text, mode: result.mode };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    await repo.completeAgentRun(db, runId, { status: "failed", decision: "DENY", reason: "specialist_failed", errorCode: detail.slice(0, 100) });
    await repo.createMessage(db, { taskId: params.taskId, role: "system", agentName: params.agent, content: `Specialist failed: ${detail}` });
    await appendAudit(db, { taskId: params.taskId, actorUserId: params.user.id, eventType: "agent_failure", decision: "DENY", reason: "specialist_failed", payload: { agent: params.agent, detail } });
    return { agent: params.agent, status: "DENY", reason: "specialist_failed", output: `Specialist failed: ${detail}` };
  }
}

export type TaskInput = {
  prompt: string;
  purpose: string;
  classification: Classification;
  selectedAgents: SpecialistAgent[];
  budgetTokens: number;
  budgetBytes: number;
};

export async function runTask(db: Db, user: SessionUser, input: TaskInput, env: Env = ENV) {
  const taskId = await repo.createTask(db, {
    workspaceId: user.workspaceId,
    createdBy: user.id,
    title: titleFromPrompt(input.prompt),
    prompt: input.prompt,
    purpose: input.purpose,
    classification: input.classification,
    selectedAgents: input.selectedAgents,
    budgetTokens: input.budgetTokens,
    budgetBytes: input.budgetBytes,
    status: "running",
  });

  await repo.createMessage(db, { taskId, role: "user", content: input.prompt });
  await repo.createMessage(db, {
    taskId,
    role: "orchestrator",
    content: `Untrusted orchestrator routed this task to: ${input.selectedAgents.join(", ")}. The orchestrator holds no authority; every action is admitted by the policy gateway or refused.`,
  });
  await appendAudit(db, { taskId, actorUserId: user.id, eventType: "task_admission", decision: "ALLOW", reason: "task_created", payload: input });

  // Shadow council is observational only. It persists a hypothetical review but
  // cannot issue a capability lease, call an executor, or change this task's
  // existing governance decision. The default mode is disabled.
  await runCouncilShadow({
    db,
    env,
    sourceTaskId: taskId,
    actorUserId: user.id,
    envelope: buildShadowEnvelope({
      sourceTaskId: taskId,
      actorUserId: user.id,
      purpose: input.purpose,
      classification: input.classification,
      promptDigest: sha256(input.prompt),
      environment: env.isProduction ? "production" : "dev",
    }),
  });

  const results: SpecialistResult[] = [];
  const actionCount = input.selectedAgents.filter(a => a !== "video_producer").length * 5 + (input.selectedAgents.includes("video_producer") ? 5 : 0);
  const reservationTokens = Math.max(1, Math.floor(input.budgetTokens / Math.max(1, actionCount)));
  const reservationBytes = Math.max(1, Math.floor(input.budgetBytes / Math.max(1, actionCount)));
  let videoJobId: number | undefined;
  let approvalId: number | undefined;

  for (const agent of input.selectedAgents) {
    if (agent === "video_producer") continue;
    const result = await runSpecialist(db, { user, taskId, agent, prompt: input.prompt, purpose: input.purpose, classification: input.classification, budgetTokens: input.budgetTokens, budgetBytes: input.budgetBytes, reservationTokens, reservationBytes, env });
    results.push(result);
    if (result.status === "STOP") break;
  }

  if (input.selectedAgents.includes("video_producer")) {
    const pack = await produceVideoPackage(db, user, taskId, input, env, reservationTokens, reservationBytes);
    results.push(...pack.results);
    videoJobId = pack.videoJobId;
    approvalId = pack.approvalId;
  }

  const stopped = results.some(result => result.status === "STOP");
  const awaiting = Boolean(approvalId) || input.classification === "restricted";
  const status = stopped ? "stopped" : awaiting ? "awaiting_approval" : results.every(result => result.status === "ALLOW") ? "completed" : "denied";
  await repo.updateTaskStatus(db, taskId, status);
  await appendAudit(db, { taskId, actorUserId: user.id, eventType: "task_settled", decision: status === "stopped" ? "STOP" : "ALLOW", reason: `task_${status}`, payload: { status, approvalId, videoJobId } });

  return { taskId, status, results, videoJobId, approvalId };
}

/**
 * Brief, script and storyboard are produced as three separate governed outputs.
 * Provider submission is never performed here — it is queued for a human.
 */
async function produceVideoPackage(db: Db, user: SessionUser, taskId: number, input: TaskInput, env: Env, reservationTokens: number, reservationBytes: number) {
  const shared = { user, taskId, agent: "video_producer" as const, purpose: input.purpose, classification: input.classification, budgetTokens: input.budgetTokens, budgetBytes: input.budgetBytes, reservationTokens, reservationBytes, env };
  const brief = await runSpecialist(db, { ...shared, tool: "video.brief", label: "Produce the PRODUCTION BRIEF only: audience, objective, tone, duration, constraints.", prompt: input.prompt });
  const script = await runSpecialist(db, { ...shared, tool: "video.brief", label: "Produce the SCRIPT only: spoken lines and on-screen text with timings.", prompt: input.prompt });
  const storyboard = await runSpecialist(db, { ...shared, tool: "video.storyboard", label: "Produce the STORYBOARD only: numbered shots with framing, motion, and duration.", prompt: input.prompt });
  const results = [brief, script, storyboard];

  const videoJobId = await repo.createVideoJob(db, {
    taskId,
    status: results.every(result => result.status === "ALLOW") ? "awaiting_approval" : "draft",
    brief: brief.output,
    script: script.output,
    storyboard: storyboard.output,
    provider: env.videoProviderUrl ? env.videoProvider : "stub",
  });

  if (!results.every(result => result.status === "ALLOW")) {
    return { results, videoJobId, approvalId: undefined };
  }

  // Pre-bind the complete future provider-job grant so the approval commits to exactly
  // one signed action. The nonce and validity window are part of the signed grant and
  // are never regenerated at submission.
  const grant = buildGrant({ ...shared, tool: "video.provider_job", operation: "provider_job", env });
  const endpoint = env.videoProviderUrl || "stub://local";
  grant.inputDigest = sha256(`${brief.output}|${script.output}|${storyboard.output}`);
  grant.providerParameters = { provider: env.videoProvider, endpointDigest: sha256(endpoint), briefDigest: sha256(brief.output), scriptDigest: sha256(script.output), storyboardDigest: sha256(storyboard.output) };
  grant.normalizedParameters = { taskId, videoJobId, provider: env.videoProvider, endpointDigest: sha256(endpoint), briefDigest: sha256(brief.output), scriptDigest: sha256(script.output), storyboardDigest: sha256(storyboard.output) };
  grant.outputConstraints = { maxBytes: input.budgetBytes, providerResponseMaxBytes: env.maxProviderResponseBytes };
  if (env.requireSignedGrants) {
    const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
    grant.issuer = signed.issuer;
    grant.signature = signed.signature;
  }
  const actionDigest = digestRequest(grant);
  const approvalNonce = randomUUID();
  const approvalExpiresAt = Math.min(Date.now() + env.approvalTtlMs, grant.expiresAt);
  const approvalId = await repo.createApproval(db, {
    taskId,
    videoJobId,
    actionDigest,
    operation: "provider_job",
    grantJson: serialiseGrant(grant),
    requestedBy: user.id,
    reason: `Provider submission for video job ${videoJobId} (request ${grant.requestId.slice(0, 8)}).`,
    nonce: approvalNonce,
    expiresAt: approvalExpiresAt,
  });
  await repo.createMessage(db, { taskId, role: "system", agentName: "video_producer", content: "Video package prepared. Provider submission is blocked until a reviewer approves it." });
  await appendAudit(db, { taskId, actorUserId: user.id, eventType: "approval_requested", decision: "PENDING", reason: "provider_submission_requires_human", payload: { approvalId, videoJobId, actionDigest, requestId: grant.requestId } });
  await notifyOwner(db, { title: "GNW approval required", body: `A provider-ready video job for task ${taskId} is waiting for human approval.`, taskId, userId: user.id }, env);

  return { results, videoJobId, approvalId };
}

export type PendingGrant = Omit<GovernanceRequest, "nonce" | "issuedAt" | "expiresAt">;

/**
 * The reviewer approves one concrete action, so the grant body is frozen at
 * request time. Only nonce and validity window are re-issued at submission —
 * neither is part of the action digest, so the binding cannot drift.
 */
export function serialiseGrant(grant: GovernanceRequest): string {
  return JSON.stringify(grant);
}

export function rehydrateGrant(grantJson: string, _ttlMs: number): GovernanceRequest {
  const grant = JSON.parse(grantJson) as GovernanceRequest;
  return grant;
}
