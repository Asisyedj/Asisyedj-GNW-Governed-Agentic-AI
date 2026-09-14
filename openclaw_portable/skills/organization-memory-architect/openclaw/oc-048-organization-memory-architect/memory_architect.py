"""
Organization Memory Architect (OC-048) — Core Implementation
=============================================================
Production-grade organizational memory system.
"""

import asyncio
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────

class Scope(Enum):
    PERSONAL = "personal"
    TEAM = "team"
    ORGANIZATION = "organization"
    PUBLIC = "public"


class MemoryTier(Enum):
    WORKING = 1      # 5 min TTL
    SHORT = 2        # 1 hour TTL
    MEDIUM = 3       # 24 hour TTL
    LONG = 4         # 7 day TTL
    ARCHIVE = 5      # No TTL


@dataclass
class MemoryEntry:
    key: str
    value: Any
    scope: str
    tier: int
    created_at: str
    updated_at: str
    access_count: int = 0
    last_accessed: str = ""
    tags: List[str] = field(default_factory=list)
    ttl: Optional[int] = None
    checksum: str = ""
    size_bytes: int = 0
    version: int = 1
    
    def __post_init__(self):
        if not self.size_bytes:
            self.size_bytes = len(json.dumps(self.value, default=str).encode())
        if not self.checksum:
            self.checksum = self._compute_checksum()
    
    def _compute_checksum(self) -> str:
        # Cover the complete canonical entry except the checksum itself.
        payload = asdict(self)
        payload.pop("checksum", None)
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def is_stale(self, staleness_days: int = 30) -> bool:
        if not self.ttl:
            return False
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(self.updated_at)).days
        return age > staleness_days
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryEntry":
        return cls(**data)


@dataclass
class SearchResult:
    entry: MemoryEntry
    score: float
    match_type: str  # "keyword", "semantic", "tag", "exact"
    highlights: List[str] = field(default_factory=list)


@dataclass
class HealthReport:
    total_entries: int
    total_size_bytes: int
    by_tier: Dict[int, int]
    by_scope: Dict[str, int]
    stale_entries: int
    corrupted_entries: int
    last_compaction: Optional[str]
    integrity_score: float
    generated_at: str


# ──────────────────────────────────────────────────────────────
# SECURITY
# ──────────────────────────────────────────────────────────────

class SecretScanner:
    """Scan for secrets in memory content."""
    
    PATTERNS = [
        (r"(api[_-]?key|apikey|api[_-]?token|access[_-]?token|auth[_-]?token|secret|password|passwd|pwd|private[_-]?key|ssh[_-]?key)\s*[:=]\s*['\"]?([^\s'\"]{8,})", "CREDENTIAL"),
        (r"(sk-[a-zA-Z0-9]{20,})", "OPENAI_KEY"),
        (r"(ghp_[a-zA-Z0-9]{36,})", "GITHUB_TOKEN"),
        (r"(xox[baprs]-[a-zA-Z0-9-]{10,})", "SLACK_TOKEN"),
        (r"(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})", "JWT_TOKEN"),
        (r"(AKIA[0-9A-Z]{16})", "AWS_ACCESS_KEY"),
        (r"(AIza[0-9A-Za-z_-]{35})", "GOOGLE_API_KEY"),
        (r"(-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----)", "PRIVATE_KEY"),
        (r"(https?://[^\s]+:[^\s]+@)", "URL_WITH_CREDENTIALS"),
        (r"(\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b)", "CREDIT_CARD"),
    ]
    
    def __init__(self):
        self.compiled = [(re.compile(p, re.IGNORECASE), name) for p, name in self.PATTERNS]
    
    def scan(self, text: str) -> List[Dict]:
        """Scan text for secrets. Returns list of findings."""
        findings = []
        for pattern, secret_type in self.compiled:
            for match in pattern.finditer(text):
                findings.append({
                    "type": secret_type,
                    "match": "[REDACTED]",
                    "position": match.start(),
                    "severity": "high" if "KEY" in secret_type or "TOKEN" in secret_type else "medium"
                })
        return findings
    
    def has_secrets(self, text: str) -> bool:
        """Quick check if text contains secrets."""
        return len(self.scan(text)) > 0
    
    def redact(self, text: str) -> str:
        """Redact secrets from text."""
        for pattern, secret_type in self.compiled:
            text = pattern.sub(f"[REDACTED:{secret_type}]", text)
        return text


