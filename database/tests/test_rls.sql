-- =============================================================================
-- SHG Pricing Engine — RLS Isolation Test
-- Verifies that Row Level Security enforces tenant data isolation.
--
-- HOW TO RUN:
--   Supabase SQL Editor: paste and execute (the transaction auto-rolls back)
--   psql:  psql $DATABASE_URL -f database/tests/test_rls.sql
--
-- WHAT IT TESTS:
--   1. Tenant Alpha (inn_owner) sees only its own properties / room_types /
--      occupancy_snapshots / bookings / rate_recs / guests
--   2. Tenant Beta  (inn_owner) sees only its own data (none of Alpha's)
--   3. shg_admin sees ALL tenants' data
--   4. shg_analyst sees ALL tenants' data (read-only; write blocked)
--   5. Unauthenticated (null tenant_id) sees nothing
--
-- EXPECTED: ALL TESTS PASS  (zero failures)
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- STEP 1 — Create isolated test tenants + data (runs as postgres/superuser,
--           which bypasses RLS so we can insert freely for setup)
-- ---------------------------------------------------------------------------
DO $setup$
DECLARE
  v_t1  uuid;
  v_t2  uuid;
  v_p1  uuid;
  v_p2  uuid;
  v_rt1 uuid;
  v_rt2 uuid;
BEGIN
  -- Tenant Alpha
  INSERT INTO tenants (name, slug, plan_tier, active)
  VALUES ('RLS Test Tenant Alpha', 'rls-test-alpha', 'starter', true)
  RETURNING id INTO v_t1;

  -- Tenant Beta
  INSERT INTO tenants (name, slug, plan_tier, active)
  VALUES ('RLS Test Tenant Beta', 'rls-test-beta', 'starter', true)
  RETURNING id INTO v_t2;

  -- Properties
  INSERT INTO properties (tenant_id, name, city, state)
  VALUES (v_t1, 'Alpha Inn', 'Charleston', 'SC')
  RETURNING id INTO v_p1;

  INSERT INTO properties (tenant_id, name, city, state)
  VALUES (v_t2, 'Beta Hotel', 'Savannah', 'GA')
  RETURNING id INTO v_p2;

  -- Room Types
  INSERT INTO room_types (tenant_id, property_id, name, base_rate, min_rate, max_rate, total_count)
  VALUES (v_t1, v_p1, 'Alpha Standard', 200.00, 150.00, 400.00, 4)
  RETURNING id INTO v_rt1;

  INSERT INTO room_types (tenant_id, property_id, name, base_rate, min_rate, max_rate, total_count)
  VALUES (v_t2, v_p2, 'Beta Deluxe', 300.00, 220.00, 550.00, 3)
  RETURNING id INTO v_rt2;

  -- Occupancy snapshots (one per tenant)
  INSERT INTO occupancy_snapshots
    (tenant_id, property_id, snapshot_date, room_type_id,
     rooms_available, rooms_occupied, occupancy_rate, adr, revpar)
  VALUES
    (v_t1, v_p1, CURRENT_DATE - 1, v_rt1, 4, 3, 0.75, 200.00, 150.00),
    (v_t2, v_p2, CURRENT_DATE - 1, v_rt2, 3, 2, 0.67, 300.00, 200.00);

  -- Bookings (one per tenant)
  INSERT INTO bookings
    (tenant_id, property_id, room_type_id, check_in, check_out, rate_paid, booking_source, booked_at)
  VALUES
    (v_t1, v_p1, v_rt1, CURRENT_DATE + 10, CURRENT_DATE + 13, 200.00, 'Direct', NOW()),
    (v_t2, v_p2, v_rt2, CURRENT_DATE + 10, CURRENT_DATE + 13, 300.00, 'Airbnb', NOW());

  -- Rate recommendations (one per tenant)
  INSERT INTO rate_recommendations
    (tenant_id, property_id, room_type_id, target_date,
     recommended_rate, current_rate, demand_score, confidence_score, status)
  VALUES
    (v_t1, v_p1, v_rt1, CURRENT_DATE + 30, 220.00, 200.00, 72, 85, 'pending'),
    (v_t2, v_p2, v_rt2, CURRENT_DATE + 30, 330.00, 300.00, 68, 80, 'pending');

  -- Guests (one per tenant)
  INSERT INTO guests
    (tenant_id, property_id, first_name, last_name, home_city, home_state)
  VALUES
    (v_t1, v_p1, 'Alice', 'Smith', 'Atlanta', 'GA'),
    (v_t2, v_p2, 'Bob',   'Jones', 'Charlotte', 'NC');

  -- Store IDs in temp table for use outside this DO block
  CREATE TEMP TABLE IF NOT EXISTS _rls_test_ids (key text PRIMARY KEY, val uuid);
  INSERT INTO _rls_test_ids (key, val) VALUES
    ('t1', v_t1), ('t2', v_t2),
    ('p1', v_p1), ('p2', v_p2),
    ('rt1', v_rt1), ('rt2', v_rt2);

  RAISE NOTICE '[SETUP] Tenant Alpha: % | Beta: %', v_t1, v_t2;
END;
$setup$;


-- ---------------------------------------------------------------------------
-- STEP 2 — Create a results table to collect pass/fail for each assertion
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _rls_results (
  test_no    serial,
  suite      text,
  test_name  text,
  expected   bigint,
  actual     bigint,
  passed     boolean GENERATED ALWAYS AS (expected = actual) STORED
);


-- ---------------------------------------------------------------------------
-- HELPER: run a count query under a specific JWT context and record result
-- We use SET LOCAL ROLE + set_config so RLS is enforced exactly as in prod.
-- ---------------------------------------------------------------------------

-- Switch to the Supabase authenticated role for all RLS tests below
SET LOCAL ROLE authenticated;


-- ===========================================================================
-- SUITE A: Tenant Alpha (inn_owner) — should see ONLY Alpha data
-- ===========================================================================
SELECT set_config('request.jwt.claims', format(
  '{"sub":"%s","role":"authenticated","tenant_id":"%s","app_role":"inn_owner"}',
  gen_random_uuid(),
  (SELECT val FROM _rls_test_ids WHERE key = 't1')
)::text, true);  -- true = transaction-local

INSERT INTO _rls_results (suite, test_name, expected, actual) VALUES
  ('A: Alpha inn_owner', 'sees own property (count=1)',
   1, (SELECT count(*) FROM properties)),

  ('A: Alpha inn_owner', 'cannot see Beta property (count=0)',
   0, (SELECT count(*) FROM properties
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't2'))),

  ('A: Alpha inn_owner', 'sees own room_type (count=1)',
   1, (SELECT count(*) FROM room_types)),

  ('A: Alpha inn_owner', 'cannot see Beta room_type (count=0)',
   0, (SELECT count(*) FROM room_types
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't2'))),

  ('A: Alpha inn_owner', 'sees own occupancy_snapshot (count=1)',
   1, (SELECT count(*) FROM occupancy_snapshots)),

  ('A: Alpha inn_owner', 'cannot see Beta occupancy_snapshot (count=0)',
   0, (SELECT count(*) FROM occupancy_snapshots
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't2'))),

  ('A: Alpha inn_owner', 'sees own booking (count=1)',
   1, (SELECT count(*) FROM bookings)),

  ('A: Alpha inn_owner', 'cannot see Beta booking (count=0)',
   0, (SELECT count(*) FROM bookings
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't2'))),

  ('A: Alpha inn_owner', 'sees own rate_recommendation (count=1)',
   1, (SELECT count(*) FROM rate_recommendations)),

  ('A: Alpha inn_owner', 'sees own guest (count=1)',
   1, (SELECT count(*) FROM guests)),

  ('A: Alpha inn_owner', 'cannot see Beta guest (count=0)',
   0, (SELECT count(*) FROM guests
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't2'))),

  ('A: Alpha inn_owner', 'can read market_signals (no RLS, expect >0)',
   1, LEAST(1, (SELECT count(*) FROM market_signals)));


