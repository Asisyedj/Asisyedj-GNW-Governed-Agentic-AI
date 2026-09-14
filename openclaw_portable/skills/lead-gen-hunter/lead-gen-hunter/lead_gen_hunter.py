#!/usr/bin/env python3
"""
Lead-Gen-Hunter: Autonomous Lead Discovery & Qualification System
Finds, scores, enriches, and imports high-intent leads into Client-Manager-Pro.
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set
from urllib.parse import quote_plus

import requests


# ============================================================
# Data Models
# ============================================================

@dataclass
class Lead:
    name: str
    id: Optional[int] = None
    title: str = ""
    company: str = ""
    email: str = ""
    email_status: str = "unknown"
    email_verified: bool = False
    phone: str = ""
    linkedin: str = ""
    linkedin_status: str = "unknown"
    twitter: str = ""
    github: str = ""
    source: str = ""
    source_url: str = ""
    raw_text: str = ""
    icp_score: float = 0.0
    intent_score: float = 0.0
    intent_signals: List[str] = field(default_factory=list)
    enriched: bool = False
    imported: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)


def neutralize_csv_cell(value: object) -> str:
    """Prevent spreadsheet formula interpretation in exported CSV values."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def safe_export_path(output_path: str, overwrite: bool = False) -> Path:
    """Validate a destination and refuse accidental overwrite or symlink traversal."""
    if not output_path or "\x00" in output_path:
        raise ValueError("output path must be a non-empty path")
    destination = Path(output_path).expanduser()
    if destination.exists() and destination.is_symlink():
        raise ValueError("refusing to export through a symlink")
    if destination.exists() and destination.is_dir():
        raise IsADirectoryError(str(destination))
    if destination.exists() and not overwrite:
        raise FileExistsError(f"export already exists: {destination}; pass overwrite=True to replace it")
    if not destination.parent.resolve().is_dir():
        raise FileNotFoundError(f"export directory does not exist: {destination.parent.resolve()}")
    return destination


def safe_input_path(input_path: str) -> Path:
    """Validate an input file without following a symlink or accepting a directory."""
    source = Path(input_path).expanduser()
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"input must be a regular, non-symlink file: {source}")
    return source


def validate_icp_config(config: object) -> Dict:
    if not isinstance(config, dict):
        raise ValueError("ICP config must be a JSON object")
    required = {"titles", "industries", "company_size", "location", "keywords"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"ICP config missing keys: {', '.join(sorted(missing))}")
    for key in ("titles", "industries", "location", "keywords"):
        if not isinstance(config[key], list) or not all(isinstance(v, str) for v in config[key]):
            raise ValueError(f"ICP config field {key!r} must be a list of strings")
    if "negative_keywords" in config and (not isinstance(config["negative_keywords"], list) or not all(isinstance(v, str) for v in config["negative_keywords"])):
        raise ValueError("ICP config field 'negative_keywords' must be a list of strings")
    size = config["company_size"]
    if not isinstance(size, dict) or not isinstance(size.get("min"), (int, float)) or not isinstance(size.get("max"), (int, float)):
        raise ValueError("ICP config company_size must contain numeric min and max")
    if size["min"] < 0 or size["max"] < size["min"]:
        raise ValueError("ICP config company_size bounds are invalid")
    return config


def validate_intent_config(config: object) -> List[Dict]:
    if not isinstance(config, list):
        raise ValueError("Intent config must be a JSON list")
    for rule in config:
        if not isinstance(rule, dict) or not isinstance(rule.get("pattern"), str) or not isinstance(rule.get("type"), str):
            raise ValueError("Each intent rule needs string pattern and type")
        if not isinstance(rule.get("weight"), (int, float)) or not 0 <= rule["weight"] <= 100:
            raise ValueError("Each intent rule weight must be between 0 and 100")
        try:
            re.compile(rule["pattern"])
        except re.error as exc:
            raise ValueError(f"Invalid intent rule regex: {exc}") from exc
    return config


