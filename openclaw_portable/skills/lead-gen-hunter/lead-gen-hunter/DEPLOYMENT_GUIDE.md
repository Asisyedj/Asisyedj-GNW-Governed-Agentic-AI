# Lead-Gen-Hunter Deployment Guide

## 🎯 What You Get

A complete autonomous lead discovery system that:
- **Finds** leads from Reddit, GitHub, Twitter, and LinkedIn
- **Scores** them against your Ideal Customer Profile (ICP)
- **Detects** buying intent signals
- **Enriches** contact data
- **Exports** to Client-Manager-Pro for automated outreach

---

## 📋 Prerequisites

| Requirement | Status | Notes |
|---|---|---|
| Python 3.8+ | ✅ | Already installed |
| `requests` library | ✅ | Run `pip install requests` if needed |
| Reddit API | Optional | Works without auth for public posts |
| GitHub API | Optional | Higher rate limits with token |
| Twitter API | Optional | Requires Bearer Token |
| LinkedIn | Manual | Use CSV export |

---

## 🚀 Quick Start (10 Minutes)

### Step 1: Install (1 min)

```bash
# Create project folder
mkdir lead-gen-hunter
cd lead-gen-hunter

# Copy files here (from ZIP or chat)
# - lead_gen_hunter.py
# - config/icp.json
# - config/intent_signals.json

# Install dependency
pip install requests
```

### Step 2: Test Discovery (3 min)

```bash
# Run a quick test hunt
python lead_gen_hunter.py hunt --queries "hiring freelancer developer" --limit 10
```

**Expected output:**
```
🔍 Hunting: hiring freelancer developer
  → reddit...
    Found 8 leads
  → github...
    Found 3 leads
  → twitter...
    No bearer token, skipping
  → linkedin...
    API access requires Sales Navigator

📊 Results: 11 found, 11 new, 4 qualified
```

### Step 3: Review Leads (2 min)

```bash
# Check statistics
python lead_gen_hunter.py stats
```

**Expected output:**
```
📊 Lead-Gen-Hunter Statistics
  Total leads:     11
  Qualified (70+): 4 (36.4%)
  Enriched:        0
  Imported:        0

  By Source:
    reddit: 8
    github: 3
```

### Step 4: Export for Outreach (2 min)

```bash
# Export qualified leads to CSV
python lead_gen_hunter.py export --output my_leads.csv

# Import into Client-Manager-Pro
python client_manager_pro.py --import my_leads.csv
```

### Step 5: Full Pipeline (2 min)

```bash
# Run complete pipeline: hunt → enrich → export
python lead_gen_hunter.py run --output my_leads.csv
```

---

## ⚙️ Configuration

### Customize Your ICP

Edit `config/icp.json`:

```json
{
  "titles": ["ceo", "founder", "owner", "director"],
  "industries": ["technology", "ecommerce", "agency"],
  "location": ["united states", "uk", "canada"],
  "keywords": ["automation", "ai", "workflow"]
}
```

**Your ICP should match YOUR ideal client:**
- Who pays the most?
- Who is easiest to work with?
- Who has the problem you solve best?

### Add API Keys (Optional)

Create `config/api_keys.json`:

```json
{
  "github_token": "ghp_your_token_here",
  "twitter_bearer": "AAAAAAAAAAAAAAAAAAAAA...",
  "hunter_api_key": "your_hunter_io_key"
}
```

**GitHub Token (free):**
1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select `public_repo` scope
4. Copy token

**Twitter Bearer Token (free tier available):**
1. Go to https://developer.twitter.com/
2. Create project + app
3. Copy Bearer Token

**Hunter.io (email finder, free tier):**
1. Go to https://hunter.io/
2. Sign up free
3. Copy API key

---

## 🔍 Hunting Strategies

### Strategy 1: Pain Point Hunting

Find people complaining about problems you solve:

```bash
python lead_gen_hunter.py hunt --queries \
  "frustrated with manual data entry" \
  "wasting time on repetitive tasks" \
  "need to automate workflow" \
  "looking for automation tool"
```

### Strategy 2: Hiring Intent

Find companies actively hiring:

```bash
python lead_gen_hunter.py hunt --queries \
  "hiring freelance developer" \
  "looking for contract designer" \
  "need agency for project" \
  "budget for automation"
```

### Strategy 3: Competitor Switching

Find unhappy competitor customers:

```bash
python lead_gen_hunter.py hunt --queries \
  "switching from [competitor]" \
  "alternative to [tool]" \
  "better than [competitor]" \
  "frustrated with [tool]"
```

### Strategy 4: Niche Communities

Target specific subreddits:

