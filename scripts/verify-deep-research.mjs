import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../", import.meta.url).pathname;
const required = [
  "src/server/deep-research.ts",
  "src/server/env.ts",
  "src/server/repo.ts",
  "src/server/app.ts",
  "src/client/views/DeepResearchPanel.tsx",
  "src/client/views/Workspace.tsx",
  "src/client/api.ts",
  "tests/deep-research.test.ts",
  "docs/DEEP-RESEARCH-ENGINE.md",
];
const checks = [];
function need(path, text) {
  const full = join(root, path);
  if (!existsSync(full)) throw new Error(`missing:${path}`);
  const body = readFileSync(full, "utf8");
  if (text && !body.includes(text)) throw new Error(`missing_text:${path}:${text}`);
  checks.push(path);
}

need("src/server/deep-research.ts", 'type: "web_search"');
need("src/server/deep-research.ts", "background: true");
need("src/server/deep-research.ts", "max_tool_calls");
need("src/server/deep-research.ts", "executeFencedExternal");
need("src/server/deep-research.ts", "GNW NON-OVERRIDABLE RESEARCH CONTROLS");
need("src/server/deep-research.ts", "cancelDeepResearch");
need("src/server/deep-research.ts", "deepResearchBaseUrl");
need("src/server/env.ts", "deepResearchApiKey");
need("src/server/repo.ts", "deep_research_runs");
need("src/server/app.ts", "/deep-research/plan");
need("src/server/app.ts", "/deep-research/start");
need("src/server/app.ts", "/deep-research/:runId/cancel");
need("src/client/views/DeepResearchPanel.tsx", "Mandatory sequence");
need("src/client/views/DeepResearchPanel.tsx", "Clarification answers");
need("tests/deep-research.test.ts", "buildToolPolicy");
need("docs/DEEP-RESEARCH-ENGINE.md", "PLAN -> CLARIFICATION/ASSUMPTIONS -> PROMPT REWRITE");

console.log(`DEEP_RESEARCH_STATIC_VERIFY=PASS checks=${checks.length}`);
