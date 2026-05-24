# Rate-Data Source Audit

Date: 2026-05-24

## The Problem

The product currently has **two parallel rate-data paths** that can produce
different numbers for the same room on the same date:

1. **DB-stored canonical** — `rate_recommendations` table, written by
   `engine.rate_engine.RateRecommender.update_all_recommendations()`.
   This is what the **Rate Calendar grid cells display** (RateCalendar.tsx
   reads `supabase.from('rate_recommendations')` directly at line 175).

2. **In-memory live compute (v2)** — module-level singletons
   `_v2_rate`, `_v2_demand`, `_v2_scraper` in `app.py`. These compute
   rates on every request without touching the DB. Drives the following
   endpoints:

   | Endpoint | Helper | Used by |
   |---|---|---|
   | `/api/rates` | `_v2_daily_rates` | (legacy / unverified) |
   | `/api/calendar` | `_v2_calendar` | (legacy) |
   | `/api/calendar/per-room` | `_v2_per_room_calendar` | RateCalendar.tsx as **overlay** on top of DB cells |
   | `/api/competitors/by-room-type` | `_v2_rate.recommend()` inline | CompetitiveIntel.tsx for "our_rates" column |
   | `/api/forecast` | `_v2_90day_forecast` | DemandDashboard.tsx |
   | `/api/performance-report` | `performance_engine.get_report(V2_PROPERTY, ...)` | PerformanceScreen.tsx — uses in-memory `V2_PROPERTY`, not the DB tenant |

3. **Direct Supabase reads from React** — the canonical path:

   | Screen | Tables |
   |---|---|
   | RateCalendar.tsx | `rate_recommendations`, `room_types`, `competitor_rates` |
   | CompetitiveIntel.tsx | `competitor_properties`, `competitor_rates`, `rate_recommendations` |

## The Inconsistency

Concrete evidence (DB query, 2026-05-24, Anchorage 1770 Inn):

- Waterfront Suite (base $378), Waterview Suite (base $335), and Cottage
  Room (base $295) all have `recommended_rate = $350.00` on the same
  date. Three different room types, same number — violating the hierarchy
  the customer-facing UI implies.
- Meanwhile `_v2_rate.recommend()` would compute *different* numbers per
  room type for the same date, because it uses room-category-aware comp
  entries and the S-curve spline.
- The RateCalendar grid shows the DB value. The Competitive Intel "our
  rate" column shows the live-computed value. A customer comparing the
  two screens will see different numbers.

## Endpoints That Return Rate Data — Classification

| Endpoint | Source | Risk |
|---|---|---|
| `/api/rates` | live compute (`_v2_daily_rates`) | divergence from DB |
| `/api/calendar` | live compute (`_v2_calendar`) | divergence from DB |
| `/api/calendar/per-room` | live compute (`_v2_per_room_calendar`) | divergence from DB |
| `/api/competitors/by-room-type` | live compute for "our_rates" | divergence from DB |
| `/api/forecast` | live compute revenue projection | independent of DB recs |
| `/api/forecast/dual` | live compute | independent |
| `/api/performance-report` | live `V2_PROPERTY` config + computed | divergence from DB |
| `/api/approve-rate` | reads + writes `rate_recommendations` | CANONICAL |
| `/api/approve-all-rates` | reads + writes `rate_recommendations` | CANONICAL |
| `/api/publish-log/<id>` | reads `rate_publish_log` | log only |
| (direct Supabase from React) | `rate_recommendations` | CANONICAL |

## Resolution

1. **Single source of truth function** added to `engine/rate_engine.py`:

   ```python
   canonical_recommendation(tenant_slug, room_type_id, target_date) -> dict
   ```

   This reads exclusively from `rate_recommendations` in the DB. Every
   endpoint that needs to expose a "current recommended rate for room X
   on date Y" must call this function. Live computation is reserved for
   *generating* the recommendations that get written to the table — never
   for read-time queries.

2. **Endpoints updated** to call `canonical_recommendation` instead of
   computing live:
   - `/api/rates`, `/api/calendar`, `/api/calendar/per-room`
   - `/api/competitors/by-room-type` (the "our_rates" column)

3. **Validator** (`scripts/validate_rates.py`) enforces hierarchy and
   cross-endpoint consistency on every commit via pre-commit hook.

## Installing the pre-commit hook (fresh clone)

```bash
cat > .git/hooks/pre-commit <<'EOF'
#!/usr/bin/env bash
set -e
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
if [ -x "venv/bin/python3" ]; then PY="venv/bin/python3"; else PY="python3"; fi
"$PY" scripts/validate_rates.py
EOF
chmod +x .git/hooks/pre-commit
```

The validator runs against the live Supabase demo tenant. Internet +
`.env` are required for the hook to pass.
