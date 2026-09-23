import { describe, expect, it } from "vitest";
import {
  OFFICE_PHASE1_SCOPE,
  answerWithCitations,
  buildCitation,
  classifySensitiveAction,
  draftProjectPlan,
  verifySource,
} from "../src/server/office.js";

describe("GNW Office Phase 1", () => {
  it("exposes exactly the bounded Phase-1 scope", () => {
    expect(OFFICE_PHASE1_SCOPE).toEqual([
      "internal_document_search",
      "live_web_research_fetch",
      "source_verification",
      "citation_answer",
      "project_plan_draft",
      "sensitive_action_stop",
      "complete_audit",
    ]);
  });

  it("fails closed for sensitive actions", () => {
    expect(classifySensitiveAction("send an email to the vendor")).toEqual({
      allowed: false,
      reason: "external_communication",
    });
    expect(classifySensitiveAction("delete the document").allowed).toBe(false);
    expect(classifySensitiveAction("create a read-only research draft")).toEqual({ allowed: true, reason: null });
  });

  it("verifies sources and binds citations to a content hash", () => {
    const source = verifySource({
      id: "s1",
      url: "https://example.gov/policy",
      title: "Official policy",
      content: "This is a sufficiently detailed official source used for evidence.",
      sourceType: "GOVERNMENT",
      retrievedAt: "2026-09-18T00:00:00Z",
      publishedAt: "2026-01-01",
    });
    expect(source.support).toBe("DIRECT");
    expect(source.contentHash).toHaveLength(64);
    expect(buildCitation(source).contentHash).toBe(source.contentHash);
  });

  it("abstains when evidence is insufficient", () => {
    const result = answerWithCitations("Draft answer", [verifySource({
      id: "weak",
      url: "https://example.com",
      title: "x",
      content: "no",
      sourceType: "SECONDARY",
    })]);
    expect(result.abstained).toBe(true);
    expect(result.citations).toHaveLength(0);
  });

  it("creates a human-reviewable plan without executing side effects", () => {
    const plan = draftProjectPlan({
      prompt: "Prepare an internal research pilot",
      deliverables: ["Research brief", "Review checklist"],
    });
    expect(plan.status).toBe("DRAFT");
    expect(plan.requiresHumanReview).toBe(true);
    expect(plan.tasks).toHaveLength(2);
    expect(plan.tasks[1].dependencies).toEqual(["draft-task-1"]);
  });
});
