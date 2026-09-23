import { randomUUID } from "node:crypto";
import type { Db } from "../db/index.js";
import { UniqueViolation } from "../db/index.js";
import { canonicalize, sha256 } from "../security.js";
import { redactForCouncil } from "./redaction.js";
import {
  parseCouncilFinding,
  parseCouncilTaskEnvelope,
  parseJudgeVerdict,
  parsePolicyDecision,
  type CouncilFinding,
  type CouncilTaskEnvelope,
  type JudgeVerdict,
  type PolicyDecision,
} from "./schemas.js";

export const COUNCIL_STATES = [
  "RECEIVED",
  "STATIC_VALIDATED",
  "COUNCIL_QUEUED",
  "PLANNING",
  "VERIFYING",
  "CRITIQUING",
  "JUDGING",
  "POLICY_DECIDED",
  "SHADOW_COMPLETED",
  "FAILED_CLOSED",
  "CANCELLED",
  "EXPIRED",
] as const;

export type CouncilState = typeof COUNCIL_STATES[number];

const TERMINAL = new Set<CouncilState>(["SHADOW_COMPLETED", "FAILED_CLOSED", "CANCELLED", "EXPIRED"]);
const ALLOWED_TRANSITIONS: Record<CouncilState, readonly CouncilState[]> = {
  RECEIVED: ["STATIC_VALIDATED", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  STATIC_VALIDATED: ["COUNCIL_QUEUED", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  COUNCIL_QUEUED: ["PLANNING", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  PLANNING: ["VERIFYING", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  VERIFYING: ["CRITIQUING", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  CRITIQUING: ["JUDGING", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  JUDGING: ["POLICY_DECIDED", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  POLICY_DECIDED: ["SHADOW_COMPLETED", "FAILED_CLOSED", "CANCELLED", "EXPIRED"],
  SHADOW_COMPLETED: [],
  FAILED_CLOSED: [],
  CANCELLED: [],
  EXPIRED: [],
};

export type CouncilTaskRow = {
  task_id: string;
  source_task_id: number | null;
  idempotency_key: string;
  status: CouncilState;
  task_envelope_json: string;
  task_envelope_sha256: string;
  policy_version: string;
  council_mode: "shadow";
  created_at: number;
  updated_at: number;
  expires_at: number | null;
  error_code: string | null;
  error_message: string | null;
};

export function assertCouncilTransition(from: CouncilState, to: CouncilState) {
  if (!ALLOWED_TRANSITIONS[from]?.includes(to)) {
    throw new Error(`invalid_council_transition:${from}->${to}`);
  }
}

export class CouncilStore {
  constructor(private readonly db: Db, private readonly now: () => number = Date.now) {}

  async createOrGetTask(input: {
    envelope: CouncilTaskEnvelope;
    sourceTaskId?: number;
    expiresAt?: number | null;
  }): Promise<{ task: CouncilTaskRow; created: boolean }> {
    const envelope = parseCouncilTaskEnvelope(redactForCouncil(input.envelope));
    const envelopeJson = canonicalize(envelope);
    const stamp = this.now();
    try {
      await this.db.run(
        `INSERT INTO council_tasks (task_id, source_task_id, idempotency_key, status, task_envelope_json, task_envelope_sha256, policy_version, council_mode, created_at, updated_at, expires_at)
         VALUES (?, ?, ?, 'RECEIVED', ?, ?, ?, 'shadow', ?, ?, ?)`,
        [envelope.taskId, input.sourceTaskId ?? null, envelope.idempotencyKey, envelopeJson, sha256(envelopeJson), envelope.policyVersion, stamp, stamp, input.expiresAt ?? null],
      );
      await this.recordTransition(envelope.taskId, null, "RECEIVED", "task_received", "system", "shadow-orchestrator");
      return { task: (await this.getTask(envelope.taskId))!, created: true };
    } catch (error) {
      if (!(error instanceof UniqueViolation)) throw error;
      const existing = await this.db.get<CouncilTaskRow>("SELECT * FROM council_tasks WHERE idempotency_key = ?", [envelope.idempotencyKey]);
      if (!existing) throw error;
      return { task: existing, created: false };
    }
  }

  async getTask(taskId: string) {
    return this.db.get<CouncilTaskRow>("SELECT * FROM council_tasks WHERE task_id = ?", [taskId]);
  }

  async transition(taskId: string, to: CouncilState, reasonCode: string, actorType = "system", actorId = "shadow-orchestrator") {
    return this.db.transaction(async tx => {
      const row = await tx.get<CouncilTaskRow>(tx.dialect === "postgres" ? "SELECT * FROM council_tasks WHERE task_id = $1 FOR UPDATE" : "SELECT * FROM council_tasks WHERE task_id = ?", [taskId]);
      if (!row) throw new Error("council_task_not_found");
      assertCouncilTransition(row.status, to);
      const stamp = this.now();
      const changed = await tx.run("UPDATE council_tasks SET status = ?, updated_at = ? WHERE task_id = ? AND status = ?", [to, stamp, taskId, row.status]);
      if (changed.changes !== 1) throw new Error("council_transition_race");
      await tx.run(
        "INSERT INTO council_transitions (transition_id, task_id, from_status, to_status, reason_code, actor_type, actor_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [randomUUID(), taskId, row.status, to, reasonCode, actorType, actorId, stamp],
      );
      return to;
    });
  }

  async failClosed(taskId: string, errorCode: string, errorMessage: string) {
    const row = await this.getTask(taskId);
    if (!row || TERMINAL.has(row.status)) return;
    const safeMessage = String(redactForCouncil(errorMessage)).slice(0, 1000);
    const stamp = this.now();
    await this.db.transaction(async tx => {
      await tx.run("UPDATE council_tasks SET status = 'FAILED_CLOSED', error_code = ?, error_message = ?, updated_at = ? WHERE task_id = ?", [errorCode.slice(0, 120), safeMessage, stamp, taskId]);
      await tx.run(
        "INSERT INTO council_transitions (transition_id, task_id, from_status, to_status, reason_code, actor_type, actor_id, created_at) VALUES (?, ?, ?, 'FAILED_CLOSED', ?, 'system', 'shadow-orchestrator', ?)",
        [randomUUID(), taskId, row.status, errorCode.slice(0, 120), stamp],
      );
    });
  }

  async saveFinding(input: { finding: CouncilFinding | JudgeVerdict; modelProvider: string; modelVersion: string; promptTemplateSha256: string }) {
    const parsed = input.finding.role === "judge" ? parseJudgeVerdict(redactForCouncil(input.finding)) : parseCouncilFinding(redactForCouncil(input.finding));
    const task = await this.getTask(parsed.taskId);
    if (!task) throw new Error("council_task_not_found");
    if (task.policy_version !== parsed.policyVersion) throw new Error("council_policy_binding_invalid");
    const outputJson = canonicalize(parsed);
    await this.db.run(
      `INSERT INTO council_findings (finding_id, task_id, role, model_provider, model_version, prompt_template_sha256, output_json, output_sha256, schema_valid, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)`,
      [randomUUID(), parsed.taskId, parsed.role, input.modelProvider.slice(0, 120), input.modelVersion.slice(0, 120), input.promptTemplateSha256, outputJson, sha256(outputJson), this.now()],
    );
    return parsed;
  }

  async savePolicyDecision(decisionInput: PolicyDecision, judge: JudgeVerdict) {
    const decision = parsePolicyDecision(redactForCouncil(decisionInput));
    const judgeVerdict = parseJudgeVerdict(redactForCouncil(judge));
    if (decision.taskId !== judgeVerdict.taskId) throw new Error("council_decision_binding_invalid");
    const decisionJson = canonicalize(decision);
    await this.db.run(
      `INSERT INTO council_policy_decisions (decision_id, task_id, hypothetical_outcome, deterministic_rule_ids_json, judge_verdict_json, decision_sha256, execution_authorized, created_at)
       VALUES (?, ?, ?, ?, ?, ?, 0, ?)`,
      [randomUUID(), decision.taskId, decision.hypotheticalOutcome, canonicalize(decision.deterministicRuleIds), canonicalize(judgeVerdict), sha256(decisionJson), this.now()],
    );
    return decision;
  }

  async countTasks() {
    const row = await this.db.get<{ count: number }>("SELECT COUNT(*) AS count FROM council_tasks");
    return Number(row?.count ?? 0);
  }

  async countDecisions() {
    const row = await this.db.get<{ count: number }>("SELECT COUNT(*) AS count FROM council_policy_decisions");
    return Number(row?.count ?? 0);
  }

  private async recordTransition(taskId: string, from: CouncilState | null, to: CouncilState, reasonCode: string, actorType: string, actorId: string) {
    await this.db.run(
      "INSERT INTO council_transitions (transition_id, task_id, from_status, to_status, reason_code, actor_type, actor_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
      [randomUUID(), taskId, from, to, reasonCode, actorType, actorId, this.now()],
    );
  }
}
