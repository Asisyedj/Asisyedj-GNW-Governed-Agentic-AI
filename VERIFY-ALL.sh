#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
GNW="$ROOT/gnw"

cd "$GNW"
echo '== GNW static security sink scan =='
node scripts/security-sink-scan.mjs

echo '== GNW production gate shell syntax =='
bash -n scripts/production-gate.sh

echo '== OpenClaw Python syntax =='
python3 -m compileall -q "$ROOT/openclaw_portable"
echo 'PASS: Python compileall'

echo '== OpenClaw package behavioral tests =='
python3 "$ROOT/openclaw_portable/run_order_smoke_tests.py"

echo '== TypeScript typecheck =='
npm run typecheck

echo '== Full TypeScript tests =='
npm test

echo '== Production build =='
npm run build

echo '== Dependency audit =='
npm audit --audit-level=high

echo '== Python council tests =='
npm run test:council-python

echo '== 100-case evidence gate =='
node scripts/validate-100-evidence.mjs

echo '== Release evidence gate =='
node scripts/validate-release-evidence.mjs

echo 'PASS: all verification and release-evidence gates passed.'
