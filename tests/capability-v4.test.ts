import { describe, expect, it } from "vitest";
import { generateKeyPairSync } from "node:crypto";
import { issueCapabilityLease, verifyCapabilityLease } from "../src/server/capability.js";
import { hashEvent } from "../src/server/audit.js";

describe("GNW v4 capability lease and audit integrity", () => {
  it("accepts an exact signed lease and rejects capability substitution", () => {
    const keys = generateKeyPairSync("ed25519", { privateKeyEncoding: { type: "pkcs8", format: "pem" }, publicKeyEncoding: { type: "spki", format: "pem" } });
    const lease = issueCapabilityLease({ requestId: "r1", actionDigest: "a1", subject: "1", tenant: "t1", taskId: 1, actorUserId: 1, capability: "video.provider_job", destination: "https://provider.example", ttlMs: 60_000, issuer: "issuer-1", privateKeyPem: keys.privateKey });
    expect(verifyCapabilityLease(lease, keys.publicKey)).toBe(true);
    expect(verifyCapabilityLease({ ...lease, capability: "artifact.storage" }, keys.publicKey)).toBe(false);
  });

  it("binds the lease lifetime and rejects expiry tampering", () => {
    const keys = generateKeyPairSync("ed25519", { privateKeyEncoding: { type: "pkcs8", format: "pem" }, publicKeyEncoding: { type: "spki", format: "pem" } });
    const lease = issueCapabilityLease({ requestId: "r1", actionDigest: "a1", subject: "1", tenant: "t1", taskId: 1, actorUserId: 1, capability: "llm.chat", ttlMs: 60_000, issuer: "issuer-1", privateKeyPem: keys.privateKey });
    expect(verifyCapabilityLease({ ...lease, expiresAt: lease.issuedAt - 1 }, keys.publicKey)).toBe(false);
  });

  it("hashes the exact persisted audit reason instead of a truncated value", () => {
    const long = "x".repeat(181);
    expect(hashEvent("GENESIS", 1, "test", "DENY", long, "digest")).not.toBe(hashEvent("GENESIS", 1, "test", "DENY", long.slice(0, 180), "digest"));
  });
});
