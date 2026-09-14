import { describe, expect, it } from "vitest";
import { generateKeyPairSync } from "node:crypto";
import { assertExecutorAuthorization } from "../src/executor/auth.js";
import { issueCapabilityLease } from "../src/server/capability.js";

function pair() {
  return generateKeyPairSync("ed25519", {
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
    publicKeyEncoding: { type: "spki", format: "pem" },
  });
}

function envelope() {
  const kp = pair();
  const lease = issueCapabilityLease({
    requestId: "executor-auth-test",
    actionDigest: "executor-action",
    subject: "7",
    tenant: "tenant-user-7",
    taskId: 77,
    actorUserId: 7,
    capability: "exec.command",
    ttlMs: 60_000,
    issuer: "executor-test-issuer",
    privateKeyPem: kp.privateKey,
  });
  return { kp, lease, auth: { lease, actionDigest: "executor-action", capability: "exec.command", actorUserId: 7, tenant: "tenant-user-7" } };
}

describe("independent remote executor authorization", () => {
  it("accepts only a valid signed lease with exact binding", () => {
    const { kp, auth } = envelope();
    expect(() => assertExecutorAuthorization(auth, 77, "executor-test-issuer", kp.publicKey)).not.toThrow();
  });

  it("rejects signature tampering and binding substitution before execution", () => {
    const { kp, auth } = envelope();
    expect(() => assertExecutorAuthorization({ ...auth, tenant: "tenant-attacker" }, 77, "executor-test-issuer", kp.publicKey)).toThrow("executor_authorization_binding");
    expect(() => assertExecutorAuthorization({ ...auth, lease: { ...auth.lease, capability: "file.write" } }, 77, "executor-test-issuer", kp.publicKey)).toThrow("executor_invalid_capability_lease");
  });

  it("fails closed when executor trust configuration is missing", () => {
    const { auth } = envelope();
    expect(() => assertExecutorAuthorization(auth, 77, "", "")).toThrow("executor_trust_not_configured");
  });
});
