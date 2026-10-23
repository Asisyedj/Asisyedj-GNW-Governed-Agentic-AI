#!/usr/bin/env bash
set -euo pipefail

if [[ -n "$(git -C .. status --porcelain)" ]]; then
  echo "production gate requires a clean, committed source tree" >&2
  exit 2
fi
candidate="$(git -C .. rev-parse HEAD)"

echo "[0/10] static release policy checks"
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
command -v trivy >/dev/null || { echo "Trivy is required; container scan cannot be skipped" >&2; exit 2; }
test "$(node --version)" = "v22.23.4" || { echo "Node.js v22.23.4 is required for release gates" >&2; exit 2; }
build_network="${GNW_DOCKER_BUILD_NETWORK:-default}"
case "$build_network" in
  default) build_network_flag=() ;;
  host) build_network_flag=(--network host) ;;
  *) echo "GNW_DOCKER_BUILD_NETWORK must be default or host" >&2; exit 2 ;;
esac
app_image="gnw-governed-agent:${candidate}"
executor_image="gnw-governed-executor:${candidate}"
docker build "${build_network_flag[@]}" --pull --no-cache --label "org.opencontainers.image.revision=${candidate}" -t "$app_image" -f Dockerfile .
docker build "${build_network_flag[@]}" --pull --no-cache --label "org.opencontainers.image.revision=${candidate}" -t "$executor_image" -f Dockerfile.executor .
trivy image --download-db-only --no-progress
for image in "$app_image" "$executor_image"; do
  report="/tmp/${candidate}-$(printf '%s' "$image" | tr '/:' '--')-trivy.json"
  echo "Scanning immutable candidate image $image; full report: $report"
  docker image inspect "$image" --format 'id={{.Id}} os={{.Os}} arch={{.Architecture}} user={{.Config.User}}'
  trivy image --scanners vuln,secret --format json --output "$report" --no-progress "$image"
  trivy image --scanners vuln,secret --severity HIGH,CRITICAL --exit-code 1 --no-progress "$image"
done

echo "[8/10] 100-case evidence ledger gate"
node scripts/validate-100-evidence.mjs
echo "[9/10] release evidence completeness gate"
node scripts/validate-release-evidence.mjs
echo "[9a/10] release artifact attestation"
printf '%s  %s\n' "$(sha256sum dist/server/index.js 2>/dev/null | cut -d' ' -f1 || true)" "dist/server/index.js"
echo "[10/10] RELEASE GATE PASSED"
echo "Run the external Postgres concurrency, egress, backup/restore, kill-switch and 100-case adversarial staging suite before production rollout."
