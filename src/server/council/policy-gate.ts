import {
  COUNCIL_SCHEMA_VERSION,
  parsePolicyDecision,
  type CouncilFinding,
  type CouncilTaskEnvelope,
  type JudgeVerdict,
  type PolicyDecision,
} from "./schemas.js";

export function evaluateShadowPolicy(input: {
  task: CouncilTaskEnvelope;
  findings: CouncilFinding[];
  judge: JudgeVerdict;
}): PolicyDecision {
  const { task, findings, judge } = input;
  const ruleIds: string[] = [];
  let hypotheticalOutcome: PolicyDecision["hypotheticalOutcome"] = "allow_limited_execution";

  if (findings.length !== 3 || new Set(findings.map(item => item.role)).size !== 3) {
    hypotheticalOutcome = "deny";
    ruleIds.push("COUNCIL_REQUIRED_ROLES_INVALID");
  } else if (findings.some(item => item.taskId !== task.taskId || item.policyVersion !== task.policyVersion)) {
    hypotheticalOutcome = "deny";
    ruleIds.push("COUNCIL_CONTEXT_BINDING_INVALID");
  } else if (findings.some(item => item.risks.some(risk => risk.severity === "critical"))) {
    hypotheticalOutcome = "deny";
    ruleIds.push("COUNCIL_CRITICAL_RISK_DENY");
  } else if (
    task.action.environment === "production" ||
    task.constraints.humanApprovalRequired ||
    findings.some(item => item.role === "critic" && item.risks.some(risk => risk.severity === "high"))
  ) {
    hypotheticalOutcome = "require_human_approval";
    ruleIds.push(task.action.environment === "production" ? "COUNCIL_PRODUCTION_REQUIRES_HUMAN" : "COUNCIL_HIGH_RISK_REQUIRES_HUMAN");
  } else if (findings.some(item => item.missingEvidence.length > 0) || judge.missingEvidence.length > 0) {
    hypotheticalOutcome = "request_more_evidence";
    ruleIds.push("COUNCIL_EVIDENCE_INCOMPLETE");
  } else if (judge.recommendation === "deny") {
    hypotheticalOutcome = "deny";
    ruleIds.push("COUNCIL_JUDGE_DENIAL");
  } else {
    ruleIds.push("COUNCIL_LOW_RISK_SHADOW_ALLOW");
  }

  return parsePolicyDecision({
    taskId: task.taskId,
    schemaVersion: COUNCIL_SCHEMA_VERSION,
    hypotheticalOutcome,
    deterministicRuleIds: ruleIds,
    executionAuthorized: false,
  });
}
