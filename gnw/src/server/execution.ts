import type { Db } from "./db/index.js";
import type { Env } from "./env.js";
import { appendAudit } from "./audit.js";
import * as repo from "./repo.js";
import { assertEgressUrl } from "./security.js";
import { verifyCapabilityLease, type CapabilityLease } from "./capability.js";

export class ExecutionDenied extends Error { constructor(public readonly reason: string, public readonly stop = false) { super(reason); } }

export async function assertFinalInterlock(db: Db) {
  const state = await repo.getInterlock(db);
  if (state.killSwitch || state.circuitOpen) throw new ExecutionDenied("safety_interlock", true);
}

export async function executeExternal<T>(p: {
  db: Db; env: Env; taskId: number; actorUserId: number; eventType: string; actionDigest: string;
  capabilityLease: CapabilityLease; capability: string; destination?: string; effect: () => Promise<T>
}) {
  try {
    const lease = p.capabilityLease;
    if (!verifyCapabilityLease(lease, p.env.grantPublicKeyPem, Date.now(), p.destination ?? null)) throw new ExecutionDenied("invalid_capability_lease");
    if (lease.taskId !== p.taskId || lease.actorUserId !== p.actorUserId || lease.actionDigest !== p.actionDigest || lease.capability !== p.capability) throw new ExecutionDenied("capability_binding");
    if (!(await repo.consumeCapabilityLease(p.db, lease.leaseId))) throw new ExecutionDenied("capability_replay");
    await assertFinalInterlock(p.db);
    if (p.destination) assertEgressUrl(p.destination, p.env.allowedEgressHosts);
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_effect_admission`, decision: "ALLOW", reason: "capability_lease_and_final_interlock_passed", payload: { actionDigest: p.actionDigest, capability: lease.capability, leaseId: lease.leaseId, destination: p.destination ?? null } });
    // Final fencing check: audit admission can take time, and the interlock may
    // change after the first check. Re-read immediately before the irreversible
    // effect so a newly asserted STOP blocks the sink.
    await assertFinalInterlock(p.db);
    const result = await p.effect();
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_effect_result`, decision: "ALLOW", reason: "external_effect_completed", payload: { actionDigest: p.actionDigest, leaseId: lease.leaseId } });
    return result;
  } catch (error) {
    await appendAudit(p.db, { taskId: p.taskId, actorUserId: p.actorUserId, eventType: `${p.eventType}_effect_blocked`, decision: error instanceof ExecutionDenied && error.stop ? "STOP" : "DENY", reason: error instanceof Error ? error.message : "external_effect_failed", payload: { actionDigest: p.actionDigest } }).catch(() => undefined);
    throw error;
  }
}
