#!/usr/bin/env bash
set -euo pipefail

echo "[0/10] force-fail-closed policy preflight"
node scripts/validate-force-policy.mjs || exit 2
node -e "const [a,b,c]=process.versions.node.split(".").map(Number); if (a<22 || (a===22 && b<12)) { console.error("Node >=22.12.0 required"); process.exit(2); }"
echo "[0a/10] static release policy checks"
if grep -R -E "npm ci[[:space:]]*\|\|[[:space:]]*npm install|npm install --omit=dev" --exclude=production-gate.sh -n Dockerfile scripts; then
  echo "unsafe dependency fallback detected" >&2
  exit 2
fi
node scripts/security-sink-scan.mjs

echo "[1/10] clean dependency install"
npm ci

echo "[2/10] typecheck"
npm run typecheck

echo "[3/10] full tests"
npm test

echo "[4/10] production build"
npm run build

echo "[5/10] dependency audit"
npm audit --audit-level=high

echo "[5a/10] OpenClaw package behavioral tests"
python3 ../openclaw_portable/run_order_smoke_tests.py

echo "[6/10] production configuration gate"
NODE_ENV=production npm run --silent typecheck >/dev/null

echo "[7/10] container/staging gate"
command -v docker >/dev/null || { echo "docker is required for the staging gate" >&2; exit 2; }
DOCKER_BUILD_NETWORK="${DOCKER_BUILD_NETWORK:-default}"
echo "Docker build network: ${DOCKER_BUILD_NETWORK}"
docker build --network "${DOCKER_BUILD_NETWORK}" -t gnw-governed-agent:4.0.0 .

echo "[8/10] 100-case evidence ledger gate"
node scripts/validate-100-evidence.mjs
echo "[9/10] release evidence completeness gate"
node scripts/validate-release-evidence.mjs
echo "[9a/10] release artifact attestation"
printf '%s  %s\n' "$(sha256sum dist/server/index.js 2>/dev/null | cut -d' ' -f1 || true)" "dist/server/index.js"
echo "[10/10] RELEASE GATE PASSED"
echo "Run the external Postgres concurrency, egress, backup/restore, kill-switch and 100-case adversarial staging suite before production rollout."
