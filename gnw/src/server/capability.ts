import { randomUUID } from "node:crypto";
import { canonicalize, signGrant, verifyGrantSignature } from "./security.js";

export type CapabilityLease = {
  leaseId: string;
  requestId: string;
  actionDigest: string;
  subject: string;
  tenant: string;
  taskId: number;
  actorUserId: number;
  capability: string;
  destination?: string | null;
  issuedAt: number;
  expiresAt: number;
  nonce: string;
  issuer: string;
  signature: string;
  /** Durable interlock generation captured at admission. */
  interlockGeneration: number;
};

export function capabilitySigningPayload(lease: Omit<CapabilityLease, "signature">) {
  return canonicalize(lease);
}

export function issueCapabilityLease(input: Omit<CapabilityLease, "leaseId" | "nonce" | "issuedAt" | "expiresAt" | "signature" | "issuer" | "interlockGeneration"> & { ttlMs: number; issuer: string; privateKeyPem: string; interlockGeneration?: number }, now = Date.now()): CapabilityLease {
  const lease: Omit<CapabilityLease, "signature"> = {
    leaseId: randomUUID(),
    requestId: input.requestId,
    actionDigest: input.actionDigest,
    subject: input.subject,
    tenant: input.tenant,
    taskId: input.taskId,
    actorUserId: input.actorUserId,
    capability: input.capability,
    destination: input.destination ?? null,
    issuedAt: now,
    expiresAt: now + input.ttlMs,
    nonce: randomUUID(),
    issuer: input.issuer,
    interlockGeneration: input.interlockGeneration ?? 0,
  };
  const signed = signGrant(lease as unknown as Record<string, unknown>, input.issuer, input.privateKeyPem);
  return { ...lease, issuer: signed.issuer, signature: signed.signature };
}

export function verifyCapabilityLease(lease: CapabilityLease, publicKeyPem: string, now = Date.now(), expectedAudience?: string | null): boolean {
  if (!Number.isInteger(lease.issuedAt) || !Number.isInteger(lease.expiresAt) || lease.expiresAt <= lease.issuedAt || now < lease.issuedAt || now >= lease.expiresAt) return false;
  if (!lease.leaseId || !lease.nonce || !lease.requestId || !lease.actionDigest || !lease.subject || !lease.tenant || !lease.capability || !lease.signature || !lease.issuer) return false;
  if (!Number.isInteger(lease.interlockGeneration) || lease.interlockGeneration < 0) return false;
  if (expectedAudience !== undefined && (lease.destination ?? null) !== (expectedAudience ?? null)) return false;
  return verifyGrantSignature(lease as unknown as Record<string, unknown>, lease.issuer, lease.signature, publicKeyPem);
}
