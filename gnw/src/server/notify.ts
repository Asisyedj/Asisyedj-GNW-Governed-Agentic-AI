import type { Db } from "./db/index.js";
import { ENV, type Env } from "./env.js";
import { recordNotification } from "./repo.js";
import type { CapabilityLease } from "./capability.js";
import { executeExternal } from "./execution.js";
import { governedFetch } from "./security.js";

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
      await executeExternal({
        db, env, taskId: notification.taskId ?? 0, actorUserId: notification.userId ?? 0, eventType: "owner_notification", actionDigest, capabilityLease, capability: "owner_notification", destination: env.notifyWebhookUrl,
        effect: async () => {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 8000);
          try {
            return await governedFetch(env.notifyWebhookUrl, {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({ source: "gnw-governed-agent", ...notification, sentAt: new Date().toISOString() }),
              signal: controller.signal,
              redirect: "manual",
              __allowedHosts: env.allowedEgressHosts,
            } as RequestInit & { __allowedHosts: readonly string[] }, env.maxProviderResponseBytes);
          } finally { clearTimeout(timer); }
        },
      });
      delivered = true;
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
