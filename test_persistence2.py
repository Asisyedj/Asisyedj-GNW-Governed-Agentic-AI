import sys
sys.path.insert(0, 'D:\\GNW\\perplexity-browser-api')

from personal_agent.state.persistence import ExecutionStateStore
import uuid

store = ExecutionStateStore(tenant_id=uuid.uuid4())
print('Store created')

eid = uuid.uuid4()
tid = store.record_transition(eid, 'supervisor', 'FAILED', 'RECOVERING', 'restart', 'supervisor')
print(f'Transition recorded: {tid}')

state = store.get_current_state('supervisor')
print(f'Current state: {state}')

history = store.get_execution_history(eid)
print(f'History length: {len(history)}')
for h in history:
    print(f'  {h.from_state} -> {h.to_state} ({h.trigger})')
print('Test passed!')
import sys
sys.exit(0)