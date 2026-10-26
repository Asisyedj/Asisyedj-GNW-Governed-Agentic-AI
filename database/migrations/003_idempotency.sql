-- Migration 003: Idempotency Keys & Dispatch Records
-- GNW Governed Agent - P3D: Idempotency Keys & Dispatch Records

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Dispatch records table - tracks every outbound provider call for reconciliation
CREATE TABLE dispatch_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id TEXT NOT NULL UNIQUE,  -- SHA256(requirement_id || canonical_args)
    requirement_id TEXT NOT NULL,
    canonical_args_hash TEXT NOT NULL,
    component TEXT NOT NULL,  -- 'router', 'bridge', 'tool'
    provider_request_id TEXT,  -- external provider's request ID
    idempotency_key TEXT,      -- our idempotency key sent to provider
    status TEXT NOT NULL,      -- 'dispatched', 'succeeded', 'failed', 'ambiguous', 'reconciled'
    response_hash TEXT,        -- SHA256 of provider response
    attempts INT DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    reconciled_at TIMESTAMP WITH TIME ZONE,
    reconciled_by UUID,
    reconciled_action TEXT,  -- 'mark_succeeded', 'mark_failed', 'retry'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tenant_id UUID NOT NULL
);

CREATE INDEX idx_dispatch_action ON dispatch_records(action_id);
CREATE INDEX idx_dispatch_status ON dispatch_records(status);
CREATE INDEX idx_dispatch_tenant ON dispatch_records(tenant_id);
CREATE INDEX idx_dispatch_requirement ON dispatch_records(requirement_id);
CREATE INDEX idx_dispatch_provider_req ON dispatch_records(provider_request_id);
CREATE INDEX idx_dispatch_created ON dispatch_records(created_at);

-- Trigger to enforce append-only: prevent deletion and modification of immutable fields
CREATE OR REPLACE FUNCTION enforce_dispatch_records_append_only()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent DELETE
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'dispatch_records table is append-only: DELETE not allowed';
    END IF;

    -- Prevent UPDATE on immutable fields
    IF TG_OP = 'UPDATE' THEN
        IF OLD.id IS DISTINCT FROM NEW.id
           OR OLD.action_id IS DISTINCT FROM NEW.action_id
           OR OLD.requirement_id IS DISTINCT FROM NEW.requirement_id
           OR OLD.canonical_args_hash IS DISTINCT FROM NEW.canonical_args_hash
           OR OLD.component IS DISTINCT FROM NEW.component
           OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
           OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'dispatch_records table is append-only: immutable fields cannot be modified';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER dispatch_records_append_only
BEFORE DELETE OR UPDATE ON dispatch_records
FOR EACH ROW EXECUTE FUNCTION enforce_dispatch_records_append_only();

-- Function to atomically record a dispatch attempt
CREATE OR REPLACE FUNCTION record_dispatch(
    p_action_id TEXT,
    p_requirement_id TEXT,
    p_canonical_args_hash TEXT,
    p_component TEXT,
    p_idempotency_key TEXT,
    p_tenant_id UUID
)
RETURNS UUID AS $$
DECLARE
    v_dispatch_id UUID;
BEGIN
    -- Try to insert new dispatch record
    INSERT INTO dispatch_records (
        action_id, requirement_id, canonical_args_hash, component,
        idempotency_key, status, attempts, last_attempt_at, tenant_id
    ) VALUES (
        p_action_id, p_requirement_id, p_canonical_args_hash, p_component,
        p_idempotency_key, 'dispatched', 1, NOW(), p_tenant_id
    )
    ON CONFLICT (action_id) DO UPDATE SET
        attempts = dispatch_records.attempts + 1,
        last_attempt_at = NOW(),
        status = CASE
            WHEN dispatch_records.status = 'succeeded' THEN 'succeeded'
            WHEN dispatch_records.status = 'reconciled' THEN 'reconciled'
            ELSE 'dispatched'
        END
    RETURNING id INTO v_dispatch_id;

    RETURN v_dispatch_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record provider response
