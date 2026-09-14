import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import request from "supertest";
import type { Express } from "express";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createApp } from "../src/server/app.js";
import { createDb, migrate, type Db } from "../src/server/db/index.js";
import { loadEnv } from "../src/server/env.js";
import { verifyAuditChain } from "../src/server/audit.js";
import * as repo from "../src/server/repo.js";

const artifactDir = fs.mkdtempSync(path.join(os.tmpdir(), "gnw-test-"));
const env = loadEnv({
  NODE_ENV: "test",
  SESSION_SECRET: "t".repeat(48),
  DATABASE_URL: "file::memory:",
  ALLOW_SELF_REGISTRATION: "true",
  ARTIFACT_DIR: artifactDir,
  LLM_API_KEY: "",
  VIDEO_PROVIDER_URL: "",
});

let app: Express;
let db: Db;
let ownerCookie = "";
let memberCookie = "";

const web = (agent: request.Test, cookie = ownerCookie) => agent.set("x-gnw-client", "web").set("cookie", cookie);

beforeAll(async () => {
  db = await createDb(env.databaseUrl);
  await migrate(db);
  app = await createApp(env, Promise.resolve(db));

  const owner = await request(app).post("/api/auth/register").set("x-gnw-client", "web").send({ email: "owner@example.com", password: "correct-horse-battery" });
  expect(owner.status).toBe(201);
  ownerCookie = extractCookie(owner.headers["set-cookie"]);

  const member = await request(app).post("/api/auth/register").set("x-gnw-client", "web").send({ email: "member@example.com", password: "another-long-password" });
  expect(member.status).toBe(201);
  memberCookie = extractCookie(member.headers["set-cookie"]);
});

afterAll(async () => {
  await db.close();
  fs.rmSync(artifactDir, { recursive: true, force: true });
});

function extractCookie(header: string[] | string | undefined) {
  const values = Array.isArray(header) ? header : header ? [header] : [];
  return values.map(value => value.split(";")[0]).join("; ");
}

describe("health and readiness", () => {
  it("reports health without a session", async () => {
    const response = await request(app).get("/api/health");
    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({ status: "ok", service: "gnw-governed-agent" });
  });

  it("reports readiness with per-check detail", async () => {
    const response = await request(app).get("/api/ready");
    expect([200, 503]).toContain(response.status);
    expect(response.body.checks).toHaveProperty("database", "ok");
    expect(response.body.notes.llm).toMatch(/offline/i);
  });
});

describe("authentication and tenancy", () => {
  it("refuses unauthenticated workspace access", async () => {
    const response = await request(app).get("/api/workspace/summary");
    expect(response.status).toBe(401);
  });

  it("refuses a mutation without the anti-CSRF header", async () => {
    const response = await request(app).post("/api/tasks").set("cookie", ownerCookie).send({ prompt: "hello world test", purpose: "p", selectedAgents: ["research"] });
    expect(response.status).toBe(403);
    expect(response.body.error).toBe("csrf_header_required");
  });

  it("throttles repeated failed logins", async () => {
    for (let attempt = 0; attempt < 9; attempt += 1) {
      await request(app).post("/api/auth/login").set("x-gnw-client", "web").send({ email: "owner@example.com", password: "wrong-password" });
    }
    const response = await request(app).post("/api/auth/login").set("x-gnw-client", "web").send({ email: "owner@example.com", password: "wrong-password" });
    expect(response.status).toBe(429);
  });

  it("hard-disables the guest-admin path", async () => {
    const response = await request(app).post("/api/auth/guest").set("x-gnw-client", "web");
    expect(response.status).toBe(410);
    expect(response.body.error).toBe("guest_access_disabled");
  });

  it("fails closed instead of trusting an unsigned Google JWT payload", async () => {
    const unsigned = `eyJhbGciOiJub25lIn0.${Buffer.from(JSON.stringify({ email: "attacker@example.com", name: "Attacker" })).toString("base64url")}.`;
    const response = await request(app).post("/api/auth/google").set("x-gnw-client", "web").send({ credential: unsigned });
    expect(response.status).toBe(503);
    expect(response.body.error).toBe("google_oidc_verifier_not_configured");
  });
});

