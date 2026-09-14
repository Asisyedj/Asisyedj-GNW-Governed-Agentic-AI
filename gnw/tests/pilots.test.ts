import { describe, expect, it } from "vitest";
import { CONTROLLED_PILOTS, evaluatePilotObservation } from "../src/server/pilots.js";

describe("GNW controlled pilots", () => {
  it("defines the three requested measurable pilot scenarios", () => {
    expect(CONTROLLED_PILOTS.map(pilot => pilot.id)).toEqual(["governed-code", "restricted-research", "provider-submission"]);
    expect(CONTROLLED_PILOTS.every(pilot => pilot.requiredApproval)).toBe(true);
  });

  it("passes only when no external effect escapes controls", () => {
    expect(evaluatePilotObservation({ deniedBeforeEffect: 3, attemptedEffects: 3, replayAttempts: 2, replayBlocked: 2, incompleteEvidence: 0, crossTenantViolations: 0, effectsWithoutApproval: 0 }).pass).toBe(true);
    expect(evaluatePilotObservation({ deniedBeforeEffect: 2, attemptedEffects: 3, replayAttempts: 2, replayBlocked: 2, incompleteEvidence: 0, crossTenantViolations: 0, effectsWithoutApproval: 0 }).pass).toBe(false);
  });
});
