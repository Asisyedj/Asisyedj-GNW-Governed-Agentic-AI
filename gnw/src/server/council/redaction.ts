const SENSITIVE_KEY = /(api[-_]?key|authorization|cookie|credential|password|private[-_]?key|secret|session|token)/i;
const SECRET_VALUE = /\b(?:Bearer\s+\S+|sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})\b/gi;
const MAX_DEPTH = 12;

export function redactForCouncil(value: unknown, depth = 0): unknown {
  if (depth > MAX_DEPTH) return "[REDACTED:DEPTH_LIMIT]";
  if (typeof value === "string") return value.replace(SECRET_VALUE, "[REDACTED]");
  if (Array.isArray(value)) return value.map(item => redactForCouncil(item, depth + 1));
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      output[key] = SENSITIVE_KEY.test(key) ? "[REDACTED]" : redactForCouncil(item, depth + 1);
    }
    return output;
  }
  return value;
}
