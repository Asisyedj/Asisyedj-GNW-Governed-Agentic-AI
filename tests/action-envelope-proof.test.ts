import { describe, expect, it } from "vitest";
import { generateKeyPairSync } from "node:crypto";
import { createDb, migrate } from "../src/server/db/index.js";
import { appendAudit } from "../src/server/audit.js";
import { createActionEnvelope, digestActionEnvelope, signActionEnvelope, verifySignedActionEnvelope, approvalMatchesAction } from "../src/server/action-envelope.js";
import { exportAuditProofBundle, verifyAuditProofBundle, verifyAuditBundleSignature } from "../src/server/merkle.js";

describe("GNW exact action and independent evidence", () => {
  const envelope = () => createActionEnvelope({
    actionId: "a-1", requestId: "r-1", tenant: "tenant-a", actor: "user-1", agent: "engineering", tool: "file.write",
    operation: "write", resource: "task:1", parameters: { path: "src/a.ts", content: "safe" }, purpose: "controlled code change",
    classification: "internal", risk: "HIGH", policy: "policy-v1", approval: null, capability: null, generation: { provider: "offline", model: "deterministic" },
    budget: { tokens: 100, bytes: 1000 }, effectConstraints: { sandbox: "task-1" }, timestamps: { issuedAt: 1, expiresAt: 10_000 }, nonce: "n-1",
    provenance: { risk: { value: "HIGH", source: "GNW", trust: "GNW_DERIVED" } },
  });

  it("changes the digest when exact parameters change", () => {
    const first = envelope();
    const changed = { ...first, parametersDigest: "changed" };
    expect(digestActionEnvelope(first)).not.toBe(digestActionEnvelope(changed));
    expect(approvalMatchesAction({ actionDigest: digestActionEnvelope(first), expiresAt: Date.now() + 10_000 }, first)).toBe(true);
    expect(approvalMatchesAction({ actionDigest: digestActionEnvelope(first), expiresAt: Date.now() + 10_000 }, changed)).toBe(false);
  });

  it("signs and verifies a canonical action envelope, rejecting mutation", () => {
    const keys = generateKeyPairSync("ed25519", { privateKeyEncoding: { type: "pkcs8", format: "pem" }, publicKeyEncoding: { type: "spki", format: "pem" } });
    const signed = signActionEnvelope(envelope(), "gnw-issuer", keys.privateKey);
    expect(verifySignedActionEnvelope(signed, keys.publicKey)).toBe(true);
    expect(verifySignedActionEnvelope({ ...signed, operation: "delete" }, keys.publicKey)).toBe(false);
  });

  it("exports complete task evidence and verifies every Merkle proof offline", async () => {
    const db = await createDb("file::memory:");
    await migrate(db);
    await appendAudit(db, { taskId: 1, eventType: "task", decision: "ALLOW", reason: "created", payload: { n: 1 } });
    await appendAudit(db, { taskId: 1, eventType: "effect", decision: "ALLOW", reason: "executed", payload: { n: 2 } });
    const keys = generateKeyPairSync("ed25519", { privateKeyEncoding: { type: "pkcs8", format: "pem" }, publicKeyEncoding: { type: "spki", format: "pem" } });
    const bundle = await exportAuditProofBundle(db, 1, { issuer: "gnw-audit", privateKeyPem: keys.privateKey });
    expect(bundle.complete).toBe(true);
    expect(verifyAuditProofBundle(bundle).valid).toBe(true);
    expect(verifyAuditBundleSignature(bundle, keys.publicKey)).toBe(true);
    await db.close();
  });
});
