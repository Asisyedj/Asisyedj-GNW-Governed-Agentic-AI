import { useCallback, useEffect, useState } from "react";
import { api, type AuditRow } from "../api";
import { StatusBadge, formatTime } from "./ui";

export default function AuditView() {
  const [events, setEvents] = useState<AuditRow[]>([]);
  const [verification, setVerification] = useState<{ valid: boolean; events: number; brokenAt?: number } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [audit, verify] = await Promise.all([api.audit(), api.verifyAudit()]);
      setEvents(audit.events);
      setVerification(verify);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <section className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <span className="eyebrow">Evidence</span>
            <h2 style={{ margin: "4px 0 0", fontSize: 19 }}>Tamper-evident audit trail</h2>
            <p className="muted small" style={{ margin: "4px 0 0" }}>
              Every admission, denial, approval, submission, result and safety stop is hash-chained to the event before it. Editing or deleting a row breaks verification.
            </p>
          </div>
          <div className="row">
            {verification && (
              <span className={`badge ${verification.valid ? "ok" : "danger"}`}>
                {verification.valid ? `chain valid · ${verification.events} events` : `chain broken at #${verification.brokenAt}`}
              </span>
            )}
            <button className="ghost" onClick={load} disabled={busy}>{busy ? "Verifying…" : "Re-verify"}</button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Time</th><th>Task</th><th>Event</th><th>Decision</th><th>Reason</th><th>Previous</th><th>Hash</th></tr></thead>
            <tbody>
              {events.map(event => (
                <tr key={event.id}>
                  <td className="muted">{formatTime(event.occurred_at)}</td>
                  <td>{event.task_id ?? "—"}</td>
                  <td>{event.event_type}</td>
                  <td><StatusBadge status={event.decision} /></td>
                  <td className="muted">{event.reason}</td>
                  <td className="mono">{event.previous_hash.slice(0, 10)}…</td>
                  <td className="mono">{event.event_hash.slice(0, 10)}…</td>
                </tr>
              ))}
              {!events.length && <tr><td colSpan={7} className="muted">No audit event recorded yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
