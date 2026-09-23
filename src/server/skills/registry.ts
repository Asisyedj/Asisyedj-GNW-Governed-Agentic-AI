import { sha256, canonicalize } from "../security.js";
import { verifyCapabilityLease } from "../capability.js";
import {
  SkillExecutionError,
  type GovernedSkillDefinition,
  type SkillExecutionContext,
  type SkillExecutionResult,
  type SkillMetadata
} from "./types.js";
import { SKILL_DIGEST_VERSION } from "./types.js";

export function skillDefinitionDigest(skill: GovernedSkillDefinition): string {
  return sha256(canonicalize({
    version: SKILL_DIGEST_VERSION,
    metadata: skill.metadata,
    parameterSchema: skill.paramSchema.toString(),
  }));
}

export class GovernedSkillRegistry {
  private skills = new Map<string, GovernedSkillDefinition<any, any>>();

  /**
   * Registers a new skill into the governed registry.
   */
  registerSkill<TParams, TResult>(skill: GovernedSkillDefinition<TParams, TResult>): void {
    if (this.skills.has(skill.metadata.id)) {
      throw new Error(`Skill with ID '${skill.metadata.id}' is already registered.`);
    }
    this.skills.set(skill.metadata.id, skill);
  }

  getSkill(skillId: string): GovernedSkillDefinition | undefined {
    return this.skills.get(skillId);
  }

  listSkills(): SkillMetadata[] {
    return Array.from(this.skills.values()).map(s => s.metadata);
  }

  findSkillsByCategory(category: string): SkillMetadata[] {
    return this.listSkills().filter(s => s.category === category);
  }

  findSkillsBySpecialist(specialist: string): SkillMetadata[] {
    return this.listSkills().filter(s => s.specialist === specialist);
  }

  searchSkills(query: string): SkillMetadata[] {
    const q = query.toLowerCase();
    return this.listSkills().filter(
      s => s.id.toLowerCase().includes(q) ||
           s.name.toLowerCase().includes(q) ||
           s.description.toLowerCase().includes(q) ||
           s.tags.some(t => t.toLowerCase().includes(q))
    );
  }

  /**
   * Executes a registered skill strictly bounded by GNW capability lease,
   * Kamil AI cognitive verification (Expected <-> Actual), and Perplexity input schemas.
   */
  async executeSkill(
    skillId: string,
    ctx: SkillExecutionContext,
    publicKeyPem: string
  ): Promise<SkillExecutionResult> {
    const skill = this.skills.get(skillId);
    if (!skill) {
      throw new Error(`Skill '${skillId}' not found in governed registry.`);
    }

    // 1. GNW v4 Cryptographic Capability Lease Verification
    if (!verifyCapabilityLease(ctx.capabilityLease, publicKeyPem)) {
      throw new SkillExecutionError("invalid_capability_lease", "Capability lease signature or TTL is invalid.");
    }
    if (ctx.capabilityLease.capability !== skill.metadata.requiredCapability) {
      throw new SkillExecutionError(
        "capability_mismatch",
        `Capability mismatch: skill requires '${skill.metadata.requiredCapability}' but lease grants '${ctx.capabilityLease.capability}'`
      );
    }
    if (ctx.capabilityLease.taskId !== ctx.taskId) {
      throw new SkillExecutionError("task_id_mismatch", "Lease taskId does not match execution context taskId.");
    }
    if (ctx.capabilityLease.actorUserId !== ctx.actorUserId || ctx.capabilityLease.subject !== String(ctx.actorUserId)) {
      throw new SkillExecutionError("actor_binding", "Lease actor and subject do not match execution context.");
    }
    if (ctx.capabilityLease.tenant !== ctx.tenant) {
      throw new SkillExecutionError("tenant_binding", "Lease tenant does not match execution context.");
    }
    if (ctx.skillDigest !== skillDefinitionDigest(skill)) {
      throw new SkillExecutionError("skill_digest_mismatch", "Skill definition digest does not match the admitted context.");
    }
    if (ctx.capabilityLease.actionDigest !== ctx.actionDigest) {
      throw new SkillExecutionError("action_digest_mismatch", "Lease actionDigest does not match context actionDigest.");
    }

    // 2. Perplexity OpenClaw Input Schema Validation
    const parsedParams = skill.paramSchema.safeParse(ctx.parameters);
    if (!parsedParams.success) {
      throw new SkillExecutionError(
        "invalid_skill_parameters",
        `Skill parameters failed schema validation: ${parsedParams.error.message}`
      );
    }

    // 3. Execution under Kamil AI Cognitive Loop
    const startTime = Date.now();
    const output = await skill.execute(ctx, parsedParams.data);
    const durationMs = Date.now() - startTime;

    // 4. Kamil AI Verification: Expected <-> Actual & Post-Condition Check
    let expectedMatchedActual = true;
    let critiqueNote: string | undefined;

    if (skill.verifyPostCondition) {
      try {
        const verified = await skill.verifyPostCondition(output, parsedParams.data);
        expectedMatchedActual = Boolean(verified);
        if (!expectedMatchedActual) {
          critiqueNote = `Kamil verification post-condition failed: Output did not satisfy '${skill.metadata.verificationPostCondition}'`;
        }
      } catch (err) {
        expectedMatchedActual = false;
        critiqueNote = `Kamil verification error: ${err instanceof Error ? err.message : String(err)}`;
      }
    }

    const evidenceHash = sha256(canonicalize({
      skillId,
      taskId: ctx.taskId,
      actorUserId: ctx.actorUserId,
      actionDigest: ctx.actionDigest,
      output,
      expectedMatchedActual,
      timestamp: Date.now(),
    }));

    return {
      skillId,
      success: expectedMatchedActual,
      stage: ctx.cognitiveStage,
      output,
      evidenceHash,
      executionDurationMs: durationMs,
      kamilVerification: {
        expectedMatchedActual,
        critiqueNote,
        beliefDiffDetected: !expectedMatchedActual,
      },
    };
  }
}
