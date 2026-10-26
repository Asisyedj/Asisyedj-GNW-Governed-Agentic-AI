import sys, json, time
sys.path.append('d:/GNW/perplexity-browser-api')
from personal_agent.bridge.supervisor import global_bridge_supervisor
global_bridge_supervisor.start()
# give some time for evaluation loop to run
time.sleep(8)
print(json.dumps(global_bridge_supervisor.status()))
