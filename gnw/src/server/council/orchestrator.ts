import { randomUUID } from "node:crypto";
import type { Db } from "../db/index.js";
import type { Env } from "../env.js";
import { appendAudit, type AuditInput } from "../audit.js";
import { canonicalize, sha256 } from "../security.js";
import { evaluateShadowPolicy } from "./policy-gate.js";
import {
  COUNCIL_ROLES,
  COUNCIL_SCHEMA_VERSION,
  parseCouncilFinding,
  parseCouncilTaskEnvelope,
  parseJudgeVerdict,
  type CouncilFinding,
  type CouncilRole,
  type CouncilTaskEnvelope,
  type JudgeVerdict,
  type PolicyDecision,
} from "./schemas.js";
import { CouncilStore } from "./store.js";

export type CouncilRoleResult = {
  output: unknown;
  modelProvider: string;
  modelVersion: string;
  promptTemplateSha256: string;
};

export interface CouncilRoleRunner {
  runRole(role: CouncilRole, task: CouncilTaskEnvelope): Promise<CouncilRoleResult>;
  runJudge(task: CouncilTaskEnvelope, findings: readonly CouncilFinding[]): Promise<CouncilRoleResult>;
}

export type CouncilShadowResult = {
  taskId: string;
  status: "disabled" | "shadow_completed" | "failed_closed" | "idempotent_replay";
  decision?: PolicyDecision;
};

const ROLE_TEMPLATE = "gnw-council-shadow-role-v1";
const JUDGE_TEMPLATE = "gnw-council-shadow-judge-v1";

/**
 * Deterministic source-only runner. It creates bounded fixture findings and never
 * contacts a model provider, imports the executor client, issues a capability,
 * or performs a tool action. A future provider adapter must still satisfy this
 * interface and every returned object is schema-validated before persistence.
 */
export class DeterministicShadowRoleRunner implements CouncilRoleRunner {
  async runRole(role: CouncilRole, task: CouncilTaskEnvelope): Promise<CouncilRoleResult> {
    const missingEvidence = task.evidence.length ? [] : ["task:evidence"];
    const productionRisk = task.action.environment === "production";
    const output = parseCouncilFinding({
      taskId: task.taskId,
      role,
      schemaVersion: COUNCIL_SCHEMA_VERSION,
      policyVersion: task.policyVersion,
      recommendation: productionRisk ? "require_human_approval" : missingEvidence.length ? "request_more_evidence" : "allow_limited_execution",
      confidence: 1,
      claims: [{ claim: `${role} produced a deterministic shadow-only assessment.`, evidenceIds: task.evidence.map(item => item.id) }],
      risks: productionRisk && role === "critic" ? [{ id: "R-PRODUCTION", severity: "high", category: "production_change", reason: "Production actions require human approval." }] : [],
      requiredControls: ["shadow_only", "no_capability_issuance", "no_executor_call"],
      missingEvidence,
    });
    return { output, modelProvider: "deterministic", modelVersion: "shadow-fixture-v1", promptTemplateSha256: sha256(`${ROLE_TEMPLATE}:${role}`) };
  }

  async runJudge(task: CouncilTaskEnvelope, findings: readonly CouncilFinding[]): Promise<CouncilRoleResult> {
    const missingEvidence = [...new Set(findings.flatMap(item => item.missingEvidence))];
    const hasHighRisk = findings.some(item => item.risks.some(risk => risk.severity === "high" || risk.severity === "critical"));
    const output = parseJudgeVerdict({
      taskId: task.taskId,
      role: "judge",
      schemaVersion: COUNCIL_SCHEMA_VERSION,
      policyVersion: task.policyVersion,
      recommendation: hasHighRisk ? "require_human_approval" : missingEvidence.length ? "request_more_evidence" : "allow_limited_execution",
      confidence: 1,
      claims: [{ claim: "Judge recommendation was derived from independently persisted shadow findings.", evidenceIds: task.evidence.map(item => item.id) }],
      risks: [],
      requiredControls: ["deterministic_policy_gate"],
      missingEvidence,
      dissentSummary: "No model provider was invoked in the deterministic source-only runner.",
    });
    return { output, modelProvider: "deterministic", modelVersion: "shadow-fixture-v1", promptTemplateSha256: sha256(JUDGE_TEMPLATE) };
  }
}

