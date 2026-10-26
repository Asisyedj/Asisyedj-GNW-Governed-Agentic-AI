import json, urllib.request, os, sys, traceback
sys.path.append(r'd:/GNW/perplexity-browser-api')
try:
    from gnw_secrets import get_bridge_key
    key = get_bridge_key()
except Exception:
    key = os.getenv('BRIDGE_KEY', '')
req = urllib.request.Request('http://127.0.0.1:8000/v1/models', headers={'Authorization': f'Bearer {key}'})
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.load(resp)
    print(json.dumps(data, indent=2))
except Exception as e:
    print('Error fetching catalog:', e)
    traceback.print_exc()