-- ===========================================================================
-- SUITE B: Tenant Beta (inn_owner) — should see ONLY Beta data
-- ===========================================================================
SELECT set_config('request.jwt.claims', format(
  '{"sub":"%s","role":"authenticated","tenant_id":"%s","app_role":"inn_owner"}',
  gen_random_uuid(),
  (SELECT val FROM _rls_test_ids WHERE key = 't2')
)::text, true);

INSERT INTO _rls_results (suite, test_name, expected, actual) VALUES
  ('B: Beta inn_owner', 'sees own property (count=1)',
   1, (SELECT count(*) FROM properties)),

  ('B: Beta inn_owner', 'cannot see Alpha property (count=0)',
   0, (SELECT count(*) FROM properties
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't1'))),

  ('B: Beta inn_owner', 'sees own room_type (count=1)',
   1, (SELECT count(*) FROM room_types)),

  ('B: Beta inn_owner', 'cannot see Alpha room_type (count=0)',
   0, (SELECT count(*) FROM room_types
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't1'))),

  ('B: Beta inn_owner', 'sees own booking (count=1)',
   1, (SELECT count(*) FROM bookings)),

  ('B: Beta inn_owner', 'cannot see Alpha booking (count=0)',
   0, (SELECT count(*) FROM bookings
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't1'))),

  ('B: Beta inn_owner', 'sees own guest (count=1)',
   1, (SELECT count(*) FROM guests)),

  ('B: Beta inn_owner', 'cannot see Alpha guest (count=0)',
   0, (SELECT count(*) FROM guests
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't1')));


