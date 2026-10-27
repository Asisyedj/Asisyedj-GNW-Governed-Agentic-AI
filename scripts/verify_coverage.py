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
from typing import Optional, Tuple


def parse_total_from_term_output(output: str) -> Optional[int]:
    """Fallback parser: extract the TOTAL line percentage from term-missing output."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("TOTAL") and "%" in stripped:
            token = stripped.split()[-1].rstrip("%")
            try:
                return int(token)
            except ValueError:
                continue
    return None


def run_coverage(min_coverage: int) -> Tuple[bool, str]:
    """Run pytest with coverage and parse results."""
    try:
        # Ensure the evidence directory exists before pytest writes reports.
        evidence_dir = Path("evidence")
        evidence_dir.mkdir(parents=True, exist_ok=True)

        # Run pytest with coverage. Use `sys.executable -m pytest` so the
        # invocation works identically on Windows and Linux regardless of PATH.
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "--cov=personal_agent",
            "--cov-report=term-missing",
            "--cov-report=xml:evidence/coverage.xml",
            "personal_agent/tests/",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Fail-closed: if any test fails, coverage evidence is not trustworthy.
        if result.returncode != 0:
            tail = (result.stdout or result.stderr or "").strip().splitlines()[-5:]
            detail = " | ".join(tail) if tail else "(no output)"
            return False, f"pytest exited with code {result.returncode}: {detail}"

        # Prefer parsing coverage.xml (exact line-rate attribute).
        coverage_path = evidence_dir / "coverage.xml"
        if coverage_path.exists():
            tree = ET.parse(coverage_path)
            root = tree.getroot()

            # Find line-rate attribute (overall coverage)
            line_rate = float(root.get("line-rate", 0))
            coverage_pct = round(line_rate * 100)
        else:
            # Fallback: parse the TOTAL row from term-missing output.
            coverage_pct = parse_total_from_term_output(result.stdout or "")
            if coverage_pct is None:
                return False, "Coverage XML not generated and no TOTAL line found in pytest output"

        if coverage_pct < min_coverage:
            return False, f"Coverage {coverage_pct}% below threshold {min_coverage}%"

        return True, f"Coverage {coverage_pct}% meets threshold {min_coverage}%"

    except subprocess.TimeoutExpired:
        return False, "Coverage run timed out"
    except FileNotFoundError:
        return False, "pytest executable not found - install pytest and pytest-cov"
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