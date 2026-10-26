"""Sequential smoke-test of configured GNW bridge model IDs; never logs response bodies or credentials."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gnw_secrets import get_bridge_key

ROOT = Path(r"D:\GNW")
BRIDGE = "http://127.0.0.1:8000"
CONFIG = ROOT / "gnw-governed-agent-v4" / "opencode.json"
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
models = cfg.get("provider", {}).get("perplexity-local", {}).get("models", {})
key = get_bridge_key()
progress_path = OUT / "perplexity-configured-model-smoke-20261023.progress.json"
if progress_path.exists():
    try:
        results = json.loads(progress_path.read_text(encoding="utf-8")).get("results", [])
    except Exception:
        results = []
else:
    results = []
done_ids = {row.get("model_id") for row in results}
batch_start = len(results)

for index, (model_id, meta) in enumerate(sorted(models.items()), 1):
    if model_id in done_ids:
        continue
    started = time.perf_counter()
    status = "FAIL_UNKNOWN"
    response_chars = 0
    detail = ""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with exactly GNW_MODEL_TEST_OK and no other text."}],
        "max_tokens": 24,
        "stream": False
    }
    req = Request(
        BRIDGE + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST"
    )
    try:
        with urlopen(req, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
            choices = body.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            response_chars = len(str(content))
            status = "PASS" if response_chars > 0 else "FAIL_EMPTY_RESPONSE"
            detail = "response_received" if response_chars else "no_choice_content"
    except HTTPError as exc:
        status = f"FAIL_HTTP_{exc.code}"
        detail = "http_error; response body suppressed"
    except URLError as exc:
        status = "FAIL_CONNECTION"
        detail = type(exc.reason).__name__
    except TimeoutError:
        status = "FAIL_TIMEOUT"
        detail = "request_timeout"
    except Exception as exc:
        status = "FAIL_UNKNOWN"
        detail = type(exc).__name__
    latency_ms = int((time.perf_counter() - started) * 1000)
    results.append({
        "index": index,
        "model_id": model_id,
        "display_name": meta.get("name", model_id),
        "status": status,
        "detail": detail,
        "latency_ms": latency_ms,
        "response_chars": response_chars
    })
    print(f"[{index:02d}/{len(models):02d}] {status:20s} {model_id} ({latency_ms} ms)")
    progress = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {"completed": len(results), "configured_total": len(models)},
        "results": results,
        "security_note": "No session token, bridge key, raw response body, or response text is stored."
    }
    progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    done_ids.add(model_id)
    time.sleep(0.25)
    if len(results) - batch_start >= 5:
        break

passed = sum(1 for row in results if row["status"] == "PASS")
failed = len(results) - passed
report = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "base_url": BRIDGE,
    "test_type": "single non-streaming smoke request per OpenCode-configured model",
    "prompt": "Reply with exactly GNW_MODEL_TEST_OK and no other text.",
    "summary": {"total": len(results), "pass": passed, "fail": failed},
    "results": results,
    "security_note": "No session token, bridge key, raw response body, or response text is stored."
}
json_path = OUT / "perplexity-configured-model-smoke-20261023.json"
md_path = OUT / "perplexity-configured-model-smoke-20261023.md"
json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
lines = [
    "# GNW Perplexity Bridge — Configured Model Smoke Test",
    "",
    f"- Generated UTC: {report['generated_at_utc']}",
    f"- Total configured models tested: {len(results)}",
    f"- PASS: {passed}",
    f"- FAIL: {failed}",
    "",
    "| # | Model ID | Display name | Result | Latency ms | Response chars | Detail |",
    "|---:|---|---|---|---:|---:|---|"
]
for row in results:
    lines.append(f"| {row['index']} | {row['model_id']} | {row['display_name']} | {row['status']} | {row['latency_ms']} | {row['response_chars']} | {row['detail']} |")
lines += ["", "Only response presence/length and status are recorded; response text and credentials are not stored.", ""]
md_path.write_text("\n".join(lines), encoding="utf-8")
print(f"MODEL_SMOKE_SUMMARY total={len(results)} pass={passed} fail={failed}")
print(f"JSON_REPORT={json_path}")
print(f"MARKDOWN_REPORT={md_path}")
