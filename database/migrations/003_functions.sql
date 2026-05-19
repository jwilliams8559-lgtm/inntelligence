-- =============================================================================
-- SHG Pricing Engine — Provisioning Functions
-- Migration 003: Run after 002_auth_rls.sql
-- =============================================================================

-- =============================================================================
-- GENERIC provision_tenant
-- Creates tenant + 1 property + 4 placeholder room types + optional owner profile.
-- SECURITY DEFINER bypasses RLS so this can be called from application code.
-- Returns jsonb: {tenant_id, property_id, room_type_ids[], owner_email, slug}
-- =============================================================================
CREATE OR REPLACE FUNCTION public.provision_tenant(
  p_name          text,
  p_slug          text,
  p_owner_email   text,
  p_plan_tier     text    DEFAULT 'starter',
  p_auth_user_id  uuid    DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_tenant_id   uuid;
  v_property_id uuid;
  v_rt1         uuid;
  v_rt2         uuid;
  v_rt3         uuid;
  v_rt4         uuid;
BEGIN
  -- Tenant (idempotent on slug)
  INSERT INTO tenants (name, slug, plan_tier, active)
  VALUES (p_name, p_slug, p_plan_tier, true)
  ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, active = true
  RETURNING id INTO v_tenant_id;

  -- Abort if property already exists (re-entrant safety)
  SELECT id INTO v_property_id
    FROM properties WHERE tenant_id = v_tenant_id LIMIT 1;

  IF v_property_id IS NULL THEN
    INSERT INTO properties (tenant_id, name, timezone)
    VALUES (v_tenant_id, p_name, 'America/New_York')
    RETURNING id INTO v_property_id;

    -- 4 placeholder room types — owner customises post-provision
    INSERT INTO room_types (tenant_id, property_id, name, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id, 'Standard Room', 150.00, 99.00, 299.00, 2)
    RETURNING id INTO v_rt1;

    INSERT INTO room_types (tenant_id, property_id, name, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id, 'Deluxe Room', 199.00, 149.00, 399.00, 2)
    RETURNING id INTO v_rt2;

    INSERT INTO room_types (tenant_id, property_id, name, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id, 'Junior Suite', 249.00, 199.00, 499.00, 1)
    RETURNING id INTO v_rt3;

    INSERT INTO room_types (tenant_id, property_id, name, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id, 'Executive Suite', 349.00, 275.00, 699.00, 1)
    RETURNING id INTO v_rt4;
  END IF;

  -- Owner profile (only if auth user exists)
  IF p_auth_user_id IS NOT NULL THEN
    INSERT INTO user_profiles (user_id, tenant_id, role)
    VALUES (p_auth_user_id, v_tenant_id, 'inn_owner')
    ON CONFLICT (user_id) DO UPDATE
      SET tenant_id = EXCLUDED.tenant_id, role = 'inn_owner';
  END IF;

  RETURN jsonb_build_object(
    'tenant_id',    v_tenant_id,
    'property_id',  v_property_id,
    'room_type_ids', jsonb_build_array(v_rt1, v_rt2, v_rt3, v_rt4),
    'owner_email',  p_owner_email,
    'slug',         p_slug
  );
END;
$$;


-- =============================================================================
-- provision_tenant_anchorage
-- Specific provisioner for Anchorage 1770 Inn with exact room type configuration.
-- Returns jsonb with individual room type IDs for seed data generation.
-- =============================================================================
CREATE OR REPLACE FUNCTION public.provision_tenant_anchorage(
  p_owner_email   text    DEFAULT 'jwilliams8559@gmail.com',
  p_plan_tier     text    DEFAULT 'professional',
  p_auth_user_id  uuid    DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_tenant_id   uuid;
  v_property_id uuid;
  v_rt_wf       uuid;   -- Waterfront Suite  (4 rooms)
  v_rt_wv       uuid;   -- Waterview Suite   (4 rooms)
  v_rt_gv       uuid;   -- Garden View Room  (5 rooms)
  v_rt_co       uuid;   -- Cottage Room      (2 rooms)
BEGIN
  -- Tenant
  INSERT INTO tenants (name, slug, plan_tier, active)
  VALUES ('Anchorage 1770 Demo', 'anchorage-1770-demo', p_plan_tier, true)
  ON CONFLICT (slug) DO UPDATE SET active = true
  RETURNING id INTO v_tenant_id;

  -- Idempotency: if property already exists, return existing IDs
  SELECT p.id INTO v_property_id
    FROM properties p WHERE p.tenant_id = v_tenant_id LIMIT 1;

  IF v_property_id IS NOT NULL THEN
    SELECT id INTO v_rt_wf FROM room_types
     WHERE tenant_id = v_tenant_id AND name = 'Waterfront Suite' LIMIT 1;
    SELECT id INTO v_rt_wv FROM room_types
     WHERE tenant_id = v_tenant_id AND name = 'Waterview Suite' LIMIT 1;
    SELECT id INTO v_rt_gv FROM room_types
     WHERE tenant_id = v_tenant_id AND name = 'Garden View Room' LIMIT 1;
    SELECT id INTO v_rt_co FROM room_types
     WHERE tenant_id = v_tenant_id AND name = 'Cottage Room' LIMIT 1;
  ELSE
    -- Property
    INSERT INTO properties (
      tenant_id, name, address, city, state, zip,
      total_rooms, pms_type, channel_manager_type, timezone
    ) VALUES (
      v_tenant_id,
      'Anchorage 1770 Inn',
      '1770 Ribaut Road',
      'Beaufort', 'SC', '29902',
      15,
      'Lodgify',
      'Cloudbeds',
      'America/New_York'
    ) RETURNING id INTO v_property_id;

    -- Room Types
    INSERT INTO room_types (tenant_id, property_id, name, description, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id,
      'Waterfront Suite',
      'Premier waterfront suites with panoramic Beaufort River views, king bed, private balcony',
      378.00, 295.00, 695.00, 4)
    RETURNING id INTO v_rt_wf;

    INSERT INTO room_types (tenant_id, property_id, name, description, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id,
      'Waterview Suite',
      'Elegant suites with river views, king bed, sitting area',
      335.00, 265.00, 595.00, 4)
    RETURNING id INTO v_rt_wv;

    INSERT INTO room_types (tenant_id, property_id, name, description, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id,
      'Garden View Room',
      'Comfortable rooms overlooking manicured gardens, queen or king bed',
      295.00, 225.00, 495.00, 5)
    RETURNING id INTO v_rt_gv;

    INSERT INTO room_types (tenant_id, property_id, name, description, base_rate, min_rate, max_rate, total_count)
    VALUES (v_tenant_id, v_property_id,
      'Cottage Room',
      'Charming private cottage rooms with garden access',
      295.00, 225.00, 495.00, 2)
    RETURNING id INTO v_rt_co;
  END IF;

  -- Owner profile (only when auth user exists)
  IF p_auth_user_id IS NOT NULL THEN
    INSERT INTO user_profiles (user_id, tenant_id, role)
    VALUES (p_auth_user_id, v_tenant_id, 'inn_owner')
    ON CONFLICT (user_id) DO UPDATE
      SET tenant_id = EXCLUDED.tenant_id, role = 'inn_owner';
  END IF;

  RETURN jsonb_build_object(
    'tenant_id',           v_tenant_id,
    'property_id',         v_property_id,
    'waterfront_suite_id', v_rt_wf,
    'waterview_suite_id',  v_rt_wv,
    'garden_view_id',      v_rt_gv,
    'cottage_id',          v_rt_co,
    'owner_email',         p_owner_email
  );
END;
$$;


-- =============================================================================
-- link_user_to_tenant
-- Called after Supabase auth.signUp to attach the new user to a tenant.
-- =============================================================================
CREATE OR REPLACE FUNCTION public.link_user_to_tenant(
  p_user_id   uuid,
  p_tenant_id uuid,
  p_role      text DEFAULT 'inn_owner'
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF p_role NOT IN ('inn_owner','inn_manager','shg_admin','shg_analyst') THEN
    RAISE EXCEPTION 'Invalid role: %', p_role;
  END IF;

  INSERT INTO user_profiles (user_id, tenant_id, role)
  VALUES (p_user_id, p_tenant_id, p_role)
  ON CONFLICT (user_id) DO UPDATE
    SET tenant_id = EXCLUDED.tenant_id, role = EXCLUDED.role;
END;
$$;
