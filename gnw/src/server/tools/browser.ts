import type { Db } from "../db/index.js";
import type { Env } from "../env.js";
import type { SessionUser } from "../auth.js";
import type { CapabilityLease } from "../capability.js";
import { executeExternal } from "../execution.js";
import { governedFetch } from "../security.js";
import { sanitizePromptInput } from "../security/guard.js";

export type BrowseResult = {
  url: string;
  title: string;
  content: string;
  byteSize: number;
};

/**
 * Distills raw HTML into clean, token-efficient text/markdown.
 * Strips scripts, styling, ads, and navigational noise.
 */
export function distillHtmlToMarkdown(html: string): { title: string; text: string } {
  // Extract <title>
  const titleMatch = /<title[^>]*>([^<]+)<\/title>/i.exec(html);
  const title = titleMatch ? titleMatch[1].trim() : "Untitled Page";

  // Remove scripts, styles, SVG, comments
  let clean = html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, "")
    .replace(/<noscript\b[^<]*(?:(?!<\/noscript>)<[^<]*)*<\/noscript>/gi, "")
    .replace(/<svg\b[^<]*(?:(?!<\/svg>)<[^<]*)*<\/svg>/gi, "")
    .replace(/<!--[\s\S]*?-->/g, "");

  // Transform basic HTML to Markdown
  clean = clean
    .replace(/<h[1-6][^>]*>(.*?)<\/h[1-6]>/gi, "\n\n### $1\n")
    .replace(/<p[^>]*>(.*?)<\/p>/gi, "\n\n$1\n")
    .replace(/<li[^>]*>(.*?)<\/li>/gi, "\n* $1")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<hr\s*\/?>/gi, "\n---\n")
    .replace(/<a\s+[^>]*href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gi, "[$2]($1)")
    .replace(/<[^>]+>/g, ""); // strip any remaining tags

  // Unescape common HTML entities
  clean = clean
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");

  // Normalize whitespace
  clean = clean.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
  return { title, text: sanitizePromptInput(clean) };
}

/**
 * Governed Browser Fetch (`browser.fetch`).
 * Fetches an external webpage under strict SSRF protection and capability lease.
 */
export async function runGovernedBrowse(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  url: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<BrowseResult> {
  const parsed = new URL(p.url);
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "browser_research_fetch",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "browser.fetch",
    destination: p.url,
    effect: async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 20_000);
      try {
        const response = await governedFetch(p.url, {
          method: "GET",
          headers: {
            "user-agent": "GNW-Governed-Research-Agent/4.0 (+https://governed.agent)",
            accept: "text/html,application/xhtml+xml,text/plain;q=0.9",
          },
          signal: controller.signal,
          redirect: "manual",
          __allowedHosts: p.env.allowedEgressHosts.length > 0 ? p.env.allowedEgressHosts : [parsed.hostname],
        } as RequestInit & { __allowedHosts: readonly string[] }, 5 * 1024 * 1024);

        if (!response.ok) {
          throw new Error(`browser_http_status_${response.status}`);
        }

        const rawHtml = await response.text();
        const { title, text } = distillHtmlToMarkdown(rawHtml);

        return {
          url: p.url,
          title,
          content: text.slice(0, 50_000), // Cap content for model context
          byteSize: Buffer.byteLength(text, "utf8"),
        };
      } finally {
        clearTimeout(timer);
      }
    },
  });
}
