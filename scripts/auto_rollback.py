#!/usr/bin/env python3
"""
Auto-rollback script for GNW CI/CD pipeline.
Rolls back deployment on KPI breach or manual trigger.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def run_cmd(cmd: list, timeout: int = 60) -> dict:
    """Run a command and return structured result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(cmd),
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout after {timeout}s",
            "success": False
        }
    except Exception as e:
        return {
            "command": " ".join(cmd),
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False
        }


def check_kpi_evidence() -> bool:
    """Check if KPI monitoring evidence shows breach."""
    evidence_files = list(Path("evidence").glob("kpi_monitoring*.json"))
    if not evidence_files:
        return False

    latest = max(evidence_files, key=lambda f: f.stat().st_mtime)
    try:
        with open(latest) as f:
            data = json.load(f)
        return data.get("any_breach", False)
    except Exception:
        return False


def rollback_kubernetes() -> dict:
    """Rollback Kubernetes deployment."""
    results = {}

    # Rollback canary deployment
    results["delete_canary"] = run_cmd([
        "kubectl", "delete", "deployment", "personal-agent-canary", "--ignore-not-found=true"
    ])

    # Rollback main deployment to previous revision
    results["rollback_main"] = run_cmd([
        "kubectl", "rollout", "undo", "deployment/personal-agent"
    ])

    # Wait for rollout to complete
    results["wait_rollout"] = run_cmd([
        "kubectl", "rollout", "status", "deployment/personal-agent", "--timeout=300s"
    ])

    return results


def rollback_local() -> dict:
    """Rollback local deployment."""
    results = {}

    # Kill canary process
    canary_pid_file = Path("/tmp/gnw_canary.pid")
    if canary_pid_file.exists():
        try:
            pid = int(canary_pid_file.read_text().strip())
            results["kill_canary"] = run_cmd(["kill", "-TERM", str(pid)])
            time.sleep(2)
            # Force kill if needed
            run_cmd(["kill", "-KILL", str(pid)], timeout=5)
        except Exception as e:
            results["kill_canary"] = {"success": False, "error": str(e)}
        canary_pid_file.unlink(missing_ok=True)

    # Restart main service
    results["restart_main"] = run_cmd([
        "pkill", "-f", "personal_agent.bridge.supervisor"
    ])
    time.sleep(2)
    results["start_main"] = run_cmd([
        "python", "-m", "personal_agent.bridge.supervisor"
    ], timeout=10)

    return results


def main():
    parser = argparse.ArgumentParser(description="Auto-rollback on KPI breach")
    parser.add_argument("--force", action="store_true", help="Force rollback without checking evidence")
    parser.add_argument("--output", default="evidence/rollback.json", help="Output file")
    args = parser.parse_args()

    print("=" * 60)
    print("GNW Auto-Rollback")
    print("=" * 60)

    # Check if rollback needed
    if not args.force:
        if not check_kpi_evidence():
            print("No KPI breach detected. Rollback not needed.")
            return 0
        print("KPI breach detected in evidence. Initiating rollback...")
    else:
        print("Force rollback requested.")

    rollback_results = {
        "schema_version": "1.0",
        "type": "auto_rollback",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": "force" if args.force else "kpi_breach",
        "actions": {}
    }

    # Determine rollback method
    if os.environ.get("KUBERNETES_SERVICE_HOST") or run_cmd(["kubectl", "version", "--client"])["success"]:
        print("--- Kubernetes rollback ---")
        rollback_results["actions"]["kubernetes"] = rollback_kubernetes()
    else:
        print("--- Local rollback ---")
        rollback_results["actions"]["local"] = rollback_local()

    # Verify rollback
    print("--- Verifying rollback ---")
    for i in range(10):
        result = run_cmd(["curl", "-sf", "http://localhost:8080/health"])
        if result["success"]:
            print("Health check passed after rollback")
            rollback_results["verification"] = {"success": True, "attempts": i + 1}
            break
        print(f"Waiting for health check... ({i+1}/10)")
        time.sleep(3)
    else:
        rollback_results["verification"] = {"success": False, "attempts": 10}
        print("ERROR: Health check failed after rollback!")

    # Write evidence
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(rollback_results, f, indent=2)

    # Create hash
    import hashlib
    with open(output_path, "rb") as f:
        content = f.read()
    file_hash = hashlib.sha256(content).hexdigest()
    hash_filepath = output_path.with_suffix(output_path.suffix + ".sha256")
    with open(hash_filepath, "w") as f:
        f.write(f"{file_hash}  {output_path.name}\n")

    print(f"\nRollback evidence: {output_path}")
    print(f"SHA256: {file_hash}")

    verification = rollback_results.get("verification", {})
    if verification.get("success"):
        print("ROLLBACK SUCCESSFUL")
        return 0
    else:
        print("ROLLBACK FAILED - MANUAL INTERVENTION REQUIRED")
        return 1


if __name__ == "__main__":
    sys.exit(main())