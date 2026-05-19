-- Migration 004: PMS integration columns and sync log.
-- Idempotent: safe to re-run against any prior state of this migration.
-- Every column add uses ADD COLUMN IF NOT EXISTS so partial applies recover.

-- Step 1: PMS credential and metadata columns on properties.
ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS pms_api_key          text,
  ADD COLUMN IF NOT EXISTS pms_base_url         text,
  ADD COLUMN IF NOT EXISTS pms_last_sync_at     timestamptz,
  ADD COLUMN IF NOT EXISTS pms_refresh_token    text,
  ADD COLUMN IF NOT EXISTS pms_token_expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS pms_external_id      text;

CREATE INDEX IF NOT EXISTS idx_properties_pms_type
  ON properties(pms_type) WHERE pms_type IS NOT NULL;

-- Step 2: pms_sync_log base table for fresh installs.
-- CREATE TABLE IF NOT EXISTS is a no-op on a pre-existing table, so Step 3
-- adds any missing columns explicitly.
CREATE TABLE IF NOT EXISTS pms_sync_log (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid        NOT NULL REFERENCES tenants(id)    ON DELETE CASCADE,
  property_id   uuid        NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  pms_type      text        NOT NULL,
  sync_kind     text        NOT NULL,
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz,
  records_count int,
  status        text        NOT NULL DEFAULT 'running',
  error_message text,
  metadata      jsonb
);

-- Step 3: Additive columns required by Phase 4C scheduler.
-- Runs cleanly whether the table is fresh (no-ops) or pre-existing (adds them).
ALTER TABLE pms_sync_log
  ADD COLUMN IF NOT EXISTS sync_date        date          NOT NULL DEFAULT current_date,
  ADD COLUMN IF NOT EXISTS duration_seconds numeric(10,3),
  ADD COLUMN IF NOT EXISTS records_synced   int,
  ADD COLUMN IF NOT EXISTS errors           jsonb,
  ADD COLUMN IF NOT EXISTS created_at       timestamptz   NOT NULL DEFAULT now();

-- Step 4: Indexes (created after the referenced columns are guaranteed to exist).
CREATE INDEX IF NOT EXISTS idx_pms_sync_log_property
  ON pms_sync_log(property_id, sync_kind, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_pms_sync_log_sync_date
  ON pms_sync_log(property_id, sync_date DESC);
