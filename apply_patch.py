from pathlib import Path

target_file = Path("D:/GNW/gnw-governed-agent-v4/scripts/preflight-production.mjs")
with open(target_file, "r", encoding="utf-8", newline="") as f:
    content = f.read()

# Normalize to LF
content_lf = content.replace("\r\n", "\n")

old_block = """function parseJson(name) {
  try { return JSON.parse(env[name] ?? ""); }
  catch { failures.push(name + " invalid JSON"); return undefined; }
}

function verifyReleaseTeeEvidence() {
  const evidence = parseJson("GNW_TEE_ATTESTATION_EVIDENCE_JSON");
  if (!evidence || typeof evidence !== "object") return;"""

new_block = """function parseJsonObject(name) {
  const raw = env[name];
  if (raw === undefined || raw === null || typeof raw !== "string" || !raw.trim()) {
    failures.push(name + " missing");
    return undefined;
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      failures.push(name + " must be a valid non-null JSON object");
      return undefined;
    }
    return parsed;
  } catch {
    failures.push(name + " invalid JSON");
    return undefined;
  }
}

function verifyReleaseTeeEvidence() {
  const evidence = parseJsonObject("GNW_TEE_ATTESTATION_EVIDENCE_JSON");
  if (!evidence) return;"""

old_mpc = """function verifyMpcReleaseEvidence() {
  const anchor = parseJson("GNW_MPC_TRUST_ANCHOR_JSON");
  const evidence = parseJson("GNW_MPC_TRUST_ANCHOR_EVIDENCE_JSON");
  if (!anchor || !evidence) return;"""

new_mpc = """function verifyMpcReleaseEvidence() {
  const anchor = parseJsonObject("GNW_MPC_TRUST_ANCHOR_JSON");
  const evidence = parseJsonObject("GNW_MPC_TRUST_ANCHOR_EVIDENCE_JSON");
  if (!anchor || !evidence) return;"""

assert old_block in content_lf, "old_block not found in content_lf"
assert old_mpc in content_lf, "old_mpc not found in content_lf"

content_lf = content_lf.replace(old_block, new_block, 1)
content_lf = content_lf.replace(old_mpc, new_mpc, 1)

content_crlf = content_lf.replace("\n", "\r\n")
with open(target_file, "w", encoding="utf-8", newline="") as f:
    f.write(content_crlf)

print("SUCCESS: Patch applied to preflight-production.mjs")
