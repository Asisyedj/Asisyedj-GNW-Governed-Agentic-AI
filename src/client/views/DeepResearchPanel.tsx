import { useEffect, useMemo, useState } from "react";
import { ApiError, api, type DeepResearchPlan, type DeepResearchRunRow } from "../api";
import { StatusBadge, formatTime } from "./ui";

type Props = { taskId: number; taskPrompt: string; existingRuns: DeepResearchRunRow[]; onRefreshTask: () => Promise<void> };

export default function DeepResearchPanel({ taskId, taskPrompt, existingRuns, onRefreshTask }: Props) {
  const [runId, setRunId] = useState<number | null>(existingRuns.at(-1)?.id ?? null);
  const [plan, setPlan] = useState<DeepResearchPlan | null>(null);
  const [run, setRun] = useState<DeepResearchRunRow | null>(existingRuns.at(-1) ?? null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [domains, setDomains] = useState("");
  const [maxToolCalls, setMaxToolCalls] = useState(20);
  const [useCode, setUseCode] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const latest = existingRuns.at(-1);
    if (latest && !run) {
      setRun(latest);
      setRunId(latest.id);
    }
  }, [existingRuns, run]);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    const load = async () => {
      try {
        const result = await api.deepResearchStatus(taskId, runId);
        if (!active) return;
        setRun(result.run);
        const clarification = result.run.clarifications as { plan?: DeepResearchPlan; answers?: Record<string, string> } | undefined;
        if (clarification?.plan) setPlan(clarification.plan);
        if (clarification?.answers) setAnswers(clarification.answers);
      } catch (caught) {
        if (active && !(caught instanceof ApiError && caught.code === "deep_research_response_not_available")) {
          setError(caught instanceof ApiError ? `Status refused (${caught.code}).` : "Status request failed.");
        }
      }
    };
    void load();
    if (run?.status === "in_progress" || run?.status === "queued") {
      const timer = window.setInterval(load, 5000);
      return () => { active = false; window.clearInterval(timer); };
    }
    return () => { active = false; };
  }, [taskId, runId, run?.status]);

  const effectivePlan = useMemo(() => plan ?? (() => {
    if (!run) return null;
    try { return (JSON.parse(run.clarifications_json) as { plan?: DeepResearchPlan }).plan ?? null; } catch { return null; }
  })(), [plan, run]);

  const makePlan = async () => {
    setBusy(true); setError(null);
    try {
      const result = await api.deepResearchPlan(taskId);
      setRunId(result.runId);
      setPlan(result.plan);
      setRun(null);
      const defaults: Record<string, string> = {};
      result.plan.clarificationQuestions.forEach(q => { defaults[q.id] = ""; });
      setAnswers(defaults);
      await onRefreshTask();
    } catch (caught) {
      setError(caught instanceof ApiError ? `Plan refused (${caught.code}).` : "Plan request failed.");
    } finally { setBusy(false); }
  };

  const start = async () => {
    if (!runId) return;
    setBusy(true); setError(null);
    try {
      await api.deepResearchStart(taskId, {
        runId,
        allowedDomains: domains.split(",").map(v => v.trim().toLowerCase()).filter(Boolean),
        useCodeInterpreter: useCode,
        maxToolCalls,
        clarificationAnswers: answers,
      });
      const result = await api.deepResearchStatus(taskId, runId);
      setRun(result.run);
      await onRefreshTask();
    } catch (caught) {
      setError(caught instanceof ApiError ? `Start refused (${caught.code}).` : "Research start failed.");
    } finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!runId) return;
    setBusy(true); setError(null);
    try {
      await api.deepResearchCancel(taskId, runId);
      const result = await api.deepResearchStatus(taskId, runId);
      setRun(result.run);
      await onRefreshTask();
    } catch (caught) {
      setError(caught instanceof ApiError ? `Cancel refused (${caught.code}).` : "Cancel failed.");
    } finally { setBusy(false); }
  };

  return (
    <section className="panel">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <span className="eyebrow">Governed research</span>
          <h3 style={{ margin: "4px 0 2px", fontSize: 17 }}>Deep Research Engine</h3>
          <p className="muted small" style={{ margin: 0 }}>Mandatory sequence: plan → clarification → rewrite → admission → background research → status → cited report.</p>
        </div>
        <StatusBadge status={run?.status ?? "NOT_STARTED"} />
      </div>

      <div className="row" style={{ marginTop: 12, gap: 8, flexWrap: "wrap" }}>
        <button className="primary" type="button" disabled={busy} onClick={makePlan}>1. Create / refresh plan</button>
        {runId && <button className="ghost" type="button" disabled={busy || run?.status === "in_progress" || run?.status === "completed"} onClick={start}>4. Admit + start</button>}
        {runId && (run?.status === "in_progress" || run?.status === "queued") && <button className="ghost" type="button" disabled={busy} onClick={cancel}>Cancel</button>}
      </div>

      {effectivePlan && (
        <div className="stack" style={{ marginTop: 14 }}>
          <div className="item" style={{ cursor: "default" }}>
            <b>Plan {effectivePlan.planVersion}</b>
            <div className="muted small" style={{ marginTop: 4 }}>{effectivePlan.language} · {effectivePlan.researchPhases.length} mandatory phases</div>
          </div>
          <div className="field">
            <label>Clarification answers</label>
            {effectivePlan.clarificationQuestions.map(question => (
              <div key={question.id} style={{ marginTop: 8 }}>
                <div className="small"><b>{question.question}</b></div>
                <div className="muted small">{question.reason}</div>
                <input value={answers[question.id] ?? ""} placeholder="Leave blank to keep this dimension open-ended" onChange={event => setAnswers(current => ({ ...current, [question.id]: event.target.value }))} />
              </div>
            ))}
            {!effectivePlan.clarificationQuestions.length && <span className="muted small">No clarification questions were generated; the research keeps the prompt's scope unchanged.</span>}
          </div>
          <div className="row" style={{ gap: 12, alignItems: "flex-end" }}>
            <div className="field" style={{ flex: "1 1 300px", marginBottom: 0 }}>
              <label>Allowed web domains (optional)</label>
              <input value={domains} placeholder="nist.gov, owasp.org" onChange={event => setDomains(event.target.value)} />
            </div>
            <div className="field" style={{ width: 150, marginBottom: 0 }}>
              <label>Max tool calls</label>
              <input type="number" min={1} max={100} value={maxToolCalls} onChange={event => setMaxToolCalls(Number(event.target.value))} />
            </div>
            <label className="small" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={useCode} onChange={event => setUseCode(event.target.checked)} /> Python analysis
            </label>
          </div>
        </div>
      )}

      {run && (
        <>
          <hr className="hr" />
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="section-title">Run #{run.id}</div>
            <span className="muted small">updated {formatTime(run.updated_at)}</span>
          </div>
          <div className="table-wrap" style={{ marginTop: 10 }}>
            <table>
              <tbody>
                <tr><th>Status</th><td><StatusBadge status={run.status} /></td></tr>
                <tr><th>Request ID</th><td className="mono">{run.request_id}</td></tr>
                <tr><th>Response ID</th><td className="mono">{run.response_id ?? "—"}</td></tr>
                <tr><th>Provider error</th><td>{run.error_code ?? "—"}</td></tr>
              </tbody>
            </table>
          </div>
          {run.result_text && (
            <div className="item" style={{ cursor: "default", marginTop: 12 }}>
              <b>Cited report</b>
              <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", margin: "8px 0 0" }}>{run.result_text}</pre>
            </div>
          )}
        </>
      )}

      {!effectivePlan && <p className="muted small" style={{ marginTop: 12 }}>No Deep Research plan exists for this task yet. The engine will not start without the plan gate.</p>}
      {error && <div className="notice error small" style={{ marginTop: 12 }}>{error}</div>}
      <div className="muted small" style={{ marginTop: 10 }}>Task prompt: {taskPrompt}</div>
    </section>
  );
}
