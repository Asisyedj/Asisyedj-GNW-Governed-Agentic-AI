import { beforeEach, describe, expect, it } from "vitest";
import { createDb, migrate, type Db } from "../src/server/db/index.js";
import { appendAudit, verifyAuditChain, GENESIS_HASH } from "../src/server/audit.js";

let db: Db;

beforeEach(async () => {
  db = await createDb("file::memory:");
  await migrate(db);
});

describe("audit chain", () => {
  it("chains events from genesis and verifies", async () => {
    const first = await appendAudit(db, { eventType: "task_admission", decision: "ALLOW", reason: "task_created", payload: { a: 1 } });
    const second = await appendAudit(db, { eventType: "agent_result", decision: "ALLOW", reason: "result_recorded", payload: { b: 2 } });
    expect(first.previous_hash).toBe(GENESIS_HASH);
    expect(second.previous_hash).toBe(first.event_hash);
    await expect(verifyAuditChain(db)).resolves.toMatchObject({ valid: true, events: 2 });
  });

  it("detects a tampered row", async () => {
    await appendAudit(db, { eventType: "task_admission", decision: "ALLOW", reason: "task_created", payload: { a: 1 } });
    const target = await appendAudit(db, { eventType: "approval_review", decision: "DENY", reason: "approval_denied", payload: { id: 7 } });
    await db.run("UPDATE audit_events SET decision = ? WHERE id = ?", ["ALLOW", target.id]);
    const verification = await verifyAuditChain(db);
    expect(verification.valid).toBe(false);
    expect(verification.brokenAt).toBe(target.id);
  });

  it("detects a deleted row", async () => {
    await appendAudit(db, { eventType: "e1", decision: "ALLOW", reason: "r1", payload: {} });
    const middle = await appendAudit(db, { eventType: "e2", decision: "ALLOW", reason: "r2", payload: {} });
    await appendAudit(db, { eventType: "e3", decision: "ALLOW", reason: "r3", payload: {} });
    await db.run("DELETE FROM audit_events WHERE id = ?", [middle.id]);
    await expect(verifyAuditChain(db)).resolves.toMatchObject({ valid: false });
  });
});
