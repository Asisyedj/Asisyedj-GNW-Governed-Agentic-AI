import json
import time
import urllib.request
from gnw_secrets import get_bridge_key

key = get_bridge_key()
models_to_probe = [
    'anthropic/claude-sonnet-5.5-thinking',
    'openai/gpt-6.1-sol-thinking',
    'x-ai/grok-4.7-thinking',
    'google/gemini-3.8-flash-thinking',
    'moonshot/kimi-k3-thinking',
    'z-ai/glm-5.3',
    'perplexity/best'
]

print("=== PROBING 7 MULTI-PROVIDER FLAGSHIP MODELS ===")
for m in models_to_probe:
    t0 = time.time()
    payload = {
        'model': m,
        'messages': [{'role': 'user', 'content': 'Reply with GNW_PROBE_OK'}],
        'max_tokens': 20,
        'stream': False
    }
    req = urllib.request.Request(
        'http://127.0.0.1:8000/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            dt = round(time.time() - t0, 2)
            data = json.loads(res.read().decode())
            text = data['choices'][0]['message']['content'].strip().replace('\n', ' ')
            print(f"[PASS] {m:<38} | {dt}s | {text[:25]}")
    except Exception as e:
        dt = round(time.time() - t0, 2)
        print(f"[FAIL] {m:<38} | {dt}s | {str(e)[:40]}")
