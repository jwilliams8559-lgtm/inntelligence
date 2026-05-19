CREATE UNIQUE INDEX IF NOT EXISTS uniq_market_signals_cell
  ON market_signals(market, month, day_of_week);

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS stripe_customer_id text,
  ADD COLUMN IF NOT EXISTS stripe_subscription_id text,
  ADD COLUMN IF NOT EXISTS plan_tier text,
  ADD COLUMN IF NOT EXISTS trial_ends_at timestamptz,
  ADD COLUMN IF NOT EXISTS billing_email text,
  ADD COLUMN IF NOT EXISTS subscription_status text,
  ADD COLUMN IF NOT EXISTS current_period_end timestamptz;

UPDATE tenants
  SET plan_tier = NULL
  WHERE plan_tier IS NOT NULL
  AND plan_tier NOT IN ('founding_member','starter','professional','enterprise','cancelled');

ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_plan_tier_check;
ALTER TABLE tenants ADD CONSTRAINT tenants_plan_tier_check
  CHECK (plan_tier IS NULL OR plan_tier IN
    ('founding_member','starter','professional','enterprise','cancelled'));

UPDATE tenants SET plan_tier = 'founding_member'
  WHERE slug = 'anchorage-1770-demo' AND plan_tier IS NULL;

CREATE TABLE IF NOT EXISTS billing_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
  stripe_event_id text UNIQUE,
  event_type text,
  payload jsonb,
  processed_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_billing_events_tenant
  ON billing_events(tenant_id, processed_at DESC);
