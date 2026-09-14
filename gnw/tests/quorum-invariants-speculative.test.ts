import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { MultiAgentQuorumEngine, computeProposalDigest, computeVoteSignature } from "../src/server/quorum.js";
import { TrajectoryInvariantEngine } from "../src/server/invariants.js";
import { SpeculativeSandboxEngine } from "../src/server/sandbox/speculative.js";
import { TaskSandbox } from "../src/server/sandbox/index.js";
import request from "supertest";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import os from "node:os";
import path from "node:path";
import { createApp } from "../src/server/app.js";
import { createDb, migrate, type Db } from "../src/server/db/index.js";
import { loadEnv } from "../src/server/env.js";

describe("Frontier Super Weapons: Quorum, Invariants & Speculative Execution", () => {
  describe("Multi-Agent Consensus Quorum Engine (Frontier Quorum)", () => {
    let engine: MultiAgentQuorumEngine;

    beforeEach(() => {
      engine = new MultiAgentQuorumEngine(0.66);
    });

    it("approves high-risk action when 3-agent consensus is reached", () => {
      const proposal = engine.createProposal({
        taskId: 101,
        actorUserId: 1,
        tool: "fs.write",
        operation: "write_file",
        parameters: { path: "src/critical.ts", content: "export const version = '4.0.0';" },
        justification: "Upgrading core version in governed repository under change request CR-441",
        isDestructive: false,
      });

      expect(proposal.digest).toBeDefined();
      expect(proposal.digest.length).toBe(64);

      // 1. Coder / Proposer votes
      engine.submitVote({
        proposalId: proposal.proposalId,
        role: "coder_proposer",
        agentId: "coder-specialist-1",
        approve: true,
        reason: "Code implementation is complete, well-formatted, and matches requirements.",
        timestamp: Date.now(),
      });

      // 2. Security Auditor automated analysis
      const auditVote = engine.auditSecurity(proposal.proposalId, "sec-auditor-1");
      expect(auditVote.approve).toBe(true);
      expect(auditVote.veto).toBe(false);

      // 3. Chief Justice adjudication
      const justiceVote = engine.adjudicateChiefJustice(proposal.proposalId, "chief-justice-1");
      expect(justiceVote.approve).toBe(true);

      // 4. Evaluate Quorum consensus
      const result = engine.adjudicate(proposal.proposalId);
      expect(result.status).toBe("APPROVED");
      expect(result.approvals).toBe(3);
      expect(result.totalVotes).toBe(3);
      expect(result.consensusRatio).toBe(1.0);
      expect(result.consensusDigest).toBeDefined();
    });

    it("vetoes immediately when Security Auditor flags dangerous malicious command", () => {
      const dangerousProposal = engine.createProposal({
        taskId: 102,
        actorUserId: 1,
        tool: "bash.execute",
        operation: "run_shell",
        parameters: { command: "rm -rf / --no-preserve-root" },
        justification: "Cleaning up workspace to free up disk space",
        isDestructive: true,
      });

      // Coder mistakenly approves
      engine.submitVote({
        proposalId: dangerousProposal.proposalId,
        role: "coder_proposer",
        agentId: "coder-specialist-1",
        approve: true,
        reason: "Proposed cleanup command.",
        timestamp: Date.now(),
      });

      // Security Auditor performs automated AST/regex analysis
      const auditVote = engine.auditSecurity(dangerousProposal.proposalId, "sec-auditor-1");
      expect(auditVote.approve).toBe(false);
      expect(auditVote.veto).toBe(true);
      expect(auditVote.reason).toContain("VETO: Security audit detected prohibited");

      // Quorum must be VETOED regardless of other votes
      const result = engine.adjudicate(dangerousProposal.proposalId);
      expect(result.status).toBe("VETOED");
      expect(result.vetoAgent).toBe("sec-auditor-1");
      expect(result.vetoReason).toContain("VETO");
    });

    it("rejects proposal when Chief Justice finds insufficient justification", () => {
      const unjustifiedProposal = engine.createProposal({
        taskId: 103,
        actorUserId: 2,
        tool: "db.migrate",
        operation: "schema_migration",
        parameters: { step: "drop_column" },
        justification: "test", // Too short / unjustified
        isDestructive: true,
      });

      engine.submitVote({
        proposalId: unjustifiedProposal.proposalId,
        role: "coder_proposer",
        agentId: "coder-1",
        approve: true,
        reason: "Drop unused column",
        timestamp: Date.now(),
      });

      engine.auditSecurity(unjustifiedProposal.proposalId);
      engine.adjudicateChiefJustice(unjustifiedProposal.proposalId);

      const result = engine.adjudicate(unjustifiedProposal.proposalId);
      expect(result.status).toBe("REJECTED");
      expect(result.approvals).toBe(2);
      expect(result.totalVotes).toBe(3);
      expect(result.consensusRatio).toBeLessThan(0.67);
    });

    it("produces deterministic cryptographic digests and tamper-evident signatures", () => {
      const raw = {
        proposalId: "prop-sample",
        taskId: 999,
        actorUserId: 1,
        tool: "test.tool",
        operation: "test_op",
        parameters: { a: 1, b: 2 },
        justification: "Deterministic hash test justification",
        isDestructive: false,
        timestamp: 1700000000000,
      };

      const digest1 = computeProposalDigest(raw);
      const digest2 = computeProposalDigest(raw);
      expect(digest1).toBe(digest2);

      const voteSig = computeVoteSignature(digest1, {
        proposalId: "prop-sample",
        role: "security_auditor",
        agentId: "agent-1",
        approve: true,
        reason: "All checks passed",
        timestamp: 1700000000100,
      });
      expect(voteSig).toBeDefined();
      expect(voteSig.length).toBe(64);
    });
  });

  describe("Trajectory Invariants & Anti-Loop Engine", () => {
    let invariants: TrajectoryInvariantEngine;

    beforeEach(() => {
      invariants = new TrajectoryInvariantEngine({
        maxConsecutiveIdenticalFailures: 2,
        maxTotalIdenticalFailures: 3,
        maxStepsPerTask: 20,
        maxCallsInWindow5s: 5,
        maxCallsInWindow30s: 15,
        maxFileThrashCount: 3,
      });
    });

    it("trips circuit breaker when identical failing tool call repeats", () => {
      const taskId = 201;
      const failingAction = {
        taskId,
        tool: "npm.install",
        parameters: { package: "non-existent-package-xyz123" },
      };

      // Record first failure
      invariants.recordStep({
        taskId,
        tool: failingAction.tool,
        parameters: failingAction.parameters,
        success: false,
        durationMs: 1500,
        timestamp: Date.now() - 2000,
      });

      // Allowed after 1 failure
      const check1 = invariants.checkInvariants(failingAction);
      expect(check1.allowed).toBe(true);

      // Record second failure
      invariants.recordStep({
        taskId,
        tool: failingAction.tool,
        parameters: failingAction.parameters,
        success: false,
        durationMs: 1400,
        timestamp: Date.now() - 1000,
      });

      // Now consecutive identical failures threshold (2) is reached
      const check2 = invariants.checkInvariants(failingAction);
      expect(check2.allowed).toBe(false);
      expect(check2.violation?.code).toContain("consecutive_identical_failure");
      expect(check2.violation?.recoveryAdvice).toBeDefined();
    });

    it("trips circuit breaker on ping-pong oscillation between two tools", () => {
      const taskId = 202;
      const now = Date.now();

      // Simulate A -> B -> A -> B
      invariants.recordStep({ taskId, tool: "toolA", parametersHash: "h1", success: true, durationMs: 10, timestamp: now - 400 });
      invariants.recordStep({ taskId, tool: "toolB", parametersHash: "h2", success: true, durationMs: 10, timestamp: now - 300 });
      invariants.recordStep({ taskId, tool: "toolA", parametersHash: "h1", success: true, durationMs: 10, timestamp: now - 200 });
      invariants.recordStep({ taskId, tool: "toolB", parametersHash: "h2", success: true, durationMs: 10, timestamp: now - 100 });

      // If agent attempts toolA again, it trips oscillation circuit breaker
      const check = invariants.checkInvariants({ taskId, tool: "toolA", parameters: {} });
      expect(check.allowed).toBe(false);
      expect(check.violation?.code).toContain("tool_oscillation_detected");
      expect(check.violation?.message).toContain("Ping-pong oscillation detected alternating between 'toolA' and 'toolB'");
    });

    it("detects rapid file thrashing on repeated writes", () => {
      const taskId = 203;
      const now = Date.now();
      const filePath = "src/index.ts";

      invariants.recordStep({
        taskId,
        tool: "fs.write",
        parametersHash: "w1",
        success: true,
        durationMs: 10,
        timestamp: now - 30000,
        metadata: { filePath },
      });
      invariants.recordStep({
        taskId,
        tool: "fs.write",
        parametersHash: "w2",
        success: true,
        durationMs: 10,
        timestamp: now - 20000,
        metadata: { filePath },
      });
      invariants.recordStep({
        taskId,
        tool: "fs.write",
        parametersHash: "w3",
        success: true,
        durationMs: 10,
        timestamp: now - 10000,
        metadata: { filePath },
      });

      // Attempting 4th edit to same file within 60s
      const check = invariants.checkInvariants({
        taskId,
        tool: "fs.write",
        parameters: { path: filePath, content: "// edit 4" },
        timestamp: now,
      });

      expect(check.allowed).toBe(false);
      expect(check.violation?.code).toContain("file_thrashing_detected");
      expect(check.violation?.recoveryAdvice).toContain("File thrashing detected");
    });

    it("enforces maximum total steps safeguard", () => {
      const taskId = 204;
      for (let i = 0; i < 20; i++) {
        invariants.recordStep({
          taskId,
          tool: `tool-${i}`,
          parametersHash: `hash-${i}`,
          success: true,
          durationMs: 5,
          timestamp: Date.now() - (20 - i) * 1000,
        });
      }

      const check = invariants.checkInvariants({ taskId, tool: "another.tool", parameters: {} });
      expect(check.allowed).toBe(false);
      expect(check.violation?.code).toBe("TASK_MAX_STEPS_EXCEEDED");
    });
  });

  describe("Speculative Sandbox Digital Twin Execution", () => {
    const testSandboxDir = "./data/test-sandboxes-speculative";
    let sandbox: TaskSandbox;
    let speculativeEngine: SpeculativeSandboxEngine;

    beforeEach(async () => {
      sandbox = new TaskSandbox(999, testSandboxDir);
      await sandbox.init();
      speculativeEngine = new SpeculativeSandboxEngine();
    });

    afterEach(async () => {
      await sandbox.destroy();
      try {
        await fs.rm(testSandboxDir, { recursive: true, force: true });
      } catch {
        // ignore
      }
    });

    it("commits changes when speculative trial action passes validation", async () => {
      // 1. Initial file in sandbox
      await sandbox.writeFile("greeting.txt", "Initial Greeting");

      // 2. Speculative action: write file and execute a passing command
      const result = await speculativeEngine.speculativeWriteAndTest(
        sandbox,
        "greeting.txt",
        "Updated Speculative Greeting",
        'node -e "process.exit(0)"'
      );

      expect(result.success).toBe(true);
      expect(result.committed).toBe(true);
      expect(result.rolledBack).toBe(false);

      // Verify file contains new committed content
      const content = await sandbox.readFile("greeting.txt");
      expect(content).toBe("Updated Speculative Greeting");
    });

    it("instantly rolls back changes when speculative trial action fails, leaving zero collateral damage", async () => {
      // 1. Baseline state
      await sandbox.writeFile("stable_app.js", "console.log('STABLE_CODE_V1');");

      // 2. Speculative attempt to inject broken code that fails tests
      const result = await speculativeEngine.speculativeWriteAndTest(
        sandbox,
        "stable_app.js",
        "SYNTAX_ERROR_BROKEN_CODE = ???",
        'node -e "process.exit(1)"'
      );

      expect(result.success).toBe(false);
      expect(result.committed).toBe(false);
      expect(result.rolledBack).toBe(true);
      expect(result.error).toContain("Execution failed with exit code 1");

      // Verify original file was 100% restored and protected!
      const content = await sandbox.readFile("stable_app.js");
      expect(content).toBe("console.log('STABLE_CODE_V1');");
    });

    it("removes newly created files on rollback if trial fails", async () => {
      const result = await speculativeEngine.executeSpeculative(sandbox, async () => {
        await sandbox.writeFile("unwanted_temp_file.txt", "garbage data");
        return {
          stdout: "",
          stderr: "Test suite failed completely",
          exitCode: 2,
          timedOut: false,
          durationMs: 50,
        };
      });

      expect(result.rolledBack).toBe(true);
      const files = await sandbox.listFiles(".");
      expect(files).not.toContain("unwanted_temp_file.txt");
    });
  });

  describe("Quorum & Invariants Governed HTTP API Endpoints", () => {
    const artifactDir = fsSync.mkdtempSync(path.join(os.tmpdir(), "gnw-quorum-test-"));
    const env = loadEnv({
      NODE_ENV: "test",
      SESSION_SECRET: "q".repeat(48),
      DATABASE_URL: "file::memory:",
      ALLOW_SELF_REGISTRATION: "true",
      ARTIFACT_DIR: artifactDir,
      LLM_API_KEY: "",
      VIDEO_PROVIDER_URL: "",
    });

    let app: any;
    let db: Db;
    let ownerCookie = "";
    let taskId = 0;

    const web = (agent: request.Test, cookie = ownerCookie) => agent.set("x-gnw-client", "web").set("cookie", cookie);

    beforeEach(async () => {
      db = await createDb(env.databaseUrl);
      await migrate(db);
      app = await createApp(env, Promise.resolve(db));

      const owner = await request(app).post("/api/auth/register").set("x-gnw-client", "web").send({
        email: "justice@governed.agent",
        password: "governed-quorum-pass-1234!",
      });
      const setCookie = owner.headers["set-cookie"];
      const cookieVal = Array.isArray(setCookie) ? setCookie[0] : setCookie ?? "";
      ownerCookie = cookieVal.split(";")[0];

      const taskRes = await web(request(app).post("/api/tasks")).send({
        prompt: "Execute safe governed quorum workflows.",
        purpose: "quorum validation",
        classification: "internal",
        selectedAgents: ["engineering", "research"],
        budgetTokens: 5000,
        budgetBytes: 100_000,
      });
      taskId = taskRes.body.taskId;
    });

    afterEach(async () => {
      try {
        await db.close();
        fsSync.rmSync(artifactDir, { recursive: true, force: true });
      } catch {
        // ignore
      }
    });

    it("proposes high-risk action and achieves consensus via HTTP API", async () => {
      const res = await web(request(app).post("/api/governance/quorum/propose")).send({
        taskId,
        tool: "fs.write",
        operation: "write_code",
        parameters: { path: "src/safe.ts", content: "console.log('safe');" },
        justification: "Adding safe audited code module under approved architecture plan",
        isDestructive: false,
      });

      expect(res.status).toBe(200);
      expect(res.body.proposal).toBeDefined();
      expect(res.body.result).toBeDefined();
      expect(res.body.result.status).toBe("APPROVED");
      expect(res.body.result.approvals).toBe(3);

      // Verify fetch via GET
      const getRes = await web(request(app).get(`/api/governance/quorum/${res.body.proposal.proposalId}`));
      expect(getRes.status).toBe(200);
      expect(getRes.body.proposal.proposalId).toBe(res.body.proposal.proposalId);
      expect(getRes.body.result.status).toBe("APPROVED");
    });

    it("evaluates trajectory invariants via HTTP API", async () => {
      const res = await web(request(app).post("/api/governance/invariants/check")).send({
        taskId,
        tool: "npm.install",
        parameters: { package: "express" },
      });

      expect(res.status).toBe(200);
      expect(res.body.allowed).toBe(true);
    });
  });
});
