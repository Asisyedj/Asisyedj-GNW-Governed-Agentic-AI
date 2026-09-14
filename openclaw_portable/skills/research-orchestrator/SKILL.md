---
name: research-orchestrator
description: Use when asked to run deep scientific or technical research, a literature review, find and compare papers, detect contradictions between sources, or produce a cited research report. Trigger phrases: 'deep research', 'literature review', 'find papers on', 'research report with citations', 'compare studies'. Integrates Semantic Scholar, arXiv, PubMed and web sources with contradiction detection and structured citation management.
---

# Scientific Research Orchestrator (OC-050)

Automated scientific research workflow with literature discovery, contradiction detection, citation management, and structured report generation.

## Features

- **Multi-Source Discovery**: Semantic Scholar, arXiv, PubMed, web search
- **Contradiction Detection**: Identify conflicting findings across papers
- **Citation Management**: BibTeX, APA, MLA, Chicago formats
- **Structured Reports**: Literature reviews, meta-analyses, systematic reviews
- **Scheduled Monitoring**: Track new publications in research areas
- **HITL Review**: Human approval for publication-ready content

## Architecture

```
research_orchestrator/
├── discovery/
│   ├── semantic_scholar.py  # Semantic Scholar API
│   ├── arxiv.py             # arXiv API
│   ├── pubmed.py            # PubMed API
│   ├── web_search.py        # General web search
│   └── aggregator.py        # Result aggregation + dedup
├── analysis/
│   ├── contradiction.py     # Contradiction detection
│   ├── clustering.py        # Topic clustering
│   ├── summarization.py     # NIM-powered summarization
│   └── citation_graph.py    # Citation network analysis
├── synthesis/
│   ├── literature_review.py # Literature review generator
│   ├── meta_analysis.py     # Meta-analysis tools
│   ├── systematic_review.py # Systematic review (PRISMA)
│   └── report_builder.py    # Structured report builder
├── citations/
│   ├── formatter.py         # Citation formatting
│   ├── bibtex.py            # BibTeX generation
│   └── manager.py           # Citation database
├── monitoring/
│   ├── scheduler.py         # Scheduled searches
│   ├── alerts.py            # New paper alerts
│   └── delta.py             # Change detection
└── cli.py                   # search | review | monitor | cite
```

## Safety (7 Layers)

1. HITL Gates — approval before publishing
2. Rate Limiting — 100 API calls/hour
3. Context Anchoring — RESEARCH.md as root
4. Credential Encryption — API keys encrypted
5. Circuit Breakers — fallback on API failure
6. Input Sanitization — validate all queries
7. Compaction Safety — backup before bulk ops

## Config

- max_papers_per_search: 100
- contradiction_threshold: 0.7
- citation_style: apa
- review_sections: [intro, methods, results, discussion]
- monitoring_interval: 24 hours
- sources: [semantic_scholar, arxiv, pubmed, web]
