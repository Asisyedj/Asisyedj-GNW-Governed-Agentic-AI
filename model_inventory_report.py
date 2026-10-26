"""Produce a secret-free inventory of live bridge models versus OpenCode configuration."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from gnw_secrets import get_bridge_key

ROOT = Path(r"D:\GNW")
BRIDGE = "http://127.0.0.1:8000"
CONFIG = ROOT / "gnw-governed-agent-v4" / "opencode.json"
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

def get_json(path):
    req = Request(BRIDGE + path, headers={"Authorization": "Bearer " + get_bridge_key()})
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

health = get_json("/health")
live_payload = get_json("/v1/models")
live = sorted(
    [{"id": m.get("id", ""), "object": m.get("object"), "owned_by": m.get("owned_by")}
     for m in live_payload.get("data", []) if m.get("id")],
    key=lambda m: m["id"]
)
cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
configured_map = cfg.get("provider", {}).get("perplexity-local", {}).get("models", {})
live_ids = {m["id"] for m in live}
configured = [
    {"id": model_id, "name": info.get("name", model_id), "live_available": model_id in live_ids}
    for model_id, info in sorted(configured_map.items())
]
report = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "bridge_health": health,
    "live_model_count": len(live),
    "configured_model_count": len(configured),
    "configured_live_match_count": sum(1 for m in configured if m["live_available"]),
    "configured_not_in_live_list": [m for m in configured if not m["live_available"]],
    "live_not_configured": [m for m in live if m["id"] not in configured_map],
    "live_models": live,
    "configured_models": configured,
    "notes": [
        "A model listed by /v1/models is advertised by the local bridge; this does not guarantee every model can complete a request.",
        "Model IDs configured in OpenCode but absent from /v1/models require a separate request test or correction.",
        "No session tokens, bridge keys, cookies, or prompt contents are stored in this report."
    ]
}
json_path = OUT / "perplexity-model-inventory-20261023.json"
md_path = OUT / "perplexity-model-inventory-20261023.md"
json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
lines = [
    "# Perplexity GNW Bridge — Model Inventory",
    "",
    f"- Generated (UTC): {report['generated_at_utc']}",
    f"- Bridge health: {health}",
    f"- Live model IDs: **{len(live)}**",
    f"- OpenCode configured model IDs: **{len(configured)}**",
    f"- Configured IDs present in live list: **{report['configured_live_match_count']}**",
    f"- Configured IDs absent from live list: **{len(report['configured_not_in_live_list'])}**",
    "",
    "## Configured models",
    "",
    "| Model ID | Display name | Advertised live |",
    "|---|---|---|",
]
for m in configured:
    lines.append(f"| {m['id']} | {m['name']} | {'YES' if m['live_available'] else 'NO'} |")
lines += ["", "## Live models not configured in OpenCode", ""]
lines += [f"- {m['id']}" for m in report["live_not_configured"]]
lines += ["", "## Configured IDs absent from the live list", ""]
lines += [f"- {m['id']} ({m['name']})" for m in report["configured_not_in_live_list"]]
lines += ["", "## Interpretation", "", *[f"- {n}" for n in report["notes"]], ""]
md_path.write_text("\n".join(lines), encoding="utf-8")
print("MODEL_INVENTORY=PASS")
print(f"LIVE_MODELS={len(live)}")
print(f"CONFIGURED_MODELS={len(configured)}")
print(f"CONFIGURED_AND_LIVE={report['configured_live_match_count']}")
print(f"CONFIGURED_NOT_LIVE={len(report['configured_not_in_live_list'])}")
print(f"JSON_REPORT={json_path}")
print(f"MARKDOWN_REPORT={md_path}")
