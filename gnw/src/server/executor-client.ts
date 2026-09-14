import type { Env } from "./env.js";
import { assertEgressUrl, governedFetch } from "./security.js";
import type { CapabilityLease } from "./capability.js";

export type RemoteExecutionResult = { stdout: string; stderr: string; exitCode: number | null; timedOut: boolean; durationMs: number };
export type ExecutorAuthorization = { lease: CapabilityLease; actionDigest: string; capability: string; actorUserId: number; tenant: string };

export async function executeInRemoteExecutor(env: Env, request: { taskId: number; command: string; args?: string[]; timeoutMs?: number; maxOutputBytes?: number; files?: Array<{ path: string; content: string }>; authorization: ExecutorAuthorization }): Promise<RemoteExecutionResult> {
  if (!env.executorUrl || !env.executorSharedToken) throw new Error("executor_not_configured");
  const auth = request.authorization;
  if (auth.lease.taskId !== request.taskId || auth.lease.actionDigest !== auth.actionDigest || auth.lease.capability !== auth.capability || auth.lease.actorUserId !== auth.actorUserId || auth.lease.subject !== String(auth.actorUserId) || auth.lease.tenant !== auth.tenant) throw new Error("executor_authorization_binding");
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
