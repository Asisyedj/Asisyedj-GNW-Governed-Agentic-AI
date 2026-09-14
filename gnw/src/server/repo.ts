import type { Db } from "./db/index.js";
import { UniqueViolation } from "./db/index.js";
import type { Interlock } from "./governance.js";
import type { Classification, SpecialistAgent, TaskStatus, VideoStatus } from "../shared/types.js";

export type UserRow = { id: number; email: string; name: string | null; password_hash: string; role: "user" | "admin"; created_at: number; last_signed_in: number | null };
export type TaskRow = {
  id: number; workspace_id: number; created_by: number; title: string; prompt: string; purpose: string;
  classification: Classification; status: TaskStatus; selected_agents: string; budget_tokens: number; budget_bytes: number;
  created_at: number; updated_at: number;
};
export type MessageRow = { id: number; task_id: number; role: string; agent_name: string | null; content: string; created_at: number };
export type AgentRunRow = {
  id: number; task_id: number; agent_name: SpecialistAgent; status: string; request_id: string; input_digest: string;
  action_digest: string; decision: string | null; reason: string | null; output: string | null; error_code: string | null;
  started_at: number | null; completed_at: number | null; created_at: number;
};
export type ApprovalRow = {
  id: number; task_id: number; video_job_id: number | null; action_digest: string; operation: string; grant_json: string | null; requested_by: number;
  reviewed_by: number | null; status: "pending" | "approved" | "denied" | "expired"; reason: string; nonce: string;
  expires_at: number; reviewed_at: number | null; created_at: number;
};
export type VideoJobRow = {
  id: number; task_id: number; status: VideoStatus; brief: string | null; script: string | null; storyboard: string | null;
  provider: string | null; provider_job_id: string | null; error_message: string | null; started_at: number | null;
  completed_at: number | null; created_at: number; updated_at: number;
};
export type ArtifactRow = {
  id: number; task_id: number; video_job_id: number | null; kind: string; storage_key: string; storage_url: string | null;
  content_type: string; byte_size: number; sha256: string; created_by: number; created_at: number;
};

const now = () => Date.now();

/* ----------------------------------------------------------------- users */

export async function findUserByEmail(db: Db, email: string) {
  return db.get<UserRow>("SELECT * FROM users WHERE email = ?", [email.trim().toLowerCase()]);
}

export async function findUserById(db: Db, id: number) {
  return db.get<UserRow>("SELECT * FROM users WHERE id = ?", [id]);
}

export async function countUsers(db: Db) {
  const row = await db.get<{ count: number }>("SELECT COUNT(*) AS count FROM users");
  return Number(row?.count ?? 0);
}

export async function createUser(db: Db, input: { email: string; name?: string | null; passwordHash: string; role?: "user" | "admin" }) {
  const id = await db.insert("INSERT INTO users (email, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)", [
    input.email.trim().toLowerCase(),
    input.name ?? null,
    input.passwordHash,
    input.role ?? "user",
    now(),
  ]);
  return id;
}

export async function markSignedIn(db: Db, userId: number) {
  await db.run("UPDATE users SET last_signed_in = ? WHERE id = ?", [now(), userId]);
}

export async function setUserRole(db: Db, userId: number, role: "user" | "admin") {
  await db.run("UPDATE users SET role = ? WHERE id = ?", [role, userId]);
}

/* ------------------------------------------------------------ workspaces */

export async function ensurePersonalWorkspace(db: Db, userId: number, email: string) {
  const tenantKey = `tenant-user-${userId}`;
  const existing = await db.get<{ id: number }>("SELECT id FROM workspaces WHERE tenant_key = ?", [tenantKey]);
  if (existing) return existing.id;
  const id = await db.insert("INSERT INTO workspaces (tenant_key, name, created_by, created_at) VALUES (?, ?, ?, ?)", [tenantKey, `${email} workspace`, userId, now()]);
  await db.run("INSERT INTO workspace_members (workspace_id, user_id, role, created_at) VALUES (?, ?, ?, ?)", [id, userId, "owner", now()]);
  return id;
}

export async function getWorkspace(db: Db, workspaceId: number) {
  return db.get<{ id: number; tenant_key: string; name: string; created_by: number }>("SELECT * FROM workspaces WHERE id = ?", [workspaceId]);
}

export async function isMember(db: Db, workspaceId: number, userId: number) {
  const row = await db.get<{ id: number }>("SELECT id FROM workspace_members WHERE workspace_id = ? AND user_id = ?", [workspaceId, userId]);
  return Boolean(row);
}

