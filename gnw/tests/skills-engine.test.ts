import { describe, it, expect, beforeEach } from "vitest";
import { createDefaultSkillRegistry, GovernedSkillRegistry } from "../src/server/skills/index.js";
import { issueCapabilityLease } from "../src/server/capability.js";
import { loadEnv } from "../src/server/env.js";

const env = loadEnv({
  DATABASE_URL: ":memory:",
  ARTIFACT_DIR: "./test-artifacts",
  ALLOW_SELF_REGISTRATION: "true",
});

describe("GNW Governed Skills Engine & Top 50 Skills Catalog", () => {
  let registry: GovernedSkillRegistry;

  beforeEach(() => {
    registry = createDefaultSkillRegistry();
  });

  it("loads exactly 50 world-class governed skills across 7 domains", () => {
    const skills = registry.listSkills();
    expect(skills.length).toBe(50);

    const categories = new Set(skills.map(s => s.category));
    expect(categories.size).toBe(7);
    expect(categories.has("research_and_intel")).toBe(true);
    expect(categories.has("code_and_engineering")).toBe(true);
    expect(categories.has("security_and_governance")).toBe(true);
    expect(categories.has("data_and_analytics")).toBe(true);
    expect(categories.has("multi_agent_quorum")).toBe(true);
    expect(categories.has("memory_and_rag")).toBe(true);
    expect(categories.has("devops_and_production")).toBe(true);
  });

  it("filters and searches skills by query, specialist, and category", () => {
    const perplexitySkills = registry.searchSkills("perplexity");
    expect(perplexitySkills.length).toBeGreaterThanOrEqual(1);
    expect(perplexitySkills[0].id).toBe("perplexity-deep-researcher");

    const quorumSkills = registry.findSkillsByCategory("multi_agent_quorum");
    expect(quorumSkills.length).toBe(8);

    const researchSpecialistSkills = registry.findSkillsBySpecialist("research");
    expect(researchSpecialistSkills.length).toBeGreaterThanOrEqual(3);
  });

  it("executes perplexity-deep-researcher under valid GNW capability lease with Kamil AI verification", async () => {
    const taskId = 301;
    const actorUserId = 1;
    const actionDigest = "test-action-digest-12345";

    const lease = issueCapabilityLease({
      requestId: "req-skill-test-01",
      taskId,
      actorUserId,
      actionDigest,
      capability: "browser.visual",
      subject: "researcher@gnw.ai",
      tenant: "tenant-dev",
      ttlMs: 60_000,
      issuer: env.grantIssuer,
      privateKeyPem: env.grantPrivateKeyPem,
    });

    const result = await registry.executeSkill(
      "perplexity-deep-researcher",
      {
        taskId,
        actorUserId,
        actionDigest,
        capabilityLease: lease,
        cognitiveStage: "act",
        parameters: {
          query: "Latest developments in governed autonomous AI agents",
          depth: "exhaustive",
        },
      },
      env.grantPublicKeyPem
    );

    expect(result.success).toBe(true);
    expect(result.skillId).toBe("perplexity-deep-researcher");
    expect(result.evidenceHash).toBeDefined();
    expect(result.evidenceHash.length).toBe(64);
    expect(result.kamilVerification.expectedMatchedActual).toBe(true);
    expect(result.kamilVerification.beliefDiffDetected).toBe(false);

    const out = result.output as { query: string; sources: unknown[] };
    expect(out.sources.length).toBe(3);
  });

  it("fails closed when capability lease is invalid or mismatched", async () => {
    const taskId = 302;
    const actorUserId = 1;
    const actionDigest = "test-action-digest-bad";

    // Issue lease for WRONG capability (e.g. 'code.symbols' instead of 'browser.visual')
    const lease = issueCapabilityLease({
      requestId: "req-skill-test-wrong-cap",
      taskId,
      actorUserId,
      actionDigest,
      capability: "code.symbols",
      subject: "attacker@gnw.ai",
      tenant: "tenant-dev",
      ttlMs: 60_000,
      issuer: env.grantIssuer,
      privateKeyPem: env.grantPrivateKeyPem,
    });

    await expect(
      registry.executeSkill(
        "perplexity-deep-researcher",
        {
          taskId,
          actorUserId,
          actionDigest,
          capabilityLease: lease,
          cognitiveStage: "act",
          parameters: { query: "Security probe" },
        },
        env.grantPublicKeyPem
      )
    ).rejects.toThrow(/capability_mismatch/);
  });

  it("rejects skill execution when parameters fail schema validation", async () => {
    const taskId = 303;
    const actorUserId = 1;
    const actionDigest = "test-action-digest-invalid-params";

    const lease = issueCapabilityLease({
      requestId: "req-skill-test-03",
      taskId,
      actorUserId,
      actionDigest,
      capability: "browser.visual",
      subject: "researcher@gnw.ai",
      tenant: "tenant-dev",
      ttlMs: 60_000,
      issuer: env.grantIssuer,
      privateKeyPem: env.grantPrivateKeyPem,
    });

    // Query is required and min length 3
    await expect(
      registry.executeSkill(
        "perplexity-deep-researcher",
        {
          taskId,
          actorUserId,
          actionDigest,
          capabilityLease: lease,
          cognitiveStage: "act",
          parameters: { query: "a" }, // Too short, fails schema
        },
        env.grantPublicKeyPem
      )
    ).rejects.toThrow(/invalid_skill_parameters/);
  });
});
