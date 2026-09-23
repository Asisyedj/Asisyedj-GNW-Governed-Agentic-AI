import { describe, expect, it } from "vitest";
import { generateKeyPairSync } from "node:crypto";
import { signGrant, verifyGrantSignature, canonicalize, sha256 } from "../src/server/security.js";
import { GovernanceService, MemoryGovernanceStores, type GovernanceRequest } from "../src/server/governance.js";

function baseGrant(): GovernanceRequest {
  const now = Date.now();
  return {
    requestId: "r1", subject: "1", tenant: "t1", role: "admin", purpose: "test", classification: "internal",
    operation: "analysis", resource: "task:1", agent: "research", tool: "knowledge.search", scope: "knowledge.search",
    budgetTokens: 1000, budgetBytes: 1000, issuedAt: now - 10, expiresAt: now + 10000, nonce: "n1",
    taskId: 1, normalizedParameters: { promptDigest: sha256("hello") }, inputDigest: sha256("hello"), budgetReservationTokens: 100, budgetReservationBytes: 100,
  };
}

describe("GNW v3 security controls", () => {
  it("signs and verifies frozen grant material", () => {
    const keys = generateKeyPairSync("ed25519", { privateKeyEncoding: { type: "pkcs8", format: "pem" }, publicKeyEncoding: { type: "spki", format: "pem" } });
    const grant = baseGrant();
    const signed = signGrant(grant as unknown as Record<string, unknown>, "issuer-1", keys.privateKey);
    expect(verifyGrantSignature({ ...grant, issuer: signed.issuer, signature: signed.signature }, signed.issuer, signed.signature, keys.publicKey)).toBe(true);
    expect(verifyGrantSignature({ ...grant, normalizedParameters: { promptDigest: sha256("changed") }, issuer: signed.issuer, signature: signed.signature }, signed.issuer, signed.signature, keys.publicKey)).toBe(false);
  });

  it("canonicalization is key-order independent", () => {
    expect(canonicalize({ b: 2, a: 1 })).toBe(canonicalize({ a: 1, b: 2 }));
  });

  it("replay remains denied after the first admission", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    const grant = baseGrant();
    expect((await service.authorize(grant)).status).toBe("ALLOW");
    expect((await service.authorize(grant)).reason).toBe("grant_replay");
  });
});
