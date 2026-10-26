#!/usr/bin/env python3
"""
Staging evidence collection script for GNW CI/CD pipeline.
Collects logs, metrics, health checks from staging environment.
Stores in evidence/staging/
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def run_cmd(cmd: list, timeout: int = 30) -> dict:
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


def collect_system_info() -> dict:
    """Collect system/environment information."""
    info = {}
    info["hostname"] = run_cmd(["hostname"])
    info["uname"] = run_cmd(["uname", "-a"])
    info["uptime"] = run_cmd(["uptime"])
    info["df"] = run_cmd(["df", "-h"])
    info["free"] = run_cmd(["free", "-h"])
    info["cpu"] = run_cmd(["lscpu"])
    info["env"] = run_cmd(["env"])
    return info


def collect_docker_info() -> dict:
    """Collect Docker/container information."""
    info = {}
    info["docker_version"] = run_cmd(["docker", "version"])
    info["docker_ps"] = run_cmd(["docker", "ps", "-a"])
    info["docker_images"] = run_cmd(["docker", "images"])
    info["docker_stats"] = run_cmd(["docker", "stats", "--no-stream", "--format", "json"])
    return info


def collect_k8s_info() -> dict:
    """Collect Kubernetes information if available."""
    info = {}
    info["kubectl_version"] = run_cmd(["kubectl", "version", "--client"])
    info["nodes"] = run_cmd(["kubectl", "get", "nodes", "-o", "wide"])
    info["pods"] = run_cmd(["kubectl", "get", "pods", "-A", "-o", "wide"])
    info["services"] = run_cmd(["kubectl", "get", "svc", "-A"])
    info["ingresses"] = run_cmd(["kubectl", "get", "ingress", "-A"])
    return info


def collect_app_logs() -> dict:
    """Collect application logs."""
    logs = {}
    # Check common log locations
    log_paths = [
        "/var/log/app/*.log",
        "/var/log/nginx/*.log",
        "/var/log/supervisor/*.log",
        "./logs/*.log",
        "./server.log",
        "./server.err",
    ]
    for pattern in log_paths:
        # Use find to locate files
        result = run_cmd(["find", "/", "-name", "*.log", "-path", f"*{pattern}*", "-mtime", "-1"])
        if result["success"] and result["stdout"]:
            logs[pattern] = result
    return logs


def collect_health_checks(base_url: str = "http://localhost:8080") -> dict:
    """Collect health check results."""
    health = {}
    endpoints = [
        ("health", f"{base_url}/health"),
        ("ready", f"{base_url}/ready"),
        ("metrics", f"{base_url}/metrics"),
    ]
    for name, url in endpoints:
        # Use curl with timeout
        result = run_cmd(["curl", "-s", "-f", "--max-time", "10", url])
        health[name] = {
            "url": url,
            "success": result["success"],
            "status_code": result.get("status_code"),
            "response": result["stdout"][:500] if result["stdout"] else result["stderr"]
        }
    return health


def collect_network_info() -> dict:
    """Collect network information."""
    info = {}
    info["ss"] = run_cmd(["ss", "-tuln"])
    info["netstat"] = run_cmd(["netstat", "-tuln"])
    info["iptables"] = run_cmd(["iptables", "-L", "-n"])
    return info


def main():
    parser = argparse.ArgumentParser(description="Collect staging evidence")
    parser.add_argument("--output-dir", default="evidence/staging", help="Output directory")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Staging base URL")
    parser.add_argument("--include-k8s", action="store_true", help="Include Kubernetes info")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence = {
        "schema_version": "1.0",
        "type": "staging_evidence",
        "collection_timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": "staging",
        "base_url": args.base_url,
        "collections": {}
    }

    print(f"Collecting staging evidence to {output_dir}...")

    # Collect system info
    print("  [1/7] System information...")
    evidence["collections"]["system"] = collect_system_info()

    # Collect Docker info
    print("  [2/7] Docker information...")
    evidence["collections"]["docker"] = collect_docker_info()

    # Collect Kubernetes info if requested
    if args.include_k8s:
        print("  [3/7] Kubernetes information...")
        evidence["collections"]["kubernetes"] = collect_k8s_info()

    # Collect app logs
    print("  [4/7] Application logs...")
    evidence["collections"]["logs"] = collect_app_logs()

    # Collect health checks
    print("  [5/7] Health checks...")
    evidence["collections"]["health"] = collect_health_checks(args.base_url)

    # Collect network info
    print("  [6/7] Network information...")
    evidence["collections"]["network"] = collect_network_info()

    # Run smoke tests
    print("  [7/7] Running smoke tests...")
    smoke_result = run_cmd([
        "pytest", "personal_agent/tests/", "-v", "-k", "smoke",
        "--junitxml=evidence/staging_smoke.xml"
    ], timeout=120)
    evidence["collections"]["smoke_tests"] = smoke_result

    # Write evidence file
    filename = f"staging_evidence_{timestamp}.json"
    filepath = output_dir / filename
    with open(filepath, "w") as f:
        json.dump(evidence, f, indent=2)

    # Create hash for integrity
    import hashlib
    with open(filepath, "rb") as f:
        content = f.read()
    file_hash = hashlib.sha256(content).hexdigest()
    hash_filepath = output_dir / f"{filename}.sha256"
    with open(hash_filepath, "w") as f:
        f.write(f"{file_hash}  {filename}\n")

    print(f"\nStaging evidence collected: {filepath}")
    print(f"SHA256: {file_hash}")

    # Print summary
    print("\nCollection Summary:")
    for category, data in evidence["collections"].items():
        if isinstance(data, dict) and "success" in data:
            status = "OK" if data["success"] else "FAIL"
            print(f"  {category}: {status}")
        elif isinstance(data, dict):
            ok_count = sum(1 for v in data.values() if isinstance(v, dict) and v.get("success"))
            total = len(data)
            print(f"  {category}: {ok_count}/{total} OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())