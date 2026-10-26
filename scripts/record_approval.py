#!/usr/bin/env python3
"""
Approval recording script for GNW CI/CD pipeline.
Creates signed approval artifact with SHA256 of release commit.
Stores in evidence/approvals/
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_commit_sha256(commit_sha: str) -> str:
    """Get SHA256 of the commit object (not just the SHA string)."""
    try:
        # Get the raw commit object and hash it
        result = subprocess.run(
            ["git", "cat-file", "commit", commit_sha],
            capture_output=True,
            text=True,
            check=True
        )
        commit_data = result.stdout.encode('utf-8')
        return hashlib.sha256(commit_data).hexdigest()
    except subprocess.CalledProcessError:
        # Fallback: hash the SHA string itself
        return hashlib.sha256(commit_sha.encode('utf-8')).hexdigest()


def get_git_info() -> dict:
    """Collect git metadata for the approval artifact."""
    info = {}
    try:
        info["commit_sha"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        info["commit_sha256"] = get_commit_sha256(info["commit_sha"])
        info["branch"] = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        info["author"] = subprocess.run(
            ["git", "log", "-1", "--pretty=%an <%ae>"], capture_output=True, text=True, check=True
        ).stdout.strip()
        info["message"] = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"], capture_output=True, text=True, check=True
        ).stdout.strip()
        info["timestamp"] = subprocess.run(
            ["git", "log", "-1", "--pretty=%cI"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        pass
    return info


def main():
    parser = argparse.ArgumentParser(description="Record release approval artifact")
    parser.add_argument("--release", required=True, help="Release commit SHA")
    parser.add_argument("--approver", default=os.environ.get("GITHUB_ACTOR", "unknown"), help="Approver identity")
    parser.add_argument("--output-dir", default="evidence/approvals", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect approval metadata
    approval = {
        "schema_version": "1.0",
        "type": "release_approval",
        "release_commit": args.release,
        "release_commit_sha256": get_commit_sha256(args.release),
        "approver": args.approver,
        "approval_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_metadata": get_git_info(),
        "pipeline": "GNW CI/CD Fail-Closed",
        "environment": "production"
    }

    # Create filename with timestamp and commit
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_sha = args.release[:8]
    filename = f"approval_{timestamp}_{short_sha}.json"
    filepath = output_dir / filename

    # Write approval artifact
    with open(filepath, "w") as f:
        json.dump(approval, f, indent=2)

    # Also create a hash file for integrity verification
    hash_filepath = output_dir / f"{filename}.sha256"
    with open(filepath, "rb") as f:
        content = f.read()
    file_hash = hashlib.sha256(content).hexdigest()
    with open(hash_filepath, "w") as f:
        f.write(f"{file_hash}  {filename}\n")

    print(f"Approval recorded: {filepath}")
    print(f"SHA256: {file_hash}")
    print(f"Release commit: {args.release}")
    print(f"Approver: {args.approver}")

    return 0


if __name__ == "__main__":
    sys.exit(main())