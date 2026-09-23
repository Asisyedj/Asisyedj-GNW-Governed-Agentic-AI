import { createHash } from "node:crypto";

export type OfficeSource = {
  id: string;
  url: string;
  title: string;
  content: string;
  retrievedAt?: string;
  publishedAt?: string;
  sourceType?: "INTERNAL" | "GOVERNMENT" | "STANDARD" | "RESEARCH" | "OFFICIAL_DOCS" | "COMPANY" | "SECONDARY";
};

export type VerifiedSource = OfficeSource & {
  contentHash: string;
  urlHost: string;
  support: "DIRECT" | "PARTIAL" | "INSUFFICIENT";
  limitations: string[];
};

export type Citation = {
  sourceId: string;
  title: string;
  url: string;
  locator: string;
  quote: string;
  contentHash: string;
};

export type ProjectPlanDraft = {
  objective: string;
  deliverables: string[];
  tasks: Array<{ id: string; title: string; description: string; dependencies: string[]; ownerToConfirm: boolean }>;
  milestones: string[];
  risks: Array<{ risk: string; mitigation: string }>;
  assumptions: string[];
  status: "DRAFT";
  requiresHumanReview: true;
};

const sensitivePatterns: Array<[RegExp, string]> = [
  [/\b(send|email|publish|post|notify)\b/i, "external_communication"],
  [/\b(pay|payment|refund|invoice|transfer|purchase)\b/i, "financial_action"],
  [/\b(delete|destroy|purge|erase)\b/i, "destructive_action"],
  [/\b(permission|role|access|credential|password)\b/i, "access_or_security_change"],
  [/\b(hire|fire|terminate|salary|promotion|discipline)\b/i, "high_impact_hr_action"],
  [/\b(production|deploy|release|database write|migration)\b/i, "production_change"],
];

export function sha256(value: string) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function classifySensitiveAction(text: string): { allowed: boolean; reason: string | null } {
  for (const [pattern, reason] of sensitivePatterns) {
    if (pattern.test(text)) return { allowed: false, reason };
  }
  return { allowed: true, reason: null };
}

export function verifySource(source: OfficeSource): VerifiedSource {
  let urlHost = "internal";
  const limitations: string[] = [];
  if (source.sourceType !== "INTERNAL") {
    try {
      const parsed = new URL(source.url);
      if (parsed.protocol !== "https:") limitations.push("non_https_source");
      urlHost = parsed.hostname;
    } catch {
      limitations.push("invalid_url");
    }
  }
  const content = source.content.trim();
  const support = content.length >= 40 && source.title.trim().length >= 2
    ? "DIRECT"
    : content.length >= 10 ? "PARTIAL" : "INSUFFICIENT";
  if (!source.retrievedAt) limitations.push("retrieval_time_missing");
  if (source.sourceType !== "INTERNAL" && !source.publishedAt) limitations.push("publication_date_missing");
  if (support === "INSUFFICIENT") limitations.push("insufficient_source_content");
  return { ...source, contentHash: sha256(content), urlHost, support, limitations };
}

export function buildCitation(source: VerifiedSource, locator = "source content", quote?: string): Citation {
  const cleanQuote = (quote ?? source.content).trim().slice(0, 500);
  return {
    sourceId: source.id,
    title: source.title.trim(),
    url: source.url,
    locator,
    quote: cleanQuote,
    contentHash: source.contentHash,
  };
}

export function draftProjectPlan(input: { prompt: string; deliverables?: string[]; constraints?: string[] }): ProjectPlanDraft {
  const objective = input.prompt.trim().replace(/\s+/g, " ").slice(0, 500);
  const deliverables = (input.deliverables ?? []).map(value => value.trim()).filter(Boolean).slice(0, 20);
  const constraints = (input.constraints ?? []).map(value => value.trim()).filter(Boolean).slice(0, 20);
  const taskTitles = deliverables.length > 0 ? deliverables : ["مقصد اور دائرۂ کار واضح کرنا", "مطلوبہ معلومات اور وسائل جمع کرنا", "محفوظ draft تیار کرنا", "انسانی review کے بعد اگلا قدم طے کرنا"];
  const tasks = taskTitles.map((title, index) => ({
    id: `draft-task-${index + 1}`,
    title,
    description: `یہ draft task انسانی review کے بعد مکمل کیا جائے گا: ${title}`,
    dependencies: index === 0 ? [] : [`draft-task-${index}`],
    ownerToConfirm: true,
  }));
  return {
    objective,
    deliverables: deliverables.length > 0 ? deliverables : ["منظور شدہ draft deliverable"],
    tasks,
    milestones: ["Scope review", "Evidence review", "Human approval", "Completion verification"],
    risks: [
      { risk: "درکار معلومات یا source نامکمل ہو سکتا ہے", mitigation: "Agent abstain کرے اور missing evidence دکھائے" },
      { risk: "draft کو final action سمجھ لیا جائے", mitigation: "ہر output پر DRAFT اور HUMAN REVIEW REQUIRED نمایاں ہو" },
    ],
    assumptions: constraints.length > 0 ? constraints : ["Owners، deadlines اور external commitments انسانی review سے confirm ہوں گے"],
    status: "DRAFT",
    requiresHumanReview: true,
  };
}

export function answerWithCitations(answer: string, sources: VerifiedSource[]): { answer: string; citations: Citation[]; abstained: boolean } {
  const usable = sources.filter(source => source.support === "DIRECT" || source.support === "PARTIAL");
  if (usable.length === 0) return { answer: "کافی مجاز اور قابلِ تصدیق ثبوت موجود نہیں؛ جواب روک دیا گیا ہے۔", citations: [], abstained: true };
  return { answer: `${answer.trim()}\n\nحوالہ: ${usable.map(source => `[${source.id}] ${source.title}`).join("؛ ")}`, citations: usable.map(source => buildCitation(source)), abstained: false };
}

export const OFFICE_PHASE1_SCOPE = Object.freeze([
  "internal_document_search",
  "live_web_research_fetch",
  "source_verification",
  "citation_answer",
  "project_plan_draft",
  "sensitive_action_stop",
  "complete_audit",
] as const);
