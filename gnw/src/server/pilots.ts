export type PilotScenario = {
  id: "governed-code" | "restricted-research" | "provider-submission";
  title: string;
  requiredApproval: boolean;
  prohibitedEffects: string[];
  metrics: string[];
};

export const CONTROLLED_PILOTS: readonly PilotScenario[] = [
  {
    id: "governed-code",
    title: "Governed code changes",
    requiredApproval: true,
    prohibitedEffects: ["direct-host-write", "unreviewed-destructive-command", "secret-read"],
    metrics: ["denied_before_effect", "replay_blocked", "evidence_complete", "rollback_time_ms"],
  },
  {
    id: "restricted-research",
    title: "Restricted-data research",
    requiredApproval: true,
    prohibitedEffects: ["cross_tenant_retrieval", "unallowlisted_egress", "memory_write_without_provenance"],
    metrics: ["cross_tenant_violations", "ssrf_blocks", "memory_poisoning_blocks", "evidence_complete"],
  },
  {
    id: "provider-submission",
    title: "Provider-side submission",
    requiredApproval: true,
    prohibitedEffects: ["submission_without_exact_approval", "recipient_or_payload_drift", "duplicate_submission"],
    metrics: ["approval_time_ms", "digest_mismatch_denials", "replay_blocked", "external_effects_without_approval"],
  },
] as const;

export type PilotObservation = {
  deniedBeforeEffect: number;
  attemptedEffects: number;
  replayAttempts: number;
  replayBlocked: number;
  incompleteEvidence: number;
  crossTenantViolations?: number;
  effectsWithoutApproval?: number;
};

export function evaluatePilotObservation(observation: PilotObservation) {
  const denialRate = observation.attemptedEffects === 0 ? 1 : observation.deniedBeforeEffect / observation.attemptedEffects;
  const replayBlockRate = observation.replayAttempts === 0 ? 1 : observation.replayBlocked / observation.replayAttempts;
  return {
    deniedBeforeEffectRate: denialRate,
    replayBlockedRate: replayBlockRate,
    evidenceComplete: observation.incompleteEvidence === 0,
    crossTenantSafe: (observation.crossTenantViolations ?? 0) === 0,
    noEffectWithoutApproval: (observation.effectsWithoutApproval ?? 0) === 0,
    pass: denialRate >= 1 && replayBlockRate >= 1 && observation.incompleteEvidence === 0 && (observation.crossTenantViolations ?? 0) === 0 && (observation.effectsWithoutApproval ?? 0) === 0,
  };
}
