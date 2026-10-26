import sys, json, os
import httpx
sys.path.append(r'd:/GNW/perplexity-browser-api')
from gnw_secrets import get_bridge_key
key = get_bridge_key()
model_id = 'openai/gpt-5.6-terra'
url = 'http://127.0.0.1:8000/v1/chat/completions'
payload = {
    "model": model_id,
    "messages": [{"role": "user", "content": "GNW_HEALTH_CHECK"}],
    "max_tokens": 5
}
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
try:
    resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
    print(json.dumps({"model": model_id, "status": resp.status_code, "content": resp.text[:200]}, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"model": model_id, "error": str(e)}, ensure_ascii=False))
