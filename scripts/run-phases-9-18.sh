#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/evidence/phase9-18"
mkdir -p "$OUT"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT="$OUT/PHASE-9-18-RUN-${TS//:/-}.json"

python3 - "$ROOT" "$REPORT" "$TS" <<'PY'
import json, os, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1]); report = Path(sys.argv[2]); ts = sys.argv[3]

def run(cmd):
    try:
        p = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=180)
        return {"status": "PASS" if p.returncode == 0 else "FAIL",
                "returncode": p.returncode,
                "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}
    except FileNotFoundError:
        return {"status": "UNPROVEN", "reason": f"command unavailable: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"status": "UNPROVEN", "reason": "command timed out"}

checks = {}
if (root/"package.json").exists() and (root/"node_modules/.bin/vitest").exists():
    checks["local_tests"] = run(["npm","test","--","--run"])
else:
    checks["local_tests"] = {"status":"UNPROVEN","reason":"node_modules/.bin/vitest unavailable"}

checks["sink_scan"] = run(["node","scripts/security-sink-scan.mjs"]) if (root/"scripts/security-sink-scan.mjs").exists() else {"status":"UNPROVEN","reason":"sink scanner unavailable"}
checks["100_evidence"] = run(["node","scripts/validate-100-evidence.mjs"]) if (root/"scripts/validate-100-evidence.mjs").exists() and (root/"node_modules").exists() else {"status":"UNPROVEN","reason":"100-evidence validator prerequisites unavailable"}

external = {
 "phase9_postgres_multi_instance": "UNPROVEN",
 "phase10_real_restore_and_secret_rotation": "UNPROVEN",
 "phase11_trusted_supply_chain_signing": "UNPROVEN",
 "phase12_independent_human_review": "UNPROVEN",
 "phase13_limited_production_pilot": "UNPROVEN",
 "phase14_external_certification": "UNPROVEN",
 "phase15_production_observability": "UNPROVEN",
 "phase16_staging_deploy_rollback": "UNPROVEN",
 "phase17_integrated_adversarial_run": "UNPROVEN",
 "phase18_final_release_evidence_freeze": "UNPROVEN",
}
report.write_text(json.dumps({
 "timestamp": ts,
 "policy": "fail-closed",
 "local_checks": checks,
 "external_gates": external,
 "release_decision": "DENY",
 "reason": "External production evidence cannot be manufactured by local static execution."
}, indent=2), encoding="utf-8")
print(report)
PY
