ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS channel_manager_type text,
  ADD COLUMN IF NOT EXISTS channel_manager_api_key text,
  ADD COLUMN IF NOT EXISTS siteminder_hotel_code text,
  ADD COLUMN IF NOT EXISTS booking_com_hotel_id text,
  ADD COLUMN IF NOT EXISTS expedia_hotel_id text;

UPDATE properties SET channel_manager_type = NULL
WHERE channel_manager_type IS NOT NULL
  AND channel_manager_type NOT IN
      ('siteminder','booking_com_direct','expedia_direct','cloudbeds_cm','none');

ALTER TABLE properties DROP CONSTRAINT IF EXISTS properties_channel_manager_type_check;
ALTER TABLE properties ADD CONSTRAINT properties_channel_manager_type_check
  CHECK (channel_manager_type IS NULL OR channel_manager_type IN
    ('siteminder','booking_com_direct','expedia_direct','cloudbeds_cm','none'));

UPDATE properties SET
  channel_manager_type = 'siteminder',
  siteminder_hotel_code = 'ANCHORAGE1770DEMO'
WHERE name ILIKE '%Anchorage%';

CREATE TABLE IF NOT EXISTS rate_publish_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
  property_id uuid REFERENCES properties(id) ON DELETE CASCADE,
  recommendation_id uuid REFERENCES rate_recommendations(id) ON DELETE SET NULL,
  channel_manager text,
  status text CHECK (status IN ('success','partial','failed')),
  otas_updated text[],
  response_body jsonb,
  published_at timestamptz DEFAULT now(),
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_publish_log_property
  ON rate_publish_log(property_id, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_publish_log_recommendation
  ON rate_publish_log(recommendation_id);

ALTER TABLE rate_recommendations DROP CONSTRAINT IF EXISTS rate_recommendations_status_check;
ALTER TABLE rate_recommendations ADD CONSTRAINT rate_recommendations_status_check
  CHECK (status IS NULL OR status IN
    ('pending','approved','rejected','published','auto_published','publish_failed'));
