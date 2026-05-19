-- =============================================================================
-- SHG Pricing Engine — Anchorage 1770 Inn Seed Data
-- Requires: 001_schema.sql, 002_auth_rls.sql, 003_functions.sql
--
-- Generates:
--   • Tenant + property + 4 room types via provision_tenant_anchorage()
--   • 2 years of daily occupancy_snapshots (Beaufort SC seasonal model)
--   • 90 days of synthetic bookings (realistic source mix + seasonal ADR)
--   • 24 months of Beaufort market_signals
-- =============================================================================

DO $$
DECLARE
  v_result      jsonb;
  v_tenant_id   uuid;
  v_property_id uuid;
  v_rt_wf       uuid;   -- Waterfront Suite  base $378  4 rooms
  v_rt_wv       uuid;   -- Waterview Suite   base $335  4 rooms
  v_rt_gv       uuid;   -- Garden View Room  base $295  5 rooms
  v_rt_co       uuid;   -- Cottage Room      base $295  2 rooms
BEGIN

  -- -------------------------------------------------------------------------
  -- 1. PROVISION TENANT
  -- -------------------------------------------------------------------------
  v_result      := public.provision_tenant_anchorage();
  v_tenant_id   := (v_result->>'tenant_id')::uuid;
  v_property_id := (v_result->>'property_id')::uuid;
  v_rt_wf       := (v_result->>'waterfront_suite_id')::uuid;
  v_rt_wv       := (v_result->>'waterview_suite_id')::uuid;
  v_rt_gv       := (v_result->>'garden_view_id')::uuid;
  v_rt_co       := (v_result->>'cottage_id')::uuid;

  RAISE NOTICE 'Provisioned tenant: % | property: %', v_tenant_id, v_property_id;

  -- -------------------------------------------------------------------------
  -- 2. OCCUPANCY SNAPSHOTS — 2 years of daily data per room type
  --
  -- Beaufort SC seasonal model (Lowcountry coastal inn):
  --   Peak    Apr–May (Gullah Festival, MCRD graduations): 82–86%
  --   High    Jul     (Water Festival, July 4th):          83%
  --   Good    Jun,Aug,Oct                                  74–79%
  --   Shoulder Mar,Sep,Nov                                 61–71%
  --   Low     Jan,Feb,Dec                                  50–66%
  --
  -- ADR seasonal multipliers mirror same seasonal curve.
  -- Weekend premium: Fri +16%, Sat +22%, Sun +9%.
  -- Noise: ±1.2% via hashtext for realistic daily variation.
  -- -------------------------------------------------------------------------
  INSERT INTO occupancy_snapshots (
    id, tenant_id, property_id, snapshot_date, room_type_id,
    rooms_available, rooms_occupied, occupancy_rate, adr, revpar, created_at
  )
  WITH

  date_series AS (
    SELECT gs::date AS d
    FROM generate_series(
      CURRENT_DATE - INTERVAL '730 days',
      CURRENT_DATE - INTERVAL '1 day',
      '1 day'::interval
    ) gs
  ),

  room_configs (rt_id, room_count, base_rate) AS (
    VALUES
      (v_rt_wf, 4, 378.00::numeric),
      (v_rt_wv, 4, 335.00::numeric),
      (v_rt_gv, 5, 295.00::numeric),
      (v_rt_co, 2, 295.00::numeric)
  ),

  seasonal AS (
    SELECT
      d.d AS snapshot_date,
      r.rt_id,
      r.room_count,
      r.base_rate,

      -- Monthly base occupancy
      CASE EXTRACT(MONTH FROM d.d)
        WHEN 1  THEN 0.50
        WHEN 2  THEN 0.55
        WHEN 3  THEN 0.65
        WHEN 4  THEN 0.82
        WHEN 5  THEN 0.86
        WHEN 6  THEN 0.79
        WHEN 7  THEN 0.83
        WHEN 8  THEN 0.76
        WHEN 9  THEN 0.71
        WHEN 10 THEN 0.74
        WHEN 11 THEN 0.61
        WHEN 12 THEN 0.66
      END AS base_occ,

      -- Day-of-week multiplier
      CASE EXTRACT(DOW FROM d.d)
        WHEN 5 THEN 1.16   -- Friday
        WHEN 6 THEN 1.22   -- Saturday
        WHEN 0 THEN 1.09   -- Sunday
        WHEN 1 THEN 0.93   -- Monday
        WHEN 2 THEN 0.91   -- Tuesday
        WHEN 3 THEN 0.93   -- Wednesday
        WHEN 4 THEN 0.98   -- Thursday
      END AS dow_occ_mult,

      -- Event / holiday occupancy boost
      CASE
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '07-01' AND '07-07'  THEN 1.26  -- July 4th
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '12-20' AND '12-31'  THEN 1.24  -- Christmas/NYE
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '05-23' AND '05-31'  THEN 1.20  -- Memorial Day
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '07-08' AND '07-14'  THEN 1.16  -- Water Festival
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '11-24' AND '11-30'  THEN 1.16  -- Thanksgiving
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '09-01' AND '09-07'  THEN 1.14  -- Labor Day
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '04-01' AND '04-07'  THEN 1.12  -- Spring break
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '10-01' AND '10-15'  THEN 1.11  -- Shrimp Festival
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '04-21' AND '04-30'  THEN 1.09  -- MCRD graduations
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '05-01' AND '05-20'  THEN 1.08  -- Gullah Festival
        WHEN TO_CHAR(d.d, 'MM-DD') BETWEEN '02-07' AND '02-16'  THEN 1.07  -- Beaufort Film Fest
        ELSE 1.00
      END AS event_occ_mult,

      -- Monthly ADR multiplier
      CASE EXTRACT(MONTH FROM d.d)
        WHEN 1  THEN 0.84
        WHEN 2  THEN 0.90
        WHEN 3  THEN 0.98
        WHEN 4  THEN 1.22
        WHEN 5  THEN 1.29
        WHEN 6  THEN 1.14
        WHEN 7  THEN 1.20
        WHEN 8  THEN 1.09
        WHEN 9  THEN 1.05
        WHEN 10 THEN 1.10
        WHEN 11 THEN 0.95
        WHEN 12 THEN 1.07
      END AS adr_seasonal_mult,

      -- Weekend ADR premium
      CASE EXTRACT(DOW FROM d.d)
        WHEN 5 THEN 1.10
        WHEN 6 THEN 1.15
        WHEN 0 THEN 1.05
        ELSE 1.00
      END AS adr_dow_mult,

      -- Deterministic noise seed (±1.2%)
      (abs(hashtext(d.d::text || '~' || r.rt_id::text)) % 25 - 12) AS noise_step

    FROM date_series d
    CROSS JOIN room_configs r
  ),

  calculated AS (
    SELECT
      snapshot_date,
      rt_id,
      room_count,
      base_rate,
      -- Clamp occupancy to [0.22, 0.97]
      LEAST(0.9700, GREATEST(0.2200,
        base_occ * dow_occ_mult * event_occ_mult
        + noise_step * 0.001
      )) AS occ_rate,
      -- ADR with event premium applied where relevant
      ROUND(
        (base_rate
          * adr_seasonal_mult
          * adr_dow_mult
          * CASE
              WHEN TO_CHAR(snapshot_date, 'MM-DD') BETWEEN '07-01' AND '07-14' THEN 1.15
              WHEN TO_CHAR(snapshot_date, 'MM-DD') BETWEEN '12-20' AND '12-31' THEN 1.12
              WHEN TO_CHAR(snapshot_date, 'MM-DD') BETWEEN '05-23' AND '05-31' THEN 1.10
              ELSE 1.00
            END
          + noise_step * 0.4   -- ±$4.80 ADR noise
        )::numeric, 2
      ) AS adr
    FROM seasonal
  )

  SELECT
    gen_random_uuid(),
    v_tenant_id,
    v_property_id,
    snapshot_date,
    rt_id,
    room_count,
    GREATEST(0, ROUND(room_count * occ_rate)::int),
    ROUND(occ_rate::numeric, 4),
    adr,
    ROUND((adr * occ_rate)::numeric, 2),
    NOW()
  FROM calculated;

  RAISE NOTICE 'Inserted occupancy snapshots: %', (
    SELECT count(*) FROM occupancy_snapshots WHERE tenant_id = v_tenant_id
  );

  -- -------------------------------------------------------------------------
  -- 3. BOOKINGS — 90 days of synthetic data
  --
  -- Strategy:
  --   For each room "slot" (room type × room number) × each possible check-in
  --   date, a booking is generated with probability:
  --       P = monthly_occ / avg_stay_nights  (= occ_rate / 2.5)
  --   using a deterministic hashtext selector for reproducibility.
  --
  --   Stay length: 1–7 nights, weighted 2–4 typical.
  --   Booking source: Direct 30%, Airbnb 30%, Booking.com 25%, Expedia 10%, VRBO 5%.
  --   Rate paid: base × seasonal_adr_mult + small noise, clamped to min/max.
  --   Booked-at: 1–75 days before check-in (realistic lead time).
  -- -------------------------------------------------------------------------
  INSERT INTO bookings (
    id, tenant_id, property_id, room_type_id,
    check_in, check_out, rate_paid, booking_source, booked_at, created_at
  )
  WITH

  check_in_series AS (
    SELECT gs::date AS check_in
    FROM generate_series(
      CURRENT_DATE - INTERVAL '90 days',
      CURRENT_DATE + INTERVAL '30 days',   -- include near-future reservations
      '1 day'::interval
    ) gs
  ),

  room_slots (rt_id, room_count, base_rate, min_rate, max_rate) AS (
    VALUES
      (v_rt_wf, 4, 378.00::numeric, 295.00::numeric, 695.00::numeric),
      (v_rt_wv, 4, 335.00::numeric, 265.00::numeric, 595.00::numeric),
      (v_rt_gv, 5, 295.00::numeric, 225.00::numeric, 495.00::numeric),
      (v_rt_co, 2, 295.00::numeric, 225.00::numeric, 495.00::numeric)
  ),

  candidates AS (
    SELECT
      c.check_in,
      r.rt_id,
      r.room_count,
      r.base_rate,
      r.min_rate,
      r.max_rate,
      slot_num,
      -- Monthly occupancy probability (same model as snapshots)
      CASE EXTRACT(MONTH FROM c.check_in)
        WHEN 1  THEN 0.50 WHEN 2  THEN 0.55 WHEN 3  THEN 0.65
        WHEN 4  THEN 0.82 WHEN 5  THEN 0.86 WHEN 6  THEN 0.79
        WHEN 7  THEN 0.83 WHEN 8  THEN 0.76 WHEN 9  THEN 0.71
        WHEN 10 THEN 0.74 WHEN 11 THEN 0.61 WHEN 12 THEN 0.66
      END *
      CASE EXTRACT(DOW FROM c.check_in)
        WHEN 5 THEN 1.16 WHEN 6 THEN 1.22 WHEN 0 THEN 1.09
        WHEN 1 THEN 0.93 WHEN 2 THEN 0.91 WHEN 3 THEN 0.93
        ELSE 0.98
      END AS occ_rate,
      -- ADR seasonal multiplier
      CASE EXTRACT(MONTH FROM c.check_in)
        WHEN 1  THEN 0.84 WHEN 2  THEN 0.90 WHEN 3  THEN 0.98
        WHEN 4  THEN 1.22 WHEN 5  THEN 1.29 WHEN 6  THEN 1.14
        WHEN 7  THEN 1.20 WHEN 8  THEN 1.09 WHEN 9  THEN 1.05
        WHEN 10 THEN 1.10 WHEN 11 THEN 0.95 WHEN 12 THEN 1.07
      END AS adr_mult,
      -- Deterministic hash for this slot
      abs(hashtext(c.check_in::text || r.rt_id::text || slot_num::text)) AS h
    FROM check_in_series c
    CROSS JOIN room_slots r
    CROSS JOIN generate_series(1, r.room_count) AS slot_num
  ),

  selected AS (
    SELECT
      check_in,
      rt_id,
      base_rate,
      min_rate,
      max_rate,
      occ_rate,
      adr_mult,
      h,
      -- P(new booking starts) ≈ occ_rate / 2.5 avg stay nights
      -- Multiply by 100 for integer threshold comparison
      (occ_rate / 2.5 * 100)::int AS booking_prob_pct
    FROM candidates
    WHERE (h % 100) < ((occ_rate / 2.5) * 100)::int
  ),

  bookings_final AS (
    SELECT
      check_in,
      rt_id,
      -- Stay length: deterministic weighted distribution
      -- h%10: 0,1→1n  2,3,4→2n  5,6→3n  7→4n  8→5n  9→7n
      check_in + (
        CASE h % 10
          WHEN 0 THEN 1 WHEN 1 THEN 1
          WHEN 2 THEN 2 WHEN 3 THEN 2 WHEN 4 THEN 2
          WHEN 5 THEN 3 WHEN 6 THEN 3
          WHEN 7 THEN 4
          WHEN 8 THEN 5
          WHEN 9 THEN 7
        END
      ) AS check_out,
      -- Rate paid: base × seasonal × ±8% noise, clamped to [min, max]
      GREATEST(min_rate,
        LEAST(max_rate,
          ROUND((base_rate * adr_mult
            * (1.0 + ((h % 17 - 8)::numeric / 100))
          )::numeric, 0)
        )
      ) AS rate_paid,
      -- Booking source (h%20 → weighted distribution)
      CASE
        WHEN h % 20 IN (0,1,2,3,4,5) THEN 'Direct'
        WHEN h % 20 IN (6,7,8,9,10)  THEN 'Airbnb'
        WHEN h % 20 IN (11,12,13,14) THEN 'Booking.com'
        WHEN h % 20 IN (15,16,17)    THEN 'Expedia'
        ELSE                              'VRBO'
      END AS booking_source,
      -- Booked-at: 1–75 days before check-in (lead time)
      check_in - ((h % 75 + 1) * INTERVAL '1 day') AS booked_at
    FROM selected
  )

  SELECT
    gen_random_uuid(),
    v_tenant_id,
    v_property_id,
    rt_id,
    check_in,
    check_out,
    rate_paid,
    booking_source,
    booked_at,
    NOW()
  FROM bookings_final
  WHERE check_out > check_in;

  RAISE NOTICE 'Inserted bookings: %', (
    SELECT count(*) FROM bookings WHERE tenant_id = v_tenant_id
  );

