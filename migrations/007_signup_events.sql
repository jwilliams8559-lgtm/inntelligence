-- Part 7: Signup event log — feeds the daily abuse monitor.
-- Apply in the Supabase SQL editor. Idempotent and additive.
-- One row per signup attempt (successful or blocked) so the daily abuse report
-- can spot velocity spikes, repeat IPs, disposable-domain probing, and low
-- verification/conversion rates. No PII beyond the email domain + IP.

CREATE TABLE IF NOT EXISTS public.signup_events (
    id           BIGSERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    email_domain TEXT,                         -- domain only, never the full address
    ip           TEXT,
    outcome      VARCHAR(32) NOT NULL,         -- created | blocked_disposable | blocked_rate | blocked_invalid | duplicate | failed
    tenant_id    UUID REFERENCES public.tenants(id) ON DELETE SET NULL,
    note         TEXT
);

CREATE INDEX IF NOT EXISTS idx_signup_events_created ON public.signup_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signup_events_ip      ON public.signup_events (ip);

ALTER TABLE public.signup_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS signup_events_service_all ON public.signup_events;
CREATE POLICY signup_events_service_all ON public.signup_events
    FOR ALL TO service_role USING (true) WITH CHECK (true);
