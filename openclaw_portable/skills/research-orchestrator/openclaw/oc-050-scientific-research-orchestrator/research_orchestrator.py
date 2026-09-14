"""
Scientific Research Orchestrator (OC-050) — Core Implementation
================================================================
Automated scientific research workflow with multi-source discovery.
"""

import asyncio
import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse


MAX_RESULT_LIMIT = 100
DEFAULT_TIMEOUT_SECONDS = 15.0


def _bounded_limit(limit: int) -> int:
    """Return a non-negative result limit bounded for every provider call."""
    try:
        return max(0, min(int(limit), MAX_RESULT_LIMIT))
    except (TypeError, ValueError):
        return MAX_RESULT_LIMIT


def _https_url(url: str) -> str:
    """Reject provider endpoints that are not HTTPS URLs."""
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError(f"Provider endpoint must use HTTPS: {url!r}")
    return url


def _stable_paper_id(provider: str, provider_id: str, *fallback_parts: Any) -> str:
    """Build a deterministic ID from a provider key, never a random UUID."""
    identity = str(provider_id or "").strip()
    if not identity:
        identity = "|".join(str(part or "").strip().lower() for part in fallback_parts)
    digest = hashlib.sha256(f"{provider}:{identity}".encode("utf-8")).hexdigest()[:24]
    return f"{provider}:{digest}"


def _normalise_identity(value: str) -> str:
    """Normalise DOI/URL/title values for cross-provider deduplication."""
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .")


def _paper_identity(paper: "Paper") -> str:
    """Select a stable cross-provider identity, preferring DOI then URL/title."""
    doi = _normalise_identity(paper.doi)
    if doi:
        return f"doi:{doi}"
    url = _normalise_identity(paper.url)
    if url:
        return f"url:{url}"
    author = _normalise_identity(paper.authors[0] if paper.authors else "")
    title = _normalise_identity(paper.title)
    return f"title:{title}|author:{author}|year:{paper.year}"


def _bibtex_escape(value: Any) -> str:
    """Escape provider text for use inside a BibTeX braced field."""
    text = str(value or "").replace("\\", r"\\")
    for char in ("{", "}", "&", "%", "#", "_", "$", "~", "^"):
        text = text.replace(char, "\\" + char)
    return text