CREATE OR REPLACE FUNCTION record_provider_response(
    p_action_id TEXT,
    p_provider_request_id TEXT,
    p_response_hash TEXT,
    p_status TEXT,  -- 'succeeded', 'failed'
    p_tenant_id UUID
)
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE dispatch_records
    SET provider_request_id = p_provider_request_id,
        response_hash = p_response_hash,
        status = p_status,
        last_attempt_at = NOW()
    WHERE action_id = p_action_id
      AND tenant_id = p_tenant_id;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get dispatch record by action_id
CREATE OR REPLACE FUNCTION get_dispatch_record(
    p_action_id TEXT,
    p_tenant_id UUID
)
RETURNS dispatch_records AS $$
DECLARE
    v_record dispatch_records;
BEGIN
    SELECT * INTO v_record
    FROM dispatch_records
    WHERE action_id = p_action_id
      AND tenant_id = p_tenant_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    RETURN v_record;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to find ambiguous actions (dispatched but no response after timeout)
CREATE OR REPLACE FUNCTION get_ambiguous_actions(
    p_tenant_id UUID,
    p_older_than_minutes INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    action_id TEXT,
    requirement_id TEXT,
    component TEXT,
    provider_request_id TEXT,
    idempotency_key TEXT,
    status TEXT,
    attempts INT,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT dr.id, dr.action_id, dr.requirement_id, dr.component,
           dr.provider_request_id, dr.idempotency_key, dr.status,
           dr.attempts, dr.last_attempt_at, dr.created_at
    FROM dispatch_records dr
    WHERE dr.tenant_id = p_tenant_id
      AND dr.status = 'dispatched'
      AND dr.last_attempt_at < NOW() - (p_older_than_minutes || ' minutes')::INTERVAL
    ORDER BY dr.last_attempt_at ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to reconcile an ambiguous action
CREATE OR REPLACE FUNCTION reconcile_dispatch(
    p_action_id TEXT,
    p_tenant_id UUID,
    p_reconciled_by UUID,
    p_reconciled_action TEXT  -- 'mark_succeeded', 'mark_failed', 'retry'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
    v_current_status TEXT;
BEGIN
    -- Get current status for validation
    SELECT status INTO v_current_status
    FROM dispatch_records
    WHERE action_id = p_action_id
      AND tenant_id = p_tenant_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Only allow reconciliation of ambiguous or dispatched actions
    IF v_current_status NOT IN ('dispatched', 'ambiguous') THEN
        RAISE EXCEPTION 'Cannot reconcile action with status: %', v_current_status;
    END IF;

    IF p_reconciled_action = 'mark_succeeded' THEN
        UPDATE dispatch_records
        SET status = 'reconciled',
            reconciled_at = NOW(),
            reconciled_by = p_reconciled_by,
            reconciled_action = 'mark_succeeded'
        WHERE action_id = p_action_id
          AND tenant_id = p_tenant_id;
    ELSIF p_reconciled_action = 'mark_failed' THEN
        UPDATE dispatch_records
        SET status = 'reconciled',
            reconciled_at = NOW(),
            reconciled_by = p_reconciled_by,
            reconciled_action = 'mark_failed'
        WHERE action_id = p_action_id
          AND tenant_id = p_tenant_id;
    ELSIF p_reconciled_action = 'retry' THEN
        UPDATE dispatch_records
        SET status = 'dispatched',
            reconciled_at = NOW(),
            reconciled_by = p_reconciled_by,
            reconciled_action = 'retry',
            attempts = attempts + 1,
            last_attempt_at = NOW()
        WHERE action_id = p_action_id
          AND tenant_id = p_tenant_id;
    ELSE
        RAISE EXCEPTION 'Invalid reconciled_action: %', p_reconciled_action;
    END IF;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;