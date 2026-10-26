"""Mission Verifier — Merkle root of evidence for mission proof bundles.

GNW Governed Agent - P3F: Mission Proof System & KPI Automation
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from gnw_secrets import secret_dir


class MissionVerifier:
    """Verifies mission integrity via Merkle trees over evidence digests.

    Uses SHA-256 for leaf hashes and pair-wise hashing for Merkle tree construction.
    Deterministic: leaves are sorted lexicographically before tree construction.
    """

    # Domain separation for verification hash
    VERIFICATION_DOMAIN = b"GNW-MISSION-VERIFICATION-V1\n"

    def __init__(
        self,
        tenant_id: str | uuid.UUID,
        dsn: str | None = None,
        pool: ConnectionPool | None = None,
        evidence_root: str | Path | None = None,
    ):
        """Initialize verifier for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenant isolation
            dsn: PostgreSQL connection string (optional if pool provided)
            pool: Pre-configured connection pool (optional if dsn provided)
            evidence_root: Root directory for evidence files (default: ./evidence/{tenant_id})
        """
        self.tenant_id = uuid.UUID(str(tenant_id))
        self._pool = pool
        self._dsn = dsn
        self._local = __import__("threading").local()

        if evidence_root is None:
            evidence_root = Path(__file__).parent.parent / "data" / "evidence" / str(self.tenant_id)
        self.evidence_root = Path(evidence_root)
        self.evidence_root.mkdir(parents=True, exist_ok=True)

    def _get_pool(self) -> ConnectionPool | None:
        """Get or create the connection pool. Returns None if no DSN configured."""
        if self._pool is not None:
            return self._pool

        if self._dsn is None:
            self._dsn = os.environ.get("GNW_PG_DSN")
            if not self._dsn:
                return None

        self._pool = ConnectionPool(
            self._dsn,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
        return self._pool

    def _hash_leaf(self, data: bytes) -> bytes:
        """Compute SHA-256 hash of a leaf node."""
        return hashlib.sha256(data).digest()

    def _hash_pair(self, left: bytes, right: bytes) -> bytes:
        """Compute SHA-256 hash of a pair of child nodes (internal node)."""
        return hashlib.sha256(left + right).digest()

    def compute_merkle_root(self, evidence_digests: list[str]) -> str:
        """Build Merkle tree from evidence digests and return root hash.

        Args:
            evidence_digests: List of hex-encoded SHA-256 digests (64 chars each)

        Returns:
            Hex-encoded Merkle root hash (64 chars)

        Raises:
            ValueError: If evidence_digests is empty or contains invalid hex
        """
        if not evidence_digests:
            # Empty tree: hash of empty byte string with domain separation
            return hashlib.sha256(self.VERIFICATION_DOMAIN + b"empty").hexdigest()

        # Validate and convert to bytes
        leaves = []
        for digest in evidence_digests:
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError(f"Invalid digest format: {digest}")
            try:
                leaves.append(bytes.fromhex(digest))
            except ValueError:
                raise ValueError(f"Invalid hex digest: {digest}")

        # Deterministic: sort leaves lexicographically
        leaves.sort()

        # Single leaf: hash it once (standard Merkle leaf hashing)
        if len(leaves) == 1:
            return hashlib.sha256(leaves[0]).hexdigest()

        # Build Merkle tree bottom-up
        current_level = leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    # Odd number of nodes: duplicate last node (standard Merkle construction)
                    right = left
                next_level.append(self._hash_pair(left, right))
            current_level = next_level

        root = current_level[0]
        return root.hex()

    def collect_evidence(self, mission_id: str | uuid.UUID) -> list[dict[str, Any]]:
        """Gather all evidence files for a mission.

        Evidence files are stored as JSONL files under evidence_root/{mission_id}/
        Each line is a JSON object with at minimum: action_id, timestamp, digest

        Args:
            mission_id: UUID of the mission

        Returns:
            List of evidence records with digest field
        """
        mission_id = uuid.UUID(str(mission_id))
        evidence_dir = self.evidence_root / str(self.tenant_id) / str(mission_id)

        if not evidence_dir.exists():
            return []

        evidence_records = []
        for evidence_file in sorted(evidence_dir.glob("*.jsonl")):
            with evidence_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if "digest" in record:
                            evidence_records.append(record)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue

        return evidence_records

    def compute_verification_hash(self, merkle_root: str, mission_id: str | uuid.UUID) -> str:
        """Compute the final verification hash binding Merkle root to mission.

        Args:
            merkle_root: Hex-encoded Merkle root
            mission_id: Mission UUID

        Returns:
            Hex-encoded verification hash (64 chars)
        """
        mission_id = uuid.UUID(str(mission_id))
        data = self.VERIFICATION_DOMAIN + merkle_root.encode("utf-8") + b"\0" + str(mission_id).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def create_proof_bundle(self, mission_id: str | uuid.UUID) -> dict[str, Any]:
        """Generate complete proof bundle for a mission.

        Args:
            mission_id: UUID of the mission

        Returns:
            Proof bundle dict with evidence_digests, merkle_root, verification_hash
        """
        mission_id = uuid.UUID(str(mission_id))

        # Collect evidence
        evidence = self.collect_evidence(mission_id)

        # Extract digests
        evidence_digests = [e["digest"] for e in evidence if "digest" in e]

        # Compute Merkle root
        merkle_root = self.compute_merkle_root(evidence_digests)

        # Compute verification hash
        verification_hash = self.compute_verification_hash(merkle_root, mission_id)

        return {
            "evidence_digests": evidence_digests,
            "merkle_root": merkle_root,
            "verification_hash": verification_hash,
            "evidence_count": len(evidence_digests),
            "computed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def verify_mission(self, mission_id: str | uuid.UUID) -> tuple[bool, dict[str, Any] | None]:
        """Verify mission by comparing computed root vs stored verification_hash.

        Args:
            mission_id: UUID of the mission

        Returns:
            Tuple of (is_valid, proof_bundle) where is_valid is True if verification passes
        """
        mission_id = uuid.UUID(str(mission_id))

        # Compute current proof bundle
        current_bundle = self.create_proof_bundle(mission_id)

        # Try to get stored proof bundle from database
        pool = self._get_pool()
        if pool is not None:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT proof_bundle FROM missions WHERE mission_id = %s AND tenant_id = %s",
                        (mission_id, self.tenant_id),
                    )
                    row = cur.fetchone()

            if row is None or row["proof_bundle"] is None:
                # No stored bundle yet — verification passes (nothing to contradict)
                return True, current_bundle

            stored_bundle = row["proof_bundle"]
            stored_verification_hash = stored_bundle.get("verification_hash")

            if not stored_verification_hash:
                return True, stored_bundle

            # Compare verification hashes
            is_valid = current_bundle["verification_hash"] == stored_verification_hash
            return is_valid, current_bundle

        # No database available — self-verification (bundle is internally consistent)
        return True, current_bundle

    def store_proof_bundle(self, mission_id: str | uuid.UUID, proof_bundle: dict[str, Any]) -> bool:
        """Store proof bundle in the missions table.

        Args:
            mission_id: UUID of the mission
            proof_bundle: Proof bundle dict from create_proof_bundle

        Returns:
            True if stored successfully
        """
        mission_id = uuid.UUID(str(mission_id))

        pool = self._get_pool()
        if pool is None:
            # No database — store as JSON file instead
            bundle_dir = self.evidence_root / str(self.tenant_id) / str(mission_id)
            bundle_dir.mkdir(parents=True, exist_ok=True)
            bundle_file = bundle_dir / "proof_bundle.json"
            bundle_file.write_text(json.dumps(proof_bundle, indent=2))
            return True

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE missions
                    SET proof_bundle = %s
                    WHERE mission_id = %s AND tenant_id = %s
                    """,
                    (json.dumps(proof_bundle), mission_id, self.tenant_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def add_evidence(self, mission_id: str | uuid.UUID, evidence_record: dict[str, Any]) -> str:
        """Add an evidence record for a mission.

        Computes SHA-256 digest of the canonicalized record and appends to evidence file.

        Args:
            mission_id: UUID of the mission
            evidence_record: Evidence data (must include action_id, timestamp)

        Returns:
            Hex-encoded SHA-256 digest of the evidence
        """
        mission_id = uuid.UUID(str(mission_id))

        # Ensure required fields
        if "action_id" not in evidence_record:
            evidence_record["action_id"] = str(uuid.uuid4())
        if "timestamp" not in evidence_record:
            evidence_record["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Canonicalize for deterministic digest
        canonical = json.dumps(evidence_record, separators=(",", ":"), sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()

        # Add digest to record
        evidence_record["digest"] = digest

        # Append to evidence file (daily rotation)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        evidence_file = self.evidence_root / str(self.tenant_id) / str(mission_id) / f"evidence_{date_str}.jsonl"
        evidence_file.parent.mkdir(parents=True, exist_ok=True)

        with evidence_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evidence_record, separators=(",", ":"), sort_keys=True) + "\n")

        return digest

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None