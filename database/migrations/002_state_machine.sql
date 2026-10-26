-- Migration 002: Execution State Machine Persistence
-- GNW Governed Agent - P3C: Execution State Machine Persistence

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Execution states table - tracks current state per component
CREATE TABLE execution_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL,  -- logical action ID
    component TEXT NOT NULL,     -- 'supervisor', 'router', 'bridge'
    state TEXT NOT NULL,
    prev_state TEXT,
    transition_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tenant_id UUID NOT NULL
);

-- State transitions table - append-only audit trail
CREATE TABLE state_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES execution_states(execution_id),
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL,  -- 'health_check', 'auth_check', 'restart', 'manual'
    actor TEXT,             -- 'supervisor', 'router', 'admin'
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

-- Indexes for query performance
CREATE INDEX idx_executions_component ON execution_states(component);
CREATE INDEX idx_executions_tenant ON execution_states(tenant_id);
CREATE INDEX idx_executions_execution_id ON execution_states(execution_id);
CREATE INDEX idx_transitions_execution ON state_transitions(execution_id);
CREATE INDEX idx_transitions_tenant ON state_transitions(tenant_id);
CREATE INDEX idx_transitions_timestamp ON state_transitions(timestamp);

-- Trigger to enforce append-only: prevent deletion and modification of state_transitions
CREATE OR REPLACE FUNCTION enforce_state_transitions_append_only()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent DELETE
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'state_transitions table is append-only: DELETE not allowed';
    END IF;

    -- Prevent UPDATE on all fields (fully immutable audit trail)
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'state_transitions table is append-only: UPDATE not allowed';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER state_transitions_append_only
BEFORE DELETE OR UPDATE ON state_transitions
FOR EACH ROW EXECUTE FUNCTION enforce_state_transitions_append_only();

-- Trigger to enforce append-only on execution_states (allow UPDATE on state/prev_state/metadata/created_at only)
CREATE OR REPLACE FUNCTION enforce_execution_states_append_only()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent DELETE
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'execution_states table is append-only: DELETE not allowed';
    END IF;

    -- Prevent UPDATE on immutable fields
    IF TG_OP = 'UPDATE' THEN
        IF OLD.id IS DISTINCT FROM NEW.id
           OR OLD.execution_id IS DISTINCT FROM NEW.execution_id
           OR OLD.component IS DISTINCT FROM NEW.component
           OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
            RAISE EXCEPTION 'execution_states table: immutable fields cannot be modified';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER execution_states_append_only
BEFORE DELETE OR UPDATE ON execution_states
FOR EACH ROW EXECUTE FUNCTION enforce_execution_states_append_only();

-- Function to record a state transition atomically with row locking
CREATE OR REPLACE FUNCTION record_state_transition(
    p_execution_id UUID,
    p_component TEXT,
    p_from_state TEXT,
    p_to_state TEXT,
    p_trigger TEXT,
    p_actor TEXT,
    p_tenant_id UUID,
    p_metadata JSONB DEFAULT '{}'::JSONB
)
RETURNS UUID AS $$
DECLARE
    v_transition_id UUID;
    v_state_id UUID;
BEGIN
    -- Lock the execution_states row for this execution_id + component to prevent race conditions
    PERFORM * FROM execution_states
    WHERE execution_id = p_execution_id
      AND component = p_component
      AND tenant_id = p_tenant_id
    FOR UPDATE;

    -- Insert or update execution_states with new current state
    INSERT INTO execution_states (execution_id, component, state, prev_state, transition_reason, metadata, tenant_id)
    VALUES (p_execution_id, p_component, p_to_state, p_from_state, p_trigger, p_metadata, p_tenant_id)
    ON CONFLICT (execution_id, component, tenant_id) DO UPDATE SET
        state = EXCLUDED.state,
        prev_state = EXCLUDED.prev_state,
        transition_reason = EXCLUDED.transition_reason,
        metadata = EXCLUDED.metadata,
        created_at = NOW()
    RETURNING id INTO v_state_id;

    -- Append-only insert into state_transitions
    INSERT INTO state_transitions (execution_id, from_state, to_state, trigger, actor, metadata, tenant_id)
    VALUES (p_execution_id, p_from_state, p_to_state, p_trigger, p_actor, p_metadata, p_tenant_id)
    RETURNING id INTO v_transition_id;

    RETURN v_transition_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get current state for a component
CREATE OR REPLACE FUNCTION get_current_state(
    p_component TEXT,
    p_tenant_id UUID
)
RETURNS TABLE (
    execution_id UUID,
    component TEXT,
    state TEXT,
    prev_state TEXT,
    transition_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT es.execution_id, es.component, es.state, es.prev_state, es.transition_reason, es.metadata, es.created_at
    FROM execution_states es
    WHERE es.component = p_component
      AND es.tenant_id = p_tenant_id
    ORDER BY es.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get full execution history
CREATE OR REPLACE FUNCTION get_execution_history(
    p_execution_id UUID,
    p_tenant_id UUID
)
RETURNS TABLE (
    id UUID,
    execution_id UUID,
    from_state TEXT,
    to_state TEXT,
    trigger TEXT,
    actor TEXT,
    timestamp TIMESTAMP WITH TIME ZONE,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT st.id, st.execution_id, st.from_state, st.to_state, st.trigger, st.actor, st.timestamp, st.metadata
    FROM state_transitions st
    WHERE st.execution_id = p_execution_id
      AND st.tenant_id = p_tenant_id
    ORDER BY st.timestamp ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to recover supervisor/router state on startup
CREATE OR REPLACE FUNCTION recover_component_state(
    p_component TEXT,
    p_tenant_id UUID
)
RETURNS TABLE (
    execution_id UUID,
    state TEXT,
    prev_state TEXT,
    transition_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT es.execution_id, es.state, es.prev_state, es.transition_reason, es.metadata, es.created_at
    FROM execution_states es
    WHERE es.component = p_component
      AND es.tenant_id = p_tenant_id
    ORDER BY es.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;