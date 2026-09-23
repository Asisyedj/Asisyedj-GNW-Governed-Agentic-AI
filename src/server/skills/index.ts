export * from "./types.js";
export * from "./registry.js";
export * from "./catalog.js";

import { GovernedSkillRegistry } from "./registry.js";
import { TOP_50_SKILLS_CATALOG } from "./catalog.js";

/**
 * Creates and initializes the default Governed Skill Registry
 * preloaded with all 50 World-Class Agent Skills.
 */
export function createDefaultSkillRegistry(): GovernedSkillRegistry {
  const registry = new GovernedSkillRegistry();
  for (const skill of TOP_50_SKILLS_CATALOG) {
    registry.registerSkill(skill);
  }
  return registry;
}
