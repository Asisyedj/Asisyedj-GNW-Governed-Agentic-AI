import { useState } from "react";
import { ApiError, api, type Summary } from "../api";
import { StatusBadge, formatTime } from "./ui";

export default function ApprovalsView({ summary, onRefresh }: { summary: Summary; onRefresh: () => Promise<void> }) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "error" | "warn"; text: string } | null>(null);

  const act = async (approvalId: number, action: "approved" | "denied" | "submit") => {
    setBusyId(approvalId);
    setMessage(null);
    try {
      if (action === "submit") {
        const result = await api.submitVideo(approvalId);
        setMessage({ tone: "ok", text: `Provider job ${result.providerJobId} submitted. Job status: ${result.status}.` });
      } else {
        await api.reviewApproval(approvalId, action);
        setMessage({ tone: action === "approved" ? "ok" : "warn", text: `Approval ${approvalId} ${action}. The decision is recorded in the audit chain.` });
      }
      await onRefresh();
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "request_failed";
      setMessage({ tone: "error", text: explain(code) });
    } finally {
      setBusyId(null);
    }
  };

  const pending = summary.approvals.filter(approval => approval.status === "pending");
  const settled = summary.approvals.filter(approval => approval.status !== "pending");

  return (
    <>
      <section className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <span className="eyebrow">Human in the loop</span>
            <h2 style={{ margin: "4px 0 0", fontSize: 19 }}>Approval queue</h2>
            <p className="muted small" style={{ margin: "4px 0 0" }}>
              Sensitive and restricted actions stay proposals until a reviewer decides. Approving does not execute: submission is a second, separately audited step that consumes the approval once.
            </p>
          </div>
          <span className={`badge ${pending.length ? "warn" : "ok"}`}>{pending.length} pending</span>
        </div>
        {message && <p className={`notice ${message.tone} small`} style={{ marginTop: 14 }}>{message.text}</p>}
      </section>

      <section className="panel">
        <div className="section-title">Pending</div>
        <div className="list" style={{ marginTop: 12 }}>
          {pending.map(approval => (
            <div key={approval.id} className="item" style={{ cursor: "default" }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h4>#{approval.id} · {approval.operation.replace(/_/g, " ")} · task {approval.task_id}</h4>
                <span className="badge warn">expires {formatTime(approval.expires_at)}</span>
              </div>
              <p className="small muted" style={{ margin: "2px 0 8px" }}>{approval.reason}</p>
              <p className="mono small" style={{ margin: "0 0 10px", overflowWrap: "anywhere" }}>digest {approval.action_digest}</p>
              <div className="row">
                <button className="primary" disabled={busyId === approval.id} onClick={() => act(approval.id, "approved")}>Approve</button>
                <button className="danger" disabled={busyId === approval.id} onClick={() => act(approval.id, "denied")}>Deny</button>
              </div>
            </div>
          ))}
          {!pending.length && <p className="muted small">Nothing is waiting for a reviewer.</p>}
        </div>
      </section>

      <section className="panel">
        <div className="section-title">Decided</div>
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead><tr><th>ID</th><th>Task</th><th>Operation</th><th>Status</th><th>Decided</th><th>Action</th></tr></thead>
            <tbody>
              {settled.map(approval => (
                <tr key={approval.id}>
                  <td>{approval.id}</td>
                  <td>{approval.title ?? approval.task_id}</td>
                  <td>{approval.operation.replace(/_/g, " ")}</td>
                  <td><StatusBadge status={approval.status} /></td>
                  <td className="muted">{formatTime(approval.created_at)}</td>
                  <td>
                    {approval.status === "approved" && approval.video_job_id ? (
                      <button disabled={busyId === approval.id} onClick={() => act(approval.id, "submit")}>Submit to provider</button>
                    ) : (
                      <span className="muted small">—</span>
                    )}
                  </td>
                </tr>
              ))}
              {!settled.length && <tr><td colSpan={6} className="muted">No decision has been recorded yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function explain(code: string) {
  const map: Record<string, string> = {
    separation_of_duties: "Separation of duties: the requester cannot approve their own action. Ask the workspace admin to review it.",
    approval_not_pending_or_expired: "That approval is no longer pending, or its window expired. Re-run the task to request a fresh approval.",
    approval_replay: "Refused: this approval was already consumed. Replay protection blocks a second submission.",
    approval_expired: "Refused: the approval window elapsed before submission.",
    approval_required: "Refused: no valid approval is bound to this action.",
    safety_interlock: "Fail-closed: the kill switch or circuit breaker is engaged.",
    tenant_binding: "Refused: that approval belongs to another tenant.",
  };
  return map[code] ?? `Request refused (${code}).`;
}
