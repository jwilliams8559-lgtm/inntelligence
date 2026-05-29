-- Part 2: Stripe billing schema (tenants additions + stripe_prices catalog)
-- Apply in Supabase SQL editor. Idempotent: safe to re-run.

-- ── tenants: subscription/billing columns ────────────────────────────────────
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS stripe_customer_id      VARCHAR(255);
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS stripe_subscription_id  VARCHAR(255);
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS plan_status             VARCHAR(50) DEFAULT 'active';
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS plan_renews_at          TIMESTAMPTZ;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS founding_member_end     DATE;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS founding_member_started_at DATE;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS converted_at            TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS tenants_stripe_customer_idx     ON public.tenants (stripe_customer_id);
CREATE INDEX IF NOT EXISTS tenants_stripe_subscription_idx ON public.tenants (stripe_subscription_id);

-- ── stripe_prices: catalog of Stripe price IDs per plan / interval ───────────
CREATE TABLE IF NOT EXISTS public.stripe_prices (
    id              BIGSERIAL PRIMARY KEY,
    plan_tier       VARCHAR(50) NOT NULL,
    interval        VARCHAR(20) NOT NULL,            -- 'month' | 'year'
    stripe_price_id VARCHAR(255) NOT NULL DEFAULT 'pending',
    amount_cents    INTEGER     NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (plan_tier, interval)
);

ALTER TABLE public.stripe_prices ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stripe_prices_service_all ON public.stripe_prices;
CREATE POLICY stripe_prices_service_all ON public.stripe_prices
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Placeholder rows (Stripe price IDs populated later by /api/admin/stripe-setup)
INSERT INTO public.stripe_prices (plan_tier, interval, stripe_price_id, amount_cents) VALUES
    ('starter',      'month', 'pending',  39900),
    ('starter',      'year',  'pending', 399000),
    ('professional', 'month', 'pending',  69900),
    ('professional', 'year',  'pending', 699000),
    ('enterprise',   'month', 'pending', 120000),
    ('enterprise',   'year',  'pending', 1199900),
    ('premium',      'month', 'pending', 240000),
    ('premium',      'year',  'pending', 2399900)
ON CONFLICT (plan_tier, interval) DO NOTHING;
