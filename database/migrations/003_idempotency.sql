-- Migration 003: Idempotency Keys & Dispatch Records
-- GNW Governed Agent - P3D: Idempotency Keys & Dispatch Records
--
-- The DDL below is intentionally portable: it runs unmodified on both
-- PostgreSQL and SQLite (only `CREATE TABLE IF NOT EXISTS` and simple
-- types are used). Timestamps are stored as unix epoch seconds (REAL) so the
-- Python implementation (personal_agent/state/idempotency.py) and the SQL
-- layer agree on a single representation.
--
-- Multi-tenancy: every row carries tenant_id and every query is scoped to it.

CREATE TABLE IF NOT EXISTS dispatch_records (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL UNIQUE,  -- SHA256(requirement_id || canonical_args)
    requirement_id TEXT NOT NULL,
    canonical_args_hash TEXT NOT NULL,
    component TEXT NOT NULL,          -- 'router', 'bridge', 'tool'
    provider_request_id TEXT,         -- external provider's request ID
    idempotency_key TEXT,             -- our idempotency key sent to the provider
    status TEXT NOT NULL DEFAULT 'dispatched',  -- 'dispatched' | 'succeeded' | 'failed' | 'reconciled'
    response_hash TEXT,               -- SHA256 of provider response
    attempts INTEGER DEFAULT 0,
    last_attempt_at REAL,             -- unix epoch seconds
    reconciled_at REAL,               -- unix epoch seconds
    reconciled_by TEXT,               -- operator UUID (TEXT for SQLite compat)
    reconciled_action TEXT,           -- 'mark_succeeded' | 'mark_failed' | 'retry'
    created_at REAL NOT NULL,         -- unix epoch seconds
    tenant_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dispatch_action ON dispatch_records(action_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_records(status);
CREATE INDEX IF NOT EXISTS idx_dispatch_tenant ON dispatch_records(tenant_id);

-- Supporting indexes for reconciliation and audit queries.
CREATE INDEX IF NOT EXISTS idx_dispatch_requirement ON dispatch_records(requirement_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_provider_req ON dispatch_records(provider_request_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_created ON dispatch_records(created_at);

-- Qualified lookups: one current dispatch per (tenant_id, action_id).
CREATE UNIQUE INDEX IF NOT EXISTS uq_dispatch_tenant_action ON dispatch_records(tenant_id, action_id);

-- ---------------------------------------------------------------------------
-- PostgreSQL-only governance extensions.
-- Everything below is skipped by SQLite (no trigger/function support).
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    -- Append-only guard: the audit history of dispatch records may never be
    -- deleted, and its identity fields may never be rewritten.
    CREATE OR REPLACE FUNCTION enforce_dispatch_records_append_only()
    RETURNS TRIGGER AS $fn$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'dispatch_records table is append-only: DELETE not allowed';
        END IF;

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
    $fn$ LANGUAGE plpgsql;

    EXECUTE 'DROP TRIGGER IF EXISTS dispatch_records_append_only ON dispatch_records';
    EXECUTE 'CREATE TRIGGER dispatch_records_append_only
             BEFORE DELETE OR UPDATE ON dispatch_records
             FOR EACH ROW EXECUTE FUNCTION enforce_dispatch_records_append_only()';
END $$;

-- Atomically record a dispatch attempt (idempotent upsert on action_id).
CREATE OR REPLACE FUNCTION record_dispatch(
    p_action_id TEXT,
    p_requirement_id TEXT,
    p_canonical_args_hash TEXT,
    p_component TEXT,
    p_idempotency_key TEXT,
    p_tenant_id TEXT
)
RETURNS TEXT AS $$
DECLARE
    v_dispatch_id TEXT;
BEGIN
    INSERT INTO dispatch_records (
        id, action_id, requirement_id, canonical_args_hash, component,
        idempotency_key, status, attempts, last_attempt_at, created_at, tenant_id
    ) VALUES (
        gen_random_uuid()::text, p_action_id, p_requirement_id, p_canonical_args_hash, p_component,
        p_idempotency_key, 'dispatched', 1, EXTRACT(EPOCH FROM NOW()), EXTRACT(EPOCH FROM NOW()), p_tenant_id
    )
    ON CONFLICT (action_id) DO UPDATE SET
        attempts = dispatch_records.attempts + 1,
        last_attempt_at = EXTRACT(EPOCH FROM NOW()),
        status = CASE
            WHEN dispatch_records.status = 'succeeded' THEN 'succeeded'
            WHEN dispatch_records.status = 'reconciled' THEN 'reconciled'
            ELSE 'dispatched'
        END,
        idempotency_key = excluded.idempotency_key
    RETURNING id INTO v_dispatch_id;

    RETURN v_dispatch_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Record the provider's response for a dispatch.
CREATE OR REPLACE FUNCTION record_provider_response(
    p_action_id TEXT,
    p_provider_request_id TEXT,
    p_response_hash TEXT,
    p_status TEXT,  -- 'succeeded' | 'failed'
    p_tenant_id TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
BEGIN
    IF p_status NOT IN ('succeeded', 'failed') THEN
        RAISE EXCEPTION 'Invalid status: %', p_status;
    END IF;

    UPDATE dispatch_records
    SET provider_request_id = p_provider_request_id,
        response_hash = p_response_hash,
        status = p_status,
        last_attempt_at = EXTRACT(EPOCH FROM NOW())
    WHERE action_id = p_action_id
      AND tenant_id = p_tenant_id;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get a dispatch record by action_id (tenant-scoped).
CREATE OR REPLACE FUNCTION get_dispatch_record(
    p_action_id TEXT,
    p_tenant_id TEXT
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

-- Find ambiguous actions: dispatched, no response, older than the threshold.
CREATE OR REPLACE FUNCTION get_ambiguous_actions(
    p_tenant_id TEXT,
    p_older_than_minutes INT DEFAULT 5
)
RETURNS TABLE (
    id TEXT,
    action_id TEXT,
    requirement_id TEXT,
    component TEXT,
    provider_request_id TEXT,
    idempotency_key TEXT,
    status TEXT,
    attempts INT,
    last_attempt_at REAL,
    created_at REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT dr.id, dr.action_id, dr.requirement_id, dr.component,
           dr.provider_request_id, dr.idempotency_key, dr.status,
           dr.attempts, dr.last_attempt_at, dr.created_at
    FROM dispatch_records dr
    WHERE dr.tenant_id = p_tenant_id
      AND dr.status = 'dispatched'
      AND COALESCE(dr.last_attempt_at, dr.created_at)
          < EXTRACT(EPOCH FROM NOW()) - (p_older_than_minutes * 60)
    ORDER BY COALESCE(dr.last_attempt_at, dr.created_at) ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Reconcile an ambiguous dispatch record.
CREATE OR REPLACE FUNCTION reconcile_dispatch(
    p_action_id TEXT,
    p_tenant_id TEXT,
    p_reconciled_by TEXT,
    p_reconciled_action TEXT  -- 'mark_succeeded' | 'mark_failed' | 'retry'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
    v_current_status TEXT;
BEGIN
    SELECT status INTO v_current_status
    FROM dispatch_records
    WHERE action_id = p_action_id
      AND tenant_id = p_tenant_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_current_status NOT IN ('dispatched', 'ambiguous') THEN
        RAISE EXCEPTION 'Cannot reconcile action with status: %', v_current_status;
    END IF;

    IF p_reconciled_action = 'mark_succeeded' OR p_reconciled_action = 'mark_failed' THEN
        UPDATE dispatch_records
        SET status = 'reconciled',
            reconciled_at = EXTRACT(EPOCH FROM NOW()),
            reconciled_by = p_reconciled_by,
            reconciled_action = p_reconciled_action
        WHERE action_id = p_action_id
          AND tenant_id = p_tenant_id;
    ELSIF p_reconciled_action = 'retry' THEN
        UPDATE dispatch_records
        SET status = 'dispatched',
            reconciled_at = EXTRACT(EPOCH FROM NOW()),
            reconciled_by = p_reconciled_by,
            reconciled_action = 'retry',
            attempts = attempts + 1,
            last_attempt_at = EXTRACT(EPOCH FROM NOW())
        WHERE action_id = p_action_id
          AND tenant_id = p_tenant_id;
    ELSE
        RAISE EXCEPTION 'Invalid reconciled_action: %', p_reconciled_action;
    END IF;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
