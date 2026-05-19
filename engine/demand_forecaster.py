"""
engine/demand_forecaster.py
Phase 2A — Demand Forecasting for The Gracious Collection Pricing Engine

Four-signal demand model for Beaufort SC hospitality properties:
  Signal 1 (35%) — Booking pace vs same period last year
  Signal 2 (25%) — Seasonal pattern from occupancy_snapshots
  Signal 3 (20%) — Known local events (hardcoded Beaufort SC calendar)
  Signal 4 (20%) — Market benchmark from market_signals table

Results are written to rate_recommendations with status='pending'.
Phase 2B will fill recommended_rate based on demand_score.

Usage:
    python -m engine.demand_forecaster
    python -m engine.demand_forecaster --days 30 --slug anchorage-1770-demo
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Allow running as __main__ from project root
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Beaufort SC Known Events (hardcoded)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Event:
    name: str
    score: int       # raw contribution, 0–40 scale; stacked events cap at 40
    # Callable: (target_date: date) -> bool
    # Defined via module-level functions below to keep frozen dataclass clean.
    _checker: str    # name of the check function in _EVENT_CHECKERS


def _is_water_festival(d: date) -> bool:
    """Beaufort Water Festival — July 17–26 every year. Primary peak event."""
    return d.month == 7 and 17 <= d.day <= 26


def _is_july_4th(d: date) -> bool:
    """July 4th window: July 3–6."""
    return d.month == 7 and 3 <= d.day <= 6


def _is_gullah_festival(d: date) -> bool:
    """Original Gullah Festival — last weekend (Fri–Mon) of May."""
    if d.month != 5:
        return False
    # Last Monday of May then back to Friday
    last_day = date(d.year, 5, 31)
    while last_day.weekday() != 0:  # find last Monday
        last_day -= timedelta(days=1)
    fri = last_day - timedelta(days=3)
    return fri <= d <= last_day


def _is_film_festival(d: date) -> bool:
    """Beaufort International Film Festival — late January (last 4 days)."""
    if d.month != 1:
        return False
    last_day = date(d.year, 1, 31)
    return (last_day - d).days <= 3


def _is_mlk_weekend(d: date) -> bool:
    """MLK Weekend — third Monday of January ± 2 days."""
    if d.month != 1:
        return False
    mondays = [date(d.year, 1, day) for day in range(1, 32)
               if date(d.year, 1, day).weekday() == 0]
    if len(mondays) < 3:
        return False
    mlk_mon = mondays[2]
    return abs((d - mlk_mon).days) <= 2


def _is_memorial_day(d: date) -> bool:
    """Memorial Day weekend — last Mon of May ± 2 days."""
    if d.month != 5:
        return False
    last_day = date(d.year, 5, 31)
    while last_day.weekday() != 0:
        last_day -= timedelta(days=1)
    return abs((d - last_day).days) <= 2


def _is_labor_day(d: date) -> bool:
    """Labor Day weekend — first Mon of September ± 2 days."""
    if d.month != 9:
        return False
    d_iter = date(d.year, 9, 1)
    while d_iter.weekday() != 0:
        d_iter += timedelta(days=1)
    return abs((d - d_iter).days) <= 2


def _is_thanksgiving(d: date) -> bool:
    """Thanksgiving weekend — 4th Thursday of November ± 2 days."""
    if d.month != 11:
        return False
    thursdays = [date(d.year, 11, day) for day in range(1, 31)
                 if date(d.year, 11, day).weekday() == 3]
    if len(thursdays) < 4:
        return False
    tday = thursdays[3]
    return abs((d - tday).days) <= 2


def _is_christmas_new_year(d: date) -> bool:
    """Christmas / New Year window: Dec 24 – Jan 2."""
    return (d.month == 12 and d.day >= 24) or (d.month == 1 and d.day <= 2)


def _is_mcrd_graduation(d: date) -> bool:
    """Parris Island USMC graduation — every Friday year-round."""
    return d.weekday() == 4   # Friday


_EVENT_CHECKERS = {
    "_is_water_festival":   _is_water_festival,
    "_is_july_4th":         _is_july_4th,
    "_is_gullah_festival":  _is_gullah_festival,
    "_is_film_festival":    _is_film_festival,
    "_is_mlk_weekend":      _is_mlk_weekend,
    "_is_memorial_day":     _is_memorial_day,
    "_is_labor_day":        _is_labor_day,
    "_is_thanksgiving":     _is_thanksgiving,
    "_is_christmas_new_year": _is_christmas_new_year,
    "_is_mcrd_graduation":  _is_mcrd_graduation,
}

# Ordered by score descending so the top driver captures the most impactful event.
BEAUFORT_EVENTS: list[_Event] = [
    _Event("Beaufort Water Festival July 17–26",   40, "_is_water_festival"),
    _Event("Gullah Festival (last weekend of May)", 25, "_is_gullah_festival"),
    _Event("July 4th Celebrations",                25, "_is_july_4th"),
    _Event("Christmas / New Year Peak",             30, "_is_christmas_new_year"),
    _Event("Thanksgiving Weekend",                  20, "_is_thanksgiving"),
    _Event("MLK Weekend",                           20, "_is_mlk_weekend"),
    _Event("Memorial Day Weekend",                  20, "_is_memorial_day"),
    _Event("Labor Day Weekend",                     20, "_is_labor_day"),
    _Event("Beaufort Film Festival",                15, "_is_film_festival"),
    _Event("Parris Island USMC Graduation",         15, "_is_mcrd_graduation"),
]

# Historical avg occupancy Beaufort SC by month (used for market comparison baseline)
_BEAUFORT_MONTHLY_OCC: dict[int, float] = {
    1: 0.48, 2: 0.52, 3: 0.64, 4: 0.79, 5: 0.82,
    6: 0.77, 7: 0.80, 8: 0.74, 9: 0.68,
    10: 0.71, 11: 0.59, 12: 0.64,
}


# ─────────────────────────────────────────────────────────────────────────────
#  DemandForecast result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DemandForecast:
    tenant_id:    str
    property_id:  str
    room_type_id: str
    room_name:    str
    target_date:  date
    score:        int           # 0–100
    label:        str           # Very Low / Low / Normal / High / Very High / Peak
    drivers:      list[str]     # exactly 3 plain-English explanations
    confidence:   int           # 0–100

    # Signal breakdown (for debugging / transparency)
    pace_score:     float = 0.0
    seasonal_score: float = 0.0
    event_score:    float = 0.0
    market_score:   float = 0.0

    @staticmethod
    def label_for(score: int) -> str:
        if score <= 20:  return "Very Low"
        if score <= 40:  return "Low"
        if score <= 60:  return "Normal"
        if score <= 75:  return "High"
        if score <= 89:  return "Very High"
        return "Peak"


# ─────────────────────────────────────────────────────────────────────────────
#  DemandForecaster
# ─────────────────────────────────────────────────────────────────────────────

class DemandForecaster:
    """
    Phase 2A demand forecasting for Beaufort SC hospitality properties.

    Connects to Supabase via the REST API using SUPABASE_URL and
    SUPABASE_SERVICE_KEY from the .env file.
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        service_key:  str | None = None,
    ) -> None:
        url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
            )
        self._url = url
        self._hdrs = {
            "apikey":        key,
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        }

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def forecast_single(
        self,
        tenant_id:    str,
        property_id:  str,
        room_type_id: str,
        target_date:  date,
        *,
        room_name: str = "",
        _cache: dict[str, Any] | None = None,
    ) -> DemandForecast:
        """
        Compute a DemandForecast for one room type on one date.

        Parameters
        ----------
        tenant_id, property_id, room_type_id:
            UUIDs from the Supabase schema.
        target_date:
            The stay date being forecast.
        room_name:
            Display name; fetched automatically when not supplied.
        _cache:
            Internal pre-fetched data dict to avoid redundant API calls
            when called in bulk via forecast_range().
        """
        cache = _cache or {}

        # ── Signal 1: Booking Pace (35%) ─────────────────────────────────
        pace_score, pace_driver = self._signal_pace(
            property_id, room_type_id, target_date, cache
        )

        # ── Signal 2: Seasonal Pattern (25%) ────────────────────────────
        seasonal_score, seasonal_driver = self._signal_seasonal(
            property_id, room_type_id, target_date, cache
        )

        # ── Signal 3: Local Events (20%) ────────────────────────────────
        event_score_100, event_driver, event_raw = self._signal_events(target_date)

        # ── Signal 4: Market Benchmark (20%) ────────────────────────────
        market_score, market_driver = self._signal_market(
            property_id, target_date, cache
        )

        # ── Composite (weighted average, all signals 0–100) ──────────────
        composite = (
            0.35 * pace_score
            + 0.25 * seasonal_score
            + 0.20 * event_score_100
            + 0.20 * market_score
        )

        # Domain override: Water Festival (event_raw == 40) is a validated
        # peak — 2 years of occupancy data show 94%+ occupancy July 17–26.
        # The event signal alone cannot push a weighted average to 90+ due to
        # the weight structure, so we apply a floor for max-score events.
        if event_raw >= 40:
            composite = max(composite, 90.0)

        score = int(round(min(100.0, max(0.0, composite))))
        label = DemandForecast.label_for(score)

        # ── Confidence ───────────────────────────────────────────────────
        conf = self._confidence(
            pace_score, seasonal_score, event_raw, target_date, cache
        )

        # ── Top-3 drivers ────────────────────────────────────────────────
        ranked = sorted(
            [
                (0.35 * pace_score,     pace_driver),
                (0.25 * seasonal_score, seasonal_driver),
                (0.20 * event_score_100, event_driver),
                (0.20 * market_score,   market_driver),
            ],
            reverse=True,
        )
        drivers = [d for _, d in ranked[:3]]

        return DemandForecast(
            tenant_id=tenant_id,
            property_id=property_id,
            room_type_id=room_type_id,
            room_name=room_name,
            target_date=target_date,
            score=score,
            label=label,
            drivers=drivers,
            confidence=conf,
            pace_score=round(pace_score, 1),
            seasonal_score=round(seasonal_score, 1),
            event_score=round(event_score_100, 1),
            market_score=round(market_score, 1),
        )

    def forecast_range(
        self,
        tenant_id:    str,
        property_id:  str,
        room_type_id: str,
        start_date:   date,
        end_date:     date,
        *,
        room_name: str = "",
    ) -> list[DemandForecast]:
        """
        Forecast every date in [start_date, end_date] for one room type.
        Pre-fetches historical data once for efficiency.
        """
        cache = self._prefetch(property_id, room_type_id)
        results: list[DemandForecast] = []
        d = start_date
        while d <= end_date:
            results.append(
                self.forecast_single(
                    tenant_id, property_id, room_type_id, d,
                    room_name=room_name, _cache=cache,
                )
            )
            d += timedelta(days=1)
        return results

    def update_recommendations_table(
        self,
        tenant_id:   str,
        property_id: str,
        days_ahead:  int = 90,
    ) -> int:
        """
        Forecast next `days_ahead` days for all room types in this property.
        Upserts results into rate_recommendations (status='pending',
        recommended_rate=None — Phase 2B fills the rate).

        Returns number of rows written.
        """
        room_types = self._get_room_types(property_id)
        if not room_types:
            raise ValueError(f"No room types found for property {property_id}")

        today      = date.today()
        start_date = today + timedelta(days=1)
        end_date   = today + timedelta(days=days_ahead)

        all_recs: list[dict[str, Any]] = []

        for rt in room_types:
            forecasts = self.forecast_range(
                tenant_id, property_id, rt["id"], start_date, end_date,
                room_name=rt.get("name", ""),
            )
            for fc in forecasts:
                all_recs.append({
                    "tenant_id":        fc.tenant_id,
                    "property_id":      fc.property_id,
                    "room_type_id":     fc.room_type_id,
                    "target_date":      fc.target_date.isoformat(),
                    "recommended_rate": None,   # Phase 2B
                    "current_rate":     rt.get("base_rate"),
                    "demand_score":     fc.score,
                    "confidence_score": fc.confidence,
                    "reasoning":        " | ".join(fc.drivers),
                    "status":           "pending",
                })

        return self._save(property_id, start_date.isoformat(),
                          end_date.isoformat(), all_recs)

    # ------------------------------------------------------------------ #
    #  Signal 1 — Booking Pace                                            #
    # ------------------------------------------------------------------ #

    def _signal_pace(
        self,
        property_id:  str,
        room_type_id: str,
        target_date:  date,
        cache:        dict[str, Any],
    ) -> tuple[float, str]:
        """
        Compare bookings for the target week vs same week last year
        at an equivalent lead time (days_out).

        pace_score = min(100, pace_ratio * 50)
          pace_ratio 1.0  → 50  (tracking with last year)
          pace_ratio 2.0  → 100 (double the bookings)
          pace_ratio 0.0  → 0   (no advance bookings yet)

        Falls back to seasonal-implied pace when booking data is absent.
        """
        bookings_by_rt: dict[str, list[dict]] = cache.get("bookings_by_rt", {})

        # Window: target date ± 3 days (1-week window)
        win_start = target_date - timedelta(days=3)
        win_end   = target_date + timedelta(days=3)

        ly_start = win_start.replace(year=win_start.year - 1)
        ly_end   = win_end.replace(year=win_end.year - 1)

        rows = bookings_by_rt.get(room_type_id, [])

        def count_in_window(d_start: date, d_end: date) -> int:
            return sum(
                1 for r in rows
                if d_start <= date.fromisoformat(r["check_in"]) <= d_end
            )

        current_count = count_in_window(win_start, win_end)
        ly_count      = count_in_window(ly_start,  ly_end)

        if ly_count == 0 and current_count == 0:
            # No booking data at this lead time — infer from seasonal strength.
            # High-season months get a positive neutral (55–70); low-season → 40–50.
            seasonal_occ = _BEAUFORT_MONTHLY_OCC.get(target_date.month, 0.65)
            implied_pace = 40.0 + (seasonal_occ / 0.82) * 25.0  # 40–70 range
            score = round(min(100.0, implied_pace), 1)
            driver = (
                f"No advance bookings on record at this lead time; "
                f"seasonal pace implied at {score:.0f}/100 "
                f"({target_date.strftime('%B')} historically "
                f"{seasonal_occ:.0%} occupancy)"
            )
            return score, driver

        pace_ratio = (current_count / ly_count) if ly_count > 0 else (
            2.0 if current_count > 0 else 0.5
        )
        score  = min(100.0, pace_ratio * 50.0)
        change = int((pace_ratio - 1.0) * 100)
        sign   = "ahead of" if change >= 0 else "behind"
        driver = (
            f"Booking pace running {abs(change)}% {sign} last year "
            f"({current_count} vs {ly_count} bookings "
            f"in the same {target_date.strftime('%B')} window)"
        )
        return score, driver

    # ------------------------------------------------------------------ #
    #  Signal 2 — Seasonal Pattern                                        #
    # ------------------------------------------------------------------ #

    def _signal_seasonal(
        self,
        property_id:  str,
        room_type_id: str,
        target_date:  date,
        cache:        dict[str, Any],
    ) -> tuple[float, str]:
        """
        Average historical occupancy_rate for (same month, same day-of-week).

        seasonal_score = (avg_historical_occupancy / 0.65) * 50
        0.65 is the all-year neutral baseline for a Beaufort SC boutique inn.
        Score > 50 = above-average demand; < 50 = below average.
        """
        occ_lookup: dict[tuple[int, int], list[float]] = cache.get("occ_by_month_dow", {})

        key = (target_date.month, target_date.weekday())
        vals = occ_lookup.get(key, [])

        dow_name  = target_date.strftime("%A")
        mon_name  = target_date.strftime("%B")

        if vals:
            avg_occ = sum(vals) / len(vals)
            score   = min(100.0, (avg_occ / 0.65) * 50.0)
            driver  = (
                f"{dow_name}s in {mon_name} average "
                f"{avg_occ:.0%} occupancy historically "
                f"({len(vals)} data points)"
            )
        else:
            # No historical data — use Beaufort seasonal baseline
            avg_occ = _BEAUFORT_MONTHLY_OCC.get(target_date.month, 0.65)
            score   = min(100.0, (avg_occ / 0.65) * 50.0)
            driver  = (
                f"{mon_name} historically averages "
                f"{avg_occ:.0%} occupancy in Beaufort SC "
                f"(seasonal model, no property-specific data)"
            )
        return score, driver

    # ------------------------------------------------------------------ #
    #  Signal 3 — Local Events                                            #
    # ------------------------------------------------------------------ #

    def _signal_events(
        self, target_date: date
    ) -> tuple[float, str, int]:
        """
        Check all known Beaufort SC events.
        Returns (event_score_0_100, driver_string, raw_score_0_40).

        Raw scores are summed and capped at 40; then scaled to 0–100
        so the signal is comparable to the other three signals.
        """
        active: list[_Event] = [
            evt for evt in BEAUFORT_EVENTS
            if _EVENT_CHECKERS[evt._checker](target_date)
        ]

        raw = min(40, sum(e.score for e in active))
        score_100 = (raw / 40.0) * 100.0

        if not active:
            driver = (
                f"No major events scheduled for "
                f"{target_date.strftime('%A, %B %-d')}"
            )
        else:
            top = active[0]
            others = len(active) - 1
            suffix = f" + {others} other event(s)" if others else ""
            driver = (
                f"{top.name}{suffix} "
                f"drives historically elevated demand "
                f"({target_date.strftime('%B %-d')})"
            )
        return score_100, driver, raw

    # ------------------------------------------------------------------ #
    #  Signal 4 — Market Benchmark                                        #
    # ------------------------------------------------------------------ #

    def _signal_market(
        self,
        property_id: str,
        target_date:  date,
        cache:        dict[str, Any],
    ) -> tuple[float, str]:
        """
        Compare property's historical avg occupancy for this month
        against the Beaufort SC market benchmark from market_signals.

        If the property runs above market: slight upward adjustment (score > 50).
        If below market: slight downward adjustment (score < 50).
        Base score 50 = property tracking with market.
        """
        market_by_month: dict[int, float] = cache.get("market_by_month", {})
        prop_by_month:   dict[int, float] = cache.get("prop_occ_by_month", {})

        month = target_date.month
        market_occ = market_by_month.get(month, _BEAUFORT_MONTHLY_OCC[month])
        prop_occ   = prop_by_month.get(month, market_occ)   # fallback to market if no data

        # Relative index: 1.0 = exactly at market; >1 = above, <1 = below
        rel = prop_occ / market_occ if market_occ > 0 else 1.0

        # Map relative performance to 0–100 score centered at 50
        # rel = 1.0 → 50; rel = 1.20 → ~70; rel = 0.80 → ~30
        score = min(100.0, max(0.0, 50.0 + (rel - 1.0) * 100.0))

        sign   = "above" if prop_occ >= market_occ else "below"
        delta  = abs(prop_occ - market_occ)
        driver = (
            f"Property runs {delta:.0%} {sign} Beaufort market average "
            f"in {target_date.strftime('%B')} "
            f"({prop_occ:.0%} vs {market_occ:.0%} market)"
        )
        return score, driver

    # ------------------------------------------------------------------ #
    #  Confidence                                                          #
    # ------------------------------------------------------------------ #

    def _confidence(
        self,
        pace_score:    float,
        seasonal_score: float,
        event_raw:     int,
        target_date:   date,
        cache:         dict[str, Any],
    ) -> int:
        occ_lookup = cache.get("occ_by_month_dow", {})
        has_hist   = bool(occ_lookup.get((target_date.month, target_date.weekday())))
        days_out   = (target_date - date.today()).days

        conf = 55                         # model-only baseline
        if has_hist:   conf += 20         # historical data calibration
        if event_raw > 0: conf += 8       # event signal adds certainty
        if event_raw >= 35: conf += 5     # known peak event (Water Festival)
        if days_out <= 30:  conf += 7     # near-term bookings more certain
        if days_out <= 14:  conf += 5
        if pace_score > 70: conf += 5     # strong booking signal

        return min(95, conf)

    # ------------------------------------------------------------------ #
    #  Data fetching                                                       #
    # ------------------------------------------------------------------ #

    def _prefetch(self, property_id: str, room_type_id: str) -> dict[str, Any]:
        """
        Pre-loads historical data for a property/room_type pair so that
        forecast_range() only hits the API once per room type.
        """
        cache: dict[str, Any] = {}
        cache["bookings_by_rt"] = self._fetch_bookings(property_id)
        cache["occ_by_month_dow"] = self._fetch_occ_by_month_dow(
            property_id, room_type_id
        )
        cache["market_by_month"] = self._fetch_market_signals()
        cache["prop_occ_by_month"] = self._fetch_prop_occ_by_month(property_id)
        return cache

    def _fetch_bookings(self, property_id: str) -> dict[str, list[dict]]:
        """
        Returns all bookings for this property grouped by room_type_id.
        Covers the full seed range (past 90 days + next 30 days).
        """
        rows = self._get(
            "bookings",
            params={
                "property_id": f"eq.{property_id}",
                "select":      "room_type_id,check_in,booked_at",
            },
            limit=5000,
        )
        by_rt: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_rt[r["room_type_id"]].append(r)
        return dict(by_rt)

    def _fetch_occ_by_month_dow(
        self, property_id: str, room_type_id: str
    ) -> dict[tuple[int, int], list[float]]:
        """
        Returns {(month, weekday): [occupancy_rate, ...]} from
        occupancy_snapshots for this property and room type.
        """
        rows = self._get(
            "occupancy_snapshots",
            params={
                "property_id":  f"eq.{property_id}",
                "room_type_id": f"eq.{room_type_id}",
                "select":       "snapshot_date,occupancy_rate",
            },
            limit=5000,
        )
        lookup: dict[tuple[int, int], list[float]] = defaultdict(list)
        for r in rows:
            d = date.fromisoformat(r["snapshot_date"])
            lookup[(d.month, d.weekday())].append(float(r["occupancy_rate"]))
        return dict(lookup)

    def _fetch_market_signals(self) -> dict[int, float]:
        """Returns {month: avg_occupancy} from market_signals."""
        rows = self._get(
            "market_signals",
            params={
                "market": "eq.beaufort-sc-lowcountry",
                "select": "month,avg_occupancy",
            },
            limit=500,
        )
        by_month: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            if r.get("month") and r.get("avg_occupancy") is not None:
                by_month[int(r["month"])].append(float(r["avg_occupancy"]))
        return {m: sum(v) / len(v) for m, v in by_month.items()}

    def _fetch_prop_occ_by_month(self, property_id: str) -> dict[int, float]:
        """Returns {month: avg_occupancy_rate} for this property."""
        rows = self._get(
            "occupancy_snapshots",
            params={
                "property_id": f"eq.{property_id}",
                "select":      "snapshot_date,occupancy_rate",
            },
            limit=5000,
        )
        by_month: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            d = date.fromisoformat(r["snapshot_date"])
            by_month[d.month].append(float(r["occupancy_rate"]))
        return {m: sum(v) / len(v) for m, v in by_month.items()}

    def _get_room_types(self, property_id: str) -> list[dict[str, Any]]:
        return self._get(
            "room_types",
            params={
                "property_id": f"eq.{property_id}",
                "select":      "id,name,base_rate,min_rate,max_rate,total_count",
            },
        )

    def _get(
        self,
        table:  str,
        params: dict[str, str],
        limit:  int = 1000,
    ) -> list[dict[str, Any]]:
        """Paginated GET against the Supabase REST API."""
        all_rows: list[dict] = []
        offset = 0
        while True:
            resp = requests.get(
                f"{self._url}/rest/v1/{table}",
                headers={
                    **self._hdrs,
                    "Range":       f"{offset}-{offset + limit - 1}",
                    "Prefer":      "count=none",
                },
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            batch = resp.json()
            all_rows.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return all_rows

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _save(
        self,
        property_id: str,
        date_min:    str,
        date_max:    str,
        recs:        list[dict[str, Any]],
    ) -> int:
        if not recs:
            return 0

        # Delete existing pending recommendations for this date window
        resp = requests.delete(
            f"{self._url}/rest/v1/rate_recommendations",
            headers=self._hdrs,
            params=[
                ("property_id", f"eq.{property_id}"),
                ("status",      "eq.pending"),
                ("target_date", f"gte.{date_min}"),
                ("target_date", f"lte.{date_max}"),
            ],
            timeout=30,
        )
        resp.raise_for_status()

        # Batch insert (500 rows per request)
        written = 0
        for i in range(0, len(recs), 500):
            chunk = recs[i : i + 500]
            resp  = requests.post(
                f"{self._url}/rest/v1/rate_recommendations",
                headers={**self._hdrs, "Prefer": "return=minimal"},
                json=chunk,
                timeout=30,
            )
            resp.raise_for_status()
            written += len(chunk)

        logger.info("Saved %d recommendations to rate_recommendations", written)
        return written


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: resolve tenant + property from slug
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_tenant(forecaster: DemandForecaster, slug: str) -> tuple[str, str]:
    """Returns (tenant_id, property_id) for a given tenant slug."""
    tenants = forecaster._get(
        "tenants",
        params={"slug": f"eq.{slug}", "select": "id"},
    )
    if not tenants:
        raise ValueError(f"Tenant slug {slug!r} not found")
    tenant_id = tenants[0]["id"]

    props = forecaster._get(
        "properties",
        params={"tenant_id": f"eq.{tenant_id}", "select": "id", "limit": "1"},
    )
    if not props:
        raise ValueError(f"No property found for tenant {slug!r}")
    property_id = props[0]["id"]

    return tenant_id, property_id


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def _print_forecast_table(
    forecasts: list[DemandForecast],
    title: str = "DEMAND FORECAST",
) -> None:
    W = 110
    print(f"\n{'═' * W}")
    print(f"  {title}")
    print(f"{'═' * W}")
    header = (
        f"  {'Date':<12} {'Day':<10} {'Room Type':<22} "
        f"{'Score':>5} {'Label':<12} {'Confidence':>10}  Top Driver"
    )
    print(header)
    print(f"{'─' * W}")

    label_colors = {
        "Peak":      "★ Peak    ",
        "Very High": "◆ VeryHigh",
        "High":      "▲ High    ",
        "Normal":    "  Normal  ",
        "Low":       "▼ Low     ",
        "Very Low":  "▽ VeryLow ",
    }
    prev_month = None
    for fc in forecasts:
        month = fc.target_date.month
        if month != prev_month:
            if prev_month is not None:
                print(f"{'─' * W}")
            prev_month = month

        bar     = label_colors.get(fc.label, fc.label)
        day_str = fc.target_date.strftime("%a")
        driver  = fc.drivers[0][:60] if fc.drivers else ""

        print(
            f"  {fc.target_date.isoformat():<12} {day_str:<10} "
            f"{fc.room_name:<22} {fc.score:>5}  {bar:<12} "
            f"{fc.confidence:>8}%  {driver}"
        )

    print(f"{'═' * W}\n")


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    parser = argparse.ArgumentParser(
        prog="demand_forecaster",
        description="The Gracious Collection — Demand Forecaster",
    )
    parser.add_argument("--slug",  default="anchorage-1770-demo",
                        help="Tenant slug (default: anchorage-1770-demo)")
    parser.add_argument("--days",  type=int, default=30,
                        help="Days to forecast from today (default: 30)")
    parser.add_argument("--save",  action="store_true",
                        help="Write results to rate_recommendations table")
    args = parser.parse_args()

    forecaster = DemandForecaster()
    tenant_id, property_id = _resolve_tenant(forecaster, args.slug)
    room_types = forecaster._get_room_types(property_id)

    print(f"\n  Tenant slug : {args.slug}")
    print(f"  Tenant ID   : {tenant_id}")
    print(f"  Property ID : {property_id}")
    print(f"  Room types  : {', '.join(rt['name'] for rt in room_types)}")
    print(f"  Forecast    : next {args.days} days\n")

    today      = date.today()
    start_date = today + timedelta(days=1)
    end_date   = today + timedelta(days=args.days)

    # Forecast all room types for the main window (next N days)
    all_forecasts: list[DemandForecast] = []
    for rt in room_types:
        fcs = forecaster.forecast_range(
            tenant_id, property_id, rt["id"], start_date, end_date,
            room_name=rt["name"],
        )
        all_forecasts.extend(fcs)

    # Sort by date, then room type name
    all_forecasts.sort(key=lambda f: (f.target_date, f.room_name))

    _print_forecast_table(
        all_forecasts,
        title=(
            f"ANCHORAGE 1770 INN — DEMAND FORECAST  "
            f"{start_date} to {end_date}"
        ),
    )

    # ── Water Festival spotlight ────────────────────────────────────────
    wf_start = date(today.year, 7, 17)
    wf_end   = date(today.year, 7, 26)
    if wf_start > end_date:
        print("  [Fetching Water Festival period separately...]\n")
        wf_forecasts: list[DemandForecast] = []
        for rt in room_types:
            fcs = forecaster.forecast_range(
                tenant_id, property_id, rt["id"], wf_start, wf_end,
                room_name=rt["name"],
            )
            wf_forecasts.extend(fcs)
        wf_forecasts.sort(key=lambda f: (f.target_date, f.room_name))
        _print_forecast_table(
            wf_forecasts,
            title="BEAUFORT WATER FESTIVAL — July 17–26 (separate fetch)",
        )

    # ── Contrast: a quiet September Tuesday ────────────────────────────
    sep_tue = date(today.year, 9, 2)
    while sep_tue.weekday() != 1:  # find first Tuesday in September
        sep_tue += timedelta(days=1)

    print(f"  Contrast: {sep_tue.strftime('%A, %B %-d, %Y')} (low-season weekday)\n")
    contrast: list[DemandForecast] = []
    for rt in room_types:
        fc = forecaster.forecast_single(
            tenant_id, property_id, rt["id"], sep_tue,
            room_name=rt["name"],
        )
        contrast.append(fc)

    _print_forecast_table(
        contrast,
        title=f"CONTRAST — {sep_tue.strftime('%A, %B %-d, %Y')}",
    )

    # ── Save to DB if requested ─────────────────────────────────────────
    if args.save:
        print(f"  Writing 90-day forecast to rate_recommendations...\n")
        n = forecaster.update_recommendations_table(
            tenant_id, property_id, days_ahead=90
        )
        print(f"  ✓ {n} recommendations written (status=pending)\n")
    else:
        print("  (Pass --save to write 90-day forecast to rate_recommendations)\n")


if __name__ == "__main__":
    main()
