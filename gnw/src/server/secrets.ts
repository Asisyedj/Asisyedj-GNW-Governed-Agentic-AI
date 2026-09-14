import { createHash, randomUUID } from "node:crypto";

export type SecretLeaseRequest = {
  secretName: string;
  tenant: string;
  taskId: number;
  actionDigest: string;
  host: string;
  path: string;
  method: string;
  now?: number;
  ttlMs?: number;
};

export type SecretLease = {
  leaseId: string;
  secretName: string;
  tenant: string;
  taskId: number;
  actionDigest: string;
  host: string;
  path: string;
  method: string;
  issuedAt: number;
  expiresAt: number;
  version: number;
  leaseDigest: string;
};

export type SecretVersion = { version: number; revoked: boolean; createdAt: number };

export interface SecretProvider {
  metadata(secretName: string): Promise<SecretVersion | null>;
  issue(name: string): Promise<{ version: number; value: string } | null>;
}

function clean(value: string, field: string) {
  const result = value.trim();
  if (!result || result.length > 512 || /[\r\n]/.test(result)) throw new Error(`invalid_${field}`);
  return result;
}

function canonicalLease(input: Omit<SecretLease, "leaseDigest">) {
  return JSON.stringify(Object.keys(input).sort().map((key) => [key, (input as Record<string, unknown>)[key]]));
}

/**
 * GNW never stores or returns the secret value. A real provider (KMS/Secrets
 * Manager/Vault) is called only by the execution-side adapter after this
 * lease is validated. Revocation is represented by the provider version and
 * an in-memory epoch in this reference implementation; production must back
 * the epoch with durable state and provider-side version revocation.
 */
export class SecretBroker {
  private readonly revoked = new Set<string>();

  constructor(private readonly provider: SecretProvider, private readonly maxTtlMs = 60_000) {}

  async issueLease(request: SecretLeaseRequest): Promise<SecretLease> {
    const secretName = clean(request.secretName, "secret_name");
    const tenant = clean(request.tenant, "tenant");
    const host = clean(request.host.toLowerCase(), "host");
    const path = clean(request.path, "path");
    const method = clean(request.method.toUpperCase(), "method");
    const actionDigest = clean(request.actionDigest, "action_digest");
    const now = request.now ?? Date.now();
    const ttlMs = request.ttlMs ?? this.maxTtlMs;
    if (!Number.isInteger(request.taskId) || request.taskId <= 0) throw new Error("invalid_task_id");
    if (!Number.isFinite(now) || !Number.isFinite(ttlMs) || ttlMs <= 0 || ttlMs > this.maxTtlMs) throw new Error("invalid_lease_ttl");
    const version = await this.provider.metadata(secretName);
    if (!version || version.revoked) throw new Error("secret_unavailable");
    const lease = {
      leaseId: randomUUID(), secretName, tenant, taskId: request.taskId,
      actionDigest, host, path, method, issuedAt: now, expiresAt: now + ttlMs,
      version: version.version,
    } satisfies Omit<SecretLease, "leaseDigest">;
    return { ...lease, leaseDigest: createHash("sha256").update(canonicalLease(lease)).digest("hex") };
  }

  revoke(secretName: string, version: number) { this.revoked.add(`${secretName}:${version}`); }

  async validateLease(lease: SecretLease, request: Pick<SecretLeaseRequest, "tenant" | "taskId" | "actionDigest" | "host" | "path" | "method">, now = Date.now()) {
    const { leaseDigest, ...unsignedLease } = lease;
    const expected = createHash("sha256").update(canonicalLease(unsignedLease)).digest("hex");
    if (expected !== lease.leaseDigest) throw new Error("secret_lease_tampered");
    if (now >= lease.expiresAt) throw new Error("secret_lease_expired");
    if (this.revoked.has(`${lease.secretName}:${lease.version}`)) throw new Error("secret_lease_revoked");
    if (lease.tenant !== request.tenant || lease.taskId !== request.taskId || lease.actionDigest !== request.actionDigest) throw new Error("secret_lease_binding_mismatch");
    if (lease.host !== request.host.toLowerCase() || lease.path !== request.path || lease.method !== request.method.toUpperCase()) throw new Error("secret_lease_destination_mismatch");
    const current = await this.provider.metadata(lease.secretName);
    if (!current || current.revoked || current.version !== lease.version) throw new Error("secret_version_stale");
    return true;
  }
}

export class MemorySecretProvider implements SecretProvider {
  private readonly records = new Map<string, { version: number; value: string; revoked: boolean; createdAt: number }>();
  put(name: string, value: string, version = 1) { this.records.set(name, { version, value, revoked: false, createdAt: Date.now() }); }
  rotate(name: string, value: string) {
    const old = this.records.get(name);
    this.put(name, value, (old?.version ?? 0) + 1);
    return old?.version ?? null;
  }
  revoke(name: string) { const record = this.records.get(name); if (record) record.revoked = true; }
  async metadata(name: string) { const record = this.records.get(name); return record ? { version: record.version, revoked: record.revoked, createdAt: record.createdAt } : null; }
  async issue(name: string) { const record = this.records.get(name); return record && !record.revoked ? { version: record.version, value: record.value } : null; }
}

export function secretReference(name: string) {
  return { secretName: clean(name, "secret_name"), value: "[BROKER_ONLY]" as const };
}
