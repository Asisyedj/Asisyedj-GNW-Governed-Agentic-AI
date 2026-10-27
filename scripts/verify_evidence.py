#!/usr/bin/env python3
"""
Evidence verification script for GNW CI/CD pipeline.
Checks all required evidence files exist and validates their contents.
Exits non-zero if any gate fails.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple


REQUIRED_EVIDENCE_FILES = [
    "evidence/unit_tests.xml",
    "evidence/security_tests.xml",
]

# Extended evidence (validated only with --require-all): artifacts produced by
# optional scanner jobs. Not required by the P3E CI pipeline, but enforced when
# a pipeline opts into deeper scanning.
EXTENDED_JUNIT_FILES = [
    "evidence/integration_tests.xml",
]

EXTENDED_JSON_VALIDATORS = [
    ("evidence/bandit.json", "validate_bandit_json"),
    ("evidence/semgrep.json", "validate_semgrep_json"),
    ("evidence/pip_audit.json", "validate_pip_audit_json"),
]

CRITICAL_SEVERITY_KEYWORDS = ["CRITICAL", "HIGH", "ERROR"]


def check_file_exists(filepath: str) -> Tuple[bool, str]:
    """Check if a file exists and is non-empty."""
    path = Path(filepath)
    if not path.exists():
        return False, f"Missing: {filepath}"
    if path.stat().st_size == 0:
        return False, f"Empty: {filepath}"
    return True, f"OK: {filepath}"


def validate_junit_xml(filepath: str, min_tests: int = 1) -> Tuple[bool, str]:
    """Validate JUnit XML has required test counts."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        # Handle both testsuites and testsuite root elements
        if root.tag == "testsuites":
            total_tests = sum(int(ts.get("tests", 0)) for ts in root.findall("testsuite"))
            total_failures = sum(int(ts.get("failures", 0)) for ts in root.findall("testsuite"))
            total_errors = sum(int(ts.get("errors", 0)) for ts in root.findall("testsuite"))
        else:
            total_tests = int(root.get("tests", 0))
            total_failures = int(root.get("failures", 0))
            total_errors = int(root.get("errors", 0))

        if total_tests < min_tests:
            return False, f"{filepath}: Only {total_tests} tests (minimum {min_tests})"
        if total_failures > 0:
            return False, f"{filepath}: {total_failures} test failures"
        if total_errors > 0:
            return False, f"{filepath}: {total_errors} test errors"

        return True, f"{filepath}: {total_tests} tests, {total_failures} failures, {total_errors} errors"

    except ET.ParseError as e:
        return False, f"{filepath}: Invalid XML - {e}"
    except Exception as e:
        return False, f"{filepath}: Validation error - {e}"


def validate_bandit_json(filepath: str) -> Tuple[bool, str]:
    """Validate Bandit JSON has no CRITICAL findings."""
    try:
        with open(filepath) as f:
            data = json.load(f)

        results = data.get("results", [])
        critical_findings = []

        for result in results:
            severity = result.get("issue_severity", "").upper()
            if severity in ("CRITICAL", "HIGH"):
                critical_findings.append({
                    "file": result.get("filename"),
                    "line": result.get("line_number"),
                    "issue": result.get("issue_text"),
                    "severity": severity
                })

        if critical_findings:
            msg = f"{filepath}: {len(critical_findings)} CRITICAL/HIGH findings:\n"
            for f in critical_findings[:5]:  # Show first 5
                msg += f"  {f['file']}:{f['line']} - {f['issue']} ({f['severity']})\n"
            return False, msg

        return True, f"{filepath}: No CRITICAL/HIGH findings"

    except json.JSONDecodeError as e:
        return False, f"{filepath}: Invalid JSON - {e}"
    except Exception as e:
        return False, f"{filepath}: Validation error - {e}"


