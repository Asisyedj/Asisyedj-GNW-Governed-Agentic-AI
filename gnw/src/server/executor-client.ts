import type { Env } from "./env.js";
import { assertEgressUrl, governedFetch } from "./security.js";

export type RemoteExecutionResult = { stdout: string; stderr: string; exitCode: number | null; timedOut: boolean; durationMs: number };

export async function executeInRemoteExecutor(env: Env, request: { taskId: number; command: string; args?: string[]; timeoutMs?: number; maxOutputBytes?: number; files?: Array<{ path: string; content: string }> }): Promise<RemoteExecutionResult> {
  if (!env.executorUrl || !env.executorSharedToken) throw new Error("executor_not_configured");
  const endpoint = `${env.executorUrl}/v1/execute`;
  assertEgressUrl(endpoint, env.allowedEgressHosts);
  const response = await governedFetch(endpoint, {
    method: "POST",
    redirect: "manual",
    headers: { "content-type": "application/json", authorization: `Bearer ${env.executorSharedToken}` },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout((request.timeoutMs ?? 45_000) + 10_000),
    __allowedHosts: env.allowedEgressHosts,
  } as RequestInit & { __allowedHosts: readonly string[] }, env.maxProviderResponseBytes);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body?.error === "string" ? body.error : `executor_http_${response.status}`);
  return body as RemoteExecutionResult;
}
