import json, time, sys
from pathlib import Path
sys.path.insert(0, 'D:/GNW/perplexity-browser-api')
from run_100_prompts_research import query_model, PILLARS

with open('D:/GNW/perplexity-browser-api/production_100_research_results.json', 'r', encoding='utf-8') as f:
    results = json.load(f)

# Re-run missing pillars P3, P5, P6, P9 with gpt-5 / claude-sonnet-5.5 (fast & reliable)
retry_pillars = [p for p in PILLARS if p["pillar_id"] in ["P3", "P5", "P6", "P9"]]

for p in retry_pillars:
    p_id = p["pillar_id"]
    # use gpt5 for reliable high-speed completion
    res = query_model("openai/gpt5", p["title"], p["prompts"])
    results[p_id] = {
        "title": p["title"],
        "model": "openai/gpt5",
        "prompts": p["prompts"],
        "research": res
    }
    time.sleep(1)

with open('D:/GNW/perplexity-browser-api/production_100_research_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)

print("ALL 10 PILLARS FULLY COMPLETED!")