END;
$$;


-- =============================================================================
-- 4. MARKET SIGNALS — Beaufort/Lowcountry SC market (24 months)
--    No tenant_id; anonymized aggregate data shared across all tenants.
-- =============================================================================
INSERT INTO market_signals (
  id, signal_date, market, day_of_week, month,
  avg_occupancy, avg_adr,
  booking_window_0_7, booking_window_8_30, booking_window_31_60, booking_window_61_plus,
  event_lift, created_at
)
WITH month_series AS (
  SELECT
    DATE_TRUNC('month', gs)::date AS signal_date,
    EXTRACT(MONTH FROM gs)::int   AS mo
  FROM generate_series(
    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '24 months'),
    DATE_TRUNC('month', CURRENT_DATE),
    '1 month'::interval
  ) gs
),
market_data AS (
  SELECT
    signal_date,
    mo,
    -- Beaufort SC Lowcountry aggregate occupancy
    CASE mo
      WHEN 1  THEN 0.4800 WHEN 2  THEN 0.5200 WHEN 3  THEN 0.6400
      WHEN 4  THEN 0.7900 WHEN 5  THEN 0.8200 WHEN 6  THEN 0.7700
      WHEN 7  THEN 0.8000 WHEN 8  THEN 0.7400 WHEN 9  THEN 0.6800
      WHEN 10 THEN 0.7100 WHEN 11 THEN 0.5900 WHEN 12 THEN 0.6400
    END AS avg_occ,
    -- Lowcountry market aggregate ADR
    CASE mo
      WHEN 1  THEN 218.00 WHEN 2  THEN 232.00 WHEN 3  THEN 258.00
      WHEN 4  THEN 312.00 WHEN 5  THEN 328.00 WHEN 6  THEN 295.00
      WHEN 7  THEN 308.00 WHEN 8  THEN 281.00 WHEN 9  THEN 269.00
      WHEN 10 THEN 283.00 WHEN 11 THEN 244.00 WHEN 12 THEN 275.00
    END AS avg_adr_val,
    -- Booking window distribution by season
    CASE
      WHEN mo IN (4,5,7) THEN 0.18   -- peak months: more last-minute
      WHEN mo IN (12,1)  THEN 0.12   -- slow months: planned further out
      ELSE                    0.15
    END AS bw_0_7,
    CASE
      WHEN mo IN (4,5,7) THEN 0.32
      WHEN mo IN (12,1)  THEN 0.25
      ELSE                    0.29
    END AS bw_8_30,
    CASE
      WHEN mo IN (4,5,7) THEN 0.28
      ELSE                    0.30
    END AS bw_31_60,
    -- Event lift: Water Festival Jul, Gullah May, MCRD Apr
    CASE mo
      WHEN 7  THEN 0.18
      WHEN 5  THEN 0.14
      WHEN 4  THEN 0.12
      WHEN 10 THEN 0.09
      WHEN 9  THEN 0.07
      WHEN 12 THEN 0.15
      ELSE         0.03
    END AS evt_lift
  FROM month_series
)
SELECT
  gen_random_uuid(),
  signal_date,
  'beaufort-sc-lowcountry',
  NULL,   -- day_of_week: NULL for monthly aggregate
  mo,
  avg_occ,
  avg_adr_val,
  bw_0_7,
  bw_8_30,
  bw_31_60,
  ROUND((1.0 - bw_0_7 - bw_8_30 - bw_31_60)::numeric, 4),  -- bw_61_plus
  evt_lift,
  NOW()
