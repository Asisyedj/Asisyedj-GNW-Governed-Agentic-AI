import { z } from "zod";
import type { CapabilityLease } from "../capability.js";
import type { SpecialistAgent } from "../../shared/types.js";

export const SKILL_DIGEST_VERSION = "GNW-SKILL-DEFINITION-V1";

/**
 * Kamil AI Cognitive Stage Definition:
 * Observe -> Understand -> Reason -> Plan -> Act -> Verify -> Critique -> Learn
 */
export type CognitiveStage =
  | "observe"
  | "understand"
  | "reason"
  | "plan"
  | "act"
  | "verify"
  | "critique"
  | "learn";

export type SkillCategory =
  | "research_and_intel"
  | "code_and_engineering"
  | "security_and_governance"
  | "data_and_analytics"
  | "multi_agent_quorum"
  | "memory_and_rag"
  | "devops_and_production";

export class SkillExecutionError extends Error {
  constructor(public readonly code: string, message?: string) {
    super(message ? `${code}: ${message}` : code);
    this.name = "SkillExecutionError";
  }
}

export interface SkillMetadata {
  id: string;
  name: string;
  version: string;
  category: SkillCategory;
  description: string;
  author: string;
  tags: string[];
  requiredCapability: string;
  specialist: SpecialistAgent;
  costTokensEstimate: number;
  timeoutMs: number;
  /** Kamil AI Cognitive Loop attributes */
  cognitiveStages: CognitiveStage[];
  disproveCriteria?: string;
  verificationPostCondition: string;
  /** Perplexity OpenClaw compatibility */
  openClawCompatible: boolean;
  searchToolsRequired?: string[];
}

export interface SkillExecutionContext {
  taskId: number;
  actorUserId: number;
  actionDigest: string;
  tenant: string;
  skillDigest: string;
  capabilityLease: CapabilityLease;
  parameters: Record<string, unknown>;
  cognitiveStage: CognitiveStage;
}

export interface SkillExecutionResult {
  skillId: string;
  success: boolean;
  stage: CognitiveStage;
  output: unknown;
  evidenceHash: string;
  executionDurationMs: number;
  kamilVerification: {
    expectedMatchedActual: boolean;
    critiqueNote?: string;
    beliefDiffDetected: boolean;
  };
}

export interface GovernedSkillDefinition<TParams = Record<string, unknown>, TResult = unknown> {
  metadata: SkillMetadata;
  paramSchema: z.ZodType<TParams>;
  execute: (ctx: SkillExecutionContext, params: TParams) => Promise<TResult>;
  verifyPostCondition?: (result: TResult, params: TParams) => Promise<boolean> | boolean;
}