/* ----------------------------------------------------------------- tasks */

export async function createTask(db: Db, input: {
  workspaceId: number; createdBy: number; title: string; prompt: string; purpose: string;
  classification: Classification; selectedAgents: SpecialistAgent[]; budgetTokens: number; budgetBytes: number; status: TaskStatus;
}) {
  const stamp = now();
  return db.insert(
    `INSERT INTO tasks (workspace_id, created_by, title, prompt, purpose, classification, status, selected_agents, budget_tokens, budget_bytes, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [input.workspaceId, input.createdBy, input.title, input.prompt, input.purpose, input.classification, input.status, JSON.stringify(input.selectedAgents), input.budgetTokens, input.budgetBytes, stamp, stamp],
  );
}

export async function listTasks(db: Db, workspaceId: number, limit = 50) {
  return db.all<TaskRow>("SELECT * FROM tasks WHERE workspace_id = ? ORDER BY updated_at DESC, id DESC LIMIT ?", [workspaceId, limit]);
}

export async function getTaskForUser(db: Db, taskId: number, workspaceId: number) {
  return db.get<TaskRow>("SELECT * FROM tasks WHERE id = ? AND workspace_id = ?", [taskId, workspaceId]);
}

export async function updateTaskStatus(db: Db, taskId: number, status: TaskStatus) {
  await db.run("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", [status, now(), taskId]);
}

/* -------------------------------------------------------------- messages */

export async function createMessage(db: Db, input: { taskId: number; role: "user" | "orchestrator" | "agent" | "system"; agentName?: string | null; content: string }) {
  return db.insert("INSERT INTO messages (task_id, role, agent_name, content, created_at) VALUES (?, ?, ?, ?, ?)", [input.taskId, input.role, input.agentName ?? null, input.content, now()]);
}

export async function listMessages(db: Db, taskId: number) {
  return db.all<MessageRow>("SELECT * FROM messages WHERE task_id = ? ORDER BY id ASC", [taskId]);
}

/* ------------------------------------------------------------ agent runs */

export async function createAgentRun(db: Db, input: { taskId: number; agentName: SpecialistAgent; requestId: string; inputDigest: string; actionDigest: string }) {
  return db.insert(
    `INSERT INTO agent_runs (task_id, agent_name, status, request_id, input_digest, action_digest, started_at, created_at)
     VALUES (?, ?, 'running', ?, ?, ?, ?, ?)`,
    [input.taskId, input.agentName, input.requestId, input.inputDigest, input.actionDigest, now(), now()],
  );
}

export async function completeAgentRun(db: Db, runId: number, input: { status: string; decision: string; reason: string; output?: string | null; errorCode?: string | null }) {
  await db.run("UPDATE agent_runs SET status = ?, decision = ?, reason = ?, output = ?, error_code = ?, completed_at = ? WHERE id = ?", [
    input.status, input.decision, input.reason, input.output ?? null, input.errorCode ?? null, now(), runId,
  ]);
}

export async function listAgentRuns(db: Db, taskId: number) {
  return db.all<AgentRunRow>("SELECT * FROM agent_runs WHERE task_id = ? ORDER BY id ASC", [taskId]);
}

/* -------------------------------------------------------------- approvals */

export async function createApproval(db: Db, input: { taskId: number; videoJobId?: number | null; actionDigest: string; operation: string; grantJson?: string | null; requestedBy: number; reason: string; nonce: string; expiresAt: number }) {
  return db.insert(
    `INSERT INTO approvals (task_id, video_job_id, action_digest, operation, grant_json, requested_by, status, reason, nonce, expires_at, created_at)
     VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)`,
    [input.taskId, input.videoJobId ?? null, input.actionDigest, input.operation, input.grantJson ?? null, input.requestedBy, input.reason, input.nonce, input.expiresAt, now()],
  );
}

export async function getApproval(db: Db, approvalId: number) {
  return db.get<ApprovalRow>("SELECT * FROM approvals WHERE id = ?", [approvalId]);
}

export async function listApprovals(db: Db, workspaceId: number, limit = 100) {
  return db.all<ApprovalRow & { title: string }>(
    `SELECT a.*, t.title AS title FROM approvals a
     INNER JOIN tasks t ON t.id = a.task_id
     WHERE t.workspace_id = ? ORDER BY a.id DESC LIMIT ?`,
    [workspaceId, limit],
  );
}

/** Single-writer review: only a pending, unexpired approval can transition. */
export async function reviewApproval(db: Db, approvalId: number, reviewerId: number, status: "approved" | "denied") {
  const result = await db.run("UPDATE approvals SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ? AND status = 'pending' AND expires_at > ?", [
    status, reviewerId, now(), approvalId, now(),
  ]);
  return result.changes > 0;
}

export async function expireApprovals(db: Db) {
  await db.run("UPDATE approvals SET status = 'expired' WHERE status = 'pending' AND expires_at <= ?", [now()]);
}

/* ------------------------------------------------------------ video jobs */

export async function createVideoJob(db: Db, input: { taskId: number; status: VideoStatus; brief?: string | null; script?: string | null; storyboard?: string | null; provider?: string | null }) {
  const stamp = now();
  return db.insert(
    `INSERT INTO video_jobs (task_id, status, brief, script, storyboard, provider, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [input.taskId, input.status, input.brief ?? null, input.script ?? null, input.storyboard ?? null, input.provider ?? null, stamp, stamp],
  );
}

