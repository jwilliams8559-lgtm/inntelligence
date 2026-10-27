-- Part 3: Reconcile billing catalog to the 4 INNtelligence tiers.
-- Replaces the legacy starter/professional/enterprise/premium catalog with
-- inn / boutique / signature / collection. Apply in Supabase SQL editor.
-- Fully idempotent: safe to re-run from scratch.

-- ── 1. Widen the plan_tier CHECK constraint FIRST ────────────────────────────
-- The legacy constraint only permits the old tier names, so it must be relaxed
-- before any row can be migrated to a new tier (and before the webhook can
-- write plan_tier='boutique' etc.). We allow the new tiers, founding_member,
-- cancelled, plus the legacy names during the transition window.
ALTER TABLE public.tenants DROP CONSTRAINT IF EXISTS tenants_plan_tier_check;
ALTER TABLE public.tenants ADD CONSTRAINT tenants_plan_tier_check
    CHECK (plan_tier IN (
        'inn', 'boutique', 'signature', 'collection',   -- current tiers
        'founding_member', 'cancelled',                  -- special states
        'starter', 'professional', 'enterprise', 'premium'  -- legacy (transitional)
    ));

-- ── 2. Migrate existing tenants off legacy tier keys ─────────────────────────
-- Map by position in the old ladder → new ladder.
UPDATE public.tenants SET plan_tier = 'inn'        WHERE plan_tier = 'starter';
UPDATE public.tenants SET plan_tier = 'boutique'   WHERE plan_tier = 'professional';
UPDATE public.tenants SET plan_tier = 'signature'  WHERE plan_tier = 'enterprise';
UPDATE public.tenants SET plan_tier = 'collection' WHERE plan_tier = 'premium';
-- founding_member and cancelled are unchanged.

-- ── 3. Repair stripe_prices: dedupe → add UNIQUE → reseed ────────────────────
-- The live table accumulated duplicate (plan_tier, interval) rows and never had
-- a unique constraint (so the original ON CONFLICT reseed had no target).

-- 3a. Collapse duplicates, keeping the lowest id per (plan_tier, interval).
DELETE FROM public.stripe_prices a
      USING public.stripe_prices b
 WHERE a.id > b.id
   AND a.plan_tier = b.plan_tier
   AND a.interval  = b.interval;

-- 3b. Add the UNIQUE constraint if an equivalent one isn't already present
--     (matched by column set, not name, so it's robust to prior naming).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.conrelid = 'public.stripe_prices'::regclass
           AND c.contype  = 'u'
           AND (
                SELECT array_agg(a.attname::text ORDER BY a.attname::text)
                  FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k
           ) = ARRAY['interval', 'plan_tier']
    ) THEN
        ALTER TABLE public.stripe_prices
            ADD CONSTRAINT stripe_prices_plan_tier_interval_key UNIQUE (plan_tier, interval);
    END IF;
END $$;

-- 3c. Remove the obsolete legacy catalog rows.
DELETE FROM public.stripe_prices
 WHERE plan_tier IN ('starter', 'professional', 'enterprise', 'premium');

-- 3d. Upsert the live monthly tiers. The ON CONFLICT target now exists.
--     stripe_price_id values mirror the live TEST-mode prices created by
--     scripts/setup_stripe_tiers.py (also stored in .env as STRIPE_PRICE_*).
INSERT INTO public.stripe_prices (plan_tier, interval, stripe_price_id, amount_cents) VALUES
    ('inn',        'month', 'price_1UVBwRHc6m4LmUs8CJG4HnTY',  14900),
    ('boutique',   'month', 'price_1UVBwSHc6m4LmUs8Mdx2kqXA',  39900),
    ('signature',  'month', 'price_1UVBwSHc6m4LmUs83vgLEiDg',  79900),
    ('collection', 'month', 'price_1UVBwTHc6m4LmUs89UHmJUPp', 149900)
ON CONFLICT (plan_tier, interval) DO UPDATE
    SET stripe_price_id = EXCLUDED.stripe_price_id,
        amount_cents    = EXCLUDED.amount_cents;

-- ── 4. (Optional) Tighten later ──────────────────────────────────────────────
-- Once all tenants are confirmed migrated and no legacy writers remain, the
-- legacy names can be dropped from the CHECK constraint in a follow-up migration.
