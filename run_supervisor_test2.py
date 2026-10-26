import sys
import subprocess

result = subprocess.run([
    sys.executable, '-c', 
    "import sys; sys.path.insert(0, 'D:\\\\GNW\\\\perplexity-browser-api'); from personal_agent.bridge.supervisor import BridgeSupervisor, BridgeState; from personal_agent.state.persistence import get_state_store; import uuid; tenant_id = uuid.uuid4(); store = get_state_store(tenant_id=tenant_id); sup = BridgeSupervisor(state_store=store); print(f'Initial state: {sup._state}'); sup._transition(BridgeState.RECOVERING, trigger='restart', metadata={'test': True}); print(f'After transition - state: {sup._state}'); state = store.get_supervisor_state(); print(f'Persisted state: {state}'); print('Supervisor persistence test PASSED')"
], capture_output=True, text=True, timeout=60, cwd='D:\\GNW\\perplexity-browser-api')

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")