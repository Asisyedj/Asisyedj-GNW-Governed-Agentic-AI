import { verifyCapabilityLease, type CapabilityLease } from "../server/capability.js";

export type ExecutorAuthorizationEnvelope = {
  lease: CapabilityLease;
  actionDigest: string;
  capability: string;
  actorUserId: number;
  tenant: string;
};

/**
 * The executor is a separate trust boundary. It must verify the signed lease
 * itself instead of trusting the application process or a caller-supplied
 * task id. Missing trust configuration is a hard failure.
 */
export function assertExecutorAuthorization(
  value: unknown,
  expectedTaskId: number,
  expectedIssuer: string,
  publicKeyPem: string,
  now = Date.now(),
): asserts value is ExecutorAuthorizationEnvelope {
  if (!expectedIssuer || !publicKeyPem) throw new Error("executor_trust_not_configured");
  if (!value || typeof value !== "object") throw new Error("executor_authorization_required");
  const auth = value as Partial<ExecutorAuthorizationEnvelope>;
  const lease = auth.lease;
  if (!lease || typeof lease !== "object") throw new Error("executor_authorization_required");
  if (lease.issuer !== expectedIssuer || !verifyCapabilityLease(lease, publicKeyPem, now)) throw new Error("executor_invalid_capability_lease");
  if (lease.taskId !== expectedTaskId || auth.actionDigest !== lease.actionDigest || auth.capability !== lease.capability || auth.actorUserId !== lease.actorUserId || lease.subject !== String(auth.actorUserId) || auth.tenant !== lease.tenant) {
    throw new Error("executor_authorization_binding");
  }
}
