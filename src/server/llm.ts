import { ENV, type Env } from "./env.js";
import type { Db } from "./db/index.js";
import type { CapabilityLease } from "./capability.js";
import { executeFencedExternal } from "./execution.js";
import { governedFetch, sha256 } from "./security.js";

export type ChatMessage = { role: "system" | "user" | "assistant"; content: string };
export type LlmResult = { text: string; mode: "live" | "offline"; model: string; usage?: { promptTokens?: number; completionTokens?: number } };

/**
 * OpenAI-compatible chat completion. When no key is configured the app runs in
 * governed offline mode: deterministic, clearly-labelled planning output and no
 * external call. The UI and audit trail both surface which mode produced a result.
 */
export async function invokeLLM(input: { messages: ChatMessage[]; maxTokens?: number; temperature?: number; env?: Env; db?: Db; taskId?: number; actorUserId?: number; actionDigest?: string; capabilityLease?: CapabilityLease }): Promise<LlmResult> {
  const env = input.env ?? ENV;
  if (!env.llmApiKey) {
    return { text: offlineResponse(input.messages), mode: "offline", model: "governed-offline" };
  }

  if (!input.db || input.taskId === undefined || input.actorUserId === undefined || !input.actionDigest || !input.capabilityLease) throw new Error("llm_capability_lease_required");
  const tenant = input.capabilityLease.tenant;
  const requestDigest = sha256(JSON.stringify({ model: env.llmModel, messages: input.messages, maxTokens: input.maxTokens ?? 1200, temperature: input.temperature ?? 0.2 }));
  const effectKey = `llm:${tenant}:${input.taskId}:${requestDigest}`;
  const idempotencyKey = sha256(`GNW-LLM-IDEMPOTENCY-V1|${tenant}|${input.taskId}|${input.actionDigest}|${requestDigest}`);
  const fenced = await executeFencedExternal({
    db: input.db,
    env,
    taskId: input.taskId,
    actorUserId: input.actorUserId,
    tenant,
    eventType: "llm_provider",
    actionDigest: input.actionDigest,
    capabilityLease: input.capabilityLease,
    capability: "llm.chat",
    provider: env.llmModel,
    effectKey,
    idempotencyKey,
    effect: async (fenceToken, providerIdempotencyKey, generation) => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), env.llmTimeoutMs);
      try {
        const response = await governedFetch(`${env.llmBaseUrl}/chat/completions`, {
          method: "POST",
          headers: { "content-type": "application/json", authorization: `Bearer ${env.llmApiKey}`, "idempotency-key": providerIdempotencyKey, "x-gnw-fence-generation": String(generation), "x-gnw-fence-token": fenceToken },
          body: JSON.stringify({
            model: env.llmModel,
            messages: input.messages,
            max_tokens: input.maxTokens ?? 1200,
            temperature: input.temperature ?? 0.2,
          }),
          signal: controller.signal,
          redirect: "manual",
          __allowedHosts: env.allowedEgressHosts,
        } as RequestInit & { __allowedHosts: readonly string[] }, env.maxProviderResponseBytes);
        if (!response.ok) {
          const detail = (await response.text()).slice(0, 400);
          throw new Error(`llm_http_${response.status}: ${detail}`);
        }
        const raw = await response.text();
        if (Buffer.byteLength(raw, "utf8") > env.maxProviderResponseBytes) throw new Error("llm_response_too_large");
        const payload = JSON.parse(raw) as {
          choices?: Array<{ message?: { content?: string | Array<{ text?: string }> } }>;
          usage?: { prompt_tokens?: number; completion_tokens?: number };
        };
        const content = payload.choices?.[0]?.message?.content;
        const text = typeof content === "string" ? content : Array.isArray(content) ? content.map(part => part?.text ?? "").join("\n") : "";
        if (!text.trim()) throw new Error("llm_empty_response");
        if (env.llmProviderIdempotencyRequired && response.headers.get("x-gnw-idempotency-key") !== providerIdempotencyKey) throw new Error("llm_idempotency_contract_not_confirmed");
        if (env.llmProviderIdempotencyRequired && response.headers.get("x-gnw-fence-token") !== fenceToken) throw new Error("llm_fence_contract_not_confirmed");
        const result = { text, mode: "live" as const, model: env.llmModel, usage: { promptTokens: payload.usage?.prompt_tokens, completionTokens: payload.usage?.completion_tokens } };
        return { result, responseDigest: sha256(raw) };
      } finally {
        clearTimeout(timer);
      }
    },
  });
  if (fenced.status !== "COMPLETED" || !fenced.result) throw new Error("llm_effect_pending_reconciliation");
  return fenced.result;
}

function offlineResponse(messages: ChatMessage[]) {
  const system = messages.find(message => message.role === "system")?.content ?? "";
  const user = messages.filter(message => message.role === "user").map(message => message.content).join("\n").trim();
  const role = /You are the ([A-Za-z ]+) specialist/.exec(system)?.[1] ?? "Specialist";
  return [
    `[GOVERNED OFFLINE MODE] No language-model credential is configured, so this is a deterministic plan, not model output.`,
    ``,
    `Role: ${role}`,
    `Request: ${user.slice(0, 500)}${user.length > 500 ? "…" : ""}`,
    ``,
    `Planned steps under the current grant:`,
    `1. Restate the request and the evidence that would be required to answer it.`,
    `2. Identify the assumptions and the uncertainty that a reviewer must accept.`,
    `3. Produce the deliverable within the bound tool scope only.`,
    `4. Route anything with an external side effect to the approval queue.`,
    ``,
    `No external tool was called and no side effect was performed. Set LLM_API_KEY to enable live specialist output.`,
  ].join("\n");
}
