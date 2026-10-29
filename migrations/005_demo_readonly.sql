-- Part 5: Public read-only demo — isolation flag.
-- Apply in Supabase SQL editor. Idempotent: safe to re-run.
--
-- SECURITY MODEL (authoritative enforcement is in the APP, not the DB):
--   The /demo visitor receives a SIGNED, time-limited demo token (engine/demo.py)
--   — NOT a Supabase JWT and NOT service_role. All data is served by the Flask
--   API, which uses service_role server-side and binds the demo principal to the
--   single demo tenant. A before_request gate returns 403 on every write and on
--   billing, and admin/cross-tenant endpoints require tgc_admin. The browser
--   never receives service_role or any cross-tenant credential.
--
-- WHY NO RLS TOGGLE HERE:
--   The browser never queries Supabase directly for tenant data (supabase-js is
--   used only for auth), so RLS is not in the demo's data path. Enabling RLS on
--   core tables (esp. `tenants`) risks breaking the custom_access_token_hook that
--   injects tenant_id/app_role claims at login. That hardening should be done and
--   validated separately against the auth hook — it is intentionally NOT bundled
--   with the demo launch. feature_trials and stripe_prices already carry
--   service_role-only RLS (migrations 002 & 004).

-- ── Mark the demo tenant (isolation flag) ────────────────────────────────────
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT false;
UPDATE public.tenants SET is_demo = true  WHERE id = '357afb97-1c29-427d-b58e-63d2fcc90f97';
UPDATE public.tenants SET is_demo = false WHERE id <> '357afb97-1c29-427d-b58e-63d2fcc90f97';
