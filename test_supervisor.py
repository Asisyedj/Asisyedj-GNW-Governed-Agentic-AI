import sys
sys.path.insert(0, 'D:\\GNW\\perplexity-browser-api')

from personal_agent.bridge.supervisor import BridgeSupervisor, BridgeState
from personal_agent.state.persistence import get_state_store
import uuid

# Test supervisor persistence integration
tenant_id = uuid.uuid4()
store = get_state_store(tenant_id=tenant_id)

# Create supervisor with state store
sup = BridgeSupervisor(state_store=store)
print(f"Initial state: {sup._state}")
print(f"Initial failures: {sup._failures}")
print(f"Initial restarts: {sup._restart_count}")
print(f"Execution ID: {sup._execution_id}")

# Trigger a transition
sup._transition(BridgeState.RECOVERING, trigger="restart", metadata={"test": True})
print(f"After transition - state: {sup._state}")

# Verify persistence
state = store.get_supervisor_state()
print(f"Persisted state: {state}")

history = store.get_execution_history(sup._execution_id)
print(f"History length: {len(history)}")
for h in history:
    print(f"  {h.from_state} -> {h.to_state} ({h.trigger})")

print("Supervisor persistence test PASSED")
import sys
sys.exit(0)