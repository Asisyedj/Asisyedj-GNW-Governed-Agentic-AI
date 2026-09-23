import { describe, expect, it } from "vitest";
import { createDb, migrate, type Db } from "../src/server/db/index.js";
import { loadEnv } from "../src/server/env.js";
import { buildShadowEnvelope, DeterministicShadowRoleRunner, runCouncilShadow } from "../src/server/council/orchestrator.js";
import { evaluateShadowPolicy } from "../src/server/council/policy-gate.js";
import { CouncilStore } from "../src/server/council/store.js";
import { parseCouncilTaskEnvelope } from "../src/server/council/schemas.js";
import { redactForCouncil } from "../src/server/council/redaction.js";

const env = loadEnv({ NODE_ENV: "test", DATABASE_URL: "file::memory:", SESSION_SECRET: "c".repeat(48), GNW_COUNCIL_MODE: "shadow" });

async function testDb(): Promise<Db> {
  const db = await createDb("file::memory:");
  await migrate(db);
  return db;
}

function envelope(idempotencyKey = `idem-${crypto.randomUUID()}`) {
  return buildShadowEnvelope({ sourceTaskId: 7, actorUserId: 42, purpose: "read-only review", classification: "internal", promptDigest: "a".repeat(64) });
}

describe("source-only shadow council", () => {
  it("validates the envelope and reaches SHADOW_COMPLETED without authorization", async () => {
    const db = await testDb();
    const result = await runCouncilShadow({ db, env, sourceTaskId: 7, actorUserId: 42, envelope: envelope() });
    expect(result.status).toBe("shadow_completed");
    expect(result.decision?.executionAuthorized).toBe(false);
    expect(await new CouncilStore(db).countTasks()).toBe(1);
    expect(await new CouncilStore(db).countDecisions()).toBe(1);
    const row = await db.get<{ status: string }>("SELECT status FROM council_tasks WHERE task_id = ?", [result.taskId]);
    expect(row?.status).toBe("SHADOW_COMPLETED");
    await db.close();
  });

  it("is idempotent on the same envelope", async () => {
    const db = await testDb();
    const first = await runCouncilShadow({ db, env, sourceTaskId: 7, actorUserId: 42, envelope: envelope() });
    const second = await runCouncilShadow({ db, env, sourceTaskId: 7, actorUserId: 42, envelope: parseCouncilTaskEnvelope(JSON.parse((await db.get<{ task_envelope_json: string }>("SELECT task_envelope_json FROM council_tasks WHERE task_id = ?", [first.taskId]))!.task_envelope_json)) });
    expect(first.status).toBe("shadow_completed");
    expect(second.status).toBe("idempotent_replay");
    expect(await new CouncilStore(db).countTasks()).toBe(1);
    await db.close();
  });

  it("fails closed on an invalid role output", async () => {
    const db = await testDb();
    const runner = new DeterministicShadowRoleRunner();
    const badRunner = {
      runRole: async () => ({ output: { invalid: true }, modelProvider: "test", modelVersion: "test", promptTemplateSha256: "b".repeat(64) }),
      runJudge: runner.runJudge.bind(runner),
    };
    const result = await runCouncilShadow({ db, env, sourceTaskId: 7, actorUserId: 42, envelope: envelope(), runner: badRunner });
    expect(result.status).toBe("failed_closed");
    const row = await db.get<{ status: string; error_code: string | null }>("SELECT status, error_code FROM council_tasks LIMIT 1");
    expect(row?.status).toBe("FAILED_CLOSED");
    expect(row?.error_code).toMatch(/^\[/);
    const decision = evaluateShadowPolicy({ task: parseCouncilTaskEnvelope(envelope()), findings: [], judge: await runner.runJudge(parseCouncilTaskEnvelope(envelope()), []).then(item => item.output as never) });
    expect(decision.executionAuthorized).toBe(false);
    await db.close();
  });

  it("redacts sensitive keys before council persistence", () => {
    expect(redactForCouncil({ password: "secret", nested: { apiKey: "secret" }, value: "safe" })).toEqual({ password: "[REDACTED]", nested: { apiKey: "[REDACTED]" }, value: "safe" });
  });
});