def _atomic_write_text(path: Path, content: str) -> None:
    """Write in the target directory, flush it, then atomically replace target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _atomic_append_jsonl(path: Path, line: str) -> None:
    """Atomically append an audit line without exposing partial JSON."""
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    _atomic_write_text(path, previous + line)


# ──────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────

class Source(Enum):
    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"
    PUBMED = "pubmed"
    WEB = "web"
    INTERNAL = "internal"


class PaperStatus(Enum):
    UNREAD = "unread"
    READING = "reading"
    READ = "read"
    CITED = "cited"
    EXCLUDED = "excluded"


@dataclass
class Paper:
    id: str
    title: str
    authors: List[str]
    abstract: str
    year: int
    source: str
    url: str = ""
    doi: str = ""
    citations: int = 0
    references: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    status: str = "unread"
    notes: str = ""
    relevance_score: float = 0.0
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Contradiction:
    id: str
    paper_a: str
    paper_b: str
    topic: str
    claim_a: str
    claim_b: str
    severity: float  # 0-1
    explanation: str
    resolved: bool = False


@dataclass
class ResearchProject:
    id: str
    name: str
    query: str
    papers: List[str] = field(default_factory=list)  # Paper IDs
    contradictions: List[str] = field(default_factory=list)  # Contradiction IDs
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Citation:
    id: str
    paper_id: str
    style: str  # apa, mla, chicago, bibtex
    text: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ──────────────────────────────────────────────────────────────
# SOURCE CONNECTORS
# ──────────────────────────────────────────────────────────────

class SemanticScholarConnector:
    """Semantic Scholar API connector."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
        self.rate_limit_delay = 1.0  # seconds between requests
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """Search Semantic Scholar."""
        try:
            import aiohttp
            
            url = f"{self.BASE_URL}/paper/search"
            limit = _bounded_limit(limit)
            params = {
                "query": query,
                "limit": limit,
                "fields": "title,authors,abstract,year,citationCount,externalIds,url,openAccessPdf"
            }
            
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(_https_url(url), params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self._parse_results(data.get("data", []))
                    else:
                        return []
        except Exception as e:
            print(f"Semantic Scholar error: {e}")
            return []
    
    def _parse_results(self, results: List[Dict]) -> List[Paper]:
        """Parse API results into Paper objects."""
        papers = []
        for item in results:
            paper = Paper(
                id=_stable_paper_id(
                    "semantic_scholar", item.get("paperId", ""),
                    item.get("externalIds", {}).get("DOI", ""), item.get("title", "")
                ),
                title=item.get("title", ""),
                authors=[a.get("name", "") for a in item.get("authors", [])],
                abstract=item.get("abstract", "") or "",
                year=item.get("year", 0),
                source="semantic_scholar",
                url=item.get("url", ""),
                doi=item.get("externalIds", {}).get("DOI", ""),
                citations=item.get("citationCount", 0),
                metadata={
                    "paper_id": item.get("paperId", ""),
                    "open_access": item.get("openAccessPdf", {}).get("url", "") if item.get("openAccessPdf") else ""
                }
            )
            papers.append(paper)
        return papers


class ArXivConnector:
    """arXiv API connector."""
    
    BASE_URL = "https://export.arxiv.org/api/query"
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """Search arXiv."""
        try:
            import aiohttp
            import xml.etree.ElementTree as ET
            
            limit = _bounded_limit(limit)
            params = {
                "search_query": f"all:{quote(query)}",
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending"
            }
            
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(_https_url(self.BASE_URL), params=params) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        return self._parse_atom(text)
                    return []
        except Exception as e:
            print(f"arXiv error: {e}")
            return []
    
    def _parse_atom(self, xml_text: str) -> List[Paper]:
        """Parse Atom XML response."""
        import xml.etree.ElementTree as ET
        
        papers = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
            
            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns)
                abstract = entry.find("atom:summary", ns)
                published = entry.find("atom:published", ns)
                authors = entry.findall("atom:author/atom:name", ns)
                
                entry_id = entry.find("atom:id", ns)
                entry_url = entry_id.text.strip() if entry_id is not None and entry_id.text else ""
                paper = Paper(
                    id=_stable_paper_id("arxiv", entry_url, title.text if title is not None else ""),
                    title=title.text.strip() if title is not None else "",
                    authors=[a.text for a in authors if a.text],
                    abstract=abstract.text.strip() if abstract is not None else "",
                    year=int(published.text[:4]) if published is not None and published.text else 0,
                    source="arxiv",
                    url=entry_url,
                    keywords=[t.text for t in entry.findall("arxiv:primary_category", ns) if t.text]
                )
                papers.append(paper)
        except Exception as e:
            print(f"arXiv parse error: {e}")
        
        return papers