export async function updateVideoJob(db: Db, jobId: number, values: Partial<{ status: VideoStatus; providerJobId: string | null; errorMessage: string | null; startedAt: number | null; completedAt: number | null }>) {
  const sets: string[] = [];
  const params: unknown[] = [];
  if (values.status !== undefined) { sets.push("status = ?"); params.push(values.status); }
  if (values.providerJobId !== undefined) { sets.push("provider_job_id = ?"); params.push(values.providerJobId); }
  if (values.errorMessage !== undefined) { sets.push("error_message = ?"); params.push(values.errorMessage); }
  if (values.startedAt !== undefined) { sets.push("started_at = ?"); params.push(values.startedAt); }
  if (values.completedAt !== undefined) { sets.push("completed_at = ?"); params.push(values.completedAt); }
  if (!sets.length) return;
  sets.push("updated_at = ?");
  params.push(now(), jobId);
  await db.run(`UPDATE video_jobs SET ${sets.join(", ")} WHERE id = ?`, params);
}

export async function getVideoJob(db: Db, jobId: number) {
  return db.get<VideoJobRow>("SELECT * FROM video_jobs WHERE id = ?", [jobId]);
}

export async function listVideoJobs(db: Db, taskId: number) {
  return db.all<VideoJobRow>("SELECT * FROM video_jobs WHERE task_id = ? ORDER BY id ASC", [taskId]);
}

/* -------------------------------------------------------------- artifacts */

