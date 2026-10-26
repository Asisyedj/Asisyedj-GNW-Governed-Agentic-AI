-- Migration 001: Approvals table with atomic consumption and HMAC verification
-- GNW Governed Agent - P3B: Approval Binding & Atomic Consumption

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approver_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    agent_id UUID,
    tenant_id UUID NOT NULL,
    action_type TEXT NOT NULL,
    action_args_hash TEXT NOT NULL,
    resource_id UUID,
    scope TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    signature BYTEA NOT NULL,  -- HMAC-SHA256 of canonical approval
    consumed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (actor_id, action_type, action_args_hash, valid_from)
);

CREATE INDEX idx_approvals_tenant_valid ON approvals(tenant_id, valid_from, valid_until);
CREATE INDEX idx_approvals_actor_action ON approvals(actor_id, action_type);
CREATE INDEX idx_approvals_consumed ON approvals(consumed_at) WHERE consumed_at IS NOT NULL;
CREATE INDEX idx_approvals_revoked ON approvals(revoked_at) WHERE revoked_at IS NOT NULL;

-- Trigger to enforce append-only: prevent deletion and modification of immutable fields
CREATE OR REPLACE FUNCTION enforce_approvals_append_only()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent DELETE
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Approvals table is append-only: DELETE not allowed';
    END IF;

    -- Prevent UPDATE on immutable fields
    IF TG_OP = 'UPDATE' THEN
        IF OLD.approval_id IS DISTINCT FROM NEW.approval_id
           OR OLD.approver_id IS DISTINCT FROM NEW.approver_id
           OR OLD.actor_id IS DISTINCT FROM NEW.actor_id
           OR OLD.agent_id IS DISTINCT FROM NEW.agent_id
           OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
           OR OLD.action_type IS DISTINCT FROM NEW.action_type
           OR OLD.action_args_hash IS DISTINCT FROM NEW.action_args_hash
           OR OLD.resource_id IS DISTINCT FROM NEW.resource_id
           OR OLD.scope IS DISTINCT FROM NEW.scope
           OR OLD.policy_version IS DISTINCT FROM NEW.policy_version
           OR OLD.valid_from IS DISTINCT FROM NEW.valid_from
           OR OLD.valid_until IS DISTINCT FROM NEW.valid_until
           OR OLD.signature IS DISTINCT FROM NEW.signature
           OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'Approvals table is append-only: immutable fields cannot be modified';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER approvals_append_only
BEFORE DELETE OR UPDATE ON approvals
FOR EACH ROW EXECUTE FUNCTION enforce_approvals_append_only();

-- Function to atomically consume an approval (returns the consumed row or NULL if already consumed/revoked/expired)
CREATE OR REPLACE FUNCTION consume_approval(p_approval_id UUID, p_tenant_id UUID)
RETURNS approvals AS $$
DECLARE
    v_approval approvals;
BEGIN
    -- Atomic select-for-update with skip locked to prevent race conditions
    SELECT * INTO v_approval
    FROM approvals
    WHERE approval_id = p_approval_id
      AND tenant_id = p_tenant_id
      AND consumed_at IS NULL
      AND revoked_at IS NULL
      AND valid_until > NOW()
    FOR UPDATE SKIP LOCKED;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- Mark as consumed
    UPDATE approvals
    SET consumed_at = NOW()
    WHERE approval_id = p_approval_id
      AND tenant_id = p_tenant_id;

    RETURN v_approval;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to verify an approval without consuming it
CREATE OR REPLACE FUNCTION verify_approval(p_approval_id UUID, p_tenant_id UUID)
RETURNS approvals AS $$
DECLARE
    v_approval approvals;
BEGIN
    SELECT * INTO v_approval
    FROM approvals
    WHERE approval_id = p_approval_id
      AND tenant_id = p_tenant_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- Check expiry
    IF v_approval.valid_until <= NOW() THEN
        RETURN NULL;
    END IF

    -- Check revocation
    IF v_approval.revoked_at IS NOT NULL THEN
        RETURN NULL;
    END IF

    RETURN v_approval;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to revoke an approval
CREATE OR REPLACE FUNCTION revoke_approval(p_approval_id UUID, p_tenant_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE approvals
    SET revoked_at = NOW()
    WHERE approval_id = p_approval_id
      AND tenant_id = p_tenant_id
      AND revoked_at IS NULL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;