import type { Db } from "./db/index.js";
import type { Env } from "./env.js";
import { appendAudit } from "./audit.js";
import * as repo from "./repo.js";
import { assertEgressUrl, sha256 } from "./security.js";
import { verifyCapabilityLease, type CapabilityLease } from "./capability.js";

export class ExecutionDenied extends Error { constructor(public readonly reason: string, public readonly stop = false) { super(reason); } }

export async function assertFinalInterlock(db: Db, expectedGeneration?: number) {
  const state = await repo.getInterlock(db);
  if (state.killSwitch || state.circuitOpen) throw new ExecutionDenied("safety_interlock", true);
  if (expectedGeneration !== undefined && state.generation !== expectedGeneration) throw new ExecutionDenied("stale_interlock_generation", true);
}

export async function executeExternal<T>(p: {
  db: Db; env: Env; taskId: number; actorUserId: number; eventType: string; actionDigest: string;
  capabilityLease: CapabilityLease; capability: string; destination?: string; effect: () => Promise<T>
}) {
  try {
    const lease = p.capabilityLease;
    if (!verifyCapabilityLease(lease, p.env.grantPublicKeyPem, Date.now(), p.destination ?? null)) throw new ExecutionDenied("invalid_capability_lease");
    const taskContext = await repo.getTaskExecutionContext(p.db, p.taskId);
    if (!taskContext || lease.taskId !== p.taskId || lease.actorUserId !== p.actorUserId || lease.subject !== String(p.actorUserId) || lease.tenant !== taskContext.tenant || lease.actionDigest !== p.actionDigest || lease.capability !== p.capability) throw new ExecutionDenied("capability_binding");
    if (!(await repo.consumeCapabilityLease(p.db, lease.leaseId))) throw new ExecutionDenied("capability_replay");
    await assertFinalInterlock(p.db, lease.interlockGeneration);
    if (p.destination) assertEgressUrl(p.destination, p.env.allowedEgressHosts);
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_effect_admission`, decision: "ALLOW", reason: "capability_lease_and_final_interlock_passed", payload: { actionDigest: p.actionDigest, capability: lease.capability, leaseId: lease.leaseId, destination: p.destination ?? null } });
    // Final fencing check: audit admission can take time, and the interlock may
    // change after the first check. Re-read immediately before the irreversible
    // effect so a newly asserted STOP blocks the sink.
    await assertFinalInterlock(p.db, lease.interlockGeneration);
    const result = await p.effect();
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_effect_result`, decision: "ALLOW", reason: "external_effect_completed", payload: { actionDigest: p.actionDigest, leaseId: lease.leaseId } });
    return result;
  } catch (error) {
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_effect_blocked`, decision: error instanceof ExecutionDenied && error.stop ? "STOP" : "DENY", reason: error instanceof Error ? error.message : "external_effect_failed", payload: { actionDigest: p.actionDigest } }).catch(() => undefined);
    throw error;
  }
}


export type FencedEffectResult<T> =
  | { status: "COMPLETED"; result?: T; providerEffectId?: string | null; effectKey: string; idempotencyKey: string; fenceToken: string }
  | { status: "PENDING_RECONCILIATION"; effectKey: string; idempotencyKey: string; fenceToken: string };

/** Durable local fence + provider contract: provider MUST enforce the idempotency key and monotonic fence token. */
export async function executeFencedExternal<T>(p: {
  db: Db; env: Env; taskId: number; actorUserId: number; tenant: string; eventType: string;
  actionDigest: string; capabilityLease: CapabilityLease; capability: string; provider: string;
  effectKey: string; idempotencyKey: string;
  effect: (fenceToken: string, idempotencyKey: string, generation: number) => Promise<{ result: T; providerEffectId?: string | null; responseDigest?: string | null }>;
}): Promise<FencedEffectResult<T>> {
  const lease = p.capabilityLease;
  if (!verifyCapabilityLease(lease, p.env.grantPublicKeyPem, Date.now())) throw new ExecutionDenied("invalid_capability_lease");
  if (lease.taskId !== p.taskId || lease.actorUserId !== p.actorUserId || lease.subject !== String(p.actorUserId) || lease.tenant !== p.tenant || lease.actionDigest !== p.actionDigest || lease.capability !== p.capability) throw new ExecutionDenied("capability_binding");
  const current = await repo.getInterlock(p.db);
  if (current.killSwitch || current.circuitOpen) throw new ExecutionDenied("safety_interlock", true);
  if (current.generation !== lease.interlockGeneration) throw new ExecutionDenied("stale_interlock_generation", true);
  if (!(await repo.consumeCapabilityLease(p.db, lease.leaseId))) throw new ExecutionDenied("capability_replay");
  const fenceToken = sha256(`GNW-FENCE-V1|${p.tenant}|${p.taskId}|${p.effectKey}|${current.generation}`);
  const existing = await repo.createEffectFence(p.db, { effectKey: p.effectKey, taskId: p.taskId, tenant: p.tenant, capability: p.capability, actionDigest: p.actionDigest, interlockGeneration: current.generation, fenceToken, idempotencyKey: p.idempotencyKey, provider: p.provider });
  if (!existing) throw new ExecutionDenied("effect_fence_unavailable");
  if (existing.action_digest !== p.actionDigest || existing.tenant !== p.tenant || existing.idempotency_key !== p.idempotencyKey || existing.fence_token !== fenceToken) throw new ExecutionDenied("effect_fence_binding");
  if (existing.state === "COMPLETED") return { status: "COMPLETED", result: undefined, providerEffectId: existing.provider_effect_id, effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken };
  if (existing.state === "PENDING_RECONCILIATION" || existing.state === "IN_FLIGHT") return { status: "PENDING_RECONCILIATION", effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken };
  if (!(await repo.claimEffectFence(p.db, p.effectKey, current.generation))) return { status: "PENDING_RECONCILIATION", effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken };
  await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_fence_claimed`, decision: "ALLOW", reason: "atomic_effect_fence_claimed", payload: { effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken } });
  try {
    const result = await p.effect(fenceToken, p.idempotencyKey, current.generation);
    await repo.completeEffectFence(p.db, p.effectKey, result.providerEffectId ?? null, result.responseDigest ?? null);
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_fence_completed`, decision: "ALLOW", reason: "provider_effect_completed", payload: { effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken, providerEffectId: result.providerEffectId ?? null } });
    return { status: "COMPLETED", result: result.result, effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken };
  } catch (error) {
    await repo.reconcileEffectFence(p.db, p.effectKey, null, null);
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_fence_pending_reconciliation`, decision: "DENY", reason: error instanceof Error ? error.message : "provider_ambiguous_failure", payload: { effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken } }).catch(() => undefined);
    return { status: "PENDING_RECONCILIATION", effectKey: p.effectKey, idempotencyKey: p.idempotencyKey, fenceToken };
  }
}
