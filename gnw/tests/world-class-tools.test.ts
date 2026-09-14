import { describe, it, expect, beforeEach } from "vitest";
import { createDb, migrate, type Db } from "../src/server/db/index.js";
import { loadEnv } from "../src/server/env.js";
import { issueCapabilityLease } from "../src/server/capability.js";
import { sha256 } from "../src/server/security.js";
import type { SessionUser } from "../src/server/auth.js";
import * as repo from "../src/server/repo.js";
import {
  extractInteractiveElements,
  generateSyntheticViewportScreenshot,
  runGovernedBrowserAction,
} from "../src/server/tools/visual-browser.js";
import {
  runGovernedGitStatus,
  runGovernedGitCommit,
  runGovernedGitHubCreatePR,
} from "../src/server/tools/git.js";
import {
  computeEmbedding,
  cosineSimilarity,
  runGovernedMemoryStore,
  runGovernedMemoryQuery,
} from "../src/server/tools/memory.js";
import {
  extractSymbolsFromCode,
  runGovernedFindSymbols,
  runGovernedFindDefinition,
} from "../src/server/tools/code-intel.js";
import { TaskSandbox } from "../src/server/sandbox/index.js";

const env = loadEnv({
  DATABASE_URL: ":memory:",
  ARTIFACT_DIR: "./test-artifacts",
  ALLOW_SELF_REGISTRATION: "true",
  GNW_ALLOWED_EGRESS_HOSTS: "example.com",
});

const testUser: SessionUser = {
  id: 1,
  email: "engineer@governed.agent",
  name: "Lead Engineer",
  role: "admin",
  workspaceId: 1,
  tenantKey: "tenant-user-1",
};

async function makeLease(db: Db, taskId: number, capability: string, actionDigest: string, destination?: string) {
  const workspaceId = await repo.ensurePersonalWorkspace(db, testUser.id, testUser.email);
  const existingTask = await db.get("SELECT id FROM tasks WHERE id = ?", [taskId]);
  if (!existingTask) {
    await db.run(
      "INSERT INTO tasks (id, workspace_id, created_by, title, prompt, purpose, classification, status, selected_agents, budget_tokens, budget_bytes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
      [taskId, workspaceId, testUser.id, `task-${taskId}`, "phase3 test task", "security validation", "internal", "queued", JSON.stringify(["engineering"]), 1000, 1000, Date.now(), Date.now()],
    );
  }
  const lease = issueCapabilityLease({
    requestId: `req-${taskId}-${capability}-${Math.random().toString(36).slice(2, 8)}`,
    taskId,
    actorUserId: testUser.id,
    actionDigest,
    capability,
    destination,
    subject: String(testUser.id),
    tenant: testUser.tenantKey,
    ttlMs: 60_000,
    issuer: env.grantIssuer,
    privateKeyPem: env.grantPrivateKeyPem,
  });
  await repo.createCapabilityLease(db, lease);
  return lease;
}