class ScopeGuard:
    """Enforce scope isolation."""
    
    HIERARCHY = {
        "personal": 0,
        "team": 1,
        "organization": 2,
        "public": 3
    }
    
    @classmethod
    def can_access(cls, entry_scope: str, request_scope: str) -> bool:
        """Check if requester can access entry scope."""
        if entry_scope not in cls.HIERARCHY or request_scope not in cls.HIERARCHY:
            return False
        entry_level = cls.HIERARCHY[entry_scope]
        request_level = cls.HIERARCHY[request_scope]
        
        # Can access same level or lower
        return request_level >= entry_level
    
    @classmethod
    def filter_results(cls, results: List[SearchResult], request_scope: str) -> List[SearchResult]:
        """Filter search results by scope."""
        return [r for r in results if cls.can_access(r.entry.scope, request_scope)]


# ──────────────────────────────────────────────────────────────
# STORAGE
# ──────────────────────────────────────────────────────────────

class AtomicStorage:
    """Atomic file I/O with backup rotation."""
    
    def __init__(self, base_path: Path, backup_retention: int = 5):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.backup_retention = backup_retention
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _safe_path(self, filename: str) -> Path:
        """Return a path contained by base_path; reject traversal/symlinks."""
        if not isinstance(filename, str) or not filename or Path(filename).is_absolute():
            raise ValueError("storage filename must be a non-empty relative path")
        filepath = self.base_path / filename
        base = self.base_path.resolve()
        resolved = filepath.resolve()
        try:
            contained = os.path.commonpath((str(base), str(resolved))) == str(base)
        except ValueError:
            contained = False
        if not contained:
            raise ValueError("storage path escapes the configured storage directory")
        return filepath
    
    async def write(self, filename: str, data: str) -> Path:
        """Write file atomically with backup."""
        filepath = self._safe_path(filename)
        
        async with self._get_lock(str(filepath)):
            # Backup existing
            if filepath.exists():
                await self._rotate_backup(filepath)
            
            # Write to temp then rename
            temp_fd, temp_path = tempfile.mkstemp(dir=str(self.base_path), prefix=".tmp_")
            try:
                with os.fdopen(temp_fd, "w") as f:
                    f.write(data)
                
                # Atomic rename
                shutil.move(temp_path, str(filepath))
            except:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        
        return filepath
    
    async def read(self, filename: str) -> Optional[str]:
        """Read file."""
        filepath = self._safe_path(filename)
        if not filepath.exists():
            return None
        
        async with self._get_lock(str(filepath)):
            with open(filepath) as f:
                return f.read()
    
    async def _rotate_backup(self, filepath: Path):
        """Rotate backup files."""
        for i in range(self.backup_retention - 1, 0, -1):
            old_backup = filepath.with_suffix(f".bak{i}")
            new_backup = filepath.with_suffix(f".bak{i+1}")
            if old_backup.exists():
                shutil.move(str(old_backup), str(new_backup))
        
        # Create new backup
        backup_path = filepath.with_suffix(".bak1")
        shutil.copy2(str(filepath), str(backup_path))
    
    async def delete(self, filename: str):
        """Delete file and backups."""
        filepath = self._safe_path(filename)
        
        async with self._get_lock(str(filepath)):
            if filepath.exists():
                filepath.unlink()
            
            for i in range(1, self.backup_retention + 1):
                backup = filepath.with_suffix(f".bak{i}")
                if backup.exists():
                    backup.unlink()


# ──────────────────────────────────────────────────────────────
# SEARCH
# ──────────────────────────────────────────────────────────────

class KeywordSearch:
    """Weighted keyword search."""
    
    WEIGHTS = {
        "exact_key": 10.0,
        "partial_key": 5.0,
        "tag": 3.0,
        "value": 1.0,
    }
    
    def search(self, entries: List[MemoryEntry], query: str) -> List[SearchResult]:
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        for entry in entries:
            score = 0.0
            highlights = []
            
            # Exact key match
            if entry.key.lower() == query_lower:
                score += self.WEIGHTS["exact_key"]
                highlights.append(f"exact_key:{entry.key}")
            
            # Partial key match
            elif query_lower in entry.key.lower():
                score += self.WEIGHTS["partial_key"]
                highlights.append(f"partial_key:{entry.key}")
            
            # Tag match
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += self.WEIGHTS["tag"]
                    highlights.append(f"tag:{tag}")
            
            # Value match
            value_str = json.dumps(entry.value, default=str).lower()
            for term in query_terms:
                if term in value_str:
                    score += self.WEIGHTS["value"]
                    highlights.append(f"value_match:{term}")
            
            if score > 0:
                results.append(SearchResult(
                    entry=entry,
                    score=score,
                    match_type="keyword",
                    highlights=highlights
                ))
        
        return sorted(results, key=lambda r: r.score, reverse=True)


