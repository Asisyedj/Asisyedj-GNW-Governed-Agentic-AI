#!/usr/bin/env bash
# ==============================================================================
# GNW Governed Agent v4 — Termux Ubuntu Auto-Setup Script
# ==============================================================================
set -e

echo "=== [1/5] Updating packages in Ubuntu... ==="
apt-get update -y && apt-get upgrade -y

echo "=== [2/5] Installing Node.js 20, Python, and build dependencies... ==="
apt-get install -y curl wget git python3 build-essential sqlite3 ca-certificates

# Install Node.js 20 LTS if node is missing or older than v20
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d'.' -f1 | tr -d 'v')" -lt 20 ]; then
  echo "Installing Node.js 20 from NodeSource..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

echo "Node version: $(node -v)"
echo "NPM version:  $(npm -v)"

echo "=== [3/5] Setting up environment configuration (.env)... ==="
if [ ! -f .env ]; then
  cp .env.example .env
  # Generate a cryptographically secure session secret
  SESSION_SECRET=$(node -e "console.log(require('crypto').randomBytes(48).toString('hex'))")
  sed -i "s/SESSION_SECRET=/SESSION_SECRET=$SESSION_SECRET/" .env
  sed -i "s/NODE_ENV=production/NODE_ENV=development/" .env
  sed -i "s/PORT=8787/PORT=8787/" .env
  echo ".env created with a new secure session secret."
else
  echo ".env already exists, keeping your existing configuration."
fi

echo "=== [4/5] Installing npm dependencies... ==="
npm install

echo "=== [5/5] Building frontend and backend bundles... ==="
npm run build

echo ""
echo "=================================================================="
echo "   GNW GOVERNED AGENT V4 SUCCESSFULLY INSTALLED IN TERMUX!        "
echo "=================================================================="
echo ""
echo "To configure your API Key, edit .env with nano:"
echo "   nano .env"
echo "   (Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL)"
echo ""
echo "To start GNW Agent, run:"
echo "   npm start"
echo ""
echo "Then open your phone browser and go to: http://localhost:8787"
echo "=================================================================="