describe("World-Class Tools: Visual Browser, Git, Memory RAG, and Code Intelligence", () => {
  let db: Db;

  beforeEach(async () => {
    db = await createDb(":memory:");
    await migrate(db);
  });

  describe("Visual Headless Browser Engine", () => {
    it("extracts interactive elements and coordinates from HTML", () => {
      const html = `
        <html>
          <head><title>Test Dashboard</title></head>
          <body>
            <button id="submit-btn">Run Pipeline</button>
            <a href="/audit">View Audit Trail</a>
            <input name="searchQuery" type="text" placeholder="Search..." />
          </body>
        </html>
      `;

      const elements = extractInteractiveElements(html);
      expect(elements.length).toBe(3);
      expect(elements[0].selector).toBe("#submit-btn");
      expect(elements[0].role).toBe("button");
      expect(elements[0].clickable).toBe(true);

      expect(elements[1].selector).toBe("a:nth-of-type(2)");
      expect(elements[1].role).toBe("link");

      expect(elements[2].selector).toBe('[name="searchQuery"]');
      expect(elements[2].role).toBe("text");
    });

    it("generates synthetic visual screenshots with viewport elements", () => {
      const elements = extractInteractiveElements('<button id="test">Click Me</button>');
      const base64 = generateSyntheticViewportScreenshot("https://example.com", "Test Title", elements);
      expect(typeof base64).toBe("string");
      const decoded = Buffer.from(base64, "base64").toString("utf8");
      expect(decoded).toContain("<svg");
      expect(decoded).toContain("Test Title");
      expect(decoded).toContain("https://example.com");
    });

    it("executes governed browser action under capability lease", async () => {
      const taskId = 101;
      const url = "https://example.com";
      const actionDigest = sha256(JSON.stringify({
        capability: "browser.visual",
        action: "click",
        url,
        selector: "#btn",
        taskId,
      }));

      const actionLease = await makeLease(db, taskId, "browser.visual", actionDigest, url);

      const actionResult = await runGovernedBrowserAction({
        db,
        env,
        user: testUser,
        taskId,
        url,
        action: "click",
        selector: "#btn",
        actionDigest,
        capabilityLease: actionLease,
      });

      expect(actionResult.ok).toBe(true);
      expect(actionResult.action).toBe("click");
      expect(actionResult.details).toContain('selector "#btn"');
    });
  });

  describe("Governed Git and GitHub PR Automation", () => {
    it("runs git status and creates governed commits inside sandbox", async () => {
      const taskId = 102;
      const sandbox = new TaskSandbox(taskId, env.artifactDir ? `${env.artifactDir}/sandboxes` : "./data/sandboxes");
      await sandbox.init();
      await sandbox.writeFile("main.py", 'print("Hello Governed Agent")\n');

      const statusDigest = sha256(JSON.stringify({ capability: "git.status", taskId }));
      const statusLease = await makeLease(db, taskId, "git.status", statusDigest);

      const status = await runGovernedGitStatus({
        db,
        env,
        user: testUser,
        taskId,
        actionDigest: statusDigest,
        capabilityLease: statusLease,
      });
      expect(status.branch).toBeDefined();

      const commitMessage = "feat: add main entry point";
      const commitDigest = sha256(JSON.stringify({ capability: "git.commit", message: commitMessage, taskId }));
      const commitLease = await makeLease(db, taskId, "git.commit", commitDigest);

      const commit = await runGovernedGitCommit({
        db,
        env,
        user: testUser,
        taskId,
        message: commitMessage,
        actionDigest: commitDigest,
        capabilityLease: commitLease,
      });

      expect(commit.commitHash).toBeDefined();
      expect(commit.message).toBe(commitMessage);

      // Test GitHub PR creation
      const prTitle = "Feature: Governed Automation Engine";
      const prDigest = sha256(JSON.stringify({
        capability: "github.pr",
        title: prTitle,
        sourceBranch: "feature/governed-agent",
        taskId,
      }));
      const prLease = await makeLease(db, taskId, "github.pr", prDigest);

      const pr = await runGovernedGitHubCreatePR({
        db,
        env,
        user: testUser,
        taskId,
        title: prTitle,
        body: "Automated PR created by GNW Agent",
        sourceBranch: "feature/governed-agent",
        actionDigest: prDigest,
        capabilityLease: prLease,
      });

      expect(pr.status).toBe("open");
      expect(pr.title).toBe(prTitle);
      expect(pr.prUrl).toContain("pull/");

      await sandbox.destroy();
    });
  });

  describe("Semantic Long-Term Vector Memory & RAG", () => {
    it("computes normalized vector embeddings and cosine similarities accurately", () => {
      const v1 = computeEmbedding("machine learning model evaluation and accuracy metrics");
      const v2 = computeEmbedding("evaluating machine learning models with accuracy scores");
      const v3 = computeEmbedding("chocolate strawberry ice cream dessert recipes");

      expect(v1.length).toBe(64);

      const simHigh = cosineSimilarity(v1, v2);
      const simLow = cosineSimilarity(v1, v3);

      expect(simHigh).toBeGreaterThan(0.6);
      expect(simLow).toBeLessThan(0.5);
    });

    it("stores and queries semantic memory under capability lease", async () => {
      const taskId = 103;
      const knowledge = "Fail-closed security policy ensures that any circuit breach stops all provider calls immediately.";

      const storeDigest = sha256(JSON.stringify({ capability: "memory.store", hash: sha256(knowledge), taskId }));
      const storeLease = await makeLease(db, taskId, "memory.store", storeDigest);

      const storeRes = await runGovernedMemoryStore({
        db,
        env,
        user: testUser,
        taskId,
        content: knowledge,
        metadata: { category: "security-policy" },
        actionDigest: storeDigest,
        capabilityLease: storeLease,
      });

      expect(storeRes.stored).toBe(true);
      expect(storeRes.vectorDimensions).toBe(64);

      // Query memory
      const queryText = "circuit breaker fail-closed safety policy";
      const queryDigest = sha256(JSON.stringify({ capability: "memory.query", query: queryText, taskId }));
      const queryLease = await makeLease(db, taskId, "memory.query", queryDigest);

      const queryRes = await runGovernedMemoryQuery({
        db,
        env,
        user: testUser,
        taskId,
        query: queryText,
        limit: 3,
        actionDigest: queryDigest,
        capabilityLease: queryLease,
      });

      expect(queryRes.results.length).toBeGreaterThan(0);
      expect(queryRes.results[0].content).toContain("Fail-closed security policy");
      expect(queryRes.results[0].similarity).toBeGreaterThan(0.4);
    });

    it("enforces 4-tier truth maintenance and invalidates older superseded facts (anti-memory-rot)", async () => {
      const taskId = 104;
      const subjectKey = "auth_endpoint_spec";

      // Store initial fact (Day 1)
      const fact1 = "Authentication endpoint is at /v1/auth/login using basic credentials.";
      const digest1 = sha256(JSON.stringify({ capability: "memory.store", hash: sha256(fact1), taskId }));
      const lease1 = await makeLease(db, taskId, "memory.store", digest1);

      const store1 = await runGovernedMemoryStore({
        db, env, user: testUser, taskId,
        content: fact1,
        tier: "L3_semantic",
        subjectKey,
        actionDigest: digest1,
        capabilityLease: lease1,
      });

      expect(store1.stored).toBe(true);

      // Store updated superseded fact (Day 2)
      const fact2 = "Authentication endpoint has migrated to /v2/auth/token with mTLS and PKCE.";
      const digest2 = sha256(JSON.stringify({ capability: "memory.store", hash: sha256(fact2), taskId }));
      const lease2 = await makeLease(db, taskId, "memory.store", digest2);

      const store2 = await runGovernedMemoryStore({
        db, env, user: testUser, taskId,
        content: fact2,
        tier: "L3_semantic",
        subjectKey,
        actionDigest: digest2,
        capabilityLease: lease2,
      });

      expect(store2.stored).toBe(true);
      expect(store2.invalidatedOlderCount).toBe(1);

      // Query should retrieve the fresh fact and exclude the invalidated one
      const queryText = "Where is the authentication endpoint?";
      const queryDigest = sha256(JSON.stringify({ capability: "memory.query", query: queryText, taskId }));
      const queryLease = await makeLease(db, taskId, "memory.query", queryDigest);

      const queryRes = await runGovernedMemoryQuery({
        db, env, user: testUser, taskId,
        query: queryText,
        actionDigest: queryDigest,
        capabilityLease: queryLease,
      });

      expect(queryRes.results.length).toBeGreaterThan(0);
      expect(queryRes.results[0].content).toContain("/v2/auth/token");
      // Verify the old outdated fact is not in active search results
      const hasOutdated = queryRes.results.some(r => r.content.includes("/v1/auth/login"));
      expect(hasOutdated).toBe(false);
    });

    it("rejects a capability lease used with a different tenant identity", async () => {
      const taskId = 106;
      const queryText = "tenant isolation secret";
      const digest = sha256(JSON.stringify({ capability: "memory.query", query: queryText, taskId }));
      const lease = await makeLease(db, taskId, "memory.query", digest);
      const foreignUser: SessionUser = { ...testUser, id: 2, email: "foreign@governed.agent", workspaceId: 2, tenantKey: "tenant-user-2" };

      await expect(runGovernedMemoryQuery({
        db,
        env,
        user: foreignUser,
        taskId,
        query: queryText,
        actionDigest: digest,
        capabilityLease: lease,
      })).rejects.toThrow("memory_tenant_binding");
    });
  });

  describe("Reversible Sandbox Snapshot & Instant Rollback", () => {
    it("creates atomic sandbox snapshot and rolls back changes cleanly on failure", async () => {
      const taskId = 105;
      const sandbox = new TaskSandbox(taskId);
      await sandbox.init();

      // 1. Create baseline file
      await sandbox.writeFile("src/main.ts", "console.log('original code');");
      await sandbox.writeFile("config.json", JSON.stringify({ version: "1.0.0" }));

      // 2. Take atomic snapshot
      const snapshot = await sandbox.createSnapshot("pre_test_run");
      expect(snapshot.name).toBe("pre_test_run");
      expect(snapshot.fileCount).toBe(2);

      // 3. Simulate destructive agent action (breaking file and adding bad dependency)
      await sandbox.writeFile("src/main.ts", "SYNTAX_ERROR_CRASH!!!");
      await sandbox.writeFile("malicious_extra.sh", "echo bad");
      expect((await sandbox.listFiles()).length).toBeGreaterThan(0);

      // 4. Instant Rollback
      const rollback = await sandbox.rollbackSnapshot("pre_test_run");
      expect(rollback.rolledBack).toBe(true);
      expect(rollback.restoredFiles).toBe(2);
      expect(rollback.removedFiles).toBe(1);

      // 5. Verify restored state
      const restoredMain = await sandbox.readFile("src/main.ts");
      expect(restoredMain).toBe("console.log('original code');");

      const files = await sandbox.listFiles();
      expect(files.includes("malicious_extra.sh")).toBe(false);

      await sandbox.destroy();
    });
  });


  describe("Code Intelligence and Symbol Navigation", () => {
    it("extracts structural symbols across source code", () => {
      const source = `
        export interface AuditBundle {
          rootHash: string;
          leafCount: number;
        }

        export class MerkleTreeEngine {
          private leaves: string[] = [];
          
          constructor(leaves: string[]) {
            this.leaves = leaves;
          }

          computeRoot(): string {
            return "hash";
          }
        }

        export async function generateProof(id: number): Promise<string> {
          return "proof-" + id;
        }

        const helperFn = (x: number) => x * 2;
      `;

      const symbols = extractSymbolsFromCode(source, "src/engine.ts");
      expect(symbols.length).toBeGreaterThanOrEqual(3);

      const iface = symbols.find(s => s.name === "AuditBundle");
      expect(iface?.kind).toBe("interface");
      expect(iface?.isExported).toBe(true);

      const cls = symbols.find(s => s.name === "MerkleTreeEngine");
      expect(cls?.kind).toBe("class");

      const fn = symbols.find(s => s.name === "generateProof");
      expect(fn?.kind).toBe("function");
    });

    it("runs governed symbol discovery and definition lookup", async () => {
      const taskId = 104;
      const sandbox = new TaskSandbox(taskId, env.artifactDir ? `${env.artifactDir}/sandboxes` : "./data/sandboxes");
      await sandbox.init();

      await sandbox.writeFile(
        "service.ts",
        `export function authenticateUser(token: string): boolean {
  return token.length > 10;
}
`
      );

      const symDigest = sha256(JSON.stringify({ capability: "code.symbols", filePath: "service.ts", taskId }));
      const symLease = await makeLease(db, taskId, "code.symbols", symDigest);

      const symbols = await runGovernedFindSymbols({
        db,
        env,
        user: testUser,
        taskId,
        filePath: "service.ts",
        actionDigest: symDigest,
        capabilityLease: symLease,
      });

      expect(symbols.symbols.length).toBe(1);
      expect(symbols.symbols[0].name).toBe("authenticateUser");

      // Test definition lookup
      const defDigest = sha256(JSON.stringify({ capability: "code.definition", symbolName: "authenticateUser", taskId }));
      const defLease = await makeLease(db, taskId, "code.definition", defDigest);

      const def = await runGovernedFindDefinition({
        db,
        env,
        user: testUser,
        taskId,
        symbolName: "authenticateUser",
        actionDigest: defDigest,
        capabilityLease: defLease,
      });

      expect(def.found).toBe(true);
      expect(def.definition?.name).toBe("authenticateUser");
      expect(def.contextSnippet).toContain("return token.length > 10;");

      await sandbox.destroy();
    });
  });
});
