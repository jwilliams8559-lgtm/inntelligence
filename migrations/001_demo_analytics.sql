-- Part 1: Demo visitor analytics
-- Apply in Supabase SQL editor (Project → SQL Editor → New query → paste → Run).
-- Idempotent: safe to re-run.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.demo_analytics (
    id              BIGSERIAL PRIMARY KEY,
    visit_id        UUID         NOT NULL DEFAULT gen_random_uuid(),
    visited_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    country         VARCHAR(100),
    region          VARCHAR(100),
    city            VARCHAR(100),
    pages_viewed    INTEGER      NOT NULL DEFAULT 1,
    completed_demo  BOOLEAN      NOT NULL DEFAULT false,
    referrer        TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS demo_analytics_visit_id_uniq
    ON public.demo_analytics (visit_id);

CREATE INDEX IF NOT EXISTS demo_analytics_visited_at_idx
    ON public.demo_analytics (visited_at DESC);

CREATE INDEX IF NOT EXISTS demo_analytics_ip_idx
    ON public.demo_analytics (ip_address);

-- Row-level security: service role (server-side only) reads/writes. Anon does not.
ALTER TABLE public.demo_analytics ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS demo_analytics_service_all ON public.demo_analytics;
CREATE POLICY demo_analytics_service_all ON public.demo_analytics
    FOR ALL TO service_role USING (true) WITH CHECK (true);
