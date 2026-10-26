import sys, json, httpx, time
sys.path.append('d:/GNW/perplexity-browser-api')
# ensure bridge supervisor started
from personal_agent.bridge.supervisor import global_bridge_supervisor
global_bridge_supervisor.start()
# wait a bit for bridge to launch
time.sleep(5)
try:
    resp = httpx.get('http://127.0.0.1:8000/health', timeout=5)
    print('Status:', resp.status_code)
    print('Body:', resp.text)
except Exception as e:
    print('Error:', e)
