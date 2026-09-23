import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type Summary, type TaskDetail } from "../api";
import { AGENT_LABELS, CLASSIFICATIONS, SPECIALIST_AGENTS, type Classification, type SpecialistAgent } from "@shared/types";
import { StatusBadge, formatTime } from "./ui";
import DeepResearchPanel from "./DeepResearchPanel";

export default function Workspace({ summary, onRefresh }: { summary: Summary; onRefresh: () => Promise<void> }) {
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(summary.tasks[0]?.id ?? null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [prompt, setPrompt] = useState("");
  const [purpose, setPurpose] = useState("Governed workspace request");
  const [classification, setClassification] = useState<Classification>("internal");
  const [agents, setAgents] = useState<SpecialistAgent[]>(["research", "analysis", "qa"]);
  const [budgetTokens, setBudgetTokens] = useState(4000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async (taskId: number) => {
    setDetail(await api.task(taskId));
  }, []);

  useEffect(() => {
    if (selectedTaskId) loadDetail(selectedTaskId).catch(() => setDetail(null));
  }, [selectedTaskId, loadDetail]);

  const toggleAgent = (agent: SpecialistAgent) => {
    setAgents(current => (current.includes(agent) ? current.filter(item => item !== agent) : [...current, agent]));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!agents.length || prompt.trim().length < 8) {
      setError("Select at least one specialist and describe the task in at least 8 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.createTask({ prompt: prompt.trim(), purpose: purpose.trim() || "Governed workspace request", classification, selectedAgents: agents, budgetTokens, budgetBytes: 4096 });
      setPrompt("");
      setSelectedTaskId(result.taskId);
      await Promise.all([onRefresh(), loadDetail(result.taskId)]);
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "safety_interlock") setError("Fail-closed: the safety interlock is engaged, so no task can be admitted.");
      else setError(caught instanceof ApiError ? `Request refused (${caught.code}).` : "Request failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <section className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <span className="eyebrow">Safe by default</span>
            <h2 style={{ margin: "4px 0 0", fontSize: 19 }}>What should the governed team do?</h2>
            <p className="muted small" style={{ margin: "4px 0 0" }}>
              Every request is scoped, classified, time-bound, and audited. Anything with an external side effect is queued for a human.
            </p>
          </div>
          <div className="metrics">
            <div><strong>{summary.tasks.length}</strong><span>tasks</span></div>
            <div><strong>{summary.approvals.filter(item => item.status === "pending").length}</strong><span>pending</span></div>
            <div><strong>5</strong><span>specialists</span></div>
          </div>
        </div>
      </section>

      <form className="panel" onSubmit={submit}>
        <div className="section-title">New governed task</div>
        <div className="field" style={{ marginTop: 12 }}>
          <label htmlFor="prompt">Task</label>
          <textarea id="prompt" value={prompt} placeholder="Describe the outcome you need. Example: draft a launch video brief for our Q4 release." onChange={event => setPrompt(event.target.value)} />
        </div>
        <div className="row" style={{ gap: 10, marginBottom: 12 }}>
          {SPECIALIST_AGENTS.map(agent => (
            <button type="button" key={agent} className={`agent-toggle ${agents.includes(agent) ? "on" : ""}`} aria-pressed={agents.includes(agent)} onClick={() => toggleAgent(agent)}>
              <b>{AGENT_LABELS[agent].label}</b>
              <small>{AGENT_LABELS[agent].detail}</small>
            </button>
          ))}
        </div>
        <div className="row" style={{ alignItems: "flex-end", gap: 14 }}>
          <div className="field" style={{ flex: "1 1 220px", marginBottom: 0 }}>
            <label htmlFor="purpose">Purpose binding</label>
            <input id="purpose" value={purpose} onChange={event => setPurpose(event.target.value)} maxLength={120} />
          </div>
          <div className="field" style={{ flex: "0 1 180px", marginBottom: 0 }}>
            <label htmlFor="classification">Classification</label>
            <select id="classification" value={classification} onChange={event => setClassification(event.target.value as Classification)}>
              {CLASSIFICATIONS.map(value => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "0 1 160px", marginBottom: 0 }}>
            <label htmlFor="budget">Token budget</label>
            <input id="budget" type="number" min={500} max={100000} step={500} value={budgetTokens} onChange={event => setBudgetTokens(Number(event.target.value))} />
          </div>
          <button className="primary" type="submit" disabled={busy}>{busy ? "Running plan…" : "Run plan"}</button>
        </div>
        {classification === "restricted" && (
          <p className="notice warn small" style={{ marginTop: 12 }}>Restricted classification: results are held in the approval queue before anything leaves the workspace.</p>
        )}
        {agents.includes("video_producer") && (
          <p className="notice warn small" style={{ marginTop: 12 }}>Video Producer selected: brief, script and storyboard are produced separately, and provider submission requires a reviewer decision.</p>
        )}
        {error && <p className="notice error small" style={{ marginTop: 12 }}>{error}</p>}
      </form>

      <div className="grid-2">
        <section className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="section-title">Live task</div>
            <span className="badge info">Fail-closed</span>
          </div>
          {!detail && <p className="muted small">Select or create a task to see the governed conversation.</p>}
          {detail && (
            <>
              <h3 style={{ margin: "10px 0 2px", fontSize: 16, overflowWrap: "anywhere" }}>{detail.task.title}</h3>
              <div className="row small" style={{ gap: 8, marginBottom: 12 }}>
                <StatusBadge status={detail.task.status} />
                <span className="badge">{detail.task.classification}</span>
                <span className="muted">purpose: {detail.task.purpose}</span>
              </div>
              <div className="messages">
                {detail.messages.map(message => (
                  <div key={message.id} className={`message ${message.role}`}>
                    <b>{message.agent_name ? message.agent_name.replace(/_/g, " ") : message.role}</b>
                    <p>{message.content}</p>
                  </div>
                ))}
              </div>

              <hr className="hr" />
              <div className="section-title">Agent execution</div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Agent</th><th>Status</th><th>Decision</th><th>Reason</th><th>Action digest</th></tr>
                  </thead>
                  <tbody>
                    {detail.runs.map(run => (
                      <tr key={run.id}>
                        <td>{run.agent_name.replace(/_/g, " ")}</td>
                        <td><StatusBadge status={run.status} /></td>
                        <td>{run.decision ?? "—"}</td>
                        <td className="muted">{run.reason ?? "—"}</td>
                        <td className="mono">{run.action_digest.slice(0, 12)}…</td>
                      </tr>
                    ))}
                    {!detail.runs.length && <tr><td colSpan={5} className="muted">No agent run recorded.</td></tr>}
                  </tbody>
                </table>
              </div>

              {detail.videoJobs.length > 0 && (
                <>
                  <hr className="hr" />
                  <div className="section-title">Video workflow</div>
                  {detail.videoJobs.map(job => (
                    <div key={job.id} className="item" style={{ cursor: "default", marginTop: 10 }}>
                      <div className="row" style={{ justifyContent: "space-between" }}>
                        <b>Job #{job.id}</b>
                        <StatusBadge status={job.status} />
                      </div>
                      <p className="muted small" style={{ margin: "6px 0 0" }}>
                        provider: {job.provider ?? "—"} · provider job: {job.provider_job_id ?? "not submitted"}
                        {job.error_message ? ` · ${job.error_message}` : ""}
                      </p>
                    </div>
                  ))}
                </>
              )}

              {detail.artifacts.length > 0 && (
                <>
                  <hr className="hr" />
                  <div className="section-title">Artifact references</div>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Kind</th><th>Storage key</th><th>SHA-256</th><th>Bytes</th></tr></thead>
                      <tbody>
                        {detail.artifacts.map(artifact => (
                          <tr key={artifact.id}>
                            <td>{artifact.kind}</td>
                            <td className="mono" style={{ overflowWrap: "anywhere" }}>{artifact.storage_key}</td>
                            <td className="mono">{artifact.sha256.slice(0, 12)}…</td>
                            <td>{artifact.byte_size}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              <hr className="hr" />
              <DeepResearchPanel taskId={detail.task.id} taskPrompt={detail.task.prompt} existingRuns={detail.deepResearchRuns} onRefreshTask={() => loadDetail(detail.task.id)} />

              <hr className="hr" />
              <div className="section-title">Task audit</div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Time</th><th>Event</th><th>Decision</th><th>Reason</th><th>Hash</th></tr></thead>
                  <tbody>
                    {detail.audit.map(event => (
                      <tr key={event.id}>
                        <td className="muted">{formatTime(event.occurred_at)}</td>
                        <td>{event.event_type}</td>
                        <td><StatusBadge status={event.decision} /></td>
                        <td className="muted">{event.reason}</td>
                        <td className="mono">{event.event_hash.slice(0, 10)}…</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        <section className="panel">
          <div className="section-title">Task history</div>
          <div className="list" style={{ marginTop: 12 }}>
            {summary.tasks.map(task => (
              <button key={task.id} className={`item ${task.id === selectedTaskId ? "active" : ""}`} onClick={() => setSelectedTaskId(task.id)}>
                <h4>{task.title}</h4>
                <div className="row small" style={{ gap: 8 }}>
                  <StatusBadge status={task.status} />
                  <span className="muted">{task.classification}</span>
                  <span className="muted">{formatTime(task.updated_at)}</span>
                </div>
              </button>
            ))}
            {!summary.tasks.length && <p className="muted small">No task has been submitted in this workspace yet.</p>}
          </div>
        </section>
      </div>
    </>
  );
}
