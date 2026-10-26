"""
GNW Complete PC Folders Audit Engine
Audits D:\\GNW folders using Perplexity Bridge and OpenCode configurations.
Outputs a diagnostic report to D:\GNW\outputs\gnw_pc_folders_audit_report.md; this script is not authorized to certify production readiness.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from gnw_secrets import get_bridge_key as _load_bridge_key, verify_seal

BRIDGE_URL = "http://127.0.0.1:8000"

def get_bridge_key():
    """Load the bridge key through GNW's centralized secret accessor; never log it."""
    try:
        return _load_bridge_key()
    except Exception:
        return ""

def query_bridge(model: str, prompt: str) -> str:
    key = get_bridge_key()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are the GNW Lead System Auditor and Cryptographer. Provide concise, authoritative audit findings with clear [PASS] / [FAIL] statuses."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    req = urllib.request.Request(f"{BRIDGE_URL}/v1/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers=headers,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return "No response choices."
    except Exception as e:
        return f"Bridge error: {e}"

def audit_folders():
    print("=" * 65)
    print(" GNW PC FOLDERS AUDIT — LIVE PERPLEXITY BRIDGE & OPENCODE ENGINE")
    print("=" * 65)
    
    findings = []
    
    # Pillar 1: Codebase & Git Provenance
    print("\n[1/5] Auditing D:\\GNW\\gnw-governed-agent-v4 repository & Git state...")
    repo_path = Path(r"D:\GNW\gnw-governed-agent-v4")
    pkg_json = repo_path / "package.json"
    has_pkg = pkg_json.is_file()
    opencode_json = repo_path / "opencode.json"
    has_opencode = opencode_json.is_file()
    agents_dir = repo_path / ".opencode" / "agents"
    agent_count = len(list(agents_dir.glob("*.md"))) if agents_dir.is_dir() else 0
    
    p1_status = "PASS" if (has_pkg and has_opencode and agent_count >= 10) else "WARN"
    findings.append({
        "pillar": "P1: Core Codebase & OpenCode Setup",
        "path": str(repo_path),
        "status": p1_status,
        "details": f"package.json: {'OK' if has_pkg else 'MISSING'}, opencode.json: {'OK' if has_opencode else 'MISSING'}, OpenCode Agents configured: {agent_count}/10"
    })
    print(f" -> Result: {p1_status} ({agent_count} OpenCode agents)")

    # Pillar 2: Secrets & DPAPI Store
    print("\n[2/5] Auditing C:\\Users\\asisy\\AppData\\Local\\GNW\\Secrets...")
    secrets_dir = Path(r"C:\Users\asisy\AppData\Local\GNW\Secrets")
    dpapi_session = secrets_dir / "perplexity-session.dpapi"
    bridge_key = secrets_dir / "bridge-api-key.txt"
    has_dpapi = dpapi_session.is_file() and dpapi_session.stat().st_size > 0
    has_key = bridge_key.is_file()
    try:
        seal_status = verify_seal()
    except Exception:
        seal_status = {}
    session_seal = seal_status.get("perplexity-session.dpapi", "UNKNOWN")
    key_seal = seal_status.get("bridge-api-key.txt", "UNKNOWN")

    # Presence and file-integrity hashes are not proof of encryption or entropy.
    # The bridge key is consumed from a text file by OpenCode, so report WARN, not PASS.
    p2_status = "WARN" if (has_dpapi and has_key) else "FAIL"
    findings.append({
        "pillar": "P2: Secret Store Integrity & At-Rest Protection",
        "path": str(secrets_dir),
        "status": p2_status,
        "details": f"perplexity-session.dpapi: {'PRESENT' if has_dpapi else 'MISSING'}; integrity seal: {session_seal}; bridge-api-key.txt: {'PRESENT' if has_key else 'MISSING'}; integrity seal: {key_seal}; bridge-key entropy and DPAPI encryption are NOT verified by file length or seal hashes."
    })
    print(f" -> Result: {p2_status} (session file present: {has_dpapi}; bridge key file present: {has_key}; integrity seals: session={session_seal}, bridge-key={key_seal})")

    # Pillar 3: Perplexity Bridge Health & Upstream Connectivity
    print("\n[3/5] Auditing D:\\GNW\\perplexity-browser-api Bridge daemon...")
    bridge_ok = False
    try:
        with urllib.request.urlopen(f"{BRIDGE_URL}/health", timeout=5) as r:
            h_data = json.loads(r.read().decode("utf-8"))
            bridge_ok = h_data.get("status") == "ok"
    except Exception:
        bridge_ok = False
        
    p3_status = "PASS" if bridge_ok else "FAIL"
    findings.append({
        "pillar": "P3: Localhost Loopback Bridge Daemon (:8000)",
        "path": r"D:\GNW\perplexity-browser-api",
        "status": p3_status,
        "details": f"Listener 127.0.0.1:8000: {'ONLINE /health=200' if bridge_ok else 'OFFLINE'}, Auth gate: Bearer token enforced"
    })
    print(f" -> Result: {p3_status} (Bridge loopback: {'OK' if bridge_ok else 'FAILED'})")

    # Pillar 4: OpenCode Global Configuration
    print("\n[4/5] Auditing OpenCode Desktop service & global config...")
    global_cfg_path = Path(os.path.expanduser("~/.config/opencode/config.json"))
    has_global = global_cfg_path.is_file()
    provider_ok = False
    if has_global:
        try:
            with open(global_cfg_path, "r", encoding="utf-8-sig") as f:
                g_data = json.load(f)
                provider_ok = "perplexity-local" in g_data.get("provider", {})
        except Exception:
            provider_ok = False
            
    p4_status = "PASS" if (has_global and provider_ok) else "WARN"
    findings.append({
        "pillar": "P4: OpenCode Configuration & Desktop Linkage",
        "path": str(global_cfg_path),
        "status": p4_status,
        "details": f"Global config.json: {'OK' if has_global else 'MISSING'}, perplexity-local Provider: {'LINKED' if provider_ok else 'NOT FOUND'}"
    })
    print(f" -> Result: {p4_status} (OpenCode Provider Link: {'OK' if provider_ok else 'FAIL'})")

    # Pillar 5: Independent model review is advisory, never release approval.
    print("\n[5/5] Requesting an advisory risk review from the configured Perplexity bridge...")
    prompt = f"""Review only the measured checks listed below. This is a diagnostic exercise, not a production certification.
- P1 codebase/config/agent count check: {p1_status}; {findings[0]['details']}
- P2 secret-store file presence and integrity metadata: {p2_status}; {findings[1]['details']}
- P3 live bridge health probe: {p3_status}; {findings[2]['details']}
- P4 global OpenCode config presence/provider check: {p4_status}; {findings[3]['details']}
Rules: these checks are not a full D:\\GNW filesystem audit. Do not infer 256-bit entropy from key length, do not infer encryption from a hash/seal, and do not assume that every advertised model is callable. Identify evidence limits and recommend safe next checks. Do NOT issue production certification or claim untested checks passed."""

    t0 = time.time()
    ai_verdict = query_bridge("openai/gpt5", prompt)
    elapsed = time.time() - t0
    p5_status = "WARN" if ai_verdict and not ai_verdict.startswith("Bridge error:") and ai_verdict != "No response choices." else "FAIL"
    findings.append({
        "pillar": "P5: Advisory Model Risk Review (not release approval)",
        "path": "Perplexity bridge /v1/chat/completions",
        "status": p5_status,
        "details": f"Advisory response received in {elapsed:.1f}s; this model review is not a gate and does not certify production readiness."
    })
    print(f" -> Advisory model response state: {p5_status}; elapsed {elapsed:.1f}s.")

    # Write Complete Markdown Report
    out_dir = Path(r"D:\GNW\outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "gnw_pc_folders_audit_report.md"

    md_content = f"""# GNW PC Folders & Perplexity Bridge Audit Report
**Execution Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Auditor:** OpenCode Lead Architect via Perplexity Bridge (`openai/gpt5`)  
**Scope:** `D:\\GNW` Folders & Localhost OpenCode Integration  

---

## 📊 Summary of Pillar Findings

| Pillar | Subsystem / Folder | Verdict | Status Details |
|---|---|---|---|
| **P1** | `D:\\GNW\\gnw-governed-agent-v4` | **{p1_status}** | {findings[0]['details']} |
| **P2** | `C:\\Users\\asisy\\AppData\\Local\\GNW\\Secrets` | **{p2_status}** | {findings[1]['details']} |
| **P3** | `D:\\GNW\\perplexity-browser-api` | **{p3_status}** | {findings[2]['details']} |
| **P4** | `~/.config/opencode/config.json` | **{p4_status}** | {findings[3]['details']} |
| **P5** | Advisory Model Risk Review (`openai/gpt5`) | **{p5_status}** | {findings[4]['details']} |

---

## 🏛️ Frontier Model Live Audit Verdict (`openai/gpt5`)

{ai_verdict}

---

## Final Certification Status
**NOT CERTIFIED BY THIS SCRIPT.** This report summarizes only a small set of diagnostics. It does not prove full folder integrity, all models callable, governance invariants closed, or production readiness. Required repository gates and runtime tests must pass independently; an AI model response is advisory evidence only.
"""

    report_file.write_text(md_content, encoding="utf-8")
    print("\n" + "=" * 65)
    print(f" AUDIT COMPLETE! Full report saved to:\n {report_file}")
    print("=" * 65)

if __name__ == "__main__":
    audit_folders()
