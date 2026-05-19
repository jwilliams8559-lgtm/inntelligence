-- =============================================================================
-- SHG Pricing Engine — Multi-tenant Schema
-- Migration 001: Core tables and indexes
-- Target: Supabase (PostgreSQL 15+)
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TENANTS
-- =============================================================================
CREATE TABLE IF NOT EXISTS tenants (
  id          uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text          NOT NULL,
  slug        text          NOT NULL UNIQUE,
  plan_tier   text          NOT NULL DEFAULT 'starter',
  active      boolean       NOT NULL DEFAULT true,
  created_at  timestamptz   NOT NULL DEFAULT now()
);

-- =============================================================================
-- PROPERTIES
-- =============================================================================
CREATE TABLE IF NOT EXISTS properties (
  id                    uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name                  text          NOT NULL,
  address               text,
  city                  text,
  state                 text,
  zip                   text,
  total_rooms           int,
  pms_type              text,
  channel_manager_type  text,
  timezone              text          NOT NULL DEFAULT 'America/New_York',
  created_at            timestamptz   NOT NULL DEFAULT now()
);

CREATE INDEX idx_properties_tenant_id ON properties(tenant_id);

-- =============================================================================
-- ROOM TYPES
-- =============================================================================
CREATE TABLE IF NOT EXISTS room_types (
  id          uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  property_id uuid          NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  name        text          NOT NULL,
  description text,
  base_rate   decimal(10,2) NOT NULL,
  min_rate    decimal(10,2) NOT NULL,
  max_rate    decimal(10,2) NOT NULL,
  total_count int           NOT NULL DEFAULT 1,
  created_at  timestamptz   NOT NULL DEFAULT now()
);

CREATE INDEX idx_room_types_tenant_id ON room_types(tenant_id);
CREATE INDEX idx_room_types_property_id ON room_types(property_id);

-- =============================================================================
-- RATE RECOMMENDATIONS
-- =============================================================================
CREATE TABLE IF NOT EXISTS rate_recommendations (
  id                uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  property_id       uuid          NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  room_type_id      uuid          NOT NULL REFERENCES room_types(id) ON DELETE CASCADE,
  target_date       date          NOT NULL,
  recommended_rate  decimal(10,2) NOT NULL,
  current_rate      decimal(10,2),
  demand_score      int           CHECK (demand_score BETWEEN 0 AND 100),
  confidence_score  int           CHECK (confidence_score BETWEEN 0 AND 100),
  reasoning         text,
  status            text          NOT NULL DEFAULT 'pending'
                                  CHECK (status IN ('pending','approved','rejected','auto_published','published')),
  created_at        timestamptz   NOT NULL DEFAULT now(),
  published_at      timestamptz
);

CREATE INDEX idx_rate_recs_tenant_id   ON rate_recommendations(tenant_id);
CREATE INDEX idx_rate_recs_property_id ON rate_recommendations(property_id);
CREATE INDEX idx_rate_recs_target_date ON rate_recommendations(target_date);
CREATE INDEX idx_rate_recs_status      ON rate_recommendations(status);

-- =============================================================================
-- BOOKINGS
-- =============================================================================
CREATE TABLE IF NOT EXISTS bookings (
  id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  property_id     uuid          NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  room_type_id    uuid          NOT NULL REFERENCES room_types(id) ON DELETE CASCADE,
  check_in        date          NOT NULL,
  check_out       date          NOT NULL,
  rate_paid       decimal(10,2) NOT NULL,
  booking_source  text,
  guest_id        uuid,
  booked_at       timestamptz,
  created_at      timestamptz   NOT NULL DEFAULT now(),
  CONSTRAINT bookings_check_in_out CHECK (check_out > check_in)
);

CREATE INDEX idx_bookings_tenant_id   ON bookings(tenant_id);
CREATE INDEX idx_bookings_property_id ON bookings(property_id);
CREATE INDEX idx_bookings_check_in    ON bookings(check_in);
CREATE INDEX idx_bookings_guest_id    ON bookings(guest_id);

-- =============================================================================
-- OCCUPANCY SNAPSHOTS
-- =============================================================================
CREATE TABLE IF NOT EXISTS occupancy_snapshots (
  id              uuid           PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid           NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  property_id     uuid           NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  snapshot_date   date           NOT NULL,
  room_type_id    uuid           NOT NULL REFERENCES room_types(id) ON DELETE CASCADE,
  rooms_available int            NOT NULL,
  rooms_occupied  int            NOT NULL,
  occupancy_rate  decimal(5,4)   NOT NULL,
  adr             decimal(10,2)  NOT NULL,
  revpar          decimal(10,2)  NOT NULL,
  created_at      timestamptz    NOT NULL DEFAULT now()
);

CREATE INDEX idx_occ_snapshots_tenant_id ON occupancy_snapshots(tenant_id);
CREATE INDEX idx_occ_snapshots_property  ON occupancy_snapshots(property_id, snapshot_date);
CREATE UNIQUE INDEX idx_occ_snapshots_unique
  ON occupancy_snapshots(property_id, room_type_id, snapshot_date);

-- =============================================================================
-- GUESTS  (PII encrypted at application layer; email_hash for dedup)
-- =============================================================================
CREATE TABLE IF NOT EXISTS guests (
  id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  property_id         uuid          NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  first_name          text,
  last_name           text,
  email_encrypted     text,                     -- AES-256 encrypted via pgcrypto
  email_hash          text,                     -- SHA-256 for dedup lookups
  phone_encrypted     text,
  home_city           text,
  home_state          text,
  total_stays         int           NOT NULL DEFAULT 0,
  total_nights        int           NOT NULL DEFAULT 0,
  total_revenue       decimal(10,2) NOT NULL DEFAULT 0,
  avg_rate_paid       decimal(10,2),
  preferred_room_type text,
  booking_sources     text[],
  last_stay_date      date,
  marketing_consent   boolean       DEFAULT false,
  consent_date        timestamptz,
  tags                text[],
  created_at          timestamptz   NOT NULL DEFAULT now()
);

CREATE INDEX idx_guests_tenant_id   ON guests(tenant_id);
CREATE INDEX idx_guests_property_id ON guests(property_id);
CREATE INDEX idx_guests_email_hash  ON guests(email_hash);

-- =============================================================================
-- MARKET SIGNALS  (NO tenant_id — anonymized aggregate market data)
-- =============================================================================
CREATE TABLE IF NOT EXISTS market_signals (
  id                      uuid           PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_date             date           NOT NULL,
  market                  text           NOT NULL,
  day_of_week             int            CHECK (day_of_week BETWEEN 0 AND 6),
  month                   int            CHECK (month BETWEEN 1 AND 12),
  avg_occupancy           decimal(5,4),
  avg_adr                 decimal(10,2),
  booking_window_0_7      decimal(5,4),
  booking_window_8_30     decimal(5,4),
  booking_window_31_60    decimal(5,4),
  booking_window_61_plus  decimal(5,4),
  event_lift              decimal(5,4),
  created_at              timestamptz    NOT NULL DEFAULT now()
);

CREATE INDEX idx_market_signals_date   ON market_signals(signal_date);
CREATE INDEX idx_market_signals_market ON market_signals(market);
CREATE UNIQUE INDEX idx_market_signals_unique ON market_signals(signal_date, market);

-- Open read access — no RLS, fully anonymized aggregate
GRANT SELECT ON market_signals TO authenticated, anon;
