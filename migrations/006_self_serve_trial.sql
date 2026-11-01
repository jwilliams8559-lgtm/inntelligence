-- Part 6: Self-serve signup + 14-day account trial + onboarding location/competitors.
-- Apply in the Supabase SQL editor BEFORE deploying the self-serve-signup build.
-- Idempotent and additive: safe to re-run; adds columns/tables only, drops nothing.

-- ── tenants: account-level trial + signup provenance ─────────────────────────
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS signup_source VARCHAR(40) DEFAULT 'self_serve';

-- ── properties: real location + the facts onboarding/discovery need ──────────
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS address       TEXT;
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS postal_code   VARCHAR(16);
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS country       VARCHAR(2)  DEFAULT 'US';
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS website_url   TEXT;
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS latitude      DOUBLE PRECISION;
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS longitude     DOUBLE PRECISION;
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS property_type VARCHAR(40) DEFAULT 'boutique_inn';
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS room_count    INTEGER;

-- ── tenant_competitors: the set the owner selects during onboarding ─────────
CREATE TABLE IF NOT EXISTS public.tenant_competitors (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    tier       SMALLINT,
    place_id   TEXT,
    address    TEXT,
    website_url TEXT,
    source     VARCHAR(20) DEFAULT 'discovered',  -- discovered | manual
    selected   BOOLEAN     DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_competitors_tenant ON public.tenant_competitors (tenant_id);

-- RLS. All app access is server-side via the service key (which bypasses RLS),
-- matching the rest of the schema; the service_role policy makes that explicit
-- and the tenant-isolation policy is defense-in-depth for any anon/authed path.
ALTER TABLE public.tenant_competitors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_competitors_service_all ON public.tenant_competitors;
CREATE POLICY tenant_competitors_service_all ON public.tenant_competitors
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS tenant_competitors_isolation ON public.tenant_competitors;
CREATE POLICY tenant_competitors_isolation ON public.tenant_competitors
    USING (tenant_id = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')::uuid);