```bash
# Edit lead_gen_hunter.py SUBREDDITS list:
SUBREDDITS = [
    "forhire", "hireadeveloper", "startups",
    "Entrepreneur", "smallbusiness", "SaaS",
    "your_niche_subreddit"  # Add yours
]
```

---

## 📊 Understanding Scores

### ICP Score (0-100)

| Score | Meaning | Action |
|---|---|---|
| 90-100 | Perfect fit | Priority outreach |
| 70-89 | Good fit | Standard outreach |
| 50-69 | Partial fit | Review manually |
| 0-49 | Poor fit | Skip |

### Intent Score (0-100)

| Score | Meaning | Signals |
|---|---|---|
| 70+ | High intent | Multiple buying signals |
| 40-69 | Medium intent | Some interest shown |
| 0-39 | Low intent | Just browsing |

### Combined Score

Use both to prioritize:

```
Priority = (ICP Score × 0.6) + (Intent Score × 0.4)

90+ = Call today
70-89 = Email this week
50-69 = Add to nurture list
```

---

## 🔗 Integration with Client-Manager-Pro

### Automatic Flow

```
Lead-Gen-Hunter (discovers + scores)
        ↓
Export CSV (qualified leads only)
        ↓
Client-Manager-Pro (imports + sends outreach)
        ↓
Track responses → Convert to clients
```

### Manual Import

```bash
# 1. Export from Lead-Gen-Hunter
python lead_gen_hunter.py export --output leads.csv --min-icp 70

# 2. Review the CSV (optional)
cat leads.csv

# 3. Import to Client-Manager-Pro
python client_manager_pro.py --import leads.csv

# 4. Start outreach
python client_manager_pro.py --send --template value_first
```

---

## 📈 Expected Results

### Week 1: Setup + Testing
- 50-100 leads discovered
- 15-30 qualified
- 5-10 responses

### Week 2-4: Optimization
- 200-500 leads discovered
- 60-150 qualified
- 20-50 responses
- 3-5 discovery calls

### Month 2+: Scale
- 500-1000 leads/month
- 150-300 qualified
- 50-100 responses
- 5-10 clients closed

---

## 🛠️ Troubleshooting

### "No leads found"

**Causes:**
- Reddit rate limiting (wait 1 hour)
- GitHub API limit (add token)
- Query too specific

**Fix:**
```bash
# Use broader queries
python lead_gen_hunter.py hunt --queries "developer" --limit 50
```

### "Low ICP scores"

**Cause:** ICP config doesn't match your target market

**Fix:** Edit `config/icp.json` to match your actual ideal client

### "No emails found"

**Cause:** Contact enrichment requires Hunter.io or manual research

**Fix:**
1. Sign up for Hunter.io free tier
2. Add API key to `config/api_keys.json`
3. Or manually research top 10 leads

---

## 🎯 Next Steps After Setup

1. **Run daily hunts** (15 min/day)
   ```bash
   python lead_gen_hunter.py run --output daily_leads.csv
   ```

2. **Import top 10 to Client-Manager-Pro** (5 min/day)
   ```bash
   python client_manager_pro.py --import daily_leads.csv --limit 10
   python client_manager_pro.py --send --template pain_point
   ```

3. **Track responses** (ongoing)
   ```bash
   python client_manager_pro.py --responses
   ```

4. **Weekly review** (30 min/week)
   - Check ICP score distribution
   - Adjust queries based on results
   - Update intent signals

---

## 💰 Revenue Timeline

| Week | Activity | Revenue |
|---|---|---|
| 1 | Setup + first leads | $0 |
| 2 | 50 leads contacted | $0-500 |
| 3 | 100 leads contacted | $500-1,500 |
| 4 | 150 leads + follow-ups | $1,000-3,000 |
| 8 | 500 leads in system | $2,000-5,000 |
| 12 | 1000 leads + referrals | $3,000-8,000 |

---

## 🔒 Compliance & Ethics

- **Respect rate limits** — Don't spam platforms
- **Follow ToS** — Each platform has rules
- **Opt-out** — Honor unsubscribe requests immediately
- **Transparency** — Say how you found them
- **Value first** — Don't pitch immediately

---

## 📞 Support

**Issues:**
1. Check this guide
2. Review error messages
3. Test with `--limit 5` first
4. Check API status pages

**Files:**
- `lead_gen_hunter.py` — Main code
- `config/icp.json` — Your ideal customer profile
- `config/intent_signals.json` — Buying intent patterns
- `lead_hunter.db` — SQLite database (auto-created)

---

*Deploy in 10 minutes. First leads in 15 minutes. First client in 2-4 weeks.*
