-- Part 4: Per-feature trials (14-day, 2 active max — enforced in the app).
-- Apply in Supabase SQL editor. Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS public.feature_trials (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    feature_key VARCHAR(64) NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at     TIMESTAMPTZ NOT NULL,
    converted   BOOLEAN     NOT NULL DEFAULT false,
    -- One trial per feature per tenant (DB-level backstop for "trialed once").
    UNIQUE (tenant_id, feature_key)
);

CREATE INDEX IF NOT EXISTS feature_trials_tenant_idx ON public.feature_trials (tenant_id);
CREATE INDEX IF NOT EXISTS feature_trials_active_idx ON public.feature_trials (tenant_id, ends_at);

ALTER TABLE public.feature_trials ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS feature_trials_service_all ON public.feature_trials;
CREATE POLICY feature_trials_service_all ON public.feature_trials
    FOR ALL TO service_role USING (true) WITH CHECK (true);
