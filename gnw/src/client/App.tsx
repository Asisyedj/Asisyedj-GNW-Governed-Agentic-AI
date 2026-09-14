import { useCallback, useEffect, useState } from "react";
import { API_BASE, ApiError, api, type Summary } from "./api";
import Workspace from "./views/Workspace";
import ApprovalsView from "./views/Approvals";
import AuditView from "./views/Audit";
import ControlsView from "./views/Controls";

type View = "workspace" | "approvals" | "audit" | "controls";

export default function App() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [view, setView] = useState<View>("workspace");
  const [bootstrap, setBootstrap] = useState(false);
  const [allowRegistration, setAllowRegistration] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const next = await api.summary();
      setSummary(next);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setSummary(null);
      } else {
        console.error("Workspace summary error:", error);
        setSummary(null);
      }
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        setBootstrap(me.bootstrap);
        setAllowRegistration(me.allowSelfRegistration);
        if (me.user) {
          await refresh();
        }
      } catch (err) {
        console.error("Failed to load session:", err);
      } finally {
        setLoading(false);
      }
    })();
  }, [refresh]);

  if (loading) {
    return (
      <div className="auth-screen">
        <div className="row">
          <span className="spinner" aria-hidden /> <span className="muted">Loading control plane…</span>
        </div>
      </div>
    );
  }

  if (!summary) {
    return <AuthScreen bootstrap={bootstrap} allowRegistration={allowRegistration} onAuthenticated={refresh} />;
  }

  const pendingApprovals = summary.approvals.filter(approval => approval.status === "pending").length;
  const interlockEngaged = summary.interlock.killSwitch || summary.interlock.circuitOpen;

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">GNW / Control plane</span>
          <h1>Governed Agent Workspace</h1>
        </div>
        <div className="row">
          <span className={`badge ${interlockEngaged ? "danger" : summary.readiness.ready ? "ok" : "warn"}`}>
            {interlockEngaged ? "Interlock engaged" : summary.readiness.ready ? "System ready" : "Degraded mode"}
          </span>
          <span className="badge info">{summary.user.email}</span>
          <button
            className="ghost"
            onClick={async () => {
              await api.logout();
              window.location.reload();
            }}
          >
            Sign out
          </button>
        </div>
      </header>

      {interlockEngaged && (
        <div className="notice error" style={{ marginTop: 16 }}>
          Fail-closed: the kill switch or circuit breaker is engaged. No new task or provider action will be admitted until an admin clears it in Safety controls.
        </div>
      )}

      <div className="layout">
        <aside className="panel">
          <div className="section-title">Mission control</div>
          <nav className="nav" style={{ marginTop: 10 }}>
            <button className={view === "workspace" ? "active" : ""} onClick={() => setView("workspace")}>◈ Workspace</button>
            <button className={view === "approvals" ? "active" : ""} onClick={() => setView("approvals")}>
              ✓ Approvals {pendingApprovals > 0 && <span className="badge warn" style={{ marginLeft: 6 }}>{pendingApprovals}</span>}
            </button>
            <button className={view === "audit" ? "active" : ""} onClick={() => setView("audit")}>◌ Audit trail</button>
            <button className={view === "controls" ? "active" : ""} onClick={() => setView("controls")}>⚙ Safety controls</button>
          </nav>
          <hr className="hr" />
          <div className="section-title">Readiness</div>
          <div className="list small" style={{ marginTop: 10 }}>
            {Object.entries(summary.readiness.checks).map(([key, value]) => (
              <div key={key} className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted">{key.replace(/_/g, " ")}</span>
                <span className={`badge ${value === "ok" ? "ok" : value === "degraded" ? "warn" : "danger"}`}>{value}</span>
              </div>
            ))}
          </div>
        </aside>

        <main className="stack">
          {view === "workspace" && <Workspace summary={summary} onRefresh={refresh} />}
          {view === "approvals" && <ApprovalsView summary={summary} onRefresh={refresh} />}
          {view === "audit" && <AuditView />}
          {view === "controls" && <ControlsView summary={summary} onRefresh={refresh} />}
        </main>
      </div>

      <p className="muted small" style={{ marginTop: 24 }}>
        GNW governed agent · specialist output is a proposal until governance admits it · external side effects require a human approval ·{" "}
        <a href={`${API_BASE}/api/health`}>health</a> · <a href={`${API_BASE}/api/ready`}>readiness</a>
      </p>
    </div>
  );
}

function AuthScreen({ bootstrap, allowRegistration, onAuthenticated }: { bootstrap: boolean; allowRegistration: boolean; onAuthenticated: () => Promise<void> }) {
  const [mode, setMode] = useState<"login" | "register">(bootstrap ? "register" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") await api.register(email, password);
      else await api.login(email, password);
      await onAuthenticated();
    } catch (caught) {
      setError(caught instanceof ApiError ? describe(caught.code) : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <form className="panel auth-card" onSubmit={submit}>
        <span className="eyebrow">GNW / Control plane</span>
        <h1 style={{ margin: "6px 0 4px", fontSize: 22 }}>{mode === "register" ? "Create the owner account" : "Sign in"}</h1>
        <p className="muted small" style={{ marginTop: 0 }}>
          {bootstrap
            ? "No account exists yet. The first account becomes the workspace administrator and reviewer."
            : "This control plane is private. Every action you take is written to the tamper-evident audit trail."}
        </p>

        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} required minLength={mode === "register" ? 12 : 8} value={password} onChange={event => setPassword(event.target.value)} />
          {mode === "register" && <span className="muted small">Minimum 12 characters.</span>}
        </div>
        {error && <div className="notice error" style={{ marginBottom: 12 }}>{error}</div>}
        <button className="primary" type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Working…" : mode === "register" ? "Create account" : "Sign in"}
        </button>
        {(bootstrap || allowRegistration) && (
          <button type="button" className="ghost" style={{ width: "100%", marginTop: 8 }} onClick={() => setMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "Create an account" : "I already have an account"}
          </button>
        )}
      </form>
    </div>
  );
}

function describe(code: string) {
  const map: Record<string, string> = {
    invalid_credentials: "That email and password combination was not accepted.",
    too_many_attempts: "Too many failed attempts. Wait a few minutes and try again.",
    registration_closed: "Self-registration is disabled. Ask an administrator to create your account.",
    email_taken: "An account already exists for that email.",
    weak_password: "Choose a password of at least 12 characters.",
    invalid_email: "Enter a valid email address.",
    invalid_input: "Check the form and try again.",
  };
  return map[code] ?? `Request failed (${code}).`;
}