class PubMedConnector:
    """PubMed API connector."""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """Search PubMed."""
        try:
            import aiohttp
            
            # First: search for IDs
            search_url = f"{self.BASE_URL}/esearch.fcgi"
            limit = _bounded_limit(limit)
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": limit,
                "retmode": "json",
                "sort": "relevance"
            }
            
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(_https_url(search_url), params=params) as resp:
                    if resp.status != 200:
                        return []
                    
                    data = await resp.json()
                    ids = data.get("esearchresult", {}).get("idlist", [])
                    
                    if not ids:
                        return []
                    
                    # Second: fetch details
                    fetch_url = f"{self.BASE_URL}/efetch.fcgi"
                    fetch_params = {
                        "db": "pubmed",
                        "id": ",".join(ids),
                        "retmode": "xml",
                        "rettype": "abstract"
                    }
                    
                    async with session.get(_https_url(fetch_url), params=fetch_params) as fetch_resp:
                        if fetch_resp.status == 200:
                            xml_text = await fetch_resp.text()
                            return self._parse_pubmed(xml_text)
            
            return []
        except Exception as e:
            print(f"PubMed error: {e}")
            return []
    
    def _parse_pubmed(self, xml_text: str) -> List[Paper]:
        """Parse PubMed XML."""
        import xml.etree.ElementTree as ET
        
        papers = []
        try:
            root = ET.fromstring(xml_text)
            
            for article in root.findall(".//PubmedArticle"):
                medline = article.find(".//MedlineCitation")
                if medline is None:
                    continue
                
                article_elem = medline.find("Article")
                if article_elem is None:
                    continue
                
                title = article_elem.find("ArticleTitle")
                abstract = article_elem.find("Abstract/AbstractText")
                authors = article_elem.findall("AuthorList/Author")
                year = article_elem.find("Journal/JournalIssue/PubDate/Year")
                
                author_names = []
                for author in authors:
                    last = author.find("LastName")
                    first = author.find("ForeName")
                    if last is not None and first is not None:
                        author_names.append(f"{first.text} {last.text}")
                
                pmid_elem = medline.find("PMID")
                pmid = pmid_elem.text.strip() if pmid_elem is not None and pmid_elem.text else ""
                paper = Paper(
                    id=_stable_paper_id("pubmed", pmid, title.text if title is not None else ""),
                    title=title.text if title is not None else "",
                    authors=author_names,
                    abstract=abstract.text if abstract is not None else "",
                    year=int(year.text) if year is not None else 0,
                    source="pubmed",
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
                )
                papers.append(paper)
        except Exception as e:
            print(f"PubMed parse error: {e}")
        
        return papers


# ──────────────────────────────────────────────────────────────
# ANALYSIS ENGINE
# ──────────────────────────────────────────────────────────────

