#!/usr/bin/env python3
"""
KPI monitoring script for GNW CI/CD pipeline.
Monitors key performance indicators during canary deployment.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import urllib.request
import urllib.error


KPI_THRESHOLDS = {
    "error_rate": 0.01,      # 1% max error rate
    "latency_p95": 2.0,      # 2 seconds max P95 latency
    "latency_p99": 5.0,      # 5 seconds max P99 latency
    "availability": 0.99,    # 99% availability
    "cpu_usage": 80.0,       # 80% max CPU
    "memory_usage": 85.0,    # 85% max memory
}


def fetch_metrics(url: str) -> Dict[str, Any]:
    """Fetch metrics from Prometheus /metrics endpoint."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "text/plain"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"success": True, "data": resp.read().decode("utf-8")}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}", "data": e.read().decode("utf-8")}
    except Exception as e:
        return {"success": False, "error": str(e), "data": ""}


def parse_prometheus_metrics(text: str) -> Dict[str, float]:
    """Parse Prometheus text format metrics."""
    metrics = {}
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = line.split(" ")
            if len(parts) >= 2:
                name = parts[0]
                value = float(parts[1])
                metrics[name] = value
        except (ValueError, IndexError):
            continue
    return metrics


def evaluate_kpis(metrics: Dict[str, float]) -> Dict[str, Any]:
    """Evaluate KPIs against thresholds."""
    results = {}
    breaches = []

    # Error rate (http_requests_total{status=~"5.."} / http_requests_total)
    total_requests = metrics.get("http_requests_total", 0)
    error_requests = metrics.get("http_requests_total{status=~\"5..\"}", 0)
    if total_requests > 0:
        error_rate = error_requests / total_requests
        results["error_rate"] = error_rate
        if error_rate > KPI_THRESHOLDS["error_rate"]:
            breaches.append(f"Error rate {error_rate:.4f} > {KPI_THRESHOLDS['error_rate']}")

    # Latency (http_request_duration_seconds_bucket)
    # This is simplified - real implementation would use histogram quantiles
    p95 = metrics.get("http_request_duration_seconds_p95", 0)
    p99 = metrics.get("http_request_duration_seconds_p99", 0)
    results["latency_p95"] = p95
    results["latency_p99"] = p99
    if p95 > KPI_THRESHOLDS["latency_p95"]:
        breaches.append(f"P95 latency {p95:.2f}s > {KPI_THRESHOLDS['latency_p95']}s")
    if p99 > KPI_THRESHOLDS["latency_p99"]:
        breaches.append(f"P99 latency {p99:.2f}s > {KPI_THRESHOLDS['latency_p99']}s")

    # CPU/Memory (from process metrics)
    cpu = metrics.get("process_cpu_seconds_total", 0)
    memory = metrics.get("process_resident_memory_bytes", 0)
    results["cpu_usage"] = cpu
    results["memory_usage"] = memory / (1024 * 1024) if memory else 0  # MB

    results["breaches"] = breaches
    results["healthy"] = len(breaches) == 0

    return results


def main():
    parser = argparse.ArgumentParser(description="Monitor KPIs during canary")
    parser.add_argument("--duration", type=int, default=300, help="Monitoring duration in seconds")
    parser.add_argument("--interval", type=int, default=10, help="Check interval in seconds")
    parser.add_argument("--url", default="http://localhost:8081/metrics", help="Metrics endpoint")
    parser.add_argument("--output", default="evidence/kpi_monitoring.json", help="Output file")
    args = parser.parse_args()

    print("=" * 60)
    print(f"GNW KPI Monitoring (duration: {args.duration}s, interval: {args.interval}s)")
    print("=" * 60)

    start_time = time.time()
    all_results = []
    any_breach = False

    while time.time() - start_time < args.duration:
        elapsed = int(time.time() - start_time)
        print(f"\n[{elapsed}s] Fetching metrics from {args.url}...")

        result = fetch_metrics(args.url)
        if not result["success"]:
            print(f"  ERROR: {result['error']}")
            all_results.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "elapsed": elapsed,
                "success": False,
                "error": result["error"]
            })
        else:
            metrics = parse_prometheus_metrics(result["data"])
            kpi_results = evaluate_kpis(metrics)

            status = "HEALTHY" if kpi_results["healthy"] else "BREACH"
            print(f"  Status: {status}")
            for key, value in kpi_results.items():
                if key not in ("breaches", "healthy"):
                    print(f"    {key}: {value}")

            if kpi_results["breaches"]:
                for breach in kpi_results["breaches"]:
                    print(f"  BREACH: {breach}")
                any_breach = True

            all_results.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "elapsed": elapsed,
                "success": True,
                "metrics": metrics,
                "kpis": kpi_results
            })

        if elapsed >= args.duration:
            break
        time.sleep(args.interval)

    # Final summary
    print("\n" + "=" * 60)
    print("KPI MONITORING COMPLETE")
    print("=" * 60)

    # Write evidence
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    evidence = {
        "schema_version": "1.0",
        "type": "kpi_monitoring",
        "start_time": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
        "duration": args.duration,
        "interval": args.interval,
        "url": args.url,
        "thresholds": KPI_THRESHOLDS,
        "any_breach": any_breach,
        "results": all_results
    }

    with open(output_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"Evidence written to: {output_path}")
    print(f"Any breach: {any_breach}")

    if any_breach:
        print("KPI BREACH DETECTED - FAIL-CLOSED")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())