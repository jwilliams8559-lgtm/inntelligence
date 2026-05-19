CREATE TABLE IF NOT EXISTS autopilot_configs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
  property_id uuid REFERENCES properties(id) ON DELETE CASCADE,
  room_type_id uuid REFERENCES room_types(id) ON DELETE CASCADE,
  enabled bool DEFAULT false,
  max_rate_change_pct decimal(5,3) DEFAULT 0.15,
  min_confidence_score int DEFAULT 75,
  autopilot_start_hour int DEFAULT 6,
  autopilot_end_hour int DEFAULT 22,
  notify_on_publish bool DEFAULT true,
  max_daily_changes int DEFAULT 3,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_autopilot_room_type
  ON autopilot_configs(property_id, room_type_id);

CREATE INDEX IF NOT EXISTS idx_autopilot_property
  ON autopilot_configs(property_id, enabled);

CREATE TABLE IF NOT EXISTS alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
  property_id uuid REFERENCES properties(id) ON DELETE CASCADE,
  alert_type text,
  message text,
  severity text,
  metadata jsonb,
  dedup_key text,
  created_at timestamptz DEFAULT now(),
  read_at timestamptz,
  dismissed_at timestamptz
);

ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_type_check;
ALTER TABLE alerts ADD CONSTRAINT alerts_type_check
  CHECK (alert_type IS NULL OR alert_type IN
    ('surge','competitor_drop','low_occupancy','festival','gap_night','autopilot_published'));

ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_severity_check;
ALTER TABLE alerts ADD CONSTRAINT alerts_severity_check
  CHECK (severity IS NULL OR severity IN ('info','warning','critical'));

CREATE INDEX IF NOT EXISTS idx_alerts_property_unread
  ON alerts(property_id, created_at DESC)
  WHERE dismissed_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_alerts_dedup
  ON alerts(property_id, dedup_key)
  WHERE dedup_key IS NOT NULL AND dismissed_at IS NULL;

ALTER TABLE market_signals
  ADD COLUMN IF NOT EXISTS rate_elasticity numeric,
  ADD COLUMN IF NOT EXISTS seasonal_index integer,
  ADD COLUMN IF NOT EXISTS sample_property_count integer,
  ADD COLUMN IF NOT EXISTS last_aggregated_at timestamptz;