def validate_semgrep_json(filepath: str) -> Tuple[bool, str]:
    """Validate Semgrep JSON has no CRITICAL findings."""
    try:
        with open(filepath) as f:
            data = json.load(f)

        results = data.get("results", [])
        critical_findings = []

        for result in results:
            severity = result.get("extra", {}).get("severity", "").upper()
            if severity in ("CRITICAL", "HIGH", "ERROR"):
                critical_findings.append({
                    "file": result.get("path"),
                    "line": result.get("start", {}).get("line"),
                    "rule": result.get("check_id"),
                    "message": result.get("extra", {}).get("message"),
                    "severity": severity
                })

        if critical_findings:
            msg = f"{filepath}: {len(critical_findings)} CRITICAL/HIGH/ERROR findings:\n"
            for f in critical_findings[:5]:
                msg += f"  {f['file']}:{f['line']} - {f['message']} ({f['severity']})\n"
            return False, msg

        return True, f"{filepath}: No CRITICAL/HIGH/ERROR findings"

    except json.JSONDecodeError as e:
        return False, f"{filepath}: Invalid JSON - {e}"
    except Exception as e:
        return False, f"{filepath}: Validation error - {e}"


def validate_pip_audit_json(filepath: str) -> Tuple[bool, str]:
    """Validate pip-audit JSON has no vulnerabilities."""
    try:
        with open(filepath) as f:
            data = json.load(f)

        # pip-audit returns a list of vulnerabilities
        vulns = data if isinstance(data, list) else data.get("vulnerabilities", [])

        if vulns:
            msg = f"{filepath}: {len(vulns)} vulnerabilities found:\n"
            for v in vulns[:5]:
                pkg = v.get("package", "unknown")
                vuln_id = v.get("id", "unknown")
                msg += f"  {pkg}: {vuln_id}\n"
            return False, msg

        return True, f"{filepath}: No vulnerabilities found"

    except json.JSONDecodeError as e:
        return False, f"{filepath}: Invalid JSON - {e}"
    except Exception as e:
        return False, f"{filepath}: Validation error - {e}"


def compute_sha256(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    import hashlib
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Verify CI/CD evidence artifacts (GNW fail-closed gate). "
            "Requires JUnit XML evidence with >0 tests and 0 failures/errors; "
            "exits non-zero on any failure."
        )
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Also require extended evidence (integration tests, bandit, semgrep, pip-audit)",
    )
    parser.add_argument("--min-tests", type=int, default=1, help="Minimum tests in each JUnit XML")
    args = parser.parse_args()

    print("=" * 60)
    print("GNW Evidence Verification")
    print("=" * 60)

    # Build the validator workload: required JUnit XMLs always, extended
    # evidence only when --require-all is set.
    junit_files = list(REQUIRED_EVIDENCE_FILES)
    json_checks = []
    if args.require_all:
        junit_files.extend(EXTENDED_JUNIT_FILES)
        json_checks = [
            (validate_bandit_json, "evidence/bandit.json"),
            (validate_semgrep_json, "evidence/semgrep.json"),
            (validate_pip_audit_json, "evidence/pip_audit.json"),
        ]
    all_paths = junit_files + [path for _, path in json_checks]

    all_passed = True

    # Check required files exist
    print("\n[1/4] Checking evidence file existence...")
    for filepath in all_paths:
        passed, msg = check_file_exists(filepath)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {msg}")
        if not passed:
            all_passed = False

    # Validate JUnit XML evidence
    print("\n[2/4] Validating JUnit XML evidence...")
    for filepath in junit_files:
        passed, msg = validate_junit_xml(filepath, args.min_tests)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {msg}")
        if not passed:
            all_passed = False

    # Validate security scan JSON evidence (extended mode only)
    if json_checks:
        print("\n[3/4] Validating security scan evidence...")
        for validator, filepath in json_checks:
            passed, msg = validator(filepath)
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {msg}")
            if not passed:
                all_passed = False
    else:
        print("\n[3/4] Skipping security scan evidence (not required in this mode)")

    # Compute hashes for audit trail
    print("\n[4/4] Computing evidence hashes for audit trail...")
    for filepath in all_paths:
        if Path(filepath).exists():
            hash_val = compute_sha256(filepath)
            print(f"  {filepath}: sha256:{hash_val}")

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL EVIDENCE GATES PASSED")
        print("=" * 60)
        return 0
    else:
        print("EVIDENCE VERIFICATION FAILED - FAIL-CLOSED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())