# ============================================================
# Database
# ============================================================

class LeadDatabase:
    def __init__(self, path: str = "lead_hunter.db"):
        self.path = path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                title TEXT DEFAULT '',
                company TEXT DEFAULT '',
                email TEXT DEFAULT '',
                email_status TEXT DEFAULT 'unknown',
                email_verified INTEGER DEFAULT 0,
                phone TEXT DEFAULT '',
                linkedin TEXT DEFAULT '',
                linkedin_status TEXT DEFAULT 'unknown',
                twitter TEXT DEFAULT '',
                github TEXT DEFAULT '',
                source TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                raw_text TEXT DEFAULT '',
                icp_score REAL DEFAULT 0,
                intent_score REAL DEFAULT 0,
                intent_signals TEXT DEFAULT '[]',
                enriched INTEGER DEFAULT 0,
                imported INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(name, company, source)
            )
        """)
        # Migrate databases created by earlier versions without losing rows.
        existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        for column, definition in (("email_status", "TEXT DEFAULT 'unknown'"), ("email_verified", "INTEGER DEFAULT 0"), ("linkedin_status", "TEXT DEFAULT 'unknown'")):
            if column not in existing:
                conn.execute(f"ALTER TABLE leads ADD COLUMN {column} {definition}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                leads_found INTEGER DEFAULT 0,
                leads_qualified INTEGER DEFAULT 0,
                started_at TEXT NOT NULL,
                finished_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def insert_lead(self, lead: Lead) -> bool:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("""
                INSERT INTO leads (name, title, company, email, email_status, email_verified, phone, linkedin, linkedin_status,
                                   twitter, github, source, source_url, raw_text,
                                   icp_score, intent_score, intent_signals, enriched, imported, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead.name, lead.title, lead.company, lead.email, lead.email_status, int(lead.email_verified),
                lead.phone, lead.linkedin, lead.linkedin_status, lead.twitter, lead.github, lead.source,
                lead.source_url, lead.raw_text, lead.icp_score, lead.intent_score,
                json.dumps(lead.intent_signals), int(lead.enriched), int(lead.imported),
                lead.created_at
            ))
            conn.commit()
            lead.id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_qualified_leads(self, min_icp: float = 70, limit: int = 100) -> List[Lead]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM leads
            WHERE icp_score >= ? AND imported = 0
            ORDER BY icp_score DESC, intent_score DESC
            LIMIT ?
        """, (min_icp, limit)).fetchall()
        conn.close()
        leads = []
        for r in rows:
            d = dict(r)
            d["intent_signals"] = json.loads(d["intent_signals"])
            d["enriched"] = bool(d["enriched"])
            d["imported"] = bool(d["imported"])
            d["email_verified"] = bool(d.get("email_verified", 0))
            d.setdefault("email_status", "verified" if d["email_verified"] else "unknown")
            d.setdefault("linkedin_status", "unknown")
            leads.append(Lead(**d))
        return leads

    def update_lead(self, lead: Lead) -> bool:
        if lead.id is None:
            return False
        conn = sqlite3.connect(self.path)
        try:
            cursor = conn.execute("""
                UPDATE leads SET email = ?, email_status = ?, email_verified = ?,
                    linkedin = ?, linkedin_status = ?, phone = ?, enriched = ?, imported = ?
                WHERE id = ?
            """, (lead.email, lead.email_status, int(lead.email_verified), lead.linkedin,
                  lead.linkedin_status, lead.phone, int(lead.enriched), int(lead.imported), lead.id))
            conn.commit()
            return cursor.rowcount == 1
        finally:
            conn.close()

    def mark_imported(self, lead: Lead):
        conn = sqlite3.connect(self.path)
        if lead.id is not None:
            conn.execute("UPDATE leads SET imported = 1 WHERE id = ?", (lead.id,))
        else:
            conn.execute("UPDATE leads SET imported = 1 WHERE name = ? AND company = ? AND source = ?",
                         (lead.name, lead.company, lead.source))
        conn.commit()
        conn.close()

    def stats(self) -> Dict:
        conn = sqlite3.connect(self.path)
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        qualified = conn.execute("SELECT COUNT(*) FROM leads WHERE icp_score >= 70").fetchone()[0]
        enriched = conn.execute("SELECT COUNT(*) FROM leads WHERE enriched = 1").fetchone()[0]
        imported = conn.execute("SELECT COUNT(*) FROM leads WHERE imported = 1").fetchone()[0]
        by_source = conn.execute("SELECT source, COUNT(*) as cnt FROM leads GROUP BY source").fetchall()
        conn.close()
        return {
            "total_leads": total,
            "qualified": qualified,
            "enriched": enriched,
            "imported": imported,
            "by_source": dict(by_source),
            "qualification_rate": round(qualified / total * 100, 1) if total else 0
        }


# ============================================================
# ICP Scorer
# ============================================================

class ICPScorer:
    def __init__(self, config_path: str = "config/icp.json"):
        self.config = self._load_config(config_path)

    def _load_config(self, path: str) -> Dict:
        if os.path.exists(path):
            with open(path) as f:
                return validate_icp_config(json.load(f))
        return validate_icp_config({
            "titles": ["ceo", "founder", "owner", "director", "manager", "president", "vp", "head"],
            "industries": ["technology", "software", "saas", "ecommerce", "agency", "consulting",
                           "marketing", "startup", "fintech", "healthtech", "edtech"],
            "company_size": {"min": 1, "max": 100},
            "location": ["united states", "usa", "uk", "united kingdom", "canada", "australia",
                         "germany", "france", "netherlands", "singapore"],
            "keywords": ["automation", "ai", "artificial intelligence", "workflow", "efficiency",
                         "scaling", "growth", "digital transformation", "machine learning",
                         "chatbot", "integration", "api", "cloud", "devops"],
            "negative_keywords": []
        })

    def score(self, lead: Lead) -> float:
        score = 0.0
        text = f"{lead.name} {lead.title} {lead.company} {lead.raw_text}".lower()

        # Title match (0-30)
        title_score = 0
        for t in self.config["titles"]:
            if t in lead.title.lower():
                title_score = 30
                break
        score += title_score

        # Industry match (0-25)
        industry_score = 0
        for ind in self.config["industries"]:
            if ind in text:
                industry_score = 25
                break
        score += industry_score

        # Location match (0-15)
        location_score = 0
        for loc in self.config["location"]:
            if loc in text:
                location_score = 15
                break
        score += location_score

        # Keywords match (0-30)
        keyword_hits = sum(1 for kw in self.config["keywords"] if kw in text)
        keyword_score = min(keyword_hits * 6, 30)
        score += keyword_score

        return min(score, 100.0)


# ============================================================
# Intent Detector
# ============================================================

class IntentDetector:
    def __init__(self, config_path: str = "config/intent_signals.json"):
        self.patterns = self._load_patterns(config_path)

    def _load_patterns(self, path: str) -> List[Dict]:
        if os.path.exists(path):
            with open(path) as f:
                return validate_intent_config(json.load(f))
        return validate_intent_config([
            {"pattern": r"hiring.*(?:freelancer|developer|consultant|agency)", "weight": 30, "type": "hiring"},
            {"pattern": r"need.*help.*(?:automation|ai|workflow|integration)", "weight": 28, "type": "need_help"},
            {"pattern": r"looking for.*(?:developer|agency|solution|tool)", "weight": 25, "type": "seeking"},
            {"pattern": r"budget.*\$[\d,]+", "weight": 25, "type": "budget"},
            {"pattern": r"frustrated with.*(?:tool|software|process|manual)", "weight": 22, "type": "pain_point"},
            {"pattern": r"recommend.*(?:tool|service|agency|developer)", "weight": 20, "type": "recommendation"},
            {"pattern": r"anyone know.*(?:how to|tool|service)", "weight": 18, "type": "question"},
            {"pattern": r"switching from.*(?:tool|platform|software)", "weight": 20, "type": "switching"},
            {"pattern": r"scaling.*(?:team|business|operations)", "weight": 15, "type": "scaling"},
            {"pattern": r"manual.*(?:process|work|task).*(?:time|wasting|slow)", "weight": 22, "type": "inefficiency"},
        ])

    def detect(self, text: str) -> tuple[float, List[str]]:
        text_lower = text.lower()
        total_score = 0.0
        signals = []
        for p in self.patterns:
            if re.search(p["pattern"], text_lower):
                total_score += p["weight"]
                signals.append(p["type"])
        return min(total_score, 100.0), signals


# ============================================================
# Contact Enricher
# ============================================================

class ContactEnricher:
    """Enriches lead data with email patterns and verification."""

    COMMON_EMAIL_PATTERNS = [
        "{first}@{domain}",
        "{first}.{last}@{domain}",
        "{first}{last}@{domain}",
        "{f}{last}@{domain}",
        "{first}_{last}@{domain}",
        "{last}@{domain}",
        "{first}{l}@{domain}",
    ]

    def __init__(self, hunter_api_key: str = "", allow_network: bool = False):
        self.hunter_api_key = hunter_api_key
        self.allow_network = allow_network
        self.session = requests.Session()

    def enrich(self, lead: Lead) -> Lead:
        if not lead.email and lead.company:
            lead.email = self._find_email(lead)
        if not lead.linkedin:
            lead.linkedin = self._guess_linkedin(lead)
        lead.enriched = True
        return lead

    def _find_email(self, lead: Lead) -> str:
        domain = self._company_to_domain(lead.company)
        if not domain:
            return ""
        if self.allow_network and self.hunter_api_key:
            email = self._hunter_lookup(lead.name, domain)
            if email:
                lead.email_status = "verified"
                lead.email_verified = True
                return email
        guessed = self._pattern_guess(lead.name, domain)
        if guessed:
            lead.email_status = "guessed"
            lead.email_verified = False
        return guessed

    def _company_to_domain(self, company: str) -> str:
        if not company:
            return ""
        clean = re.sub(r'[^a-z0-9\s]', '', company.lower())
        clean = clean.replace(' ', '').replace('inc', '').replace('llc', '').replace('ltd', '')
        return f"{clean}.com" if clean else ""

    def _pattern_guess(self, name: str, domain: str) -> str:
        if not name or not domain:
            return ""
        parts = name.strip().split()
        if len(parts) < 2:
            return f"{parts[0].lower()}@{domain}" if parts else ""
        first, last = parts[0].lower(), parts[-1].lower()
        pattern = self.COMMON_EMAIL_PATTERNS[1]  # first.last@domain.com
        return pattern.format(first=first, last=last, f=first[0], l=last[0], domain=domain)

    def _hunter_lookup(self, name: str, domain: str) -> str:
        try:
            url = "https://api.hunter.io/v2/email-finder"
            params = {"domain": domain, "full_name": name}
            resp = self.session.get(url, params=params, headers={"X-API-Key": self.hunter_api_key}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("email", "")
        except Exception:
            pass
        return ""

    def _guess_linkedin(self, lead: Lead) -> str:
        if not lead.name:
            return ""
        slug = re.sub(r"[^a-z0-9-]+", "-", lead.name.lower()).strip("-")
        lead.linkedin_status = "guessed"
        return f"https://linkedin.com/in/{slug}" if slug else ""


# ============================================================
# Source Connectors
# ============================================================

class BaseConnector:
    name = "base"

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.allow_network = bool(self.config.get("allow_network", False))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "LeadGenHunter/1.0"})

    def search(self, query: str, limit: int = 50) -> List[Lead]:
        raise NotImplementedError


class RedditConnector(BaseConnector):
    name = "reddit"

    SUBREDDITS = [
        "forhire", "hireadeveloper", "startups", "Entrepreneur",
        "smallbusiness", "SaaS", "webdev", "marketing", "ecommerce"
    ]

    def search(self, query: str, limit: int = 50) -> List[Lead]:
        if not self.allow_network:
            return []
        leads = []
        for sub in self.SUBREDDITS[:5]:
            try:
                url = f"https://www.reddit.com/r/{sub}/search.json"
                params = {"q": query, "restrict_sr": "on", "sort": "new", "limit": 25, "t": "month"}
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    for post in data.get("data", {}).get("children", []):
                        p = post["data"]
                        lead = Lead(
                            name=p.get("author", ""),
                            title="Reddit User",
                            company="",
                            source=self.name,
                            source_url=f"https://reddit.com{p.get('permalink', '')}",
                            raw_text=f"{p.get('title', '')} {p.get('selftext', '')}"[:2000]
                        )
                        leads.append(lead)
                        if len(leads) >= limit:
                            return leads
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"[Reddit] Error in r/{sub}: {e}", file=sys.stderr)
        return leads


class GitHubConnector(BaseConnector):
    name = "github"

    def search(self, query: str, limit: int = 50) -> List[Lead]:
        if not self.allow_network:
            return []
        leads = []
        try:
            url = "https://api.github.com/search/users"
            params = {"q": f"{query} in:bio", "sort": "followers", "per_page": min(limit, 50)}
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for user in data.get("items", [])[:limit]:
                    username = user.get("login", "")
                    profile = self._get_profile(username)
                    if profile:
                        lead = Lead(
                            name=profile.get("name", username),
                            title=profile.get("bio", "")[:100],
                            company=profile.get("company", ""),
                            email=profile.get("email", "") or "",
                            email_status="provided" if profile.get("email") else "unknown",
                            github=f"https://github.com/{username}",
                            source=self.name,
                            source_url=f"https://github.com/{username}",
                            raw_text=f"{profile.get('bio', '')} {profile.get('blog', '')} {profile.get('location', '')}"
                        )
                        leads.append(lead)
        except Exception as e:
            print(f"[GitHub] Error: {e}", file=sys.stderr)
        return leads

    def _get_profile(self, username: str) -> Optional[Dict]:
        try:
            resp = self.session.get(f"https://api.github.com/users/{username}", timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None


class TwitterConnector(BaseConnector):
    name = "twitter"

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.bearer_token = self.config.get("bearer_token", "")

    def search(self, query: str, limit: int = 50) -> List[Lead]:
        if not self.allow_network:
            return []
        if not self.bearer_token:
            print("[Twitter] No bearer token, skipping", file=sys.stderr)
            return []
        leads = []
        try:
            url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            params = {
                "query": f"{query} -is:retweet lang:en",
                "max_results": min(limit, 100),
                "tweet.fields": "author_id,created_at,text",
                "expansions": "author_id",
                "user.fields": "name,username,description,location"
            }
            resp = self.session.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                for tweet in data.get("data", []):
                    user = users.get(tweet["author_id"], {})
                    lead = Lead(
                        name=user.get("name", ""),
                        title=user.get("description", "")[:100],
                        twitter=f"https://twitter.com/{user.get('username', '')}",
                        source=self.name,
                        source_url=f"https://twitter.com/{user.get('username', '')}/status/{tweet['id']}",
                        raw_text=tweet.get("text", "")
                    )
                    leads.append(lead)
        except Exception as e:
            print(f"[Twitter] Error: {e}", file=sys.stderr)
        return leads


class LinkedInConnector(BaseConnector):
    name = "linkedin"

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")

    def search(self, query: str, limit: int = 50) -> List[Lead]:
        # LinkedIn requires Sales Navigator API or manual export
        # This is a placeholder for the integration
        print("[LinkedIn] API access requires Sales Navigator. Use CSV import instead.", file=sys.stderr)
        return []

    def import_csv(self, csv_path: str) -> List[Lead]:
        leads = []
        try:
            source_path = safe_input_path(csv_path)
        except (ValueError, OSError):
            return leads
        with source_path.open(newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lead = Lead(
                    name=row.get("Name", row.get("First Name", "") + " " + row.get("Last Name", "")).strip(),
                    title=row.get("Title", row.get("Position", "")),
                    company=row.get("Company", row.get("Company Name", "")),
                    email=row.get("Email", ""),
                    email_status="provided" if row.get("Email", "").strip() else "unknown",
                    email_verified=False,
                    linkedin=row.get("LinkedIn", row.get("Profile URL", "")),
                    linkedin_status="provided" if row.get("LinkedIn", row.get("Profile URL", "")).strip() else "unknown",
                    source=self.name,
                    source_url=row.get("Profile URL", ""),
                    raw_text=f"{row.get('Title', '')} {row.get('Company', '')} {row.get('Industry', '')}"
                )
                if lead.name:
                    leads.append(lead)
        return leads


# ============================================================
# Lead-Gen-Hunter Core
# ============================================================

class LeadGenHunter:
    def __init__(self, config_dir: str = "config", db_path: str = "lead_hunter.db", allow_network: bool = False, hunter_api_key: str = ""):
        self.db = LeadDatabase(db_path)
        self.icp_scorer = ICPScorer(os.path.join(config_dir, "icp.json"))
        self.intent_detector = IntentDetector(os.path.join(config_dir, "intent_signals.json"))
        self.enricher = ContactEnricher(hunter_api_key=hunter_api_key, allow_network=allow_network)
        connector_config = {"allow_network": allow_network}
        self.connectors: List[BaseConnector] = [
            RedditConnector(connector_config),
            GitHubConnector(connector_config),
            TwitterConnector(connector_config),
            LinkedInConnector(connector_config),
        ]

    def hunt(self, queries: List[str], limit_per_query: int = 30) -> Dict:
        results = {"total": 0, "new": 0, "qualified": 0, "by_source": {}}
        for query in queries:
            print(f"\n🔍 Hunting: {query}")
            for connector in self.connectors:
                print(f"  → {connector.name}...")
                try:
                    leads = connector.search(query, limit=limit_per_query)
                    results["by_source"][connector.name] = len(leads)
                    for lead in leads:
                        lead.icp_score = self.icp_scorer.score(lead)
                        lead.intent_score, lead.intent_signals = self.intent_detector.detect(lead.raw_text)
                        if self.db.insert_lead(lead):
                            results["new"] += 1
                            if lead.icp_score >= 70:
                                results["qualified"] += 1
                    results["total"] += len(leads)
                    print(f"    Found {len(leads)} leads")
                except Exception as e:
                    print(f"    Error: {e}", file=sys.stderr)
                time.sleep(2)  # Rate limiting between connectors
        return results

    def enrich_qualified(self, limit: int = 100) -> int:
        leads = self.db.get_qualified_leads(min_icp=70, limit=limit)
        count = 0
        for lead in leads:
            if not lead.enriched:
                lead = self.enricher.enrich(lead)
                if self.db.update_lead(lead):
                    count += 1
        return count

    def export_for_client_manager(self, output_path: str = "leads_for_outreach.csv", min_icp: float = 70, overwrite: bool = False) -> str:
        leads = self.db.get_qualified_leads(min_icp=min_icp, limit=1000)
        if not leads:
            print("No qualified leads to export")
            return ""
        destination = safe_export_path(output_path, overwrite=overwrite)
        with destination.open('x' if not overwrite else 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["name", "email", "email_status", "company", "title", "phone", "source"])
            writer.writeheader()
            for lead in leads:
                writer.writerow({
                    "name": neutralize_csv_cell(lead.name),
                    "email": neutralize_csv_cell(lead.email),
                    "email_status": neutralize_csv_cell(lead.email_status),
                    "company": neutralize_csv_cell(lead.company),
                    "title": neutralize_csv_cell(lead.title),
                    "phone": neutralize_csv_cell(lead.phone),
                    "source": neutralize_csv_cell(lead.source)
                })
        print(f"✅ Exported {len(leads)} leads to {output_path}")
        return output_path

    def stats(self) -> Dict:
        return self.db.stats()

    def add_connector(self, connector: BaseConnector):
        self.connectors.append(connector)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Lead-Gen-Hunter: Autonomous Lead Discovery")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Hunt command
    hunt_parser = subparsers.add_parser("hunt", help="Discover new leads")
    hunt_parser.add_argument("--queries", nargs="+", default=[
        "hiring freelancer developer",
        "need automation help",
        "looking for AI solution",
        "frustrated with manual process",
        "scaling business operations"
    ], help="Search queries")
    hunt_parser.add_argument("--limit", type=int, default=30, help="Results per query")

    # Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Enrich qualified leads")
    enrich_parser.add_argument("--limit", type=int, default=100)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export leads for Client-Manager-Pro")
    export_parser.add_argument("--output", default="leads_for_outreach.csv")
    export_parser.add_argument("--min-icp", type=float, default=70)
    export_parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing export")

    # Import command (LinkedIn CSV)
    import_parser = subparsers.add_parser("import", help="Import LinkedIn CSV export")
    import_parser.add_argument("--csv", required=True, help="Path to LinkedIn CSV")

    # Stats command
    subparsers.add_parser("stats", help="Show statistics")

    # Run all
    run_parser = subparsers.add_parser("run", help="Full pipeline: hunt → enrich → export")
    run_parser.add_argument("--queries", nargs="+", default=[])
    run_parser.add_argument("--output", default="leads_for_outreach.csv")
    run_parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing export")

    args = parser.parse_args()

    hunter = LeadGenHunter()

    if args.command == "hunt":
        results = hunter.hunt(args.queries, args.limit)
        print(f"\n📊 Results: {results['total']} found, {results['new']} new, {results['qualified']} qualified")

    elif args.command == "enrich":
        count = hunter.enrich_qualified(args.limit)
        print(f"✅ Enriched {count} leads")

    elif args.command == "export":
        hunter.export_for_client_manager(args.output, args.min_icp, overwrite=args.overwrite)

    elif args.command == "import":
        connector = LinkedInConnector()
        leads = connector.import_csv(args.csv)
        for lead in leads:
            lead.icp_score = hunter.icp_scorer.score(lead)
            lead.intent_score, lead.intent_signals = hunter.intent_detector.detect(lead.raw_text)
            hunter.db.insert_lead(lead)
        print(f"✅ Imported {len(leads)} leads from {args.csv}")

    elif args.command == "stats":
        stats = hunter.stats()
        print("\n📊 Lead-Gen-Hunter Statistics")
        print(f"  Total leads:     {stats['total_leads']}")
        print(f"  Qualified (70+): {stats['qualified']} ({stats['qualification_rate']}%)")
        print(f"  Enriched:        {stats['enriched']}")
        print(f"  Imported:        {stats['imported']}")
        print("\n  By Source:")
        for src, cnt in stats['by_source'].items():
            print(f"    {src}: {cnt}")

    elif args.command == "run":
        queries = args.queries or [
            "hiring freelancer developer",
            "need automation help",
            "looking for AI solution"
        ]
        print("🚀 Running full pipeline...")
        results = hunter.hunt(queries, 30)
        print(f"\n📊 Hunt: {results['total']} found, {results['new']} new, {results['qualified']} qualified")
        count = hunter.enrich_qualified(100)
        print(f"✅ Enriched {count} leads")
        hunter.export_for_client_manager(args.output, overwrite=args.overwrite)
        print("\n✅ Pipeline complete! Import CSV into Client-Manager-Pro")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
