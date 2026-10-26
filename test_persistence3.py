import sys
sys.path.insert(0, 'D:\\GNW\\perplexity-browser-api')

import sqlite3
from pathlib import Path

DB_PATH = Path('personal_agent/data/state_machine.db')
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Test basic connection
conn = sqlite3.connect(str(DB_PATH))
conn.execute('PRAGMA foreign_keys = ON')
conn.execute('PRAGMA journal_mode = WAL')
print('Basic connection OK')
conn.close()

# Test schema init
conn = sqlite3.connect(str(DB_PATH))
conn.execute('PRAGMA foreign_keys = ON')
conn.execute('PRAGMA journal_mode = WAL')
schema = '''
CREATE TABLE IF NOT EXISTS execution_states (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    component TEXT NOT NULL,
    state TEXT NOT NULL,
    prev_state TEXT,
    transition_reason TEXT,
    metadata TEXT,
    created_at REAL NOT NULL,
    tenant_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_transitions (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL,
    actor TEXT,
    timestamp REAL NOT NULL,
    metadata TEXT,
    tenant_id TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_component_tenant
    ON execution_states(execution_id, component, tenant_id);
'''
conn.executescript(schema)
print('Schema init OK')
conn.close()

# Test record_transition logic
import uuid
import time
import json

conn = sqlite3.connect(str(DB_PATH))
conn.execute('PRAGMA foreign_keys = ON')
conn.execute('PRAGMA journal_mode = WAL')
conn.row_factory = sqlite3.Row

eid = uuid.uuid4()
tid = uuid.uuid4()
now = time.time()

conn.execute(
    'SELECT 1 FROM execution_states WHERE execution_id = ? AND component = ? AND tenant_id = ?',
    (str(eid), 'supervisor', 'test-tenant')
)
conn.execute(
    '''
    INSERT INTO execution_states (id, execution_id, component, state, prev_state, transition_reason, metadata, created_at, tenant_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(execution_id, component, tenant_id) DO UPDATE SET
        state = excluded.state,
        prev_state = excluded.prev_state,
        transition_reason = excluded.transition_reason,
        metadata = excluded.metadata,
        created_at = excluded.created_at
    ''',
    (str(uuid.uuid4()), str(eid), 'supervisor', 'RECOVERING', 'FAILED', 'restart', '{}', now, 'test-tenant')
)
conn.execute(
    '''
    INSERT INTO state_transitions (id, execution_id, from_state, to_state, trigger, actor, timestamp, metadata, tenant_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''',
    (str(tid), str(eid), 'FAILED', 'RECOVERING', 'restart', 'supervisor', now, '{}', 'test-tenant')
)
conn.commit()
print('Transaction committed')

row = conn.execute(
    'SELECT * FROM execution_states WHERE component = ? AND tenant_id = ? ORDER BY created_at DESC LIMIT 1',
    ('supervisor', 'test-tenant')
).fetchone()
print(f'Current state: {row}')

conn.close()
print('All OK')
import sys
sys.exit(0)