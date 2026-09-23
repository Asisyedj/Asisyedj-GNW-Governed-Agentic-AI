/**
 * Security Guard & Command Risk Classifier for GNW Governed Agent.
 *
 * Implements supply-chain defense, command risk analysis, and prompt injection
 * sanitization. All terminal execution and external inputs pass through this guard.
 */

export type CommandRisk = "safe" | "mutation" | "destructive";

export type CommandAnalysis = {
  risk: CommandRisk;
  reason?: string;
  matchedPattern?: string;
  requiresHumanApproval: boolean;
};

// High-risk patterns that must never run without explicit human approval
const DESTRUCTIVE_PATTERNS = [
  { pattern: /\brm\s+-[rf]{1,3}\b/i, reason: "recursive_forced_deletion" },
  { pattern: /\brmdir\s+\/s\b/i, reason: "windows_recursive_directory_deletion" },
  { pattern: /\b(del|erase)\s+\/[fqsa]\b/i, reason: "windows_forced_file_deletion" },
  { pattern: /\b(mkfs|dd\s+if=|fdisk|format\s+[a-z]:)/i, reason: "raw_disk_format_or_overwrite" },
  { pattern: /\bdrop\s+(table|database|schema|view)\b/i, reason: "sql_drop_destructive" },
  { pattern: /\btruncate\s+(table)?\b/i, reason: "sql_truncate_destructive" },
  { pattern: /\b(chmod\s+-R\s+777|chmod\s+777)\b/i, reason: "insecure_privilege_escalation" },
  { pattern: /curl\s+[^|]+\|\s*(ba|z)?sh/i, reason: "unvetted_remote_script_execution" },
  { pattern: /wget\s+[^|]+\|\s*(ba|z)?sh/i, reason: "unvetted_remote_script_execution" },
  { pattern: /:\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:/, reason: "fork_bomb" },
  { pattern: /\b(nc|netcat|ncat)\s+-[lvpe]/i, reason: "potential_reverse_shell" },
  { pattern: /\b(shutdown|reboot|init\s+0|halt)\b/i, reason: "system_shutdown_halt" },
  { pattern: />\s*\/dev\/sd[a-z]/i, reason: "raw_device_redirection" },
  { pattern: /\bkill\s+-9\s+-1\b/i, reason: "mass_process_termination" },
];

// Safe read-only commands
const SAFE_PATTERNS = [
  /^(ls|dir|pwd|echo|cat|type|head|tail|grep|findstr|which|where)\b/i,
  /^(git\s+(status|diff|log|branch|show))\b/i,
  /^(node\s+-v|npm\s+-v|python\s+--version|python\s+-V)\b/i,
  /^(vitest|pytest|npm\s+test|npm\s+run\s+test)\b/i,
];

export function analyzeCommandRisk(command: string): CommandAnalysis {
  const trimmed = command.trim();
  if (!trimmed) {
    return { risk: "safe", requiresHumanApproval: false };
  }

  for (const { pattern, reason } of DESTRUCTIVE_PATTERNS) {
    if (pattern.test(trimmed)) {
      return {
        risk: "destructive",
        reason,
        matchedPattern: pattern.source,
        requiresHumanApproval: true,
      };
    }
  }

  for (const safe of SAFE_PATTERNS) {
    if (safe.test(trimmed)) {
      return { risk: "safe", requiresHumanApproval: false };
    }
  }

  // Default for mutating / build / script execution commands
  return { risk: "mutation", requiresHumanApproval: false };
}

/**
 * Sanitizes untrusted user or scraped web text to prevent terminal escapes,
 * directional unicode override exploits, and common prompt injection attacks.
 */
export function sanitizePromptInput(input: string, maxBytes = 100_000): string {
  if (!input) return "";

  // 1. Strip ANSI escape codes
  let clean = input.replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, "");

  // 2. Strip Unicode bidirectional overrides (used in RTL Trojan Source exploits)
  clean = clean.replace(/[\u202A-\u202E\u2066-\u2069]/g, "");

  // 3. Enforce maximum byte length
  const buf = Buffer.from(clean, "utf8");
  if (buf.length > maxBytes) {
    clean = buf.subarray(0, maxBytes).toString("utf8");
  }

  return clean;
}