describe("governed task execution", () => {
  it("runs specialists and records runs, messages and audit", async () => {
    const response = await web(request(app).post("/api/tasks")).send({
      prompt: "Assess the rollout risk of the new billing service.",
      purpose: "risk review",
      classification: "internal",
      selectedAgents: ["research", "analysis", "qa"],
      budgetTokens: 4000,
      budgetBytes: 4096,
    });
    expect(response.status).toBe(201);
    expect(response.body.status).toBe("completed");

    const detail = await web(request(app).get(`/api/tasks/${response.body.taskId}`));
    expect(detail.status).toBe(200);
    expect(detail.body.runs).toHaveLength(3);
    expect(detail.body.runs.every((run: { status: string }) => run.status === "completed")).toBe(true);
    expect(detail.body.messages.some((message: { role: string }) => message.role === "orchestrator")).toBe(true);
    expect(detail.body.audit.some((event: { event_type: string }) => event.event_type === "agent_admission")).toBe(true);
  });

  it("holds a restricted task in the approval queue", async () => {
    const response = await web(request(app).post("/api/tasks")).send({
      prompt: "Summarise the restricted incident report for the board.",
      purpose: "board briefing",
      classification: "restricted",
      selectedAgents: ["analysis"],
      budgetTokens: 2000,
      budgetBytes: 4096,
    });
    expect(response.status).toBe(201);
    expect(response.body.status).toBe("awaiting_approval");
  });

  it("refuses a task that another tenant owns", async () => {
    const created = await web(request(app).post("/api/tasks")).send({
      prompt: "Owner only task for tenant isolation.",
      purpose: "isolation",
      classification: "internal",
      selectedAgents: ["research"],
      budgetTokens: 1000,
      budgetBytes: 4096,
    });
    const response = await web(request(app).get(`/api/tasks/${created.body.taskId}`), memberCookie);
    expect(response.status).toBe(404);
  });
});

describe("video workflow, approvals and replay protection", () => {
  let taskId = 0;
  let approvalId = 0;
  let videoJobId = 0;

  it("produces brief, script and storyboard and queues provider submission", async () => {
    const response = await web(request(app).post("/api/tasks")).send({
      prompt: "Produce a launch video package for the Q4 release.",
      purpose: "launch video",
      classification: "internal",
      selectedAgents: ["video_producer"],
      budgetTokens: 4000,
      budgetBytes: 4096,
    });
    expect(response.status).toBe(201);
    expect(response.body.status).toBe("awaiting_approval");
    taskId = response.body.taskId;
    approvalId = response.body.approvalId;
    videoJobId = response.body.videoJobId;
    expect(approvalId).toBeGreaterThan(0);

    const detail = await web(request(app).get(`/api/tasks/${taskId}`));
    const outputs = detail.body.runs.map((run: { action_digest: string }) => run.action_digest);
    expect(new Set(outputs).size).toBe(3);
    expect(detail.body.videoJobs[0].status).toBe("awaiting_approval");
  });

  it("refuses provider submission before approval", async () => {
    const response = await web(request(app).post("/api/video/submit")).send({ approvalId });
    expect(response.status).toBe(403);
    expect(response.body.reason).toBe("approval_required");
  });

  it("refuses review by a different tenant", async () => {
    const response = await web(request(app).post(`/api/approvals/${approvalId}/review`), memberCookie).send({ status: "approved" });
    expect(response.status).toBe(403);
  });

  it("submits once after approval and refuses the replay", async () => {
    const review = await web(request(app).post(`/api/approvals/${approvalId}/review`)).send({ status: "approved" });
    expect(review.status).toBe(200);

    const first = await web(request(app).post("/api/video/submit")).send({ approvalId });
    expect(first.status).toBe(200);
    expect(first.body.status).toBe("completed");
    expect(first.body.providerJobId).toMatch(/^stub-/);

    const replay = await web(request(app).post("/api/video/submit")).send({ approvalId });
    expect(replay.status).toBe(403);
    expect(replay.body.reason).toBe("approval_replay");
  });

  it("registers an external storage reference for the completed job", async () => {
    const response = await web(request(app).get(`/api/video/${videoJobId}`));
    expect(response.status).toBe(200);
    expect(response.body.job.status).toBe("completed");
    const artifact = response.body.artifacts.find((item: { kind: string }) => item.kind === "video");
    expect(artifact).toBeTruthy();
    expect(fs.existsSync(path.join(artifactDir, artifact.storage_key))).toBe(true);
  });

  it("raises owner notifications for approval and completion", async () => {
    const summary = await web(request(app).get("/api/workspace/summary"));
    const titles = summary.body.notifications.map((item: { title: string }) => item.title);
    expect(titles).toContain("GNW approval required");
    expect(titles).toContain("GNW video job completed");
  });

  it("refuses a denied approval and stops its video job", async () => {
    const created = await web(request(app).post("/api/tasks")).send({
      prompt: "Second launch video package to be denied by the reviewer.",
      purpose: "launch video",
      classification: "internal",
      selectedAgents: ["video_producer"],
      budgetTokens: 4000,
      budgetBytes: 4096,
    });
    const review = await web(request(app).post(`/api/approvals/${created.body.approvalId}/review`)).send({ status: "denied" });
    expect(review.status).toBe(200);
    const submit = await web(request(app).post("/api/video/submit")).send({ approvalId: created.body.approvalId });
    expect(submit.status).toBe(403);
    expect(submit.body.reason).toBe("approval_required");
    const job = await web(request(app).get(`/api/video/${created.body.videoJobId}`));
    expect(job.body.job.status).toBe("stopped");
  });

  it("refuses an expired approval", async () => {
    const created = await web(request(app).post("/api/tasks")).send({
      prompt: "Third launch video package used for approval expiry.",
      purpose: "launch video",
      classification: "internal",
      selectedAgents: ["video_producer"],
      budgetTokens: 4000,
      budgetBytes: 4096,
    });
    await web(request(app).post(`/api/approvals/${created.body.approvalId}/review`)).send({ status: "approved" });
    await db.run("UPDATE approvals SET expires_at = ? WHERE id = ?", [Date.now() - 1000, created.body.approvalId]);
    const submit = await web(request(app).post("/api/video/submit")).send({ approvalId: created.body.approvalId });
    expect(submit.status).toBe(403);
    expect(["approval_expired", "approval_required"]).toContain(submit.body.reason);
  });
});