export async function runCouncilShadow(input: {
  db: Db;
  env: Env;
  sourceTaskId: number;
  actorUserId: number;
  envelope: CouncilTaskEnvelope;
  runner?: CouncilRoleRunner;
  auditWriter?: (db: Db, event: AuditInput) => Promise<unknown>;
}): Promise<CouncilShadowResult> {
  if (input.env.councilMode !== "shadow") {
    return { taskId: input.envelope.taskId, status: "disabled" };
  }

  const store = new CouncilStore(input.db);
  const runner = input.runner ?? new DeterministicShadowRoleRunner();
  const auditWriter = input.auditWriter ?? appendAudit;
  let taskId = input.envelope.taskId;

  try {
    const envelope = parseCouncilTaskEnvelope(input.envelope);
    taskId = envelope.taskId;
    const created = await store.createOrGetTask({ envelope, sourceTaskId: input.sourceTaskId });
    if (!created.created) {
      return { taskId: created.task.task_id, status: "idempotent_replay" };
    }

    await store.transition(taskId, "STATIC_VALIDATED", "schema_validated");
    await store.transition(taskId, "COUNCIL_QUEUED", "shadow_queue_recorded");
    await auditWriter(input.db, {
      taskId: input.sourceTaskId,
      actorUserId: input.actorUserId,
      eventType: "council_shadow_started",
      decision: "SHADOW",
      reason: "shadow_mode_no_authority",
      payload: { councilTaskId: taskId, envelopeDigest: sha256(canonicalize(envelope)) },
    });

    await store.transition(taskId, "PLANNING", "planner_started");
    const plannerResult = await runner.runRole("planner", envelope);
    const planner = parseCouncilFinding(plannerResult.output);
    if (planner.role !== "planner" || planner.taskId !== taskId) throw new Error("council_role_binding_invalid");
    await store.saveFinding({ finding: planner, ...plannerResult });

    await store.transition(taskId, "VERIFYING", "verifier_started");
    const verifierResult = await runner.runRole("verifier", envelope);
    const verifier = parseCouncilFinding(verifierResult.output);
    if (verifier.role !== "verifier" || verifier.taskId !== taskId) throw new Error("council_role_binding_invalid");
    await store.saveFinding({ finding: verifier, ...verifierResult });

    await store.transition(taskId, "CRITIQUING", "critic_started");
    const criticResult = await runner.runRole("critic", envelope);
    const critic = parseCouncilFinding(criticResult.output);
    if (critic.role !== "critic" || critic.taskId !== taskId) throw new Error("council_role_binding_invalid");
    await store.saveFinding({ finding: critic, ...criticResult });

    const findings = [planner, verifier, critic];
    await store.transition(taskId, "JUDGING", "judge_started");
    const judgeResult = await runner.runJudge(envelope, findings);
    const judge = parseJudgeVerdict(judgeResult.output);
    if (judge.taskId !== taskId) throw new Error("council_judge_binding_invalid");
    await store.saveFinding({ finding: judge, ...judgeResult });

    const decision = evaluateShadowPolicy({ task: envelope, findings, judge });
    await store.savePolicyDecision(decision, judge);
    await store.transition(taskId, "POLICY_DECIDED", "hypothetical_policy_recorded");
    await auditWriter(input.db, {
      taskId: input.sourceTaskId,
      actorUserId: input.actorUserId,
      eventType: "council_shadow_decision",
      decision: "SHADOW",
      reason: decision.hypotheticalOutcome,
      payload: {
        councilTaskId: taskId,
        decisionDigest: sha256(canonicalize(decision)),
        executionAuthorized: false,
      },
    });
    await store.transition(taskId, "SHADOW_COMPLETED", "shadow_recording_complete");
    return { taskId, status: "shadow_completed", decision };
  } catch (error) {
    const code = error instanceof Error ? error.message.split(":", 1)[0] : "council_failure";
    const detail = error instanceof Error ? error.message : String(error);
    try {
      await store.failClosed(taskId, code || "council_failure", detail);
    } catch {
      // Persistence itself may be unavailable. The active authorization path is
      // intentionally untouched; the caller receives a fail-closed shadow state.
    }
    return { taskId, status: "failed_closed" };
  }
}

export function buildShadowEnvelope(input: {
  sourceTaskId: number;
  actorUserId: number;
  purpose: string;
  classification: string;
  promptDigest: string;
  environment?: "dev" | "staging" | "production";
  requestedAt?: string;
}): CouncilTaskEnvelope {
  return parseCouncilTaskEnvelope({
    taskId: randomUUID(),
    idempotencyKey: `gnw-task:${input.sourceTaskId}:council-shadow:v1`,
    requestedAt: input.requestedAt ?? new Date().toISOString(),
    actor: { id: String(input.actorUserId), type: "user" },
    action: {
      type: "analysis",
      target: `task:${input.sourceTaskId}`,
      environment: input.environment ?? "dev",
      requestedEffect: input.purpose,
    },
    policyVersion: "council-shadow-v1",
    allowedCapabilities: [],
    evidence: [{ id: "task:prompt-digest", type: "sha256", sha256: input.promptDigest }],
    constraints: {
      maxRuntimeSeconds: 60,
      maxCostUsd: 0,
      networkEgress: "none",
      humanApprovalRequired: input.classification === "restricted",
    },
  });
}
