#!/usr/bin/env python3
"""
Coverage verification script for GNW CI/CD pipeline.
Runs pytest with coverage and fails if coverage is below threshold.
"""

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple


def run_coverage(min_coverage: int) -> Tuple[bool, str]:
    """Run pytest with coverage and parse results."""
    try:
        # Run pytest with coverage
        cmd = [
            "pytest",
            "--cov=personal_agent",
            "--cov-report=xml:evidence/coverage.xml",
            "--cov-report=term-missing",
            "personal_agent/tests/",
            "-v"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Parse coverage.xml
        coverage_path = Path("evidence/coverage.xml")
        if not coverage_path.exists():
            return False, "Coverage XML not generated"

        tree = ET.parse(coverage_path)
        root = tree.getroot()

        # Find line-rate attribute (overall coverage)
        line_rate = float(root.get("line-rate", 0))
        coverage_pct = int(line_rate * 100)

        if coverage_pct < min_coverage:
            return False, f"Coverage {coverage_pct}% below threshold {min_coverage}%"

        return True, f"Coverage {coverage_pct}% meets threshold {min_coverage}%"

    except subprocess.TimeoutExpired:
        return False, "Coverage run timed out"
    except ET.ParseError as e:
        return False, f"Failed to parse coverage.xml: {e}"
    except Exception as e:
        return False, f"Coverage check failed: {e}"


def main():
    parser = argparse.ArgumentParser(description="Verify test coverage meets threshold")
    parser.add_argument("--min", type=int, default=80, help="Minimum coverage percentage")
    args = parser.parse_args()

    print("=" * 60)
    print(f"GNW Coverage Verification (min: {args.min}%)")
    print("=" * 60)

    passed, msg = run_coverage(args.min)
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {msg}")
    print("=" * 60)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())