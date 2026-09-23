import { describe, expect, it } from "vitest";
import { buildDeepResearchPlan, buildToolPolicy, outputText, outputAnnotations, rewriteResearchPrompt } from "../src/server/deep-research.js";
import { loadEnv } from "../src/server/env.js";

function testEnv() {
  return loadEnv({
    NODE_ENV: "test",
    LLM_BASE_URL: "https://api.openai.com/v1",
    LLM_API_KEY: "test-key",
    GNW_ALLOWED_EGRESS_HOSTS: "api.openai.com,mcp.example.com",
    GNW_DEEP_RESEARCH_MAX_TOOL_CALLS: "20",
    GNW_DEEP_RESEARCH_USE_CODE_INTERPRETER: "true",
    GNW_DEEP_RESEARCH_ALLOWED_DOMAINS: "nist.gov,owasp.org",
  });
}

describe("GNW deep research planning", () => {
  it("creates an explicit multi-phase plan and clarification questions", () => {
    const plan = buildDeepResearchPlan("Research production readiness of a software platform and cite official sources.");
    expect(plan.planVersion).toBe("GNW-DR-1");
    expect(plan.researchPhases.length).toBeGreaterThanOrEqual(8);
    expect(plan.defaultAssumptions.length).toBeGreaterThan(0);
    expect(plan.clarificationQuestions.some(q => q.id === "timeframe")).toBe(true);
  });

  it("rewrites without inventing unspecified dimensions", () => {
    const plan = buildDeepResearchPlan("Deeply audit this architecture.");
    const prompt = rewriteResearchPrompt(plan);
    expect(prompt).toContain("Not specified; keep this dimension open-ended.");
    expect(prompt).toContain("USER REQUEST:");
    expect(prompt).toContain("OUTPUT REQUIREMENTS:");
  });

  it("enforces vector-store and domain policy", () => {
    const env = testEnv();
    const policy = buildToolPolicy(env, {
      allowedDomains: ["nist.gov"],
      vectorStoreIds: ["vs_123"],
      useCodeInterpreter: true,
      maxToolCalls: 7,
    });
    expect(policy.webSearch.type).toBe("web_search");
    expect(policy.webSearch.filters?.allowed_domains).toEqual(["nist.gov"]);
    expect(policy.fileSearch?.vector_store_ids).toEqual(["vs_123"]);
    expect(policy.codeInterpreter?.container.type).toBe("auto");
    expect(policy.maxToolCalls).toBe(7);
    expect(() => buildToolPolicy(env, { vectorStoreIds: ["vs_1", "vs_2", "vs_3"] })).toThrow("at most two");
    expect(() => buildToolPolicy(env, { allowedDomains: ["example.com"] })).toThrow("outside GNW allowlist");
  });
});

describe("GNW deep research response extraction", () => {
  it("extracts final output text and citations", () => {
    const payload = {
      output: [{
        type: "message",
        content: [{
          type: "output_text",
          text: "Final report.",
          annotations: [{ type: "url_citation", url: "https://nist.gov", title: "NIST" }],
        }],
      }],
    };
    expect(outputText(payload)).toBe("Final report.");
    expect(outputAnnotations(payload)).toHaveLength(1);
  });
});
