import type { Db } from "./db/index.js";
import { ENV, type Env } from "./env.js";
import { recordNotification } from "./repo.js";
import type { CapabilityLease } from "./capability.js";
import { executeFencedExternal } from "./execution.js";
import { governedFetch, sha256 } from "./security.js";

export type Notification = { title: string; body: string; userId?: number | null; taskId?: number | null };

/**
 * Owner notifications for approval requests, safety interlocks and completed
 * jobs. Always persisted and logged; optionally forwarded to a webhook. A
 * webhook failure never breaks the governed request path.
 */
export async function notifyOwner(db: Db, notification: Notification, env: Env = ENV, capabilityLease?: CapabilityLease, actionDigest = "") {
  let delivered = false;
  if (env.notifyWebhookUrl && capabilityLease && actionDigest) {
    try {
      const tenant = capabilityLease.tenant;
      const notificationDigest = sha256(JSON.stringify({ ...notification, webhook: env.notifyWebhookUrl }));
      const effectKey = `notification:${tenant}:${notification.taskId ?? 0}:${notificationDigest}`;
      const idempotencyKey = sha256(`GNW-NOTIFICATION-IDEMPOTENCY-V1|${tenant}|${notification.taskId ?? 0}|${actionDigest}|${notificationDigest}`);
      const fenced = await executeFencedExternal({
        db, env, taskId: notification.taskId ?? 0, actorUserId: notification.userId ?? 0, tenant, eventType: "owner_notification", actionDigest, capabilityLease, capability: "owner_notification", provider: env.notifyWebhookUrl, effectKey, idempotencyKey,
        effect: async (fenceToken, providerIdempotencyKey, generation) => {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 8000);
          try {
            const response = await governedFetch(env.notifyWebhookUrl, {
              method: "POST",
              headers: { "content-type": "application/json", "idempotency-key": providerIdempotencyKey, "x-gnw-fence-generation": String(generation), "x-gnw-fence-token": fenceToken },
              body: JSON.stringify({ source: "gnw-governed-agent", ...notification, sentAt: new Date().toISOString() }),
              signal: controller.signal,
              redirect: "manual",
              __allowedHosts: env.allowedEgressHosts,
            } as RequestInit & { __allowedHosts: readonly string[] }, env.maxProviderResponseBytes);
            if (!response.ok) throw new Error(`notification_http_${response.status}`);
            if (env.notifyProviderIdempotencyRequired && response.headers.get("x-gnw-idempotency-key") !== providerIdempotencyKey) throw new Error("notification_idempotency_contract_not_confirmed");
            if (env.notifyProviderIdempotencyRequired && response.headers.get("x-gnw-fence-token") !== fenceToken) throw new Error("notification_fence_contract_not_confirmed");
            return { result: { status: response.status }, responseDigest: sha256(`${response.status}|${providerIdempotencyKey}|${fenceToken}`) };
          } finally { clearTimeout(timer); }
        },
      });
      delivered = fenced.status === "COMPLETED";
    } catch (error) {
      console.warn(JSON.stringify({ level: "warn", event: "notification_delivery_failed", detail: String(error) }));
    }
  }
  console.log(JSON.stringify({ level: "info", event: "notification", title: notification.title, taskId: notification.taskId ?? null, delivered }));
  await recordNotification(db, {
    userId: notification.userId ?? null,
    taskId: notification.taskId ?? null,
    title: notification.title,
    body: notification.body,
    channel: env.notifyWebhookUrl ? "webhook" : "log",
    delivered,
  });
}
