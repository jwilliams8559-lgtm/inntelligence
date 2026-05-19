ALTER TABLE guests
  ADD COLUMN IF NOT EXISTS preferred_room_type text,
  ADD COLUMN IF NOT EXISTS booking_sources text[],
  ADD COLUMN IF NOT EXISTS next_stay_date date,
  ADD COLUMN IF NOT EXISTS unsubscribe_token text,
  ADD COLUMN IF NOT EXISTS source text;

CREATE INDEX IF NOT EXISTS idx_guests_tags
  ON guests USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_guests_property_consent
  ON guests(property_id, marketing_consent);

CREATE TABLE IF NOT EXISTS campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
  property_id uuid REFERENCES properties(id) ON DELETE CASCADE,
  name text NOT NULL,
  target_segment text,
  subject text,
  body_html text,
  status text,
  scheduled_at timestamptz,
  sent_at timestamptz,
  recipient_count int DEFAULT 0,
  delivered_count int DEFAULT 0,
  opened_count int DEFAULT 0,
  clicked_count int DEFAULT 0,
  bookings_attributed int DEFAULT 0,
  revenue_attributed decimal(10,2) DEFAULT 0,
  trigger_source text,
  trigger_metadata jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_status_check;
ALTER TABLE campaigns ADD CONSTRAINT campaigns_status_check
  CHECK (status IS NULL OR status IN ('draft','scheduled','sending','sent','cancelled'));

CREATE INDEX IF NOT EXISTS idx_campaigns_property_status
  ON campaigns(property_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS campaign_recipients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid REFERENCES campaigns(id) ON DELETE CASCADE,
  guest_id uuid REFERENCES guests(id) ON DELETE CASCADE,
  status text,
  sent_at timestamptz,
  opened_at timestamptz,
  clicked_at timestamptz,
  booking_id uuid
);

ALTER TABLE campaign_recipients DROP CONSTRAINT IF EXISTS campaign_recipients_status_check;
ALTER TABLE campaign_recipients ADD CONSTRAINT campaign_recipients_status_check
  CHECK (status IS NULL OR status IN ('pending','delivered','opened','clicked','unsubscribed','bounced'));

CREATE INDEX IF NOT EXISTS idx_campaign_recipients_campaign
  ON campaign_recipients(campaign_id, status);

CREATE INDEX IF NOT EXISTS idx_campaign_recipients_guest
  ON campaign_recipients(guest_id);

CREATE TABLE IF NOT EXISTS wifi_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
  property_id uuid REFERENCES properties(id) ON DELETE CASCADE,
  guest_id uuid REFERENCES guests(id) ON DELETE SET NULL,
  connected_at timestamptz DEFAULT now(),
  ip_hash text,
  user_agent text
);

CREATE INDEX IF NOT EXISTS idx_wifi_sessions_property
  ON wifi_sessions(property_id, connected_at DESC);
