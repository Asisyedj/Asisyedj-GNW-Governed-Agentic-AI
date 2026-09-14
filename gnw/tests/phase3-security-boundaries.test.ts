import { describe, expect, it } from "vitest";
import { generateKeyPairSync } from "node:crypto";
import { executeExternal, ExecutionDenied } from "../src/server/execution.js";
import { executeInRemoteExecutor } from "../src/server/executor-client.js";
import { issueCapabilityLease } from "../src/server/capability.js";
import { loadEnv } from "../src/server/env.js";
import { createDb, migrate } from "../src/server/db/index.js";
import * as repo from "../src/server/repo.js";

const env = loadEnv({
  NODE_ENV: "test",
  DATABASE_URL: "file::memory:",
  SESSION_SECRET: "s".repeat(48),
  ALLOW_SELF_REGISTRATION: "true",
  ARTIFACT_DIR: "./test-artifacts",
  GNW_EXECUTOR_URL: "https://executor.example",
  GNW_EXECUTOR_SHARED_TOKEN: "executor-test-token",
  ALLOWED_EGRESS_HOSTS: "executor.example",
});

function keys() {
  return generateKeyPairSync("ed25519", {
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
    publicKeyEncoding: { type: "spki", format: "pem" },
  });
}

async function taskDb() {
  const db = await createDb("file::memory:");
  await migrate(db);
  const workspaceId = await repo.ensurePersonalWorkspace(db, 7, "phase3@example.test");
  const taskId = await repo.createTask(db, {
    workspaceId,
    createdBy: 7,
    title: "Phase 3 test task",
    prompt: "Test executor security",
    purpose: "security validation",
    classification: "internal",
    selectedAgents: ["engineering"],
    budgetTokens: 1000,
    budgetBytes: 1000,
    status: "queued",
  });
  return { db, taskId, tenant: "tenant-user-7" };
}

describe("Phase 3 executor and fencing adversarial boundaries", () => {
  it("increments the durable interlock generation and blocks a stale lease before the sink", async () => {
    const { db, taskId, tenant } = await taskDb();
    const lease = issueCapabilityLease({
      requestId: "phase3-stale-lease",
      actionDigest: "phase3-action",
      subject: "7",
      tenant,
      taskId,
      actorUserId: 7,
      capability: "exec.command",
      ttlMs: 60_000,
      issuer: env.grantIssuer,
      privateKeyPem: env.grantPrivateKeyPem,
      interlockGeneration: 0,
    });
    await repo.createCapabilityLease(db, lease);
    expect((await repo.getInterlock(db)).generation).toBe(0);
    await repo.setInterlock(db, { killSwitch: true }, 7);
    await repo.setInterlock(db, { killSwitch: false }, 7);
    expect((await repo.getInterlock(db)).generation).toBe(2);

    let effects = 0;
    await expect(executeExternal({
      db,
      env,
      taskId,
      actorUserId: 7,
      eventType: "phase3_stale_probe",
      actionDigest: "phase3-action",
      capabilityLease: lease,
      capability: "exec.command",
      effect: async () => { effects += 1; return "must-not-run"; },
    })).rejects.toMatchObject({ reason: "stale_interlock_generation", stop: true });
    expect(effects).toBe(0);
    await db.close();
  });

  it("rejects actor and tenant substitution in the central execution gate", async () => {
    const { db, taskId, tenant } = await taskDb();
    const lease = issueCapabilityLease({
      requestId: "phase3-binding",
      actionDigest: "phase3-binding-action",
      subject: "999",
      tenant: "tenant-attacker",
      taskId,
      actorUserId: 999,
      capability: "file.write",
      ttlMs: 60_000,
      issuer: env.grantIssuer,
      privateKeyPem: env.grantPrivateKeyPem,
    });
    await repo.createCapabilityLease(db, lease);
    await expect(executeExternal({
      db,
      env,
      taskId,
      actorUserId: 7,
      eventType: "phase3_binding_probe",
      actionDigest: "phase3-binding-action",
      capabilityLease: lease,
      capability: "file.write",
      effect: async () => "must-not-run",
    })).rejects.toMatchObject({ reason: "capability_binding" });
    expect((await repo.getInterlock(db)).generation).toBe(0);
    // Binding denial occurs before lease consumption, so an attacker cannot burn
    // a valid lease by presenting it under the wrong actor or tenant.
    expect(await repo.consumeCapabilityLease(db, lease.leaseId)).toBe(true);
    expect(await repo.consumeCapabilityLease(db, lease.leaseId)).toBe(false);
    expect(tenant).toBe("tenant-user-7");
    await db.close();
  });

  it("rejects a remote executor request whose authorization envelope is substituted", async () => {
    const kp = keys();
    const lease = issueCapabilityLease({
      requestId: "phase3-remote-binding",
      actionDigest: "remote-action",
      subject: "7",
      tenant: "tenant-user-7",
      taskId: 77,
      actorUserId: 7,
      capability: "exec.command",
      ttlMs: 60_000,
      issuer: "phase3-test-issuer",
      privateKeyPem: kp.privateKey,
    });
    await expect(executeInRemoteExecutor(env, {
      taskId: 77,
      command: "echo blocked",
      authorization: {
        lease,
        actionDigest: "remote-action",
        capability: "exec.command",
        actorUserId: 7,
        tenant: "tenant-attacker",
      },
    })).rejects.toThrow("executor_authorization_binding");
  });
});