describe("separation of duties", () => {
  it("refuses self-approval by a non-admin requester", async () => {
    const created = await web(request(app).post("/api/tasks"), memberCookie).send({
      prompt: "Member video package that the member must not self-approve.",
      purpose: "launch video",
      classification: "internal",
      selectedAgents: ["video_producer"],
      budgetTokens: 4000,
      budgetBytes: 4096,
    });
    const review = await web(request(app).post(`/api/approvals/${created.body.approvalId}/review`), memberCookie).send({ status: "approved" });
    expect(review.status).toBe(403);
    expect(review.body.error).toBe("separation_of_duties");
  });
});

describe("safety interlocks", () => {
  it("refuses interlock changes from a member and admits them from an admin", async () => {
    const refused = await web(request(app).post("/api/controls/interlock"), memberCookie).send({ killSwitch: true });
    expect(refused.status).toBe(403);

    const engaged = await web(request(app).post("/api/controls/interlock")).send({ killSwitch: true });
    expect(engaged.status).toBe(200);
    expect(engaged.body.killSwitch).toBe(true);
  });

  it("fails closed for new tasks while the kill switch is engaged", async () => {
    const response = await web(request(app).post("/api/tasks")).send({
      prompt: "This task must not be admitted while stopped.",
      purpose: "interlock test",
      classification: "internal",
      selectedAgents: ["research"],
      budgetTokens: 1000,
      budgetBytes: 4096,
    });
    expect(response.status).toBe(423);
    expect(response.body.error).toBe("safety_interlock");
  });

  it("persists interlock state in the database and clears it", async () => {
    expect(await repo.getInterlock(db)).toMatchObject({ killSwitch: true });
    const cleared = await web(request(app).post("/api/controls/interlock")).send({ killSwitch: false, circuitOpen: false });
    expect(cleared.body).toMatchObject({ killSwitch: false, circuitOpen: false });
  });
});

describe("audit integrity", () => {
  it("keeps the whole chain verifiable after the full workflow", async () => {
    const response = await web(request(app).get("/api/audit/verify"));
    expect(response.body.valid).toBe(true);
    expect(response.body.events).toBeGreaterThan(10);
    await expect(verifyAuditChain(db)).resolves.toMatchObject({ valid: true });
  });

  it("records denials as first-class evidence", async () => {
    const response = await web(request(app).get("/api/audit"));
    const denials = response.body.events.filter((event: { decision: string }) => event.decision === "DENY");
    expect(denials.length).toBeGreaterThan(0);
  });
});
