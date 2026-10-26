"""
Multi-Model GNW Blocker Deep Research Script
Queries Top 10 AI models via local Perplexity Bridge on port 8000.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

BRIDGE_URL = "http://127.0.0.1:8000"
SESSION_TOKEN = os.getenv("PERPLEXITY_SESSION_TOKEN", "")

TOP_10_MODELS = [
    "openai/gpt5",
    "anthropic/claude-opus-5",
    "anthropic/claude-sonnet-5.5",
    "google/gemini-3.8-flash",
    "google/gemini-3.5-pro",
    "x-ai/grok-4.7",
    "perplexity/sonar-pro",
    "meta/llama-4-maverick",
    "z-ai/glm-5.3",
    "deepseek/deepseek-r2",
]

RESEARCH_PROMPT = """You are a Principal Security Architect reviewing critical governance preflight code.
Context: GNW Governance Invariant 1 mandates FAIL-CLOSED behavior (any malformed, null, boolean, or absent security evidence must trigger a hard rejection, never silently pass).

Current vulnerable implementation in scripts/preflight-production.mjs:
```javascript
function parseJson(name) {
  try { return JSON.parse(env[name] ?? ""); }
  catch { failures.push(name + " invalid JSON"); return undefined; }
}

function verifyReleaseTeeEvidence() {
  const evidence = parseJson("GNW_TEE_ATTESTATION_EVIDENCE_JSON");
  if (!evidence || typeof evidence !== "object") return;
  // ... checks ...
}

function verifyMpcReleaseEvidence() {
  const anchor = parseJson("GNW_MPC_TRUST_ANCHOR_JSON");
  const evidence = parseJson("GNW_MPC_TRUST_ANCHOR_EVIDENCE_JSON");
  if (!anchor || !evidence) return;
  // ... threshold & cryptographic checks ...
}
```

Vulnerability:
If an attacker or corrupted config sets GNW_MPC_TRUST_ANCHOR_JSON="null" or "false":
JSON.parse("null") returns null without throwing -> parseJson() returns null -> if (!anchor || !evidence) return; exits early -> 0 failures recorded -> preflight reports PASS (CRITICAL FAIL-OPEN BYPASS).

Your Task:
Provide in 3 concise bullet points:
1. Exact root cause analysis.
2. The optimal, bulletproof fail-closed replacement implementation that enforces non-null object requirement and records failure if missing/null/primitive.
3. Any subtle edge cases (e.g. Array.isArray, prototype pollution, empty object, numeric thresholds).
"""

def query_model(model_name: str) -> str:
    print(f"\n[QUERYING] {model_name}...")
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a Principal Security Architect. Be rigorous and concise."},
            {"role": "user", "content": RESEARCH_PROMPT}
        ],
        "stream": False
    }
    req_data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SESSION_TOKEN}"
    }
    req = urllib.request.Request(
        f"{BRIDGE_URL}/v1/chat/completions",
        data=req_data,
        headers=headers,
        method="POST"
    )
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                print(f"[SUCCESS] {model_name} responded in {elapsed:.1f}s ({len(content)} chars)")
                return content
            return f"Error: No choices returned: {data}"
    except Exception as e:
        print(f"[FAILED] {model_name}: {e}")
        return f"Error querying {model_name}: {e}"

def main():
    results = {}
    print(f"Starting Multi-Model Deep Research across {len(TOP_10_MODELS)} models...")
    for model in TOP_10_MODELS:
        ans = query_model(model)
        results[model] = ans
        time.sleep(1) # courteous pause

    out_file = Path("D:/GNW/perplexity-browser-api/gnw_top10_models_research.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nDone! All results saved to {out_file}")

if __name__ == "__main__":
    main()