class ContradictionDetector:
    """Detect contradictions between papers."""
    
    # Simple contradiction patterns
    CONTRADICTION_PATTERNS = [
        (r"increases?", r"decreases?"),
        (r"improves?", r"worsens?"),
        (r"effective", r"ineffective"),
        (r"significant", r"not significant"),
        (r"positive", r"negative"),
        (r"supports?", r"contradicts?"),
        (r"confirms?", r"refutes?"),
        (r"associated with", r"not associated with"),
        (r"higher", r"lower"),
        (r"more", r"less"),
        (r"beneficial", r"harmful"),
        (r"safe", r"unsafe"),
        (r"recommended", r"not recommended"),
    ]
    
    def detect(self, papers: List[Paper], topic: str = "") -> List[Contradiction]:
        """Detect contradictions between papers."""
        contradictions = []
        
        # Extract claims from abstracts
        claims = {}
        for paper in papers:
            claims[paper.id] = self._extract_claims(paper.abstract)
        
        # Compare claims pairwise
        paper_list = list(claims.items())
        for i in range(len(paper_list)):
            for j in range(i + 1, len(paper_list)):
                id_a, claims_a = paper_list[i]
                id_b, claims_b = paper_list[j]
                
                # Check for contradictions
                for claim_a in claims_a:
                    for claim_b in claims_b:
                        contradiction = self._check_contradiction(
                            claim_a, claim_b, id_a, id_b, topic
                        )
                        if contradiction:
                            contradictions.append(contradiction)
        
        return contradictions
    
    def _extract_claims(self, abstract: str) -> List[str]:
        """Extract key claims from abstract."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', abstract)
        
        # Filter for claim-like sentences
        claims = []
        claim_indicators = [
            "show", "demonstrate", "find", "conclude", "suggest",
            "indicate", "reveal", "prove", "establish", "confirm",
            "increase", "decrease", "improve", "reduce", "enhance",
            "associated", "correlated", "linked", "related"
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            
            # Check if sentence contains claim indicators
            if any(indicator in sentence.lower() for indicator in claim_indicators):
                claims.append(sentence)
        
        return claims
    
    def _check_contradiction(self, claim_a: str, claim_b: str,
                            paper_a: str, paper_b: str, topic: str) -> Optional[Contradiction]:
        """Check if two claims contradict each other."""
        claim_a_lower = claim_a.lower()
        claim_b_lower = claim_b.lower()
        
        for pattern_pos, pattern_neg in self.CONTRADICTION_PATTERNS:
            # Check if one claim has positive pattern and other has negative
            a_has_pos = bool(re.search(pattern_pos, claim_a_lower))
            a_has_neg = bool(re.search(pattern_neg, claim_a_lower))
            b_has_pos = bool(re.search(pattern_pos, claim_b_lower))
            b_has_neg = bool(re.search(pattern_neg, claim_b_lower))
            
            if (a_has_pos and b_has_neg) or (a_has_neg and b_has_pos):
                # Check if they're about the same topic (simple keyword overlap)
                words_a = set(claim_a_lower.split())
                words_b = set(claim_b_lower.split())
                overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                
                if overlap > 0.3:  # Threshold for topic similarity
                    return Contradiction(
                        id=str(uuid.uuid4())[:8],
                        paper_a=paper_a,
                        paper_b=paper_b,
                        topic=topic,
                        claim_a=claim_a,
                        claim_b=claim_b,
                        severity=overlap,
                        explanation=f"Contradictory findings on similar topic (overlap: {overlap:.2f})"
                    )
        
        return None


class CitationFormatter:
    """Format citations in various styles."""
    
    @staticmethod
    def format_apa(paper: Paper) -> str:
        """Format citation in APA style."""
        authors = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors += " et al."
        
        return f"{authors} ({paper.year}). {paper.title}. Retrieved from {paper.url}"
    
    @staticmethod
    def format_mla(paper: Paper) -> str:
        """Format citation in MLA style."""
        authors = ", ".join(paper.authors[:2])
        if len(paper.authors) > 2:
            authors += ", et al."
        
        return f"{authors}. \"{paper.title}.\" {paper.year}, {paper.url}."
    
    @staticmethod
    def format_bibtex(paper: Paper) -> str:
        """Format citation in BibTeX."""
        # Generate citation key
        first_author = paper.authors[0].split()[-1] if paper.authors else "unknown"
        key = f"{first_author}{paper.year}"
        
        safe_key = re.sub(r"[^A-Za-z0-9:_-]+", "-", f"{first_author}{paper.year}").strip("-") or "paper"
        fields = [
            f"  title = {{{_bibtex_escape(paper.title)}}}",
            f"  author = {{{_bibtex_escape(' and '.join(paper.authors))}}}",
            f"  year = {{{_bibtex_escape(paper.year)}}}",
        ]
        if paper.url:
            fields.append(f"  url = {{{_bibtex_escape(paper.url)}}}")
        if paper.doi:
            fields.append(f"  doi = {{{_bibtex_escape(_normalise_identity(paper.doi))}}}")
        return "@article{" + safe_key + ",\n" + ",\n".join(fields) + "\n}"


# ──────────────────────────────────────────────────────────────
# RESEARCH ORCHESTRATOR
# ──────────────────────────────────────────────────────────────

class ResearchOrchestrator:
    """Main research orchestrator."""
    
    def __init__(self, storage_path: str = "~/.openclaw/research"):
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.papers: Dict[str, Paper] = {}
        self.projects: Dict[str, ResearchProject] = {}
        self.contradictions: Dict[str, Contradiction] = {}
        self.citations: Dict[str, Citation] = {}
        
        # Connectors
        self.semantic_scholar = SemanticScholarConnector()
        self.arxiv = ArXivConnector()
        self.pubmed = PubMedConnector()
        
        # Analysis
        self.contradiction_detector = ContradictionDetector()
        
        # Audit
        self.audit_log: List[Dict] = []
        
        self._load_data()
    
    def _load_data(self):
        """Load data from disk."""
        papers_file = self.storage_path / "papers.json"
        if papers_file.exists():
            with open(papers_file) as f:
                data = json.load(f)
                for p in data:
                    self.papers[p["id"]] = Paper(**p)
    
    def _save_data(self):
        """Save data to disk."""
        content = json.dumps([asdict(p) for p in self.papers.values()], indent=2, default=str)
        _atomic_write_text(self.storage_path / "papers.json", content)
    
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
        
        audit_file = self.storage_path / "audit.jsonl"
        _atomic_append_jsonl(audit_file, json.dumps(entry, default=str) + "\n")
    
    # ── Search ──
    
    async def search(self, query: str, sources: List[str] = None, 
                    limit: int = 20) -> List[Paper]:
        """Search across multiple sources."""
        sources = sources or ["semantic_scholar", "arxiv", "pubmed"]
        
        tasks = []
        
        if "semantic_scholar" in sources:
            tasks.append(self.semantic_scholar.search(query, limit))
        if "arxiv" in sources:
            tasks.append(self.arxiv.search(query, limit))
        if "pubmed" in sources:
            tasks.append(self.pubmed.search(query, limit))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten, deduplicate by DOI/URL/title identity, and cap aggregate output.
        all_papers = []
        seen_identities = set()
        result_limit = _bounded_limit(limit)
        
        for result in results:
            if isinstance(result, list):
                for paper in result:
                    identity = _paper_identity(paper)
                    if identity not in seen_identities and len(all_papers) < result_limit:
                        seen_identities.add(identity)
                        self.papers[paper.id] = paper
                        all_papers.append(paper)
        
        self._save_data()
        
        self._audit("search", "user", query, "success", {
            "sources": sources,
            "results": len(all_papers)
        })
        
        return all_papers
    
    # ── Project Management ──
    
    def create_project(self, name: str, query: str) -> ResearchProject:
        """Create a new research project."""
        project = ResearchProject(
            id=str(uuid.uuid4())[:8],
            name=name,
            query=query
        )
        
        self.projects[project.id] = project
        
        self._audit("project_created", "user", project.id, "success", {"name": name})
        return project
    
    def add_to_project(self, project_id: str, paper_ids: List[str]):
        """Add papers to a project."""
        project = self.projects.get(project_id)
        if not project:
            return False
        
        for pid in paper_ids:
            if pid in self.papers and pid not in project.papers:
                project.papers.append(pid)
        
        project.updated_at = datetime.now(timezone.utc).isoformat()
        return True
    
    # ── Analysis ──
    
    async def analyze_project(self, project_id: str) -> Dict:
        """Run full analysis on a project."""
        project = self.projects.get(project_id)
        if not project:
            return {"error": "Project not found"}
        
        # Get papers
        papers = [self.papers[pid] for pid in project.papers if pid in self.papers]
        
        if not papers:
            return {"error": "No papers in project"}
        
        # Detect contradictions
        contradictions = self.contradiction_detector.detect(papers, project.query)
        for c in contradictions:
            self.contradictions[c.id] = c
            if c.id not in project.contradictions:
                project.contradictions.append(c.id)
        
        # Generate citations
        citations = []
        for paper in papers:
            citation = Citation(
                id=str(uuid.uuid4())[:8],
                paper_id=paper.id,
                style="apa",
                text=CitationFormatter.format_apa(paper)
            )
            self.citations[citation.id] = citation
            citations.append(citation.text)
        
        # Build report
        report = {
            "project": asdict(project),
            "paper_count": len(papers),
            "papers": [asdict(p) for p in papers],
            "contradictions": [asdict(c) for c in contradictions],
            "citations": citations,
            "analysis_status": "draft",
            "publication_status": "not_published",
            "published": False,
            "summary": self._generate_summary(papers, project.query),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Save report
        report_file = self.storage_path / f"report_{project_id}.json"
        _atomic_write_text(
            report_file, json.dumps(report, indent=2, default=str)
        )
        
        self._audit("analysis_completed", "system", project_id, "success", {
            "papers": len(papers),
            "contradictions": len(contradictions)
        })
        
        return report
    
    def _generate_summary(self, papers: List[Paper], topic: str) -> str:
        """Generate a simple summary of papers."""
        if not papers:
            return "No papers to summarize."
        
        total = len(papers)
        years = [p.year for p in papers if p.year > 0]
        avg_year = sum(years) / len(years) if years else 0
        
        # Extract common keywords
        all_keywords = []
        for p in papers:
            all_keywords.extend(p.keywords)
        
        keyword_counts = {}
        for kw in all_keywords:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        summary = f"""Research Summary: {topic}

