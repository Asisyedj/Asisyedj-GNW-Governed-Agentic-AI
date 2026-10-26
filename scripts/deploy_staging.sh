#!/bin/bash
# Staging deployment script for GNW CI/CD pipeline
set -euo pipefail

echo "=== GNW Staging Deployment ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Commit: ${GITHUB_SHA:-local}"
echo "Branch: ${GITHUB_REF_NAME:-local}"

# Ensure we're in the repo root
cd "$(git rev-parse --show-toplevel)"

# Install/update dependencies
echo "--- Installing dependencies ---"
pip install -e .[dev]

# Run database migrations if needed
echo "--- Running migrations ---"
python -m personal_agent.db.migrate || echo "No migrations module, skipping"

# Start/restart services
echo "--- Starting services ---"
# Example: using docker-compose for staging
if [ -f docker-compose.staging.yml ]; then
    docker-compose -f docker-compose.staging.yml up -d --build
else
    echo "No docker-compose.staging.yml found, starting manually..."
    # Start the application directly
    python -m personal_agent.bridge.supervisor &
    SUPERVISOR_PID=$!
    echo $SUPERVISOR_PID > /tmp/gnw_supervisor.pid
    sleep 5
fi

# Wait for health check
echo "--- Waiting for health check ---"
for i in {1..30}; do
    if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
        echo "Health check passed"
        break
    fi
    echo "Waiting for health check... ($i/30)"
    sleep 2
done

# Final verification
curl -sf http://localhost:8080/health || {
    echo "ERROR: Health check failed after deployment"
    exit 1
}

echo "=== Staging Deployment Complete ==="