class SemanticSearch:
    """TF-IDF cosine similarity search."""
    
    def __init__(self):
        self.vocabulary: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self._fitted = False
    
    def fit(self, documents: List[str]):
        """Fit TF-IDF on documents."""
        import math
        
        # Build vocabulary
        all_terms = set()
        for doc in documents:
            terms = self._tokenize(doc)
            all_terms.update(terms)
        
        self.vocabulary = {term: i for i, term in enumerate(sorted(all_terms))}
        
        # Compute IDF
        n_docs = len(documents)
        for term in self.vocabulary:
            doc_count = sum(1 for doc in documents if term in self._tokenize(doc))
            self.idf[term] = math.log(n_docs / (1 + doc_count))
        
        self._fitted = True
    
    def search(self, entries: List[MemoryEntry], query: str, top_k: int = 10) -> List[SearchResult]:
        if not self._fitted:
            return []
        
        import math
        
        query_vec = self._vectorize(query)
        results = []
        
        for entry in entries:
            doc = f"{entry.key} {' '.join(entry.tags)} {json.dumps(entry.value, default=str)}"
            doc_vec = self._vectorize(doc)
            
            similarity = self._cosine_similarity(query_vec, doc_vec)
            
            if similarity > 0.1:  # Threshold
                results.append(SearchResult(
                    entry=entry,
                    score=similarity * 10,  # Scale to comparable with keyword
                    match_type="semantic",
                    highlights=[f"similarity:{similarity:.2f}"]
                ))
        
        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        return re.findall(r'\b\w+\b', text.lower())
    
    def _vectorize(self, text: str) -> Dict[int, float]:
        """Convert text to TF-IDF vector."""
        terms = self._tokenize(text)
        vec = {}
        
        for term in terms:
            if term in self.vocabulary:
                idx = self.vocabulary[term]
                tf = terms.count(term) / len(terms)
                idf = self.idf.get(term, 0)
                vec[idx] = tf * idf
        
        return vec
    
    def _cosine_similarity(self, vec1: Dict[int, float], vec2: Dict[int, float]) -> float:
        """Compute cosine similarity between sparse vectors."""
        import math
        
        dot = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in set(vec1) | set(vec2))
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot / (mag1 * mag2)


class HybridSearch:
    """Combined keyword + semantic search."""
    
    def __init__(self):
        self.keyword = KeywordSearch()
        self.semantic = SemanticSearch()
    
    def fit(self, entries: List[MemoryEntry]):
        """Fit semantic search on entries."""
        documents = [
            f"{e.key} {' '.join(e.tags)} {json.dumps(e.value, default=str)}"
            for e in entries
        ]
        self.semantic.fit(documents)
    
    def search(self, entries: List[MemoryEntry], query: str, top_k: int = 10) -> List[SearchResult]:
        """Hybrid search with combined ranking."""
        keyword_results = self.keyword.search(entries, query)
        semantic_results = self.semantic.search(entries, query, top_k * 2)
        
        # Merge by key
        merged: Dict[str, SearchResult] = {}
        
        for result in keyword_results:
            merged[result.entry.key] = result
        
        for result in semantic_results:
            if result.entry.key in merged:
                # Boost existing
                merged[result.entry.key].score += result.score * 0.5
                merged[result.entry.key].match_type = "hybrid"
            else:
                merged[result.entry.key] = result
        
        return sorted(merged.values(), key=lambda r: r.score, reverse=True)[:top_k]


# ──────────────────────────────────────────────────────────────
# CORE MEMORY ARCHITECT
# ──────────────────────────────────────────────────────────────

