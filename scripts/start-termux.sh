#!/usr/bin/env bash
# ==============================================================================
# GNW Governed Agent v4 — Termux Ubuntu Launch Script
# ==============================================================================
set -e

if [ ! -f dist/server/index.js ]; then
  echo "Building distribution files first..."
  npm run build
fi

PORT=${PORT:-8787}
echo "=================================================================="
echo " Starting GNW Governed Agent v4 inside Termux Ubuntu..."
echo " Open your mobile browser at: http://localhost:$PORT"
echo " (Press Ctrl+C anytime to stop the server)"
echo "=================================================================="

node dist/server/index.js
