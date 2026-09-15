export type PhaseToolStatus = "implemented" | "hardened" | "planned";
export type PhaseToolPriority = "P0" | "P1" | "P2";

export interface PhaseOneTool {
  rank: number;
  id: string;
  name: string;
  priority: PhaseToolPriority;
  status: PhaseToolStatus;
  capability: string;
  description: string;
  safetyGate: string;
}

/**
 * Canonical first-phase tool contract. This is deliberately a status registry,
 * not a claim that a placeholder integration is production-certified.
 */
export const PHASE_ONE_TOOLS: readonly PhaseOneTool[] = [
  { rank: 1, id: "policy-engine", name: "Policy Engine", priority: "P0", status: "implemented", capability: "policy.evaluate", description: "Evaluates an action against GNW policy and task classification.", safetyGate: "fail-closed authorization" },
  { rank: 2, id: "identity-authentication", name: "Identity & Authentication", priority: "P0", status: "implemented", capability: "identity.assert", description: "Binds requests to an authenticated user and tenant.", safetyGate: "tenant and session validation" },
  { rank: 3, id: "capability-system", name: "Capability System", priority: "P0", status: "implemented", capability: "capability.issue", description: "Issues scoped, expiring and revocable action leases.", safetyGate: "short-lived scoped capability" },
  { rank: 4, id: "effect-gate", name: "Effect Gate", priority: "P0", status: "implemented", capability: "effect.admit", description: "Performs the final check immediately before an external effect.", safetyGate: "kill-switch and circuit-breaker recheck" },
  { rank: 5, id: "sandbox-executor", name: "Sandbox Executor", priority: "P0", status: "hardened", capability: "sandbox.execute", description: "Runs governed commands and Python inside a task jail.", safetyGate: "path confinement and scrubbed environment" },
  { rank: 6, id: "resource-limits-kill-switch", name: "Resource Limits & Kill Switch", priority: "P0", status: "implemented", capability: "execution.interlock", description: "Bounds time, output, budget and emergency stop state.", safetyGate: "durable stop and budget reservation" },
  { rank: 7, id: "audit-evidence", name: "Audit Evidence", priority: "P0", status: "hardened", capability: "audit.append", description: "Records decisions, commands, results and evidence hashes.", safetyGate: "append-only chained audit" },
  { rank: 8, id: "rollback", name: "Rollback", priority: "P0", status: "implemented", capability: "change.rollback", description: "Supports Git-based reversal and task-safe recovery paths.", safetyGate: "no destructive mutation without governance" },
  { rank: 9, id: "controlled-terminal", name: "Controlled Terminal", priority: "P1", status: "implemented", capability: "executor.command", description: "Classifies and executes admitted shell commands.", safetyGate: "danger classifier and approval" },
  { rank: 10, id: "governed-file-tools", name: "Governed File Tools", priority: "P1", status: "implemented", capability: "file.read", description: "Reads, writes and lists files within the task boundary.", safetyGate: "jail containment and byte ceilings" },
  { rank: 11, id: "git-integration", name: "Git Integration", priority: "P1", status: "implemented", capability: "git.status", description: "Provides governed status, diff, commit and PR operations.", safetyGate: "capability and approval per mutation" },
  { rank: 12, id: "test-build-verification", name: "Test & Build Verification", priority: "P1", status: "implemented", capability: "executor.test", description: "Runs validation commands and captures results as evidence.", safetyGate: "postcondition and audit record" },
  { rank: 13, id: "tool-registry", name: "Tool Registry", priority: "P1", status: "implemented", capability: "tool.registry", description: "Catalogues governed skills/tools and required capabilities.", safetyGate: "allowlisted capability contract" },
  { rank: 14, id: "network-control", name: "Network Control", priority: "P1", status: "hardened", capability: "network.egress", description: "Applies HTTPS, egress allowlisting and private destination blocking.", safetyGate: "default-deny production egress" },
  { rank: 15, id: "security-scanner", name: "Security Scanner", priority: "P1", status: "planned", capability: "security.scan", description: "Dependency, container, code and secret scanning before release.", safetyGate: "release gate blocks on critical findings" },
  { rank: 16, id: "effect-attestation", name: "Effect Attestation", priority: "P1", status: "implemented", capability: "effect.attest", description: "Captures the executor result and outcome digest after an effect.", safetyGate: "result must bind to action digest" },
  { rank: 17, id: "gnw-verify", name: "GNW Independent Verifier", priority: "P1", status: "implemented", capability: "evidence.verify", description: "Verifies Merkle and audit proof material outside the execution path.", safetyGate: "cryptographic proof verification" },
  { rank: 18, id: "web-search-browser", name: "Governed Web Search & Browser", priority: "P2", status: "implemented", capability: "browser.browse", description: "Performs SSRF-safe browse and controlled browser actions.", safetyGate: "URL policy and content distillation" },
  { rank: 19, id: "mcp-integration", name: "Governed MCP Integration", priority: "P2", status: "planned", capability: "mcp.invoke", description: "Connects approved external tools through a governed registry.", safetyGate: "server allowlist and per-tool capability" },
  { rank: 20, id: "subagents-long-running", name: "Subagents & Long-running Tasks", priority: "P2", status: "implemented", capability: "agent.delegate", description: "Supports specialist skills, task budgets and durable orchestration.", safetyGate: "delegation scope and aggregate budget" },
];

export function getPhaseOneTool(id: string): PhaseOneTool | undefined {
  return PHASE_ONE_TOOLS.find((tool) => tool.id === id);
}

export function phaseOneSummary() {
  return PHASE_ONE_TOOLS.reduce((summary, tool) => {
    summary.total += 1;
    summary[tool.status] += 1;
    return summary;
  }, { total: 0, implemented: 0, hardened: 0, planned: 0 });
}

export function isPhaseOneTool(value: string): boolean {
  return Boolean(getPhaseOneTool(value));
}

export function phaseOneToolsForPriority(priority: PhaseToolPriority): PhaseOneTool[] {
  return PHASE_ONE_TOOLS.filter((tool) => tool.priority === priority);
}