class MemoryArchitect:
    """Organization Memory Architect — production implementation."""
    
    TIER_TTLS = {
        MemoryTier.WORKING: 300,      # 5 min
        MemoryTier.SHORT: 3600,       # 1 hour
        MemoryTier.MEDIUM: 86400,     # 24 hours
        MemoryTier.LONG: 604800,      # 7 days
        MemoryTier.ARCHIVE: None,     # Permanent
    }
    
    def __init__(
        self,
        storage_path: str = "~/.openclaw/memory",
        scopes: List[str] = None,
        backup_retention: int = 5,
        compaction_threshold: int = 1000,
        staleness_days: int = 30
    ):
        self.storage_path = Path(storage_path).expanduser()
        self.storage = AtomicStorage(self.storage_path, backup_retention)
        self.scopes = scopes or ["personal", "team", "organization", "public"]
        self.compaction_threshold = compaction_threshold
        self.staleness_days = staleness_days
        
        # Security
        self.scanner = SecretScanner()
        self.scope_guard = ScopeGuard()
        
        # Search
        self.search_engine = HybridSearch()
        
        # In-memory cache
        self._cache: Dict[str, MemoryEntry] = {}
        self._cache_loaded = False
        self._corrupted_entries = 0
        
        # Audit
        self.audit_log: List[Dict] = []
        
        # Stats
        self.stats = {
            "captures": 0,
            "retrievals": 0,
            "searches": 0,
            "compactions": 0,
            "secrets_blocked": 0,
        }
    
    async def initialize(self):
        """Load memory from disk."""
        await self._load_all()
        self._fit_search()
    
    def _validate_scope(self, scope: Optional[str]) -> bool:
        return isinstance(scope, str) and scope in self.scopes and scope in ScopeGuard.HIERARCHY

    @staticmethod
    def _filename_for_key(key: str) -> str:
        # Do not derive paths from user-controlled key characters; the digest
        # also prevents slash/underscore collisions.
        digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        return f"entry-{digest}.json"

    def _entry_payload(self, entry: MemoryEntry) -> str:
        return json.dumps(entry.to_dict(), sort_keys=True, separators=(",", ":"), default=str)

    def _entry_is_intact_and_safe(self, entry: MemoryEntry) -> bool:
        return entry._compute_checksum() == entry.checksum and not self.scanner.has_secrets(self._entry_payload(entry))

    async def capture(
        self,
        key: str,
        value: Any,
        scope: str = "personal",
        tier: int = 2,
        tags: List[str] = None,
        ttl: int = None
    ) -> Dict:
        """Capture a memory entry."""
        
        # Captures accept only known, configured scopes.
        if not self._validate_scope(scope):
            return {"success": False, "error": f"Invalid scope: {scope}. Must be one of {self.scopes}"}
        try:
            tier_enum = MemoryTier(tier)
        except (ValueError, TypeError):
            return {"success": False, "error": "Invalid tier. Must be an integer from 1 to 5."}
        
        # Scan the complete canonical entry, including key and metadata. Do not
        # include matched secret material in the response or audit log.
        value_str = json.dumps(value, default=str)
        candidate = {
            "key": key, "value": value, "scope": scope, "tier": tier,
            "tags": tags or [], "ttl": ttl,
        }
        canonical = json.dumps(candidate, sort_keys=True, default=str)
        if self.scanner.has_secrets(canonical):
            self.stats["secrets_blocked"] += 1
            self._audit("capture_blocked", "system", self.scanner.redact(str(key)), "secret_detected")
            return {
                "success": False,
                "error": "Secret detected in entry. Use secure storage instead.",
                "secrets_found": self.scanner.scan(canonical)
            }
        
        # Create entry
        now = datetime.now(timezone.utc).isoformat()
        entry = MemoryEntry(
            key=key,
            value=value,
            scope=scope,
            tier=tier,
            created_at=now,
            updated_at=now,
            last_accessed=now,
            tags=tags or [],
            ttl=ttl if ttl is not None else self.TIER_TTLS.get(tier_enum)
        )
        
        # Store
        self._cache[key] = entry
        await self._save_entry(entry)
        
        self.stats["captures"] += 1
        self._audit("capture", "user", key, "success", {"scope": scope, "tier": tier})
        
        return {"success": True, "key": key, "checksum": entry.checksum}
    
    async def retrieve(self, key: str, scope: str = None) -> Optional[Any]:
        """Retrieve a memory entry using an explicit, known scope."""
        if not self._validate_scope(scope):
            self._audit("retrieve_denied", "user", self.scanner.redact(str(key)), "invalid_scope")
            return None
        entry = self._cache.get(key)
        
        if not entry:
            # Try loading from disk
            entry = await self._load_entry(key)
        
        if not entry or not self._entry_is_intact_and_safe(entry):
            return None
        
        # Scope check
        if not self.scope_guard.can_access(entry.scope, scope):
            self._audit("retrieve_denied", "user", key, "scope_violation", {
                "entry_scope": entry.scope,
                "request_scope": scope
            })
            return None
        
        # TTL check
        if entry.ttl:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(entry.updated_at)).total_seconds()
            if age > entry.ttl:
                # Promote in place. The former capture-then-delete sequence
                # deleted the newly promoted entry because both used the key.
                if entry.tier < 5:
                    entry.tier += 1
                    entry.ttl = self.TIER_TTLS.get(MemoryTier(entry.tier))
                    entry.updated_at = datetime.now(timezone.utc).isoformat()
                    await self._save_entry(entry)
                    self._cache[key] = entry
                else:
                    await self._delete_entry(key)
                return None
        
        # Update access
        entry.access_count += 1
        entry.last_accessed = datetime.now(timezone.utc).isoformat()
        await self._save_entry(entry)
        
        self.stats["retrievals"] += 1
        return entry.value
    
    async def search(
        self,
        query: str,
        scope: str = None,
        limit: int = 10,
        strategy: str = "hybrid"
    ) -> List[Dict]:
        """Search memory using an explicit, known scope."""
        if not self._validate_scope(scope):
            self._audit("search_denied", "user", "memory", "invalid_scope")
            return []
        entries = [e for e in self._cache.values() if self._entry_is_intact_and_safe(e)]
        
        # Filter by scope
        entries = [e for e in entries if self.scope_guard.can_access(e.scope, scope)]
        
        # Search
        if strategy == "keyword":
            results = self.search_engine.keyword.search(entries, query)
        elif strategy == "semantic":
            results = self.search_engine.semantic.search(entries, query, limit)
        else:
            results = self.search_engine.search(entries, query, limit)
        
        self.stats["searches"] += 1
        
        return [
            {
                "key": r.entry.key,
                "value": r.entry.value,
                "scope": r.entry.scope,
                "score": r.score,
                "match_type": r.match_type,
                "tags": r.entry.tags,
                "updated_at": r.entry.updated_at,
            }
            for r in results[:limit]
        ]
    
    async def compact(self, dry_run: bool = False) -> Dict:
        """Compact memory by summarizing stale entries."""
        entries = list(self._cache.values())
        
        # Find stale entries
        stale = [e for e in entries if e.is_stale(self.staleness_days)]
        
        if len(stale) < self.compaction_threshold and not dry_run:
            return {
                "success": False,
                "message": f"Only {len(stale)} stale entries, threshold is {self.compaction_threshold}",
                "stale_count": len(stale)
            }
        
        # Group by tags for summarization
        groups: Dict[str, List[MemoryEntry]] = {}
        for entry in stale:
            key = entry.tags[0] if entry.tags else "untagged"
            if key not in groups:
                groups[key] = []
            groups[key].append(entry)
        
        # Summarize groups
        compacted = []
        for tag, group_entries in groups.items():
            summary = {
                "type": "compacted_summary",
                "original_count": len(group_entries),
                "keys": [e.key for e in group_entries],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "summary": f"Compacted {len(group_entries)} entries tagged '{tag}'",
            }
            compacted.append(summary)
            
            if not dry_run:
                # Archive originals
                for entry in group_entries:
                    await self._archive_entry(entry)
                
                # Store summary
                await self.capture(
                    key=f"compacted:{tag}:{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                    value=summary,
                    scope="organization",
                    tier=5,
                    tags=["compacted", tag]
                )
        
        self.stats["compactions"] += 1
        self._audit("compact", "system", "memory", "success", {
            "stale_processed": len(stale),
            "groups_created": len(groups),
            "dry_run": dry_run
        })
        
        return {
            "success": True,
            "stale_processed": len(stale),
            "groups": len(groups),
            "compacted": compacted,
            "dry_run": dry_run
        }
    
    async def health(self) -> HealthReport:
        """Generate memory health report."""
        entries = list(self._cache.values())
        
        by_tier = {}
        by_scope = {}
        stale_count = 0
        corrupted = self._corrupted_entries
        total_size = 0
        
        for entry in entries:
            by_tier[entry.tier] = by_tier.get(entry.tier, 0) + 1
            by_scope[entry.scope] = by_scope.get(entry.scope, 0) + 1
            total_size += entry.size_bytes
            
            if entry.is_stale(self.staleness_days):
                stale_count += 1
            
            # Verify checksum
            if entry._compute_checksum() != entry.checksum or self.scanner.has_secrets(self._entry_payload(entry)):
                corrupted += 1
        
        integrity = 1.0 - (corrupted / len(entries)) if entries else 1.0
        
        return HealthReport(
            total_entries=len(entries),
            total_size_bytes=total_size,
            by_tier=by_tier,
            by_scope=by_scope,
            stale_entries=stale_count,
            corrupted_entries=corrupted,
            last_compaction=self._get_last_compaction(),
            integrity_score=integrity,
            generated_at=datetime.now(timezone.utc).isoformat()
        )
    
    async def _load_all(self):
        """Load all entries from disk."""
        for filepath in self.storage_path.glob("*.json"):
            if filepath.name.startswith(".tmp_"):
                continue
            
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    entry = MemoryEntry.from_dict(data)
                    if self._entry_is_intact_and_safe(entry):
                        self._cache[entry.key] = entry
                    else:
                        self._corrupted_entries += 1
            except Exception:
                self._corrupted_entries += 1
        
        self._cache_loaded = True
    
    async def _save_entry(self, entry: MemoryEntry):
        """Save entry to disk with a fresh complete-entry checksum."""
        entry.checksum = entry._compute_checksum()
        filename = self._filename_for_key(entry.key)
        await self.storage.write(filename, json.dumps(entry.to_dict(), indent=2, default=str))
    
    async def _load_entry(self, key: str) -> Optional[MemoryEntry]:
        """Load and verify one entry from disk."""
        filename = self._filename_for_key(key)
        data = await self.storage.read(filename)
        if not data:
            return None
        try:
            entry = MemoryEntry.from_dict(json.loads(data))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return entry if self._entry_is_intact_and_safe(entry) else None
    
    async def _delete_entry(self, key: str):
        """Delete entry from disk."""
        filename = self._filename_for_key(key)
        await self.storage.delete(filename)
        self._cache.pop(key, None)
    
    async def _archive_entry(self, entry: MemoryEntry):
        """Archive entry to tier 5."""
        entry.tier = 5
        entry.ttl = None
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        await self._save_entry(entry)
    
    def _fit_search(self):
        """Fit search engine on current entries."""
        self.search_engine.fit(list(self._cache.values()))
    
    def _audit(self, action: str, actor: str, target: str, result: str, metadata: Dict = None):
        """Log audit entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor": actor,
            "target": target,
            "result": result,
            "metadata": metadata or {},
            "audit_id": str(uuid.uuid4())[:8]
        }
        self.audit_log.append(entry)
    
    def _get_last_compaction(self) -> Optional[str]:
        """Get timestamp of last compaction."""
        for entry in reversed(self.audit_log):
            if entry["action"] == "compact":
                return entry["timestamp"]
        return None
    
    def get_stats(self) -> Dict:
        """Get usage statistics."""
        return {
            **self.stats,
            "cache_size": len(self._cache),
            "audit_entries": len(self.audit_log),
        }


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Organization Memory Architect")
    parser.add_argument("command", choices=["capture", "retrieve", "search", "compact", "health", "stats"])
    parser.add_argument("--key", help="Memory key")
    parser.add_argument("--value", help="Memory value (JSON)")
    parser.add_argument("--scope", default="personal", help="Scope")
    parser.add_argument("--tier", type=int, default=2, help="Memory tier (1-5)")
    parser.add_argument("--tags", nargs="*", help="Tags")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Result limit")
    parser.add_argument("--dry-run", action="store_true", help="Dry run compaction")
    parser.add_argument("--storage", default="~/.openclaw/memory", help="Storage path")
    
    args = parser.parse_args()
    
    architect = MemoryArchitect(storage_path=args.storage)
    await architect.initialize()
    
    if args.command == "capture":
        value = json.loads(args.value) if args.value else None
        result = await architect.capture(args.key, value, scope=args.scope, tier=args.tier, tags=args.tags)
        print(json.dumps(result, indent=2))
    
    elif args.command == "retrieve":
        result = await architect.retrieve(args.key, scope=args.scope)
        print(json.dumps({"key": args.key, "value": result}, indent=2, default=str))
    
    elif args.command == "search":
        results = await architect.search(args.query, scope=args.scope, limit=args.limit)
        print(json.dumps(results, indent=2, default=str))
    
    elif args.command == "compact":
        result = await architect.compact(dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
    
    elif args.command == "health":
        report = await architect.health()
        print(json.dumps(asdict(report), indent=2))
    
    elif args.command == "stats":
        print(json.dumps(architect.get_stats(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
