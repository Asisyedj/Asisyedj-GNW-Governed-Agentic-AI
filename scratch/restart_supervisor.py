import sys, time
sys.path.append(r'D:\\GNW\\perplexity-browser-api')
from personal_agent.bridge.supervisor import BridgeSupervisor

sup = BridgeSupervisor()
sup.start()
# give the daemon a moment to import new packages
time.sleep(2)
print('Supervisor restarted – state:', sup._state)