FROM market_data
ON CONFLICT (signal_date, market) DO NOTHING;


-- =============================================================================
-- VERIFICATION SUMMARY
-- =============================================================================
DO $$
DECLARE
  v_tenant_id uuid := (
    SELECT id FROM tenants WHERE slug = 'anchorage-1770-demo'
  );
BEGIN
  RAISE NOTICE '';
  RAISE NOTICE '══════════════════════════════════════════════════════';
  RAISE NOTICE ' ANCHORAGE 1770 SEED VERIFICATION';
  RAISE NOTICE '══════════════════════════════════════════════════════';
  RAISE NOTICE '  Tenant ID      : %', v_tenant_id;
  RAISE NOTICE '  Properties     : %', (SELECT count(*) FROM properties WHERE tenant_id = v_tenant_id);
  RAISE NOTICE '  Room Types     : %', (SELECT count(*) FROM room_types WHERE tenant_id = v_tenant_id);
  RAISE NOTICE '  Occ Snapshots  : %', (SELECT count(*) FROM occupancy_snapshots WHERE tenant_id = v_tenant_id);
  RAISE NOTICE '  Bookings       : %', (SELECT count(*) FROM bookings WHERE tenant_id = v_tenant_id);
  RAISE NOTICE '  Market Signals : %', (SELECT count(*) FROM market_signals WHERE market = 'beaufort-sc-lowcountry');
  RAISE NOTICE '';
  RAISE NOTICE '  Avg Occupancy (all time):';
  RAISE NOTICE '    Waterfront Suite : %', (
    SELECT ROUND(AVG(occupancy_rate)::numeric, 3)
    FROM occupancy_snapshots os
    JOIN room_types rt ON rt.id = os.room_type_id
    WHERE os.tenant_id = v_tenant_id AND rt.name = 'Waterfront Suite'
  );
  RAISE NOTICE '    Waterview Suite  : %', (
    SELECT ROUND(AVG(occupancy_rate)::numeric, 3)
    FROM occupancy_snapshots os
    JOIN room_types rt ON rt.id = os.room_type_id
    WHERE os.tenant_id = v_tenant_id AND rt.name = 'Waterview Suite'
  );
  RAISE NOTICE '    Garden View Room : %', (
    SELECT ROUND(AVG(occupancy_rate)::numeric, 3)
    FROM occupancy_snapshots os
    JOIN room_types rt ON rt.id = os.room_type_id
    WHERE os.tenant_id = v_tenant_id AND rt.name = 'Garden View Room'
  );
  RAISE NOTICE '    Cottage Room     : %', (
    SELECT ROUND(AVG(occupancy_rate)::numeric, 3)
    FROM occupancy_snapshots os
    JOIN room_types rt ON rt.id = os.room_type_id
    WHERE os.tenant_id = v_tenant_id AND rt.name = 'Cottage Room'
  );
  RAISE NOTICE '';
  RAISE NOTICE '  Booking Source Mix (last 90d):';
  RAISE NOTICE '    %', (
    SELECT string_agg(booking_source || ': ' || cnt::text, '  ')
    FROM (
      SELECT booking_source, count(*) AS cnt
      FROM bookings
      WHERE tenant_id = v_tenant_id
        AND check_in >= CURRENT_DATE - 90
      GROUP BY booking_source
      ORDER BY cnt DESC
    ) s
  );
  RAISE NOTICE '══════════════════════════════════════════════════════';
END;
$$;
