import sys, time
sys.path.append(r'D:\\GNW\\perplexity-browser-api')
from personal_agent.bridge.supervisor import BridgeSupervisor
sup = BridgeSupervisor()
sup.start()
# wait for a few cycles
time.sleep(10)
print('BridgeSupervisor state:', sup._state)
# attempt health check directly
import httpx
try:
    resp = httpx.get('http://127.0.0.1:8000/health', timeout=5.0)
    print('Health endpoint status:', resp.status_code)
except Exception as e:
    print('Health request error:', e)
