import { z } from "zod";

export const COUNCIL_SCHEMA_VERSION = "1.0.0" as const;
export const COUNCIL_ROLES = ["planner", "verifier", "critic"] as const;
export const COUNCIL_RECOMMENDATIONS = [
  "allow_limited_execution",
  "require_human_approval",
  "request_more_evidence",
  "deny",
] as const;

const boundedText = (max: number) => z.string().trim().min(1).max(max);
const sha256 = z.string().regex(/^[a-f0-9]{64}$/);
const evidenceId = boundedText(160);

export const evidenceReferenceSchema = z.object({
  id: evidenceId,
  type: boundedText(80),
  sha256,
  uri: z.string().url().max(1000).optional(),
}).strict();

export const councilTaskEnvelopeSchema = z.object({
  taskId: z.string().uuid(),
  idempotencyKey: boundedText(200),
  requestedAt: z.string().datetime(),
  actor: z.object({
    id: boundedText(200),
    type: z.enum(["user", "service", "workflow"]),
  }).strict(),
  action: z.object({
    type: z.enum(["command", "python", "deployment", "connector_write", "analysis", "read_only"]),
    target: boundedText(500),
    environment: z.enum(["dev", "staging", "production"]),
    requestedEffect: boundedText(1000),
  }).strict(),
  policyVersion: boundedText(100),
  allowedCapabilities: z.array(boundedText(160)).max(32),
  evidence: z.array(evidenceReferenceSchema).max(100),
  constraints: z.object({
    maxRuntimeSeconds: z.number().int().positive().max(3600),
    maxCostUsd: z.number().nonnegative().max(1000),
    networkEgress: z.enum(["none", "allowlisted"]),
    humanApprovalRequired: z.boolean(),
  }).strict(),
}).strict();

export const claimSchema = z.object({
  claim: boundedText(1000),
  evidenceIds: z.array(evidenceId).max(50),
}).strict();

export const riskSchema = z.object({
  id: boundedText(80),
  severity: z.enum(["low", "medium", "high", "critical"]),
  category: boundedText(120),
  reason: boundedText(1000),
}).strict();

export const councilFindingSchema = z.object({
  taskId: z.string().uuid(),
  role: z.enum(COUNCIL_ROLES),
  schemaVersion: z.literal(COUNCIL_SCHEMA_VERSION),
  policyVersion: boundedText(100),
  recommendation: z.enum(COUNCIL_RECOMMENDATIONS),
  confidence: z.number().min(0).max(1),
  claims: z.array(claimSchema).max(100),
  risks: z.array(riskSchema).max(100),
  requiredControls: z.array(boundedText(160)).max(50),
  missingEvidence: z.array(evidenceId).max(50),
}).strict();

export const judgeVerdictSchema = z.object({
  taskId: z.string().uuid(),
  role: z.literal("judge"),
  schemaVersion: z.literal(COUNCIL_SCHEMA_VERSION),
  policyVersion: boundedText(100),
  recommendation: z.enum(COUNCIL_RECOMMENDATIONS),
  confidence: z.number().min(0).max(1),
  claims: z.array(claimSchema).max(100),
  risks: z.array(riskSchema).max(100),
  requiredControls: z.array(boundedText(160)).max(50),
  missingEvidence: z.array(evidenceId).max(50),
  dissentSummary: z.string().max(2000),
}).strict();

export const policyDecisionSchema = z.object({
  taskId: z.string().uuid(),
  schemaVersion: z.literal(COUNCIL_SCHEMA_VERSION),
  hypotheticalOutcome: z.enum(COUNCIL_RECOMMENDATIONS),
  deterministicRuleIds: z.array(boundedText(160)).min(1).max(50),
  executionAuthorized: z.literal(false),
}).strict();

export type CouncilTaskEnvelope = z.infer<typeof councilTaskEnvelopeSchema>;
export type CouncilFinding = z.infer<typeof councilFindingSchema>;
export type JudgeVerdict = z.infer<typeof judgeVerdictSchema>;
export type PolicyDecision = z.infer<typeof policyDecisionSchema>;
export type CouncilRole = typeof COUNCIL_ROLES[number];
export type CouncilRecommendation = typeof COUNCIL_RECOMMENDATIONS[number];

export function parseCouncilTaskEnvelope(value: unknown): CouncilTaskEnvelope {
  return councilTaskEnvelopeSchema.parse(value);
}

export function parseCouncilFinding(value: unknown): CouncilFinding {
  return councilFindingSchema.parse(value);
}

export function parseJudgeVerdict(value: unknown): JudgeVerdict {
  return judgeVerdictSchema.parse(value);
}

export function parsePolicyDecision(value: unknown): PolicyDecision {
  return policyDecisionSchema.parse(value);
}
