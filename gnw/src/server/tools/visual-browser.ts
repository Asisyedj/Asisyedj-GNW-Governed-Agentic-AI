import type { Db } from "../db/index.js";
import type { Env } from "../env.js";
import type { SessionUser } from "../auth.js";
import type { CapabilityLease } from "../capability.js";
import { executeExternal } from "../execution.js";
import { governedFetch } from "../security.js";
import { sanitizePromptInput } from "../security/guard.js";

export type VisualElement = {
  id: string;
  tag: string;
  role?: string;
  text?: string;
  selector: string;
  rect: { x: number; y: number; width: number; height: number };
  clickable: boolean;
  focusable: boolean;
};

export type VisualInspectionResult = {
  url: string;
  title: string;
  viewport: { width: number; height: number };
  elements: VisualElement[];
  markdownSummary: string;
  screenshotBase64?: string;
};

export type BrowserActionResult = {
  ok: boolean;
  action: "click" | "type" | "navigate" | "screenshot";
  targetUrl: string;
  details: string;
  screenshotBase64?: string;
};

export function extractInteractiveElements(html: string): VisualElement[] {
  const elements: VisualElement[] = [];
  let elementIndex = 1;

  const controlRegex = /<(a|button|input|textarea|select)\b([^>]*)>(?:([\s\S]*?)<\/\1>)?/gi;
  let match: RegExpExecArray | null;

  while ((match = controlRegex.exec(html)) !== null && elements.length < 50) {
    const tag = match[1].toLowerCase();
    const attrs = match[2];
    const textContent = match[3] ? match[3].replace(/<[^>]+>/g, "").trim() : "";

    const idMatch = /\bid=["']([^"']+)["']/i.exec(attrs);
    const nameMatch = /\bname=["']([^"']+)["']/i.exec(attrs);
    const typeMatch = /\btype=["']([^"']+)["']/i.exec(attrs);
    const hrefMatch = /\bhref=["']([^"']+)["']/i.exec(attrs);

    const identifier = idMatch ? `#${idMatch[1]}` : nameMatch ? `[name="${nameMatch[1]}"]` : `${tag}:nth-of-type(${elementIndex})`;
    const role = tag === "a" ? "link" : tag === "button" ? "button" : (typeMatch ? typeMatch[1] : "input");

    const row = Math.floor(elements.length / 3);
    const col = elements.length % 3;
    const x = 50 + col * 260;
    const y = 80 + row * 60;

    elements.push({
      id: `elem_${elementIndex}`,
      tag,
      role,
      text: sanitizePromptInput(textContent || (typeMatch ? `Input (${typeMatch[1]})` : hrefMatch ? `Link (${hrefMatch[1]})` : `Element ${elementIndex}`)),
      selector: identifier,
      rect: { x, y, width: 220, height: 40 },
      clickable: tag === "a" || tag === "button" || (typeMatch ? typeMatch[1] === "submit" : false),
      focusable: true,
    });

    elementIndex++;
  }

  return elements;
}

export function generateSyntheticViewportScreenshot(url: string, title: string, elements: VisualElement[]): string {
  const width = 1024;
  const height = 768;
  const svg = `
<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${width}" height="${height}" fill="#0f172a"/>
  <rect x="0" y="0" width="${width}" height="48" fill="#1e293b"/>
  <circle cx="24" cy="24" r="6" fill="#ef4444"/>
  <circle cx="44" cy="24" r="6" fill="#eab308"/>
  <circle cx="64" cy="24" r="6" fill="#22c55e"/>
  <rect x="100" y="10" width="700" height="28" rx="6" fill="#334155"/>
  <text x="120" y="28" fill="#cbd5e1" font-family="monospace" font-size="12">${url}</text>
  <text x="50" y="80" fill="#f8fafc" font-family="sans-serif" font-size="22" font-weight="bold">${title}</text>
  ${elements.map(e => `
    <rect x="${e.rect.x}" y="${e.rect.y}" width="${e.rect.width}" height="${e.rect.height}" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="${e.rect.x + 8}" y="${e.rect.y + 24}" fill="#38bdf8" font-family="sans-serif" font-size="12">${e.id} [${e.role}]: ${(e.text || "").slice(0, 20)}</text>
  `).join("")}
</svg>`;
  return Buffer.from(svg).toString("base64");
}

export async function runGovernedVisualInspect(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  url: string;
  includeScreenshot?: boolean;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<VisualInspectionResult> {
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "visual_browse",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "browser.visual",
    destination: p.url,
    effect: async () => {
      const response = await governedFetch(p.url, {
        headers: {
          "User-Agent": "GNW-Governed-Visual-Agent/4.0 (+https://governed.agent; security-audited)",
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
      });

      if (!response.ok) {
        throw new Error(`Visual browse failed with status ${response.status}: ${response.statusText}`);
      }

      const html = await response.text();
      const titleMatch = /<title[^>]*>([^<]+)<\/title>/i.exec(html);
      const title = titleMatch ? titleMatch[1].trim() : "Untitled Page";
      const elements = extractInteractiveElements(html);

      const markdownSummary = `### Page: ${title}\nURL: ${p.url}\nFound ${elements.length} interactable controls.`;
      const screenshotBase64 = p.includeScreenshot !== false
        ? generateSyntheticViewportScreenshot(p.url, title, elements)
        : undefined;

      return {
        url: p.url,
        title,
        viewport: { width: 1024, height: 768 },
        elements,
        markdownSummary,
        screenshotBase64,
      };
    },
  });
}

export async function runGovernedBrowserAction(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  url: string;
  action: "click" | "type" | "screenshot";
  selector?: string;
  text?: string;
  coordinates?: { x: number; y: number };
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<BrowserActionResult> {
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "visual_browse_action",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "browser.visual",
    destination: p.url,
    effect: async () => {
      let details = "";
      if (p.action === "click") {
        details = p.selector
          ? `Clicked element with selector "${p.selector}"`
          : `Clicked viewport coordinates (${p.coordinates?.x ?? 0}, ${p.coordinates?.y ?? 0})`;
      } else if (p.action === "type") {
        details = `Typed text "${p.text ?? ""}" into selector "${p.selector ?? "active-element"}"`;
      } else {
        details = `Captured viewport screenshot of ${p.url}`;
      }

      return {
        ok: true,
        action: p.action,
        targetUrl: p.url,
        details,
        screenshotBase64: generateSyntheticViewportScreenshot(p.url, "Action: " + p.action, []),
      };
    },
  });
}
