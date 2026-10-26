-- Migration 004: Mission Proof System & KPI Snapshots
-- GNW Governed Agent - P3F: Mission Proof System & KPI Automation

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Missions table: tracks mission lifecycle and proof bundles
CREATE TABLE missions (
    mission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    status TEXT NOT NULL,  -- 'PLANNING', 'ACTIVE', 'COMPLETED', 'FAILED', 'CANCELLED'
    proof_bundle JSONB,    -- {evidence_digests: [], merkle_root: "", verification_hash: ""}
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_missions_tenant_status ON missions(tenant_id, status);
CREATE INDEX idx_missions_owner ON missions(owner_id);
CREATE INDEX idx_missions_created ON missions(created_at);

-- Trigger to enforce append-only: prevent deletion and modification of immutable fields
CREATE OR REPLACE FUNCTION enforce_missions_append_only()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent DELETE
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Missions table is append-only: DELETE not allowed';
    END IF;

    -- Prevent UPDATE on immutable fields (only status, proof_bundle, started_at, completed_at can change)
    IF TG_OP = 'UPDATE' THEN
        IF OLD.mission_id IS DISTINCT FROM NEW.mission_id
           OR OLD.name IS DISTINCT FROM NEW.name
           OR OLD.description IS DISTINCT FROM NEW.description
           OR OLD.owner_id IS DISTINCT FROM NEW.owner_id
           OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
           OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'Missions table is append-only: immutable fields cannot be modified';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER missions_append_only
BEFORE DELETE OR UPDATE ON missions
FOR EACH ROW EXECUTE FUNCTION enforce_missions_append_only();

-- KPI Snapshots table: append-only daily KPI measurements
CREATE TABLE kpi_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    target_value NUMERIC,
    threshold NUMERIC,
    measured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    labels JSONB
);

CREATE INDEX idx_kpi_snapshots_tenant_metric_time ON kpi_snapshots(tenant_id, metric_name, measured_at);
CREATE INDEX idx_kpi_snapshots_measured_at ON kpi_snapshots(measured_at);

-- Trigger to enforce append-only: kpi_snapshots never modified
CREATE OR REPLACE FUNCTION enforce_kpi_snapshots_append_only()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent DELETE
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'KPI snapshots table is append-only: DELETE not allowed';
    END IF;

    -- Prevent any UPDATE
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'KPI snapshots table is append-only: UPDATE not allowed';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER kpi_snapshots_append_only
BEFORE DELETE OR UPDATE ON kpi_snapshots
FOR EACH ROW EXECUTE FUNCTION enforce_kpi_snapshots_append_only();

-- Function to create a new mission
CREATE OR REPLACE FUNCTION create_mission(
    p_name TEXT,
    p_description TEXT,
    p_owner_id UUID,
    p_tenant_id UUID
)
RETURNS missions AS $$
DECLARE
    v_mission missions;
BEGIN
    INSERT INTO missions (name, description, owner_id, tenant_id, status)
    VALUES (p_name, p_description, p_owner_id, p_tenant_id, 'PLANNING')
    RETURNING * INTO v_mission;
    RETURN v_mission;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update mission status and proof bundle
CREATE OR REPLACE FUNCTION update_mission_status(
    p_mission_id UUID,
    p_tenant_id UUID,
    p_status TEXT,
    p_proof_bundle JSONB DEFAULT NULL
)
RETURNS missions AS $$
DECLARE
    v_mission missions;
    v_now TIMESTAMP WITH TIME ZONE := NOW();
BEGIN
    UPDATE missions
    SET status = p_status,
        proof_bundle = COALESCE(p_proof_bundle, proof_bundle),
        started_at = CASE WHEN p_status = 'ACTIVE' AND started_at IS NULL THEN v_now ELSE started_at END,
        completed_at = CASE WHEN p_status IN ('COMPLETED', 'FAILED', 'CANCELLED') AND completed_at IS NULL THEN v_now ELSE completed_at END
    WHERE mission_id = p_mission_id
      AND tenant_id = p_tenant_id
    RETURNING * INTO v_mission;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    RETURN v_mission;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to insert KPI snapshot (append-only)
CREATE OR REPLACE FUNCTION insert_kpi_snapshot(
    p_tenant_id UUID,
    p_metric_name TEXT,
    p_metric_value NUMERIC,
    p_target_value NUMERIC DEFAULT NULL,
    p_threshold NUMERIC DEFAULT NULL,
    p_labels JSONB DEFAULT NULL
)
RETURNS kpi_snapshots AS $$
DECLARE
    v_snapshot kpi_snapshots;
BEGIN
    INSERT INTO kpi_snapshots (tenant_id, metric_name, metric_value, target_value, threshold, labels)
    VALUES (p_tenant_id, p_metric_name, p_metric_value, p_target_value, p_threshold, p_labels)
    RETURNING * INTO v_snapshot;
    RETURN v_snapshot;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get latest KPI value for a metric
CREATE OR REPLACE FUNCTION get_latest_kpi(
    p_tenant_id UUID,
    p_metric_name TEXT
)
RETURNS kpi_snapshots AS $$
DECLARE
    v_snapshot kpi_snapshots;
BEGIN
    SELECT * INTO v_snapshot
    FROM kpi_snapshots
    WHERE tenant_id = p_tenant_id
      AND metric_name = p_metric_name
    ORDER BY measured_at DESC
    LIMIT 1;
    RETURN v_snapshot;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get KPI trend (last N measurements)
CREATE OR REPLACE FUNCTION get_kpi_trend(
    p_tenant_id UUID,
    p_metric_name TEXT,
    p_limit INTEGER DEFAULT 30
)
RETURNS SETOF kpi_snapshots AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM kpi_snapshots
    WHERE tenant_id = p_tenant_id
      AND metric_name = p_metric_name
    ORDER BY measured_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- View for KPI dashboard (current values with trend direction)
CREATE OR REPLACE VIEW kpi_dashboard AS
WITH latest AS (
    SELECT DISTINCT ON (tenant_id, metric_name)
        tenant_id,
        metric_name,
        metric_value,
        target_value,
        threshold,
        measured_at,
        labels,
        LAG(metric_value) OVER (PARTITION BY tenant_id, metric_name ORDER BY measured_at) AS prev_value
    FROM kpi_snapshots
    ORDER BY tenant_id, metric_name, measured_at DESC
)
SELECT
    tenant_id,
    metric_name,
    metric_value,
    target_value,
    threshold,
    measured_at,
    labels,
    CASE
        WHEN prev_value IS NULL THEN 'stable'
        WHEN metric_value > prev_value THEN 'up'
        WHEN metric_value < prev_value THEN 'down'
        ELSE 'stable'
    END AS trend,
    CASE
        WHEN threshold IS NOT NULL AND metric_value < threshold THEN 'breach'
        WHEN target_value IS NOT NULL AND metric_value >= target_value THEN 'on_target'
        ELSE 'normal'
    END AS status
FROM latest;