import type { Classification, SpecialistAgent } from "@shared/types";

// Empty for the normal single-origin deployment. Set VITE_API_BASE at build
// time when the client is hosted separately from the API.
export const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export type SessionUser = { id: number; email: string; name: string | null; role: "user" | "admin"; workspaceId: number; tenantKey: string };

export type TaskRow = {
  id: number; title: string; prompt: string; purpose: string; classification: Classification; status: string;
  selected_agents: string; budget_tokens: number; budget_bytes: number; created_at: number; updated_at: number;
};
export type MessageRow = { id: number; task_id: number; role: string; agent_name: string | null; content: string; created_at: number };
export type AgentRunRow = { id: number; agent_name: SpecialistAgent; status: string; decision: string | null; reason: string | null; action_digest: string; started_at: number | null; completed_at: number | null };
export type ApprovalRow = {
  id: number; task_id: number; video_job_id: number | null; action_digest: string; operation: string; status: string;
  reason: string; expires_at: number; created_at: number; reviewed_by: number | null; requested_by: number; title?: string;
};
export type VideoJobRow = { id: number; task_id: number; status: string; brief: string | null; script: string | null; storyboard: string | null; provider: string | null; provider_job_id: string | null; error_message: string | null };
export type ArtifactRow = { id: number; kind: string; storage_key: string; storage_url: string | null; sha256: string; byte_size: number; created_at: number };
export type AuditRow = { id: number; task_id: number | null; event_type: string; decision: string; reason: string; event_hash: string; previous_hash: string; occurred_at: number };
export type Interlock = { killSwitch: boolean; circuitOpen: boolean };
export type Readiness = { ready: boolean; checks: Record<string, string>; notes: Record<string, string> };

export type Summary = {
  user: SessionUser;
  agents: SpecialistAgent[];
  tasks: TaskRow[];
  approvals: ApprovalRow[];
  interlock: Interlock;
  notifications: Array<{ id: number; title: string; body: string; created_at: number }>;
  readiness: Readiness;
};

export type TaskDetail = {
  task: TaskRow;
  messages: MessageRow[];
  runs: AgentRunRow[];
  approvals: ApprovalRow[];
  videoJobs: VideoJobRow[];
  artifacts: ArtifactRow[];
  audit: AuditRow[];
};

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, public readonly detail?: unknown) {
    super(code);
  }
}

// Cookies remain the primary session channel. The token is only ever present
// when the server was started with SESSION_TOKEN_IN_BODY=true, which exists for
// proxied hosting where the cookie cannot survive the hop.
const TOKEN_KEY = "gnw.session";
const readToken = () => {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};
const writeToken = (token: string | null) => {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: cookies still carry the session */
  }
};

async function request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = readToken();
  const headers: Record<string, string> = { "content-type": "application/json", "x-gnw-client": "web" };
  if (token) headers.authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}/api${path}`, {
    method: options.method ?? "GET",
    headers,
    credentials: "include",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) throw new ApiError(response.status, payload.error ?? "request_failed", payload.detail ?? payload);
  if (typeof payload.token === "string") writeToken(payload.token);
  if (path === "/auth/logout") writeToken(null);
  return payload as T;
}

export const api = {
  me: () => request<{ user: SessionUser | null; bootstrap: boolean; allowSelfRegistration: boolean }>("/auth/me"),
  login: (email: string, password: string) => request<{ user: SessionUser }>("/auth/login", { method: "POST", body: { email, password } }),
  register: (email: string, password: string, name?: string) => request<{ user: SessionUser }>("/auth/register", { method: "POST", body: { email, password, name } }),
  logout: () => request<{ success: boolean }>("/auth/logout", { method: "POST" }),
  summary: () => request<Summary>("/workspace/summary"),
  task: (taskId: number) => request<TaskDetail>(`/tasks/${taskId}`),
  createTask: (body: { prompt: string; purpose: string; classification: Classification; selectedAgents: SpecialistAgent[]; budgetTokens: number; budgetBytes: number }) =>
    request<{ taskId: number; status: string; approvalId?: number; videoJobId?: number }>("/tasks", { method: "POST", body }),
  reviewApproval: (approvalId: number, status: "approved" | "denied") => request<{ success: boolean }>(`/approvals/${approvalId}/review`, { method: "POST", body: { status } }),
  submitVideo: (approvalId: number) => request<{ ok: boolean; jobId: number; providerJobId: string; status: string }>("/video/submit", { method: "POST", body: { approvalId } }),
  audit: (taskId?: number) => request<{ events: AuditRow[] }>(taskId ? `/audit?taskId=${taskId}` : "/audit"),
  verifyAudit: () => request<{ valid: boolean; events: number; brokenAt?: number }>("/audit/verify"),
  setInterlock: (values: Partial<Interlock>) => request<Interlock>("/controls/interlock", { method: "POST", body: values }),
  ready: () => request<Readiness>("/ready"),
};
