---
name: lead-gen-hunter
description: Use when asked to find leads, generate prospects, discover potential clients, score leads against an ICP, or build a lead list from LinkedIn, Twitter/X, GitHub, Reddit or local directories. Trigger phrases: 'find leads', 'lead generation', 'find clients for my service', 'prospect list', 'score these leads', 'who is looking for X'. Outputs qualified, enriched, ICP-scored leads ready for outreach.
---

# Lead-Gen-Hunter

## Overview

Lead-Gen-Hunter is an autonomous lead discovery engine that continuously scans multiple platforms to find potential clients who are actively looking for solutions you offer. It scores leads against your Ideal Customer Profile (ICP), enriches their contact data, and feeds qualified prospects directly into Client-Manager-Pro for automated outreach.

## Core Capabilities

### 1. Multi-Source Lead Discovery

| Source | Type | Access Method |
|---|---|---|
| LinkedIn | Professional network | Sales Navigator API / manual export |
| Twitter/X | Social signals | API v2 / scraping |
| GitHub | Developer community | REST API |
| Reddit | Community intent | JSON API |
| Local directories | Business listings | Web scraping |
| Industry forums | Niche communities | Custom scrapers |

### 2. ICP Scoring System

Scores each lead 0-100 based on:

| Factor | Weight | Indicators |
|---|---|---|
| Role/Title match | 25% | Decision-maker keywords |
| Company size | 20% | Employee count, revenue |
| Industry fit | 20% | Sector alignment |
| Intent signals | 25% | Active buying behavior |
| Engagement potential | 10% | Social activity, responsiveness |

### 3. Intent Signal Detection

Identifies leads actively seeking solutions:

| Signal | Source | Example |
|---|---|---|
| Job posting | LinkedIn, Indeed | "Hiring [your service] freelancer" |
| Question asking | Reddit, Twitter | "Need help with [problem you solve]" |
| Tool seeking | GitHub, forums | "Looking for [solution type]" |
| Complaint | Twitter, Reddit | "Frustrated with [competitor]" |
| Budget mention | All sources | "Budget $X for [project]" |

### 4. Contact Enrichment

Enriches raw lead data with:
- Email addresses (pattern detection + verification)
- Phone numbers (where public)
- Social profiles (LinkedIn, Twitter, etc.)
- Company information
- Recent activity/posts

### 5. Auto-Import to Client-Manager-Pro

Qualified leads automatically flow into your outreach system:

```
Lead-Gen-Hunter discovers lead
        ↓
ICP score ≥ 70?
        ↓
YES → Enrich contact data
        ↓
Import to Client-Manager-Pro
        ↓
Trigger outreach sequence
        ↓
Track response & conversion
```

## Architecture

```
┌─────────────────────────────────────────┐
│         Lead-Gen-Hunter Core            │
├─────────────────────────────────────────┤
│  Source Connectors                      │
│  ├── LinkedIn Connector                 │
│  ├── Twitter Connector                  │
│  ├── GitHub Connector                   │
│  ├── Reddit Connector                   │
│  └── Directory Scraper                  │
├─────────────────────────────────────────┤
│  Processing Pipeline                    │
│  ├── Deduplication Engine               │
│  ├── ICP Scorer                         │
│  ├── Intent Detector                    │
│  ├── Contact Enricher                   │
│  └── Quality Filter                     │
├─────────────────────────────────────────┤
│  Integration Layer                      │
│  ├── Client-Manager-Pro API             │
│  ├── CRM Export (CSV/JSON)              │
│  └── Webhook Notifications              │
└─────────────────────────────────────────┘
```

## Configuration

### ICP Definition

```json
{
  "icp": {
    "titles": ["CEO", "Founder", "Owner", "Director", "Manager"],
    "industries": ["technology", "ecommerce", "agency", "consulting"],
    "company_size": {"min": 1, "max": 50},
    "location": ["United States", "United Kingdom", "Canada", "Australia"],
    "keywords": ["automation", "AI", "workflow", "efficiency", "scaling"]
  }
}
```

### Intent Signals

```json
{
  "intent_signals": [
    {"pattern": "hiring.*freelancer", "weight": 30},
    {"pattern": "need.*help.*automation", "weight": 25},
    {"pattern": "looking for.*developer", "weight": 25},
    {"pattern": "budget.*\\$\\d+", "weight": 20},
    {"pattern": "frustrated with.*tool", "weight": 15}
  ]
}
```

## Revenue Model

| Tier | Price | Features |
|---|---|---|
| Starter | $500/mo | 100 leads/mo, 2 sources, basic scoring |
| Growth | $2,000/mo | 500 leads/mo, 5 sources, intent detection |
| Enterprise | $5,000/mo | Unlimited leads, all sources, custom ICP, API access |

## Deployment Checklist

- [ ] Set up API credentials (LinkedIn, Twitter, GitHub, Reddit)
- [ ] Configure ICP parameters
- [ ] Set up intent signal patterns
- [ ] Connect to Client-Manager-Pro
- [ ] Test lead discovery on small batch
- [ ] Verify ICP scoring accuracy
- [ ] Enable auto-import
- [ ] Monitor first 50 leads
- [ ] Adjust scoring weights
- [ ] Scale to full discovery mode

## Success Metrics

| Metric | Target |
|---|---|
| Leads discovered/day | 10-50 |
| ICP match rate | ≥30% |
| Contact enrichment rate | ≥70% |
| Import to CRM rate | ≥80% |
| Response rate (via Client-Manager-Pro) | ≥10% |
| Conversion to call | ≥3% |
| Close rate | ≥20% |

## Files

- `lead_gen_hunter.py` — Main implementation
- `connectors/` — Platform-specific connectors
- `config/icp.json` — ICP definition
- `config/intent_signals.json` — Intent patterns
- `DEPLOYMENT_GUIDE.md` — Setup instructions
