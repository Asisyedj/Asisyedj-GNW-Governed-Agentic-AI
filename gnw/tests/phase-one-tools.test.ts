import { describe, expect, it } from "vitest";
import { PHASE_ONE_TOOLS, phaseOneSummary, phaseOneToolsForPriority } from "../src/server/phase-one-tools.js";

describe("GNW phase-one tool contract", () => {
  it("defines exactly the requested 20 ranked tools", () => {
    expect(PHASE_ONE_TOOLS).toHaveLength(20);
    expect(PHASE_ONE_TOOLS.map((tool) => tool.rank)).toEqual(Array.from({ length: 20 }, (_, index) => index + 1));
    expect(new Set(PHASE_ONE_TOOLS.map((tool) => tool.id)).size).toBe(20);
  });

  it("keeps P0 governance and execution controls ahead of productivity integrations", () => {
    expect(phaseOneToolsForPriority("P0").map((tool) => tool.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(PHASE_ONE_TOOLS.slice(0, 8).every((tool) => tool.safetyGate.length > 0)).toBe(true);
  });

  it("reports implementation status without overstating production certification", () => {
    const summary = phaseOneSummary();
    expect(summary.total).toBe(20);
    expect(summary.planned).toBeGreaterThan(0);
    expect(summary.implemented + summary.hardened + summary.planned).toBe(20);
  });
});
