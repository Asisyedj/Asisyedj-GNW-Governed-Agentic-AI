import { createHash } from "node:crypto";
import { canonicalize } from "./security.js";
import type { Db } from "./db/index.js";

export type AuditInput = {
  taskId?: number | null;
  actorUserId?: number | null;
  eventType: string;
  decision: string;
  reason: string;
  payload: unknown;
  occurredAt?: number;
};

export type AuditRow = {
  id: number;
  task_id: number | null;
  actor_user_id: number | null;
  event_type: string;
  decision: string;
  reason: string;
  payload_digest: string;
  previous_hash: string;
  event_hash: string;
  occurred_at: number;
};

export const GENESIS_HASH = "GENESIS";

export function hashEvent(previousHash: string, occurredAt: number, eventType: string, decision: string, reason: string, payloadDigest: string) {
  return createHash("sha256").update(`${previousHash}|${occurredAt}|${eventType}|${decision}|${reason}|${payloadDigest}`).digest("hex");
}

/**
 * Appends a tamper-evident event. The chain lives in the database, so the
 * evidence survives restarts; a rewritten or deleted row breaks verification.
 */
export async function appendAudit(db: Db, input: AuditInput): Promise<AuditRow> {
  const occurredAt = input.occurredAt ?? Date.now();
  const payloadDigest = createHash("sha256").update(canonicalize(input.payload ?? null)).digest("hex");
  const reason = input.reason;
  return db.transaction(async tx => {
    const state = await tx.get<{ event_hash: string }>(tx.dialect === "postgres" ? "SELECT event_hash FROM audit_chain_state WHERE id = 1 FOR UPDATE" : "SELECT event_hash FROM audit_chain_state WHERE id = 1");
    const previousHash = state?.event_hash ?? GENESIS_HASH;
    const eventHash = hashEvent(previousHash, occurredAt, input.eventType, input.decision, reason, payloadDigest);
    const id = await tx.insert(`INSERT INTO audit_events (task_id, actor_user_id, event_type, decision, reason, payload_digest, previous_hash, event_hash, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`, [input.taskId ?? null, input.actorUserId ?? null, input.eventType, input.decision, reason, payloadDigest, previousHash, eventHash, occurredAt]);
    await tx.run("UPDATE audit_chain_state SET event_hash = ?, updated_at = ? WHERE id = 1", [eventHash, occurredAt]);
    return { id, task_id: input.taskId ?? null, actor_user_id: input.actorUserId ?? null, event_type: input.eventType, decision: input.decision, reason, payload_digest: payloadDigest, previous_hash: previousHash, event_hash: eventHash, occurred_at: occurredAt };
  });
}

export async function listAudit(db: Db, taskId?: number, limit = 200): Promise<AuditRow[]> {
  if (taskId) return db.all<AuditRow>("SELECT * FROM audit_events WHERE task_id = ? ORDER BY id ASC LIMIT ?", [taskId, limit]);
  return db.all<AuditRow>("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", [limit]);
}

/** Complete ordered retrieval used by proof generation; UI reads remain bounded. */
export async function listAuditComplete(db: Db, taskId?: number): Promise<AuditRow[]> {
  if (taskId) return db.all<AuditRow>("SELECT * FROM audit_events WHERE task_id = ? ORDER BY id ASC", [taskId]);
  return db.all<AuditRow>("SELECT * FROM audit_events ORDER BY id ASC");
}

export type ChainVerification = { valid: boolean; events: number; brokenAt?: number; expected?: string; found?: string };

/** Recomputes the whole chain. Used by the audit page and the acceptance tests. */
export async function verifyAuditChain(db: Db): Promise<ChainVerification> {
  const rows = await db.all<AuditRow>("SELECT * FROM audit_events ORDER BY id ASC");
  let previous = GENESIS_HASH;
  for (const row of rows) {
    const expected = hashEvent(previous, Number(row.occurred_at), row.event_type, row.decision, row.reason, row.payload_digest);
    if (row.previous_hash !== previous || row.event_hash !== expected) {
      return { valid: false, events: rows.length, brokenAt: row.id, expected, found: row.event_hash };
    }
    previous = row.event_hash;
  }
  return { valid: true, events: rows.length };
}