export async function createArtifact(db: Db, input: { taskId: number; videoJobId?: number | null; kind: string; storageKey: string; storageUrl?: string | null; contentType: string; byteSize: number; sha256: string; createdBy: number }) {
  return db.insert(
    `INSERT INTO artifacts (task_id, video_job_id, kind, storage_key, storage_url, content_type, byte_size, sha256, created_by, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [input.taskId, input.videoJobId ?? null, input.kind, input.storageKey, input.storageUrl ?? null, input.contentType, input.byteSize, input.sha256, input.createdBy, now()],
  );
}

export async function listArtifacts(db: Db, taskId: number) {
  return db.all<ArtifactRow>("SELECT * FROM artifacts WHERE task_id = ? ORDER BY id ASC", [taskId]);
}

/* ---------------------------------------------------------- notifications */

export async function recordNotification(db: Db, input: { userId?: number | null; taskId?: number | null; tenantKey?: string | null; title: string; body: string; channel: string; delivered: boolean }) {
  const tenantKey = input.tenantKey ?? (input.taskId ? (await getTaskExecutionContext(db, input.taskId))?.tenant : null);
  if (!tenantKey) throw new Error("notification_tenant_required");
  return db.insert("INSERT INTO notifications (user_id, task_id, tenant_key, title, body, channel, delivered, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
    input.userId ?? null, input.taskId ?? null, tenantKey, input.title, input.body, input.channel, input.delivered ? 1 : 0, now(),
  ]);
}

export async function listNotifications(db: Db, userId: number, limit = 50) {
  return db.all("SELECT * FROM notifications WHERE user_id = ? OR user_id IS NULL ORDER BY id DESC LIMIT ?", [userId, limit]);
}

/* ------------------------------------------------------- nonces + control */

export async function claimNonce(db: Db, kind: string, nonce: string, taskId?: number) {
  try {
    await db.insert("INSERT INTO governance_nonces (nonce, kind, task_id, created_at) VALUES (?, ?, ?, ?)", [nonce, kind, taskId ?? null, now()]);
    return true;
  } catch (error) {
    if (error instanceof UniqueViolation) return false;
    throw error;
  }
}

export async function createCapabilityLease(db: Db, input: { leaseId: string; requestId: string; actionDigest: string; subject: string; tenant: string; taskId: number; actorUserId: number; capability: string; destination?: string | null; issuedAt: number; expiresAt: number; nonce: string; issuer: string; signature: string; interlockGeneration: number }) {
  await db.insert(`INSERT INTO capability_leases (lease_id, request_id, action_digest, subject, tenant, task_id, actor_user_id, capability, destination, issued_at, expires_at, nonce, issuer, signature, interlock_generation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, [
    input.leaseId, input.requestId, input.actionDigest, input.subject, input.tenant, input.taskId, input.actorUserId, input.capability, input.destination ?? null, input.issuedAt, input.expiresAt, input.nonce, input.issuer, input.signature, input.interlockGeneration,
  ]);
  return input;
}

export async function consumeCapabilityLease(db: Db, leaseId: string, nowMs = now()) {
  const result = await db.run(`UPDATE capability_leases SET consumed_at = ? WHERE lease_id = ? AND consumed_at IS NULL AND expires_at > ?`, [nowMs, leaseId, nowMs]);
  return result.changes > 0;
}

export async function getInterlock(db: Db): Promise<Interlock> {
  const rows = await db.all<{ key: string; value: string }>("SELECT key, value FROM system_controls WHERE key IN ('kill_switch', 'circuit_open', 'interlock_generation')");
  const map = new Map(rows.map(row => [row.key, row.value]));
  return { killSwitch: map.get("kill_switch") === "true", circuitOpen: map.get("circuit_open") === "true", generation: Number(map.get("interlock_generation") ?? 0) };
}

export async function setInterlock(db: Db, values: Partial<Interlock>, updatedBy: number) {
  const entries: Array<[string, boolean | undefined]> = [["kill_switch", values.killSwitch], ["circuit_open", values.circuitOpen]];
  await db.transaction(async tx => {
    let changed = false;
    for (const [key, value] of entries) {
      if (value === undefined) continue;
      changed = true;
      const stamp = now();
      await tx.run("INSERT INTO system_controls (key, value, updated_by, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_by = excluded.updated_by, updated_at = excluded.updated_at", [key, String(value), updatedBy, stamp]);
    }
    if (changed) {
      const current = await tx.get<{ value: string }>(tx.dialect === "postgres"
        ? "SELECT value FROM system_controls WHERE key = 'interlock_generation' FOR UPDATE"
        : "SELECT value FROM system_controls WHERE key = 'interlock_generation'");
      const next = Number(current?.value ?? 0) + 1;
      await tx.run("INSERT INTO system_controls (key, value, updated_by, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_by = excluded.updated_by, updated_at = excluded.updated_at", ["interlock_generation", String(next), updatedBy, now()]);
    }
  });
  return getInterlock(db);
}

export async function getTaskExecutionContext(db: Db, taskId: number) {
  return db.get<{ taskId: number; tenant: string }>(
    "SELECT t.id AS taskId, w.tenant_key AS tenant FROM tasks t INNER JOIN workspaces w ON w.id = t.workspace_id WHERE t.id = ?",
    [taskId],
  );
}

export type EffectFenceRow = {
  effect_key: string; task_id: number; tenant: string; capability: string; action_digest: string;
  interlock_generation: number; fence_token: string; idempotency_key: string; provider: string;
  state: "READY" | "IN_FLIGHT" | "COMPLETED" | "PENDING_RECONCILIATION" | "FAILED";
  provider_effect_id: string | null; response_digest: string | null; attempt_count: number;
  created_at: number; updated_at: number;
};

export async function getEffectFence(db: Db, effectKey: string) {
  return db.get<EffectFenceRow>("SELECT * FROM effect_fences WHERE effect_key = ?", [effectKey]);
}

export async function createEffectFence(db: Db, input: {
  effectKey: string; taskId: number; tenant: string; capability: string; actionDigest: string;
  interlockGeneration: number; fenceToken: string; idempotencyKey: string; provider: string;
}) {
  try {
    await db.insert(
      "INSERT INTO effect_fences (effect_key, task_id, tenant, capability, action_digest, interlock_generation, fence_token, idempotency_key, provider, state, attempt_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'READY', 0, ?, ?)",
      [input.effectKey, input.taskId, input.tenant, input.capability, input.actionDigest, input.interlockGeneration, input.fenceToken, input.idempotencyKey, input.provider, now(), now()],
    );
  } catch (error) {
    if (!(error instanceof UniqueViolation)) throw error;
  }
  return getEffectFence(db, input.effectKey);
}

export async function claimEffectFence(db: Db, effectKey: string, generation: number) {
  if (db.dialect === "sqlite") {
    const result = await db.run(
      "UPDATE effect_fences SET state = 'IN_FLIGHT', attempt_count = attempt_count + 1, updated_at = ? WHERE effect_key = ? AND state = 'READY' AND interlock_generation = ? AND ? = CAST((SELECT value FROM system_controls WHERE key = 'interlock_generation') AS INTEGER)",
      [now(), effectKey, generation, generation],
    );
    return result.changes > 0;
  }
  return db.transaction(async tx => {
    const control = await tx.get<{ value: string }>(tx.dialect === "postgres"
      ? "SELECT value FROM system_controls WHERE key = 'interlock_generation' FOR UPDATE"
      : "SELECT value FROM system_controls WHERE key = 'interlock_generation'");
    if (Number(control?.value ?? 0) !== generation) return false;
    const result = await tx.run(
      "UPDATE effect_fences SET state = 'IN_FLIGHT', attempt_count = attempt_count + 1, updated_at = ? WHERE effect_key = ? AND state = 'READY' AND interlock_generation = ?",
      [now(), effectKey, generation],
    );
    return result.changes > 0;
  });
}

export async function completeEffectFence(db: Db, effectKey: string, providerEffectId: string | null, responseDigest: string | null) {
  await db.run("UPDATE effect_fences SET state = 'COMPLETED', provider_effect_id = ?, response_digest = ?, updated_at = ? WHERE effect_key = ? AND state = 'IN_FLIGHT'", [providerEffectId, responseDigest, now(), effectKey]);
}

export async function reconcileEffectFence(db: Db, effectKey: string, providerEffectId: string | null, responseDigest: string | null) {
  await db.run("UPDATE effect_fences SET state = 'PENDING_RECONCILIATION', provider_effect_id = COALESCE(?, provider_effect_id), response_digest = COALESCE(?, response_digest), updated_at = ? WHERE effect_key = ? AND state = 'IN_FLIGHT'", [providerEffectId, responseDigest, now(), effectKey]);
}

export async function reserveBudget(db: Db, taskId: number, grantNonce: string, tokens: number, bytes: number) {
  return db.transaction(async tx => {
    const task = await tx.get<{ budget_tokens: number; budget_bytes: number }>(tx.dialect === "postgres" ? "SELECT budget_tokens, budget_bytes FROM tasks WHERE id = $1 FOR UPDATE" : "SELECT budget_tokens, budget_bytes FROM tasks WHERE id = ?", [taskId]);
    if (!task) return false;
    const used = await tx.get<{ tokens: number; bytes: number }>("SELECT COALESCE(SUM(tokens),0) AS tokens, COALESCE(SUM(bytes),0) AS bytes FROM budget_reservations WHERE task_id = ?", [taskId]);
    if (Number(used?.tokens ?? 0) + tokens > Number(task.budget_tokens) || Number(used?.bytes ?? 0) + bytes > Number(task.budget_bytes)) return false;
    try { await tx.run("INSERT INTO budget_reservations (task_id, grant_nonce, tokens, bytes, created_at) VALUES (?, ?, ?, ?, ?)", [taskId, grantNonce, tokens, bytes, now()]); return true; }
    catch (error) { if (error instanceof UniqueViolation) return false; throw error; }
  });
}

/* --------------------------------------------------------- login attempts */

export async function recordLoginAttempt(db: Db, email: string, ip: string, succeeded: boolean) {
  await db.run("INSERT INTO login_attempts (email, ip, succeeded, created_at) VALUES (?, ?, ?, ?)", [email, ip, succeeded ? 1 : 0, now()]);
}

export async function recentFailedLogins(db: Db, email: string, windowMs = 15 * 60 * 1000) {
  const row = await db.get<{ count: number }>("SELECT COUNT(*) AS count FROM login_attempts WHERE email = ? AND succeeded = 0 AND created_at > ?", [email, now() - windowMs]);
  return Number(row?.count ?? 0);
}
