import { describe, expect, it } from "vitest";
import { GovernanceService, MemoryGovernanceStores, digestRequest, requiresHumanApproval, type ApprovalRecord, type GovernanceRequest } from "../src/server/governance.js";

function grant(overrides: Partial<GovernanceRequest> = {}): GovernanceRequest {
  const issuedAt = Date.now() - 1000;
  return {
    requestId: "req-1",
    subject: "42",
    tenant: "tenant-user-42",
    role: "member",
    purpose: "unit test",
    classification: "internal",
    operation: "analysis",
    resource: "task:1",
    agent: "research",
    tool: "knowledge.search",
    scope: "knowledge.search",
    budgetTokens: 4000,
    budgetBytes: 4096,
    issuedAt,
    expiresAt: issuedAt + 600_000,
    nonce: `nonce-${Math.random()}`,
    ...overrides,
  };
}

function approvalFor(request: GovernanceRequest, overrides: Partial<ApprovalRecord> = {}): ApprovalRecord {
  return {
    approvalId: 1,
    requestId: request.requestId,
    actionDigest: digestRequest(request),
    tenant: request.tenant,
    status: "approved",
    expiresAt: Date.now() + 60_000,
    nonce: `approval-${Math.random()}`,
    ...overrides,
  };
}

describe("policy gateway", () => {
  it("admits a fully bound request", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    const decision = await service.authorize(grant());
    expect(decision).toMatchObject({ allowed: true, status: "ALLOW", reason: "governance_admitted" });
  });

  it("refuses a missing binding", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    for (const field of ["subject", "tenant", "role", "purpose", "resource", "nonce"] as const) {
      const decision = await service.authorize(grant({ [field]: "  " } as Partial<GovernanceRequest>));
      expect(decision.reason).toBe("context_missing");
      expect(decision.allowed).toBe(false);
    }
  });

  it("refuses a tool outside the agent scope and a scope that is not bound to the tool", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    expect((await service.authorize(grant({ tool: "video.provider_job", scope: "video.provider_job" }))).reason).toBe("tool_not_allowed");
    expect((await service.authorize(grant({ scope: "evidence.summarize" }))).reason).toBe("scope_binding");
  });

  it("refuses an expired or not-yet-valid grant", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    const past = Date.now() - 10_000;
    expect((await service.authorize(grant({ issuedAt: past, expiresAt: past + 1000 }))).reason).toBe("grant_expired");
    const future = Date.now() + 60_000;
    expect((await service.authorize(grant({ issuedAt: future, expiresAt: future + 1000 }))).reason).toBe("grant_expired");
  });

  it("refuses invalid budgets", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    expect((await service.authorize(grant({ budgetTokens: 0 }))).reason).toBe("budget_tokens_invalid");
    expect((await service.authorize(grant({ budgetTokens: 10_000_000 }))).reason).toBe("budget_tokens_invalid");
    expect((await service.authorize(grant({ budgetBytes: -1 }))).reason).toBe("budget_bytes_invalid");
  });

  it("refuses a replayed grant nonce", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    const request = grant();
    expect((await service.authorize(request)).allowed).toBe(true);
    expect((await service.authorize(request)).reason).toBe("grant_replay");
  });

  it("does not burn the grant nonce on a denial", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    const request = grant({ scope: "evidence.summarize" });
    expect((await service.authorize(request)).reason).toBe("scope_binding");
    expect((await service.authorize({ ...request, scope: request.tool })).allowed).toBe(true);
  });

  it("requires human approval for provider jobs, restricted data, and provider tooling", () => {
    expect(requiresHumanApproval({ operation: "provider_job", classification: "internal", agent: "research", tool: "knowledge.search" })).toBe(true);
    expect(requiresHumanApproval({ operation: "analysis", classification: "restricted", agent: "research", tool: "knowledge.search" })).toBe(true);
    expect(requiresHumanApproval({ operation: "analysis", classification: "internal", agent: "video_producer", tool: "video.provider_job" })).toBe(true);
    expect(requiresHumanApproval({ operation: "analysis", classification: "internal", agent: "video_producer", tool: "video.brief" })).toBe(false);
  });

  it("enforces approval presence, state, binding, expiry, and single use", async () => {
    const service = new GovernanceService(new MemoryGovernanceStores());
    const request = grant({ agent: "video_producer", tool: "video.provider_job", scope: "video.provider_job", operation: "provider_job" });

    expect((await service.authorize(request)).reason).toBe("approval_required");
    expect((await service.authorize(request, approvalFor(request, { status: "pending" }))).reason).toBe("approval_required");
    expect((await service.authorize(request, approvalFor(request, { actionDigest: "wrong" }))).reason).toBe("approval_binding");
    expect((await service.authorize(request, approvalFor(request, { tenant: "tenant-user-99" }))).reason).toBe("approval_binding");
    expect((await service.authorize(request, approvalFor(request, { expiresAt: Date.now() - 1 }))).reason).toBe("approval_expired");

    const approval = approvalFor(request);
    expect((await service.authorize(request, approval)).allowed).toBe(true);
    // Same approval, fresh grant nonce: replay protection must still refuse.
    expect((await service.authorize({ ...request, nonce: "fresh" }, approval)).reason).toBe("approval_replay");
  });

  it("returns STOP while the kill switch or circuit breaker is engaged", async () => {
    const stores = new MemoryGovernanceStores();
    const service = new GovernanceService(stores);
    stores.setInterlock({ killSwitch: true });
    expect(await service.authorize(grant())).toMatchObject({ allowed: false, status: "STOP", reason: "safety_interlock" });
    stores.setInterlock({ killSwitch: false, circuitOpen: true });
    expect((await service.authorize(grant())).status).toBe("STOP");
    stores.setInterlock({ circuitOpen: false });
    expect((await service.authorize(grant())).allowed).toBe(true);
  });

  it("fails closed when the interlock cannot be read", async () => {
    const service = new GovernanceService({
      claimNonce: async () => true,
      reserveBudget: async () => true,
      getInterlock: async () => {
        throw new Error("database unavailable");
      },
    });
    expect((await service.authorize(grant())).status).toBe("STOP");
  });

  it("produces a stable digest that ignores timing and nonce", () => {
    const request = grant();
    const rehydrated = { ...request, nonce: "different", issuedAt: request.issuedAt + 5, expiresAt: request.expiresAt + 5 };
    expect(digestRequest(rehydrated)).toBe(digestRequest(request));
    expect(digestRequest({ ...request, budgetTokens: 4001 })).not.toBe(digestRequest(request));
  });
});
