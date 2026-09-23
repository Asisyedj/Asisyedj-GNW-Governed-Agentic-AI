import { useState } from "react";
import { ApiError, api, type Summary } from "../api";
import { formatTime } from "./ui";

export default function ControlsView({ summary, onRefresh }: { summary: Summary; onRefresh: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = summary.user.role === "admin";

  const set = async (values: { killSwitch?: boolean; circuitOpen?: boolean }) => {
    setBusy(true);
    setError(null);
    try {
      await api.setInterlock(values);
      await onRefresh();
    } catch (caught) {
      setError(caught instanceof ApiError && caught.code === "admin_required" ? "Only a workspace administrator can change the safety interlocks." : "The control change was refused.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <section className="panel">
        <span className="eyebrow">Fail-closed controls</span>
        <h2 style={{ margin: "4px 0 0", fontSize: 19 }}>Safety interlocks</h2>
        <p className="muted small" style={{ margin: "4px 0 12px" }}>
          State is stored in the database, so a stop holds across restarts and across every instance. While either control is engaged the policy gateway returns STOP for every action, including approved provider submissions.
        </p>
        {!isAdmin && <p className="notice warn small">You are signed in as a member. Interlock changes require an administrator.</p>}
        {error && <p className="notice error small">{error}</p>}

        <div className="row" style={{ gap: 14, marginTop: 12 }}>
          <div className="item" style={{ cursor: "default", flex: "1 1 280px" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>Kill switch</b>
              <span className={`badge ${summary.interlock.killSwitch ? "danger" : "ok"}`}>{summary.interlock.killSwitch ? "engaged" : "clear"}</span>
            </div>
            <p className="muted small" style={{ margin: "6px 0 10px" }}>Halts all agent admission and every external action immediately.</p>
            <button className={summary.interlock.killSwitch ? "" : "danger"} disabled={!isAdmin || busy} onClick={() => set({ killSwitch: !summary.interlock.killSwitch })}>
              {summary.interlock.killSwitch ? "Clear kill switch" : "Engage kill switch"}
            </button>
          </div>

          <div className="item" style={{ cursor: "default", flex: "1 1 280px" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>Circuit breaker</b>
              <span className={`badge ${summary.interlock.circuitOpen ? "danger" : "ok"}`}>{summary.interlock.circuitOpen ? "open" : "closed"}</span>
            </div>
            <p className="muted small" style={{ margin: "6px 0 10px" }}>Opens when downstream behaviour is untrusted; blocks admission without discarding queued work.</p>
            <button className={summary.interlock.circuitOpen ? "" : "danger"} disabled={!isAdmin || busy} onClick={() => set({ circuitOpen: !summary.interlock.circuitOpen })}>
              {summary.interlock.circuitOpen ? "Close circuit" : "Open circuit"}
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-title">Deployment readiness</div>
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead><tr><th>Check</th><th>State</th><th>Note</th></tr></thead>
            <tbody>
              {Object.entries(summary.readiness.checks).map(([key, value]) => (
                <tr key={key}>
                  <td>{key.replace(/_/g, " ")}</td>
                  <td><span className={`badge ${value === "ok" ? "ok" : value === "degraded" ? "warn" : "danger"}`}>{value}</span></td>
                  <td className="muted">{summary.readiness.notes[key] ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="section-title">Owner notifications</div>
        <div className="list" style={{ marginTop: 12 }}>
          {summary.notifications.map(notification => (
            <div key={notification.id} className="item" style={{ cursor: "default" }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <b>{notification.title}</b>
                <span className="muted small">{formatTime(notification.created_at)}</span>
              </div>
              <p className="small muted" style={{ margin: "4px 0 0" }}>{notification.body}</p>
            </div>
          ))}
          {!summary.notifications.length && <p className="muted small">No notification has been raised yet.</p>}
        </div>
      </section>
    </>
  );
}
