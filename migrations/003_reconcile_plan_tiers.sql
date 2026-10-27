-- Part 3: Reconcile billing catalog to the 4 INNtelligence tiers.
-- Replaces the legacy starter/professional/enterprise/premium catalog with
-- inn / boutique / signature / collection. Apply in Supabase SQL editor.
-- Idempotent: safe to re-run.

-- ── 1. Migrate existing tenants off legacy tier keys ─────────────────────────
-- Map by position in the old ladder → new ladder.
UPDATE public.tenants SET plan_tier = 'inn'        WHERE plan_tier = 'starter';
UPDATE public.tenants SET plan_tier = 'boutique'   WHERE plan_tier = 'professional';
UPDATE public.tenants SET plan_tier = 'signature'  WHERE plan_tier = 'enterprise';
UPDATE public.tenants SET plan_tier = 'collection' WHERE plan_tier = 'premium';
-- founding_member and cancelled are unchanged.

-- ── 2. Reseed stripe_prices with the live monthly tiers ──────────────────────
-- Remove the obsolete legacy rows.
DELETE FROM public.stripe_prices
 WHERE plan_tier IN ('starter', 'professional', 'enterprise', 'premium');

-- Insert the new tiers. stripe_price_id values mirror the live TEST-mode prices
-- created by scripts/setup_stripe_tiers.py (also stored in .env as STRIPE_PRICE_*).
INSERT INTO public.stripe_prices (plan_tier, interval, stripe_price_id, amount_cents) VALUES
    ('inn',        'month', 'price_1UVBwRHc6m4LmUs8CJG4HnTY',  14900),
    ('boutique',   'month', 'price_1UVBwSHc6m4LmUs8Mdx2kqXA',  39900),
    ('signature',  'month', 'price_1UVBwSHc6m4LmUs83vgLEiDg',  79900),
    ('collection', 'month', 'price_1UVBwTHc6m4LmUs89UHmJUPp', 149900)
ON CONFLICT (plan_tier, interval) DO UPDATE
    SET stripe_price_id = EXCLUDED.stripe_price_id,
        amount_cents    = EXCLUDED.amount_cents;
