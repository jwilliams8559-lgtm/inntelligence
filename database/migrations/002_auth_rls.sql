-- Migration 002: Auth, RLS Policies, Custom JWT Hook
-- Run after 001_schema.sql

CREATE TABLE IF NOT EXISTS user_profiles (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id   uuid        REFERENCES tenants(id) ON DELETE SET NULL,
  role        text        NOT NULL DEFAULT 'inn_owner'
                          CHECK (role IN ('inn_owner','inn_manager','shg_admin','shg_analyst')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_profiles_user_id   ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_tenant_id ON user_profiles(tenant_id);

-- Custom access token hook: injects tenant_id and app_role into the JWT.
-- After running this file, register public.custom_access_token_hook in
-- Supabase Dashboard under Authentication > Hooks > Custom Access Token Hook.
CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  claims      jsonb;
  v_tenant_id uuid;
  v_role      text;
BEGIN
  SELECT tenant_id, role
    INTO v_tenant_id, v_role
    FROM public.user_profiles
   WHERE user_id = (event->>'user_id')::uuid;

  claims := event->'claims';

  IF v_tenant_id IS NOT NULL THEN
    claims := jsonb_set(claims, '{tenant_id}', to_jsonb(v_tenant_id::text));
  END IF;

  claims := jsonb_set(
    claims,
    '{app_role}',
    to_jsonb(COALESCE(v_role, 'inn_owner'))
  );

  RETURN jsonb_set(event, '{claims}', claims);
END;
$$;

GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin;
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook FROM authenticated, anon;

-- RLS helper functions read tenant_id and app_role from JWT claims.
CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT (auth.jwt()->>'tenant_id')::uuid;
$$;

CREATE OR REPLACE FUNCTION public.current_app_role()
RETURNS text LANGUAGE sql STABLE AS $$
  SELECT auth.jwt()->>'app_role';
$$;

-- Enable RLS. market_signals is excluded (public aggregate data).
ALTER TABLE tenants              ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties           ENABLE ROW LEVEL SECURITY;
ALTER TABLE room_types           ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings             ENABLE ROW LEVEL SECURITY;
ALTER TABLE occupancy_snapshots  ENABLE ROW LEVEL SECURITY;
ALTER TABLE guests               ENABLE ROW LEVEL SECURITY;

-- Policies: tenants
CREATE POLICY "tenants_select" ON tenants
  FOR SELECT USING (
    id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "tenants_insert" ON tenants
  FOR INSERT WITH CHECK (
    current_app_role() = 'shg_admin'
  );

CREATE POLICY "tenants_update" ON tenants
  FOR UPDATE USING (
    (id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "tenants_delete" ON tenants
  FOR DELETE USING (
    current_app_role() = 'shg_admin'
  );

-- Policies: user_profiles
CREATE POLICY "user_profiles_select" ON user_profiles
  FOR SELECT USING (
    user_id = auth.uid()
    OR tenant_id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "user_profiles_insert" ON user_profiles
  FOR INSERT WITH CHECK (
    tenant_id = current_tenant_id()
    AND current_app_role() IN ('inn_owner', 'shg_admin')
  );

CREATE POLICY "user_profiles_update" ON user_profiles
  FOR UPDATE USING (
    (tenant_id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "user_profiles_delete" ON user_profiles
  FOR DELETE USING (
    current_app_role() = 'shg_admin'
  );

-- Policies: properties (inn_manager excluded from INSERT/DELETE)
CREATE POLICY "properties_select" ON properties
  FOR SELECT USING (
    tenant_id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "properties_insert" ON properties
  FOR INSERT WITH CHECK (
    tenant_id = current_tenant_id()
    AND current_app_role() IN ('inn_owner', 'shg_admin')
  );

CREATE POLICY "properties_update" ON properties
  FOR UPDATE USING (
    (tenant_id = current_tenant_id() AND current_app_role() IN ('inn_owner', 'shg_admin'))
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "properties_delete" ON properties
  FOR DELETE USING (
    (tenant_id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );

-- Policies: room_types
CREATE POLICY "room_types_select" ON room_types
  FOR SELECT USING (
    tenant_id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "room_types_insert" ON room_types
  FOR INSERT WITH CHECK (
    tenant_id = current_tenant_id()
    AND current_app_role() IN ('inn_owner', 'shg_admin')
  );

CREATE POLICY "room_types_update" ON room_types
  FOR UPDATE USING (
    (tenant_id = current_tenant_id() AND current_app_role() IN ('inn_owner', 'shg_admin'))
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "room_types_delete" ON room_types
  FOR DELETE USING (
    (tenant_id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );

-- Policies: rate_recommendations (inn_manager can read/write but not delete)
CREATE POLICY "rate_recs_select" ON rate_recommendations
  FOR SELECT USING (
    tenant_id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "rate_recs_insert" ON rate_recommendations
  FOR INSERT WITH CHECK (
    tenant_id = current_tenant_id()
    AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin')
  );

CREATE POLICY "rate_recs_update" ON rate_recommendations
  FOR UPDATE USING (
    (tenant_id = current_tenant_id()
     AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin'))
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "rate_recs_delete" ON rate_recommendations
  FOR DELETE USING (
    (tenant_id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );

-- Policies: bookings
CREATE POLICY "bookings_select" ON bookings
  FOR SELECT USING (
    tenant_id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "bookings_insert" ON bookings
  FOR INSERT WITH CHECK (
    tenant_id = current_tenant_id()
    AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin')
  );

CREATE POLICY "bookings_update" ON bookings
  FOR UPDATE USING (
    (tenant_id = current_tenant_id()
     AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin'))
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "bookings_delete" ON bookings
  FOR DELETE USING (
    (tenant_id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );

-- Policies: occupancy_snapshots
CREATE POLICY "occ_snapshots_select" ON occupancy_snapshots
  FOR SELECT USING (
    tenant_id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "occ_snapshots_insert" ON occupancy_snapshots
  FOR INSERT WITH CHECK (
    tenant_id = current_tenant_id()
    AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin')
  );

CREATE POLICY "occ_snapshots_update" ON occupancy_snapshots
  FOR UPDATE USING (
    (tenant_id = current_tenant_id()
     AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin'))
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "occ_snapshots_delete" ON occupancy_snapshots
  FOR DELETE USING (
    (tenant_id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );

-- Policies: guests
CREATE POLICY "guests_select" ON guests
  FOR SELECT USING (
    tenant_id = current_tenant_id()
    OR current_app_role() IN ('shg_admin', 'shg_analyst')
  );

CREATE POLICY "guests_insert" ON guests
  FOR INSERT WITH CHECK (
    tenant_id = current_tenant_id()
    AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin')
  );

CREATE POLICY "guests_update" ON guests
  FOR UPDATE USING (
    (tenant_id = current_tenant_id()
     AND current_app_role() IN ('inn_owner', 'inn_manager', 'shg_admin'))
    OR current_app_role() = 'shg_admin'
  );

CREATE POLICY "guests_delete" ON guests
  FOR DELETE USING (
    (tenant_id = current_tenant_id() AND current_app_role() = 'inn_owner')
    OR current_app_role() = 'shg_admin'
  );
