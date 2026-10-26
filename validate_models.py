"""
Validate every model on the local perplexity-webui-scraper API, one by one.

Prerequisites:
  1. Server running: uv run perplexity-webui-scraper api --host 127.0.0.1 --port 8000
  2. Set PERPLEXITY_SESSION_TOKEN in .env or environment.

Output:
  - Prints per-model PASS / FAIL with reason
  - Writes model_validation_report_<timestamp>.json
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from openai import APIStatusError, APIConnectionError, RateLimitError, AuthenticationError

load_dotenv()

SESSION_TOKEN = os.getenv("PERPLEXITY_SESSION_TOKEN")
BASE_URL = os.getenv("PPLX_API_BASE_URL", "http://127.0.0.1:8000/v1")

if not SESSION_TOKEN:
    raise SystemExit(
        "PERPLEXITY_SESSION_TOKEN not set. Edit .env or export it, then re-run."
    )

TEST_QUERY = "Say 'ok' in one word."
TIMEOUT_SEC = 60

client = OpenAI(base_url=BASE_URL, api_key=SESSION_TOKEN, max_retries=1)


def fetch_models():
    """Return list of model ids from /v1/models."""
    models = client.models.list()
    return [m.id for m in models.data]


def test_model(model_id: str):
    """Test a single model. Returns (status, detail, latency_ms)."""
    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": TEST_QUERY}],
            stream=False,
            timeout=TIMEOUT_SEC,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        content = resp.choices[0].message.content or ""
        return "PASS", content[:80], latency_ms

    except AuthenticationError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "FAIL_AUTH", str(exc)[:120], latency_ms

    except RateLimitError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "FAIL_RATE_LIMIT", str(exc)[:120], latency_ms

    except APIStatusError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return f"FAIL_HTTP_{exc.status_code}", str(exc)[:120], latency_ms

    except APIConnectionError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "FAIL_CONNECTION", str(exc)[:120], latency_ms

    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - start) * 1000)
        return "FAIL_UNKNOWN", f"{type(exc).__name__}: {exc}"[:120], latency_ms


def main():
    print("Fetching model list from", BASE_URL)
    model_ids = fetch_models()
    print(f"Found {len(model_ids)} models. Starting validation...\n")

    results = []
    pass_count = fail_count = 0

    for idx, model_id in enumerate(model_ids, 1):
        status, detail, latency_ms = test_model(model_id)
        results.append({
            "index": idx,
            "model": model_id,
            "status": status,
            "detail": detail,
            "latency_ms": latency_ms,
            "tested_at": datetime.utcnow().isoformat() + "Z",
        })

        if status == "PASS":
            pass_count += 1
            mark = "✅"
        else:
            fail_count += 1
            mark = "❌"

        print(
            f"[{idx:3d}/{len(model_ids)}] {mark} {model_id:45s} "
            f"{status:15s} {detail} ({latency_ms} ms)"
        )
        sys.stdout.flush()
        # small pause to be gentle on the session
        time.sleep(0.5)

    # Summary
    print("\n" + "=" * 70)
    print(f"VALIDATION COMPLETE")
    print(f"  Total models : {len(model_ids)}")
    print(f"  PASS         : {pass_count}")
    print(f"  FAIL         : {fail_count}")
    print("=" * 70)

    # Write JSON report
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "base_url": BASE_URL,
        "summary": {
            "total": len(model_ids),
            "pass": pass_count,
            "fail": fail_count,
        },
        "results": results,
    }
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = Path(f"model_validation_report_{ts}.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport saved: {report_path}")

    # Also print failing models for quick reference
    fails = [r for r in results if r["status"] != "PASS"]
    if fails:
        print("\n--- FAILING MODELS ---")
        for r in fails:
            print(f"  {r['model']:45s} {r['status']} - {r['detail']}")


if __name__ == "__main__":
    main()