-- ===========================================================================
-- SUITE C: shg_admin — sees ALL tenants, can write
-- ===========================================================================
SELECT set_config('request.jwt.claims', format(
  '{"sub":"%s","role":"authenticated","tenant_id":"%s","app_role":"shg_admin"}',
  gen_random_uuid(),
  (SELECT val FROM _rls_test_ids WHERE key = 't1')  -- admin's home tenant irrelevant
)::text, true);

INSERT INTO _rls_results (suite, test_name, expected, actual) VALUES
  ('C: shg_admin', 'sees ALL properties (count=2+)',
   1, LEAST(1, (SELECT count(*) FROM properties
                WHERE tenant_id IN (
                  SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2')
                ))::int / 2)),

  ('C: shg_admin', 'sees Alpha properties',
   1, (SELECT count(*) FROM properties
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't1'))),

  ('C: shg_admin', 'sees Beta properties',
   1, (SELECT count(*) FROM properties
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't2'))),

  ('C: shg_admin', 'sees all bookings (both tenants)',
   2, (SELECT count(*) FROM bookings
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2')))),

  ('C: shg_admin', 'sees all guests (both tenants)',
   2, (SELECT count(*) FROM guests
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2')))),

  ('C: shg_admin', 'sees all rate_recommendations (both tenants)',
   2, (SELECT count(*) FROM rate_recommendations
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2'))));


-- ===========================================================================
-- SUITE D: shg_analyst — sees ALL tenants, READ ONLY (INSERT blocked)
-- ===========================================================================
SELECT set_config('request.jwt.claims', format(
  '{"sub":"%s","role":"authenticated","app_role":"shg_analyst"}',
  gen_random_uuid()
)::text, true);

INSERT INTO _rls_results (suite, test_name, expected, actual) VALUES
  ('D: shg_analyst', 'reads Alpha properties',
   1, (SELECT count(*) FROM properties
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't1'))),

  ('D: shg_analyst', 'reads Beta properties',
   1, (SELECT count(*) FROM properties
       WHERE tenant_id = (SELECT val FROM _rls_test_ids WHERE key = 't2'))),

  ('D: shg_analyst', 'reads all bookings',
   2, (SELECT count(*) FROM bookings
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2')))),

  ('D: shg_analyst', 'reads all occupancy_snapshots',
   2, (SELECT count(*) FROM occupancy_snapshots
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2'))));

-- Verify shg_analyst INSERT is blocked (should throw, caught in DO block)
DO $analyst_write_test$
DECLARE
  v_t1 uuid := (SELECT val FROM _rls_test_ids WHERE key = 't1');
  v_p1 uuid := (SELECT val FROM _rls_test_ids WHERE key = 'p1');
BEGIN
  -- Attempt INSERT as analyst — must be rejected by RLS
  INSERT INTO bookings
    (tenant_id, property_id, room_type_id, check_in, check_out, rate_paid)
  VALUES
    (v_t1, v_p1, (SELECT val FROM _rls_test_ids WHERE key = 'rt1'),
     CURRENT_DATE + 100, CURRENT_DATE + 102, 200.00);

  -- If we reach here, the INSERT was NOT blocked — test fails
  INSERT INTO _rls_results (suite, test_name, expected, actual)
  VALUES ('D: shg_analyst', 'INSERT blocked by RLS (expect 0=blocked)', 0, 1);

EXCEPTION
  WHEN insufficient_privilege OR check_violation THEN
    -- Correctly blocked
    INSERT INTO _rls_results (suite, test_name, expected, actual)
    VALUES ('D: shg_analyst', 'INSERT blocked by RLS (expect 0=blocked)', 0, 0);
END;
$analyst_write_test$;


-- ===========================================================================
-- SUITE E: Unauthenticated (no tenant_id in JWT) — sees nothing
-- ===========================================================================
SELECT set_config('request.jwt.claims',
  '{"sub":"anon-user","role":"authenticated","app_role":"inn_owner"}'::text,
  true);
-- No tenant_id in claims → current_tenant_id() returns NULL → no rows match

INSERT INTO _rls_results (suite, test_name, expected, actual) VALUES
  ('E: no tenant_id in JWT', 'sees 0 properties (tenant_id IS NULL → no match)',
   0, (SELECT count(*) FROM properties
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2')))),

  ('E: no tenant_id in JWT', 'sees 0 bookings',
   0, (SELECT count(*) FROM bookings
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2')))),

  ('E: no tenant_id in JWT', 'sees 0 guests',
   0, (SELECT count(*) FROM guests
       WHERE tenant_id IN (SELECT val FROM _rls_test_ids WHERE key IN ('t1','t2'))));


-- ---------------------------------------------------------------------------
-- STEP 3 — Restore superuser role, print results, fail if any test failed
-- ---------------------------------------------------------------------------
RESET ROLE;

-- Full results table
SELECT
  suite,
  test_name,
  expected,
  actual,
  CASE WHEN passed THEN '✓ PASS' ELSE '✗ FAIL' END AS result
FROM _rls_results
ORDER BY test_no;

-- Summary
DO $summary$
DECLARE
  v_total  int;
  v_passed int;
  v_failed int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE passed), count(*) FILTER (WHERE NOT passed)
    INTO v_total, v_passed, v_failed
    FROM _rls_results;

  RAISE NOTICE '';
  RAISE NOTICE '╔══════════════════════════════════════════════════════╗';
  RAISE NOTICE '║          RLS ISOLATION TEST RESULTS                 ║';
  RAISE NOTICE '╠══════════════════════════════════════════════════════╣';
  RAISE NOTICE '║  Total tests : %-5s                                 ║', v_total;
  RAISE NOTICE '║  Passed      : %-5s                                 ║', v_passed;
  RAISE NOTICE '║  Failed      : %-5s                                 ║', v_failed;
  RAISE NOTICE '╚══════════════════════════════════════════════════════╝';

  IF v_failed > 0 THEN
    RAISE EXCEPTION 'RLS TEST SUITE FAILED — % of % tests did not pass', v_failed, v_total;
  ELSE
    RAISE NOTICE 'ALL % RLS TESTS PASSED — tenant isolation is working correctly.', v_total;
  END IF;
END;
$summary$;

-- Roll back ALL test data — leaves the database unchanged
ROLLBACK;

-- After ROLLBACK the test tenants, properties, bookings etc. are gone.
-- market_signals rows inserted in seed/anchorage_1770.sql are unaffected
-- (they were committed in a separate transaction).
