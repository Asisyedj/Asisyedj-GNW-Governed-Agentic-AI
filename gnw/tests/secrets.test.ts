import { describe, expect, it } from "vitest";
import { MemorySecretProvider, SecretBroker, secretReference } from "../src/server/secrets.js";

describe("Step 5 secret boundary", () => {
  it("issues a digest-bound lease without returning a secret value", async () => {
    const provider = new MemorySecretProvider();
    provider.put("provider/api", "never-return-this");
    const broker = new SecretBroker(provider, 1000);
    const lease = await broker.issueLease({ secretName: "provider/api", tenant: "tenant-a", taskId: 7, actionDigest: "digest-a", host: "api.example.com", path: "/v1/generate", method: "post", now: 100, ttlMs: 500 });
    expect(secretReference("provider/api").value).toBe("[BROKER_ONLY]");
    await expect(broker.validateLease(lease, { tenant: "tenant-a", taskId: 7, actionDigest: "digest-a", host: "api.example.com", path: "/v1/generate", method: "POST" }, 200)).resolves.toBe(true);
  });

  it("rejects tenant, action, destination, and expiry mismatches", async () => {
    const provider = new MemorySecretProvider(); provider.put("s", "x");
    const broker = new SecretBroker(provider, 1000);
    const lease = await broker.issueLease({ secretName: "s", tenant: "a", taskId: 1, actionDigest: "d", host: "h.example", path: "/x", method: "GET", now: 10, ttlMs: 10 });
    await expect(broker.validateLease(lease, { tenant: "a", taskId: 1, actionDigest: "d", host: "h.example", path: "/x", method: "GET" }, 21)).rejects.toThrow("secret_lease_expired");
    await expect(broker.validateLease(lease, { tenant: "a", taskId: 1, actionDigest: "wrong", host: "h.example", path: "/x", method: "GET" }, 10)).rejects.toThrow("secret_lease_binding_mismatch");
  });

  it("rejects tampering and old leases after rotation or revocation", async () => {
    const provider = new MemorySecretProvider(); provider.put("s", "v1");
    const broker = new SecretBroker(provider, 1000);
    const input = { secretName: "s", tenant: "a", taskId: 1, actionDigest: "d", host: "h.example", path: "/x", method: "GET", now: 10 } as const;
    const lease = await broker.issueLease(input);
    await expect(broker.validateLease({ ...lease, path: "/other" }, input, 11)).rejects.toThrow("secret_lease_tampered");
    provider.rotate("s", "v2");
    await expect(broker.validateLease(lease, input, 11)).rejects.toThrow("secret_version_stale");
    const fresh = await broker.issueLease(input);
    broker.revoke("s", fresh.version);
    await expect(broker.validateLease(fresh, input, 11)).rejects.toThrow("secret_lease_revoked");
  });
});