Total papers analyzed: {total}
Average publication year: {avg_year:.0f}
Key themes: {', '.join([k for k, v in top_keywords])}

This collection of {total} papers spans {min(years) if years else 'N/A'} to {max(years) if years else 'N/A'}.
The most cited paper has {max(p.citations for p in papers)} citations.
"""
        
        return summary
    
    # ── Monitoring ──
    
    async def check_for_new_papers(self, project_id: str) -> List[Paper]:
        """Check for new papers matching project query."""
        project = self.projects.get(project_id)
        if not project:
            return []
        
        # Get existing paper IDs
        existing_ids = set(project.papers)
        
        # Search for new papers
        new_papers = await self.search(project.query, limit=50)
        
        # Filter out existing
        truly_new = []
        for paper in new_papers:
            if paper.id not in existing_ids:
                truly_new.append(paper)
                self.add_to_project(project_id, [paper.id])
        
        if truly_new:
            self._audit("new_papers_found", "system", project_id, "success", {
                "new_count": len(truly_new)
            })
        
        return truly_new
    
    def get_project_report(self, project_id: str) -> Dict:
        """Get project report."""
        report_file = self.storage_path / f"report_{project_id}.json"
        if report_file.exists():
            with open(report_file) as f:
                return json.load(f)
        return {"error": "Report not found"}
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        return {
            "total_papers": len(self.papers),
            "total_projects": len(self.projects),
            "total_contradictions": len(self.contradictions),
            "total_citations": len(self.citations),
            "papers_by_source": self._count_by_source(),
            "papers_by_year": self._count_by_year(),
        }
    
    def _count_by_source(self) -> Dict[str, int]:
        counts = {}
        for p in self.papers.values():
            counts[p.source] = counts.get(p.source, 0) + 1
        return counts
    
    def _count_by_year(self) -> Dict[int, int]:
        counts = {}
        for p in self.papers.values():
            if p.year > 0:
                counts[p.year] = counts.get(p.year, 0) + 1
        return counts


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scientific Research Orchestrator")
    parser.add_argument("command", choices=["search", "project", "analyze", "monitor", "stats"])
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--project-id", help="Project ID")
    parser.add_argument("--name", help="Project name")
    parser.add_argument("--sources", nargs="*", default=["semantic_scholar", "arxiv"], help="Sources")
    parser.add_argument("--limit", type=int, default=20, help="Result limit")
    parser.add_argument("--storage", default="~/.openclaw/research", help="Storage path")
    
    args = parser.parse_args()
    
    orchestrator = ResearchOrchestrator(storage_path=args.storage)
    
    if args.command == "search":
        papers = await orchestrator.search(args.query, sources=args.sources, limit=args.limit)
        print(f"Found {len(papers)} papers:")
        for p in papers[:5]:
            print(f"  - {p.title} ({p.year}) [{p.source}]")
    
    elif args.command == "project":
        if args.name and args.query:
            project = orchestrator.create_project(args.name, args.query)
            print(f"Project created: {project.id}")
        elif args.project_id:
            report = orchestrator.get_project_report(args.project_id)
            print(json.dumps(report, indent=2, default=str))
    
    elif args.command == "analyze":
        report = await orchestrator.analyze_project(args.project_id)
        print(json.dumps(report, indent=2, default=str))
    
    elif args.command == "stats":
        print(json.dumps(orchestrator.get_stats(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
