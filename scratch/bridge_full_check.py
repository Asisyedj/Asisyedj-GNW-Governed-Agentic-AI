import sys, time, os
sys.path.append(r'D:\\GNW\\perplexity-browser-api')
from personal_agent.bridge.supervisor import BridgeSupervisor
from personal_agent.agent.router import global_router, TaskCategory
import httpx

sup = BridgeSupervisor()
sup.start()
# Wait for bridge to start and stabilize
for _ in range(10):
    time.sleep(1)
    # health check via supervisor internal flag
    if sup._state == 'HEALTHY':
        break
print('Supervisor state after wait:', sup._state)
# Direct health endpoint
try:
    resp = httpx.get('http://127.0.0.1:8000/health', timeout=5.0)
    print('Health endpoint status:', resp.status_code)
except Exception as e:
    print('Health request error:', e)
# Test a simple routed inference (use a known cheap model)
try:
    result = global_router.execute_with_fallback(
        messages=[{'role': 'user', 'content': 'GNW_HEALTH_CHECK'}],
        requested_model='perplexity/deep-research',
        task_category=TaskCategory.DEFAULT,
        timeout=10,
    )
    print('Router inference result keys:', result.keys())
    print('Content snippet:', str(result.get('content'))[:100])
except Exception as e:
    print('Router inference error:', e)
