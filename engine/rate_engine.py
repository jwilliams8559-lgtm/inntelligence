"""
engine/rate_engine.py
Phase 2B — Rate Recommendation Engine for The Gracious Collection Pricing Engine

Components:
  RateRecommendation  — dataclass returned by the rate engine
  RateFenceResult     — dataclass returned by apply_rate_fences()
  RateRecommender     — S-curve pricing with competitive/quality/weather adjustments
  LengthOfStayPricer  — minimum-stay rules, gap-night detection, LOS discount table
  apply_rate_fences() — weekend, advance-purchase, and last-minute fence rules

Usage:
    python -m engine.rate_engine
    python -m engine.rate_engine --slug anchorage-1770-demo
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import requests
from dotenv import load_dotenv
from scipy.interpolate import CubicSpline

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  S-Curve spline — built once at import time
# ─────────────────────────────────────────────────────────────────────────────

# Recalibrated to Beaufort SC market reality (Anchorage 1770 / Cuthbert $531 ceiling)
# score 0→0.80x ($302), 50→1.00x ($378 base), 95→1.40x ($529 near Cuthbert), 100→1.45x ($549 peak)
_SPLINE_X = np.array([0,   25,   50,   65,   75,   85,   95,  100], dtype=float)
_SPLINE_Y = np.array([0.80, 0.88, 1.00, 1.10, 1.20, 1.32, 1.40, 1.45], dtype=float)
_DEMAND_SPLINE = CubicSpline(_SPLINE_X, _SPLINE_Y, extrapolate=False)

# Hard rate ceilings per Anchorage 1770 room type — anchored to Cuthbert House $531 peak
# Waterfront can exceed Cuthbert only when they sell out; Waterview/Garden/Cottage stay below
_ROOM_HARD_CEILINGS: dict[str, float] = {
    'Waterfront Suite': 550.0,
    'Waterview Suite':  440.0,
    'Garden View Room': 380.0,
    'Cottage Room':     380.0,
}
_FALLBACK_HARD_CEILING = 550.0  # used when room name not in dict


def _spline_multiplier(demand_score: int) -> float:
    """Return the S-curve price multiplier for a demand score 0–100."""
    score = float(max(0, min(100, demand_score)))
    val = float(_DEMAND_SPLINE(score))
    # CubicSpline with extrapolate=False returns NaN out of range — clamp
    if np.isnan(val):
        val = float(_SPLINE_Y[0]) if score <= 0 else float(_SPLINE_Y[-1])
    return val


# ─────────────────────────────────────────────────────────────────────────────
#  Canonical recommendation — SINGLE SOURCE OF TRUTH
# ─────────────────────────────────────────────────────────────────────────────
#
# Every API endpoint that needs to surface "the current recommended rate for
# room X on date Y" MUST go through canonical_recommendation(). It reads the
# rate_recommendations table — the persisted output of the rate engine — and
# never recomputes. This eliminates the class of bug where the Rate Calendar
# (DB-backed) and Competitive Intel (recomputed) show different numbers for
# the same room/date.
#
# Live recomputation is reserved for the WRITE path — RateRecommender.update_
# all_recommendations() generates rates and writes them to the DB. Read paths
# never touch the engine.

def canonical_recommendation(property_id: str, room_type_id: str,
                             target_date) -> dict[str, Any] | None:
    """Read the canonical rate for (property, room, date) from the DB.

    Returns the rate_recommendations row as a dict, or None if no record
    exists for that (property, room_type, date) combination. Every API
    endpoint that exposes a rate to a customer must call this — no
    parallel live computation is allowed on read paths.
    """
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (sb_url and sb_key):
        return None
    date_iso = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
    try:
        r = requests.get(
            f"{sb_url}/rest/v1/rate_recommendations",
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
            params={
                "property_id":  f"eq.{property_id}",
                "room_type_id": f"eq.{room_type_id}",
                "target_date":  f"eq.{date_iso}",
                "select":       "id,recommended_rate,status,demand_score,confidence_score,minimum_stay_rec,reasoning",
                "limit":        1,
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None
    except requests.RequestException:
        return None


def canonical_recommendations_bulk(property_id: str,
                                   date_from, date_to) -> dict[tuple[str, str], dict]:
    """Bulk read — returns {(room_type_id, date_iso): rec_dict}.

    The bulk variant exists so /api/calendar/per-room can fetch a 90-day
    window in one DB call instead of 360 individual lookups. Same SOT
    guarantee: never recomputes.
    """
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (sb_url and sb_key):
        return {}
    df = date_from.isoformat() if hasattr(date_from, "isoformat") else str(date_from)
    dt = date_to.isoformat()   if hasattr(date_to,   "isoformat") else str(date_to)
    try:
        r = requests.get(
            f"{sb_url}/rest/v1/rate_recommendations",
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
            params={
                "property_id": f"eq.{property_id}",
                "target_date": f"gte.{df}",
                "select":      "room_type_id,target_date,recommended_rate,status,demand_score,confidence_score,minimum_stay_rec,reasoning",
                "order":       "target_date",
                "limit":       "10000",
            },
            timeout=30,
        )
        r.raise_for_status()
        out: dict[tuple[str, str], dict] = {}
        for row in r.json():
            if row["target_date"] <= dt and row.get("recommended_rate") is not None:
                out[(row["room_type_id"], row["target_date"])] = row
        return out
    except requests.RequestException:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WeatherData:
    precip_probability: float = 0.0   # 0.0–1.0
    temp_high: int = 75
    condition: str = "Clear"


@dataclass
class RateFenceResult:
    recommended_rate:       float
    minimum_stay:           int
    advance_purchase_rate:  Optional[float]
    advance_discount_pct:   Optional[int]
    last_minute_fill:       bool
    last_minute_fill_rate:  Optional[float]
    fence_notes:            list[str] = field(default_factory=list)


@dataclass
class RateRecommendation:
    recommended_rate:           float
    current_rate:               float
    rate_change_dollars:        float
    rate_change_percent:        float
    demand_score:               int
    demand_label:               str
    confidence_score:           int
    reasoning:                  str
    minimum_stay_required:      int
    los_discount_table:         dict
    los_adjusted_rates:         dict
    is_gap_night:               bool
    gap_fill_rate:              Optional[float]
    advance_purchase_rate:      Optional[float]
    advance_purchase_discount_pct: Optional[int]
    last_minute_fill:           bool
    last_minute_fill_rate:      Optional[float]
    ota_commission_analysis:    dict
    competitive_position:       str
    comp_avg_rate:              Optional[float]
    quality_premium:            float
    recommended_direct_rate:    float
    weather_adjustment:         int
    competitor_sold_out_boost:  int
    bathroom_type:              str
    bathroom_premium_applied:   float   # fraction, e.g. 0.03 for rain shower
    bathroom_premium_dollars:   float   # dollar impact on final rate
    cuthbert_rate:              Optional[float]   # primary competitor rate for this date
    cuthbert_sold_out:          bool              # True if primary competitor fully booked
    applied_hard_ceiling:       bool              # True if hard ceiling was binding
    # Tiered market intelligence (added in Phase 2C full rebuild)
    primary_competitor_name:    str = ""
    primary_competitor_rate:    Optional[float] = None
    primary_competitor_sold_out: bool = False
    tier2_ceiling:              Optional[float] = None
    tier3_reference:            Optional[float] = None
    tier4_floor:                Optional[float] = None
    market_ladder:              list = field(default_factory=list)

    @staticmethod
    def label_for(score: int) -> str:
        if score <= 20:  return "Very Low"
        if score <= 40:  return "Low"
        if score <= 60:  return "Normal"
        if score <= 75:  return "High"
        if score <= 89:  return "Very High"
        return "Peak"


# ─────────────────────────────────────────────────────────────────────────────
#  Rate fence rules (standalone function)
# ─────────────────────────────────────────────────────────────────────────────

def apply_rate_fences(
    recommended_rate:             float,
    demand_score:                 int,
    target_date:                  date,
    days_until_target:            int,
    current_occupancy_for_date:   float,
    room_type:                    dict[str, Any],
    existing_minimum_stay:        int = 1,
) -> RateFenceResult:
    """
    Apply weekend, advance-purchase, and last-minute fence rules.
    Returns a RateFenceResult with the (possibly adjusted) rate and flags.
    """
    notes: list[str] = []
    min_stay = existing_minimum_stay
    advance_rate: Optional[float] = None
    advance_pct:  Optional[int]   = None
    lm_fill       = False
    lm_fill_rate: Optional[float] = None

    is_weekend = target_date.weekday() in (4, 5)   # Friday or Saturday
    min_rate   = float(room_type.get("min_rate", 0))
    base_rate  = float(room_type.get("base_rate", recommended_rate))

    # ── Weekend minimum-stay fence ─────────────────────────────────────
    if is_weekend and demand_score >= 60:
        min_stay = max(min_stay, 2)
        notes.append("Weekend demand ≥ 60 → 2-night minimum stay")

    # ── Advance-purchase discount ─────────────────────────────────────
    if days_until_target >= 60 and demand_score <= 35:
        advance_rate = round(recommended_rate * 0.92 / 5) * 5
        advance_pct  = 8
        notes.append(
            f"Low demand ({demand_score}) 60+ days out → 8% advance-purchase "
            f"discount at ${advance_rate:.0f}"
        )

    # ── Last-minute fill ──────────────────────────────────────────────
    if days_until_target <= 7 and current_occupancy_for_date < 0.50:
        fill = max(min_rate, round(base_rate * 0.88 / 5) * 5)
        lm_fill      = True
        lm_fill_rate = fill
        notes.append(
            f"Last-minute fill: occ {current_occupancy_for_date:.0%} < 50%, "
            f"{days_until_target}d out → ${fill:.0f} fill rate"
        )

    return RateFenceResult(
        recommended_rate=recommended_rate,
        minimum_stay=min_stay,
        advance_purchase_rate=advance_rate,
        advance_discount_pct=advance_pct,
        last_minute_fill=lm_fill,
        last_minute_fill_rate=lm_fill_rate,
        fence_notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  LengthOfStayPricer
# ─────────────────────────────────────────────────────────────────────────────

class LengthOfStayPricer:
    """Length-of-stay pricing rules, gap-night detection, and LOS discounts."""

    def __init__(self, supabase_url: str, headers: dict[str, str]) -> None:
        self._url  = supabase_url
        self._hdrs = headers

    # ── LOS discount table ────────────────────────────────────────────

    def get_los_discount_table(self) -> dict[int, float]:
        """
        Returns {nights: discount_fraction}.
        Display: "Stay 3 nights, save 7% per night."
        """
        return {1: 0.00, 2: 0.03, 3: 0.07, 4: 0.10, 5: 0.10}

    # ── Minimum-stay rules ────────────────────────────────────────────

    def get_minimum_stay(self, demand_score: int, target_date: date) -> int:
        """Return the required minimum stay for a given date and demand level."""
        m, d = target_date.month, target_date.day

        # Water Festival: July 17–26 → always 3 nights
        if m == 7 and 17 <= d <= 26:
            return 3

        if demand_score >= 90:
            return 3
        if demand_score >= 76:
            return 2

        # Gullah Festival — last weekend of May
        if m == 5 and d >= 22:
            last_day = date(target_date.year, 5, 31)
            while last_day.weekday() != 0:
                last_day -= timedelta(days=1)
            fri = last_day - timedelta(days=3)
            if fri <= target_date <= last_day:
                return 2

        # Memorial Day weekend (last Mon of May ± 2 days)
        if m == 5:
            last_day = date(target_date.year, 5, 31)
            while last_day.weekday() != 0:
                last_day -= timedelta(days=1)
            if abs((target_date - last_day).days) <= 2:
                return 2

        return 1

    # ── Gap-night detection ───────────────────────────────────────────

    def detect_gap_night(
        self,
        property_id:  str,
        room_type_id: str,
        target_date:  date,
    ) -> tuple[bool, int]:
        """
        Returns (is_gap, gap_nights).

        A gap night is a date that is unbooked for this room type while
        the immediately preceding stay ends on target_date and the next
        stay starts within 1–2 nights.
        """
        win_start = (target_date - timedelta(days=4)).isoformat()
        win_end   = (target_date + timedelta(days=5)).isoformat()

        resp = requests.get(
            f"{self._url}/rest/v1/bookings",
            headers=self._hdrs,
            params=[
                ("property_id",  f"eq.{property_id}"),
                ("room_type_id", f"eq.{room_type_id}"),
                ("check_in",     f"gte.{win_start}"),
                ("check_in",     f"lte.{win_end}"),
                ("select",       "check_in,check_out"),
            ],
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()

        bookings = [
            (date.fromisoformat(r["check_in"]), date.fromisoformat(r["check_out"]))
            for r in rows
        ]

        # Is target_date itself unbooked?
        is_unbooked = not any(ci <= target_date < co for ci, co in bookings)
        if not is_unbooked:
            return False, 0

        # Is there a booking that checks out on target_date (night before is occupied)?
        has_preceding = any(co == target_date for _, co in bookings)
        if not has_preceding:
            return False, 0

        # Is there a booking starting 1 or 2 nights after target_date?
        for gap in (1, 2):
            follow_date = target_date + timedelta(days=gap)
            if any(ci == follow_date for ci, _ in bookings):
                return True, gap

        return False, 0

    # ── Gap-fill pricing ──────────────────────────────────────────────

    def get_gap_fill_rate(self, base_rate: float, gap_size: int) -> float:
        if gap_size == 1:
            return round(base_rate * 0.80 / 5) * 5
        return round(base_rate * 0.88 / 5) * 5   # 2 nights

    # ── LOS-adjusted rate schedule ────────────────────────────────────

    def apply_los_adjusted_rates(
        self, base_rate: float, min_rate: float
    ) -> dict[int, float]:
        return {
            1: base_rate,
            2: max(min_rate, round(base_rate * 0.97 / 5) * 5),
            3: max(min_rate, round(base_rate * 0.93 / 5) * 5),
            4: max(min_rate, round(base_rate * 0.90 / 5) * 5),
            5: max(min_rate, round(base_rate * 0.90 / 5) * 5),  # same as 4-night
        }


# ─────────────────────────────────────────────────────────────────────────────
#  RateRecommender
# ─────────────────────────────────────────────────────────────────────────────

class RateRecommender:
    """
    Phase 2B rate engine for The Gracious Collection Pricing Engine.

    Reads demand scores from rate_recommendations (populated by Phase 2A),
    applies the S-curve algorithm with competitive, quality, weather, and
    fence adjustments, then writes recommended_rate back to the table.
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
        self._url  = url
        self._hdrs = {
            "apikey":        key,
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        }
        self._los = LengthOfStayPricer(url, self._hdrs)
        # Per-instance caches for bulk runs — avoids repeated identical DB calls
        self._mkt_cache:   dict[str, dict] = {}   # date_str → tiered market signals
        self._rank1_cache: dict[str, str | None] = {}  # property_id → comp_id

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def recommend_rate(
        self,
        tenant_id:            str,
        property_id:          str,
        room_type_id:         str,
        target_date:          date,
        demand_score:         int | None = None,
        comp_rates:           dict[str, float] | None = None,
        weather_data:         WeatherData | None = None,
        competitor_sold_out:  int | None = None,
        current_occupancy:    float = 0.75,
    ) -> RateRecommendation:
        """
        Compute a full RateRecommendation for one room type on one date.

        demand_score: pre-loaded from DB (avoids extra API call in bulk runs).
        """
        rt = self._get_room_type(room_type_id)
        room_name         = rt.get("name", "")
        base_rate         = float(rt["base_rate"])
        min_rate          = float(rt["min_rate"])
        max_rate          = float(rt["max_rate"])
        bathroom_premium  = float(rt.get("bathroom_premium") or 0.0)
        bathroom_type     = rt.get("bathroom_type") or "shower_only"

        # Fetch demand_score from DB if not provided
        if demand_score is None:
            demand_score = self._fetch_demand_score(
                property_id, room_type_id, target_date
            )

        days_out = max(0, (target_date - date.today()).days)

        # ── Signal adjustments before S-curve ─────────────────────────
        weather_adj    = 0
        sold_out_boost = 0
        drivers: list[str] = []

        if (weather_data and weather_data.precip_probability > 0.70
                and days_out <= 7):
            weather_adj = -5
            drivers.append("Rain forecast may soften last-minute demand")

        if competitor_sold_out is not None and competitor_sold_out >= 3:
            sold_out_boost = 15
            drivers.append(
                f"{competitor_sold_out} competitors fully booked — "
                "market is selling out"
            )

        # ── Tiered market signals (replaces hardcoded Cuthbert) ────────
        # Cached per date: 4 room types share the same market context for a date.
        _mkt_key = target_date.isoformat()
        if _mkt_key in self._mkt_cache:
            mkt = self._mkt_cache[_mkt_key]
        else:
            try:
                from engine.competitor_ranker import get_tiered_market_signals
                mkt = get_tiered_market_signals(
                    property_id, target_date,
                    supabase_url=self._url, service_key=self._hdrs["apikey"],
                )
            except Exception:
                mkt = {"tier1_primary": None, "tier2_ceiling": None,
                       "tier3_reference": None, "tier4_floor": None,
                       "tier4_compression": False, "market_ladder": []}
            self._mkt_cache[_mkt_key] = mkt

        tier1_primary  = mkt.get("tier1_primary") or {}
        cuthbert_rate  = tier1_primary.get("rate")
        cuthbert_sold_out = bool(tier1_primary.get("sold_out", False))
        primary_name   = tier1_primary.get("name", "primary competitor")
        tier2_ceiling  = mkt.get("tier2_ceiling")
        tier3_reference = mkt.get("tier3_reference")
        tier4_floor    = mkt.get("tier4_floor")

        # Legacy: also check _get_cuthbert_signal for fallback
        if cuthbert_rate is None:
            cuthbert_rate, cuthbert_sold_out = self._get_cuthbert_signal(
                property_id, target_date
            )

        cuthbert_boost = 0
        if cuthbert_sold_out:
            cuthbert_boost = 20
            drivers.append(
                f"{primary_name} (your closest competitor) is fully booked "
                "on this date — you are the premium waterfront alternative. "
                "Rate reflects your strong competitive position."
            )

        # Tier 4 demand compression signal
        if mkt.get("tier4_compression") and tier4_floor:
            drivers.append(
                f"Budget hotels are pricing at ${tier4_floor:.0f} tonight "
                "due to high market demand — your boutique experience "
                "justifies a significant premium."
            )

        adjusted_score = int(
            max(0, min(100,
                demand_score + weather_adj + sold_out_boost + cuthbert_boost
            ))
        )

        # ── S-curve rate — bathroom premium adjusts the base ──────────
        multiplier    = _spline_multiplier(adjusted_score)
        adjusted_base = base_rate * (1 + bathroom_premium)
        raw_rate      = adjusted_base * multiplier

        # Bounds + rounding
        final_rate = max(min_rate, min(max_rate, raw_rate))
        final_rate = round(final_rate / 5) * 5

        # Dollar impact: compare to what rate would be without bathroom premium
        raw_no_bath      = base_rate * multiplier
        rate_no_bath     = round(max(min_rate, min(max_rate, raw_no_bath)) / 5) * 5
        # (quality premium applied later — captured in dollar delta after that step)

        # ── Competitive adjustment ─────────────────────────────────────
        comp_avg: Optional[float] = None
        comp_position = "No competitive data"
        if comp_rates:
            comp_avg = sum(comp_rates.values()) / len(comp_rates)
            if final_rate > comp_avg * 1.25 and adjusted_score < 70:
                final_rate = min(final_rate, round(comp_avg * 1.15 / 5) * 5)
                drivers.append(
                    f"Rate capped at 15% above comp avg (${comp_avg:.0f}) — "
                    "demand < 70"
                )
            elif final_rate < comp_avg * 0.80 and adjusted_score >= 40:
                final_rate = max(final_rate, round(comp_avg * 0.85 / 5) * 5)
                drivers.append(
                    f"Rate floored at 85% of comp avg (${comp_avg:.0f}) — "
                    "demand signal warrants it"
                )
            pct_vs_comp = (final_rate - comp_avg) / comp_avg * 100
            if pct_vs_comp > 5:
                comp_position = f"{pct_vs_comp:+.0f}% above comp avg (${comp_avg:.0f})"
            elif pct_vs_comp < -5:
                comp_position = f"{pct_vs_comp:+.0f}% below comp avg (${comp_avg:.0f})"
            else:
                comp_position = f"At market (comp avg ${comp_avg:.0f})"

        # ── Quality premium — capped so bath+quality ≤ 8% total ──────
        quality_premium = self._quality_premium(property_id, room_type_id)
        # Enforce: bathroom_premium (already in adjusted_base) + quality ≤ 8%
        quality_premium = min(quality_premium, max(0.0, 0.08 - bathroom_premium))
        if quality_premium != 0.0:
            final_rate   = round(final_rate   * (1 + quality_premium) / 5) * 5
            rate_no_bath = round(rate_no_bath * (1 + quality_premium) / 5) * 5
            sign = "premium" if quality_premium > 0 else "discount"
            drivers.append(
                f"Room quality {sign} of "
                f"{abs(quality_premium) * 100:.1f}% applied"
            )

        # ── Cuthbert House dynamic ceiling ────────────────────────────
        # Cuthbert peaks at ~$531; we stay at 97% unless they sell out.
        # Ceiling only applies when Cuthbert is pricing above our floor
        # (avoids suppressing rates in low season when they're also discounting).
        applied_hard_ceiling = False
        dynamic_ceil: Optional[float] = None
        if cuthbert_rate and cuthbert_rate > min_rate * 1.05:
            if cuthbert_sold_out:
                # We're the last comparable waterfront option — price above Cuthbert
                dynamic_ceil = cuthbert_rate * (1.20 if adjusted_score >= 85 else 1.15)
            else:
                # Cuthbert has rooms; stay slightly below (they're #1 TripAdvisor)
                dynamic_ceil = cuthbert_rate * 0.97
            if final_rate > dynamic_ceil:
                final_rate = round(dynamic_ceil / 5) * 5
        elif not cuthbert_rate:
            # No Cuthbert data — use conservative fallback ceiling for Waterfront
            fallback_ceil = 540.0 if room_name == 'Waterfront Suite' else final_rate
            if final_rate > fallback_ceil:
                final_rate = round(fallback_ceil / 5) * 5

        # ── Hard ceiling per room type (absolute final cap) ───────────
        hard_ceil = _ROOM_HARD_CEILINGS.get(room_name, _FALLBACK_HARD_CEILING)
        if final_rate > hard_ceil:
            final_rate = round(hard_ceil / 5) * 5
            applied_hard_ceiling = True

        # Bathroom dollar impact computed AFTER all ceilings (always non-negative)
        rate_no_bath_capped = rate_no_bath
        if quality_premium != 0.0:
            rate_no_bath_capped = round(rate_no_bath_capped * (1 + quality_premium) / 5) * 5
        if dynamic_ceil is not None:
            rate_no_bath_capped = min(rate_no_bath_capped, round(dynamic_ceil / 5) * 5)
        rate_no_bath_capped = min(rate_no_bath_capped, hard_ceil)
        bathroom_premium_dollars = max(0.0, round(final_rate - rate_no_bath_capped, 2))

        # ── Bathroom driver ────────────────────────────────────────────
        if bathroom_premium > 0:
            bath_label = bathroom_type.replace("_", " ").title()
            drivers.append(
                f"{bath_label} commands {bathroom_premium * 100:.0f}% premium — "
                f"${bathroom_premium_dollars:.0f} above shower-only equivalent. "
                f"Tag this room as '{bath_label}' on Booking.com filters to "
                "capture guests specifically searching this amenity."
            )

        # ── LOS and fence rules ────────────────────────────────────────
        los = self._los
        min_stay  = los.get_minimum_stay(adjusted_score, target_date)
        los_table = los.get_los_discount_table()
        los_rates = los.apply_los_adjusted_rates(final_rate, min_rate)

        gap, gap_size = los.detect_gap_night(
            property_id, room_type_id, target_date
        )
        gap_fill: Optional[float] = (
            los.get_gap_fill_rate(final_rate, gap_size) if gap else None
        )

        fences = apply_rate_fences(
            final_rate, adjusted_score, target_date, days_out,
            current_occupancy, rt, existing_minimum_stay=min_stay,
        )
        min_stay = fences.minimum_stay

        # ── OTA commission analysis ────────────────────────────────────
        booking_com_equiv    = round(final_rate * 0.85 / 5) * 5
        expedia_equiv        = round(final_rate * 0.82 / 5) * 5
        recommended_direct   = round(final_rate * 0.94 / 5) * 5
        net_revenue_ota      = round(final_rate * 0.85, 2)
        net_revenue_direct   = float(recommended_direct)
        ota_analysis = {
            "listed_ota_rate":            final_rate,
            "booking_com_direct_equiv":   booking_com_equiv,
            "expedia_direct_equiv":       expedia_equiv,
            "recommended_direct_rate":    recommended_direct,
            "net_revenue_ota":            net_revenue_ota,
            "net_revenue_direct":         net_revenue_direct,
            "net_uplift_direct_vs_ota":   round(net_revenue_direct - net_revenue_ota, 2),
        }

        # ── Demand label ───────────────────────────────────────────────
        demand_label = RateRecommendation.label_for(adjusted_score)

        # ── Confidence ─────────────────────────────────────────────────
        confidence = self._confidence(adjusted_score, days_out, quality_premium)

        # ── Plain-English reasoning (2–3 sentences) ────────────────────
        rate_delta = final_rate - base_rate
        direction  = "increase" if rate_delta >= 0 else "decrease"
        reasoning  = self._build_reasoning(
            demand_label, adjusted_score, rate_delta, direction, final_rate,
            comp_avg, drivers, recommended_direct, net_revenue_ota,
            target_date, rt.get("name", ""),
            bathroom_type=bathroom_type,
            bathroom_premium=bathroom_premium,
            bathroom_premium_dollars=bathroom_premium_dollars,
        )

        return RateRecommendation(
            recommended_rate=final_rate,
            current_rate=base_rate,
            rate_change_dollars=round(rate_delta, 2),
            rate_change_percent=round(rate_delta / base_rate * 100, 1),
            demand_score=adjusted_score,
            demand_label=demand_label,
            confidence_score=confidence,
            reasoning=reasoning,
            minimum_stay_required=min_stay,
            los_discount_table=los_table,
            los_adjusted_rates=los_rates,
            is_gap_night=gap,
            gap_fill_rate=gap_fill,
            advance_purchase_rate=fences.advance_purchase_rate,
            advance_purchase_discount_pct=fences.advance_discount_pct,
            last_minute_fill=fences.last_minute_fill,
            last_minute_fill_rate=fences.last_minute_fill_rate,
            ota_commission_analysis=ota_analysis,
            competitive_position=comp_position,
            comp_avg_rate=comp_avg,
            quality_premium=quality_premium,
            recommended_direct_rate=recommended_direct,
            weather_adjustment=weather_adj,
            competitor_sold_out_boost=sold_out_boost,
            bathroom_type=bathroom_type,
            bathroom_premium_applied=bathroom_premium,
            bathroom_premium_dollars=bathroom_premium_dollars,
            cuthbert_rate=cuthbert_rate,
            cuthbert_sold_out=cuthbert_sold_out,
            applied_hard_ceiling=applied_hard_ceiling,
            primary_competitor_name=primary_name,
            primary_competitor_rate=cuthbert_rate,
            primary_competitor_sold_out=cuthbert_sold_out,
            tier2_ceiling=tier2_ceiling,
            tier3_reference=tier3_reference,
            tier4_floor=tier4_floor,
            market_ladder=mkt.get("market_ladder", []),
        )

    def update_all_recommendations(
        self,
        tenant_id:   str,
        property_id: str,
        days_ahead:  int = 90,
    ) -> int:
        """
        Fill recommended_rate for all pending rate_recommendations for this
        property (next 90 days).  Phase 2A populated demand_score; Phase 2B
        fills recommended_rate, reasoning, confidence_score, minimum_stay_rec.

        Returns rows updated.
        """
        from modules.hospitality.rate_engine import enforce_hierarchy_top_down

        room_types = self._get_room_types(property_id)

        # Compute every (room, date) recommendation first, indexed by date so
        # we can hierarchy-snap across room types before writing. The previous
        # loop wrote one room type at a time, which made it impossible to
        # enforce Waterfront > Waterview > Cottage >= Garden at the point of
        # write — hierarchy violations could land in the DB and only get
        # caught later by scripts/validate_rates.py.
        per_date: dict[str, list[dict[str, Any]]] = {}
        for rt in room_types:
            for rec in self._get_pending_recs(property_id, rt["id"]):
                target_date  = date.fromisoformat(rec["target_date"])
                demand_score = int(rec.get("demand_score") or 50)
                recommendation = self.recommend_rate(
                    tenant_id, property_id, rt["id"], target_date,
                    demand_score=demand_score,
                )
                per_date.setdefault(rec["target_date"], []).append({
                    "rec_id":         rec["id"],
                    "rt_name":        rt.get("name", ""),
                    "recommendation": recommendation,
                })

        # WRITE-TIME HIERARCHY ENFORCEMENT — snap each date's set of rates to
        # the canonical hierarchy before the PATCH. enforce_hierarchy_top_down
        # is the same function the validator's checks were modeled after; if
        # the engine writes a violation, the validator was always going to
        # catch it, but only after the bad data was already in the DB. Snap
        # here and the violation never gets written.
        updates: list[dict] = []
        for date_iso, entries in per_date.items():
            rates_by_name = {e["rt_name"]: float(e["recommendation"].recommended_rate)
                             for e in entries}
            snapped = enforce_hierarchy_top_down(rates_by_name)
            for e in entries:
                rec_obj = e["recommendation"]
                new_rate = snapped.get(e["rt_name"], rec_obj.recommended_rate)
                updates.append({
                    "id":               e["rec_id"],
                    "recommended_rate": float(new_rate),
                    "reasoning":        rec_obj.reasoning,
                    "confidence_score": rec_obj.confidence_score,
                    "minimum_stay_rec": rec_obj.minimum_stay_required,
                    "current_rate":     rec_obj.current_rate,
                })

        if not updates:
            return 0
        written = self._batch_patch(updates)
        logger.info("Updated %d recommendations across %d dates (hierarchy-enforced)",
                    written, len(per_date))
        return written

    def score_room_images(self, image_urls: list[str]) -> dict:
        """Placeholder for Phase 6B Claude vision API integration.
        Will analyze room photos and return quality scores by dimension."""
        return {
            "status":     "not_implemented",
            "phase":      "6B",
            "dimensions": [
                "furniture", "linens", "lighting", "bathroom",
                "view", "amenities", "staging", "aesthetic",
            ],
        }

    # ------------------------------------------------------------------ #
    #  Internal — helpers                                                  #
    # ------------------------------------------------------------------ #

    def _quality_premium(self, property_id: str, room_type_id: str) -> float:
        if not hasattr(self, "_qp_cache"):
            self._qp_cache: dict[str, float] = {}
        cache_key = f"{property_id}:{room_type_id}"
        if cache_key in self._qp_cache:
            return self._qp_cache[cache_key]
        rows = self._get(
            "property_quality_scores",
            params={
                "property_id":  f"eq.{property_id}",
                "room_type_id": f"eq.{room_type_id}",
                "select":       "total_score",
            },
        )
        if not rows or rows[0].get("total_score") is None:
            self._qp_cache[cache_key] = 0.0
            return 0.0
        score = float(rows[0]["total_score"])
        if score >= 8.0:
            result = min(0.08, (score - 8.0) * 0.125)   # hard cap 8% (was 25%)
        elif score <= 6.0:
            result = max(-0.08, (score - 6.0) * 0.075)  # floor -8%
        else:
            result = 0.0
        self._qp_cache[cache_key] = result
        return result

    def _get_room_type(self, room_type_id: str) -> dict[str, Any]:
        if not hasattr(self, "_rt_cache"):
            self._rt_cache: dict[str, dict] = {}
        if room_type_id not in self._rt_cache:
            rows = self._get(
                "room_types",
                params={
                    "id":     f"eq.{room_type_id}",
                    "select": "id,name,base_rate,min_rate,max_rate,total_count,bathroom_type,bathroom_premium,bathroom_description",
                },
            )
            if not rows:
                raise ValueError(f"Room type {room_type_id} not found")
            self._rt_cache[room_type_id] = rows[0]
        return self._rt_cache[room_type_id]

    def _get_room_types(self, property_id: str) -> list[dict[str, Any]]:
        return self._get(
            "room_types",
            params={
                "property_id": f"eq.{property_id}",
                "select":      "id,name,base_rate,min_rate,max_rate,total_count,bathroom_type,bathroom_premium,bathroom_description",
            },
        )

    def _get_pending_recs(
        self, property_id: str, room_type_id: str
    ) -> list[dict[str, Any]]:
        today = date.today()
        return self._get(
            "rate_recommendations",
            params=[
                ("property_id",  f"eq.{property_id}"),
                ("room_type_id", f"eq.{room_type_id}"),
                ("status",       "eq.pending"),
                ("target_date",  f"gt.{today.isoformat()}"),
                ("select",       "id,target_date,demand_score,confidence_score"),
            ],
            limit=500,
        )

    def _fetch_demand_score(
        self, property_id: str, room_type_id: str, target_date: date
    ) -> int:
        rows = self._get(
            "rate_recommendations",
            params={
                "property_id":  f"eq.{property_id}",
                "room_type_id": f"eq.{room_type_id}",
                "target_date":  f"eq.{target_date.isoformat()}",
                "status":       "eq.pending",
                "select":       "demand_score",
            },
        )
        if rows and rows[0].get("demand_score") is not None:
            return int(rows[0]["demand_score"])
        return 50  # neutral fallback

    def _get_cuthbert_signal(
        self, property_id: str, target_date: date
    ) -> tuple[Optional[float], bool]:
        """
        Returns (rate, is_sold_out) for the primary competitor on target_date.

        Uses competitor_rankings table (populated by CompetitorRanker) to
        find the rank-1 competitor dynamically. Falls back to searching by
        'Cuthbert' name if no rankings exist (legacy compatibility).
        """
        # Rank-1 competitor_id doesn't change per date — cache for bulk runs.
        if property_id not in self._rank1_cache:
            ranking_rows = self._get(
                "competitor_rankings",
                {"property_id": f"eq.{property_id}",
                 "rank":         "eq.1",
                 "select":       "competitor_id"},
            )
            if ranking_rows:
                self._rank1_cache[property_id] = ranking_rows[0]["competitor_id"]
            else:
                # Legacy fallback: Cuthbert House by name
                comps = self._get(
                    "competitor_properties",
                    {"property_id":    f"eq.{property_id}",
                     "competitor_name": "ilike.*Cuthbert*",
                     "select":          "id"},
                )
                self._rank1_cache[property_id] = comps[0]["id"] if comps else None
        comp_id = self._rank1_cache[property_id]
        if not comp_id:
            return None, False

        rows = self._get(
            "competitor_rates",
            {"competitor_id": f"eq.{comp_id}",
             "rate_date":     f"eq.{target_date.isoformat()}",
             "is_stale":      "eq.false",
             "select":        "rate_amount,is_sold_out"},
        )
        if not rows or rows[0].get("rate_amount") is None:
            return None, False

        return float(rows[0]["rate_amount"]), bool(rows[0]["is_sold_out"])

    def _confidence(
        self, demand_score: int, days_out: int, quality_premium: float
    ) -> int:
        conf = 60
        if quality_premium != 0.0:
            conf += 10   # quality data adds certainty
        if days_out <= 30:
            conf += 10
        if days_out <= 14:
            conf += 10
        if demand_score >= 80 or demand_score <= 30:
            conf += 10   # extreme scores are more reliable
        return min(95, conf)

    def _build_reasoning(
        self,
        demand_label:            str,
        score:                   int,
        rate_delta:              float,
        direction:               str,
        final_rate:              float,
        comp_avg:                Optional[float],
        drivers:                 list[str],
        direct_rate:             float,
        net_ota:                 float,
        target_date:             date,
        room_name:               str,
        bathroom_type:           str = "shower_only",
        bathroom_premium:        float = 0.0,
        bathroom_premium_dollars: float = 0.0,
    ) -> str:
        parts: list[str] = []

        # Sentence 1: demand + rate change
        delta_str = f"${abs(rate_delta):.0f} {direction}"
        # Use the first non-bathroom driver as the lead sentence driver
        lead_drivers = [d for d in drivers if "Tag this room" not in d]
        if lead_drivers:
            top_driver = lead_drivers[0].rstrip(".")
            parts.append(
                f"Demand is {demand_label} (score {score}) — {top_driver}. "
                f"Rate {direction} of {delta_str} to ${final_rate:.0f}/night."
            )
        else:
            parts.append(
                f"Demand is {demand_label} (score {score}). "
                f"Rate {direction} of {delta_str} to ${final_rate:.0f}/night."
            )

        # Sentence 2: bathroom premium (when meaningful)
        if bathroom_premium > 0 and bathroom_premium_dollars > 0:
            parts.append(
                f"Rain shower premium of {bathroom_premium * 100:.0f}% applied "
                f"(${bathroom_premium_dollars:.0f} above standard shower equivalent). "
                f"Tag as 'Rain Shower' on Booking.com/Expedia filters — "
                "guests searching this amenity convert at 2× standard rate."
            )

        # Sentence 3: competitive context
        if comp_avg:
            pct = (final_rate - comp_avg) / comp_avg * 100
            sign = "below" if pct < 0 else "above"
            parts.append(
                f"${final_rate:.0f} sits {abs(pct):.0f}% {sign} the "
                f"competitive set average of ${comp_avg:.0f}."
            )

        # Sentence 4: OTA vs direct comparison (only if rate is meaningful)
        if final_rate >= 300:
            uplift = round(direct_rate - net_ota, 0)
            if uplift > 0:
                parts.append(
                    f"Booking direct at ${direct_rate:.0f} nets the same "
                    f"revenue as a ${final_rate:.0f} Booking.com rate after "
                    f"their 15% commission — worth promoting in pre-arrival emails."
                )

        return " ".join(parts)

    # ------------------------------------------------------------------ #
    #  Internal — REST helpers                                             #
    # ------------------------------------------------------------------ #

    def _get(
        self,
        table:  str,
        params: dict | list,
        limit:  int = 1000,
    ) -> list[dict[str, Any]]:
        resp = requests.get(
            f"{self._url}/rest/v1/{table}",
            headers={**self._hdrs, "Prefer": "count=none"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _batch_patch(self, updates: list[dict]) -> int:
        """PATCH each row individually (PostgREST requires row-level updates)."""
        for row in updates:
            row_id  = row.pop("id")
            payload = {k: v for k, v in row.items() if v is not None}
            resp = requests.patch(
                f"{self._url}/rest/v1/rate_recommendations",
                headers={**self._hdrs, "Prefer": "return=minimal"},
                params={"id": f"eq.{row_id}"},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            row["id"] = row_id  # restore for caller
        return len(updates)


# ─────────────────────────────────────────────────────────────────────────────
#  Package pricing optimizer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PackageRecommendation:
    product_id:         str
    product_name:       str
    product_type:       str
    base_price:         float
    recommended_price:  float
    price_change_pct:   float          # signed; positive = increase
    strategy:           str            # 'premium_pricing' | 'bundle_offer' | 'hold'
    bundle_with_room:   bool
    bundle_savings:     float          # discount vs. à-la-carte when bundled
    reasoning:          str


class PackagePricingOptimizer:
    """
    Ancillary product pricing recommendations driven by room demand score.

    Rules:
      demand_score > 65  → Premium pricing: lift package prices by
                           PACKAGE_LIFT_FACTOR × room-rate uplift pct.
                           Guests paying $775 for a room are less price-sensitive.

      demand_score < 40  → Bundle strategy: attach package to room stay at a
                           modest discount to increase total booking value without
                           touching the room rate floor.

      40 ≤ score ≤ 65   → Hold: keep prices at base; no disruption to regular
                           booking flow.
    """

    PACKAGE_LIFT_FACTOR = 0.50   # packages get half the room premium
    MAX_PACKAGE_LIFT    = 0.25   # cap package price increase at 25%
    BUNDLE_DISCOUNT     = 0.15   # 15% off when bundled with a room booking

    def __init__(self, url: str, headers: dict[str, str]) -> None:
        self._url  = url
        self._hdrs = headers

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def optimize(
        self,
        products:           list[dict[str, Any]],
        demand_score:       int,
        room_rate_multiplier: float,
    ) -> list[PackageRecommendation]:
        """
        Return pricing recommendations for each active ancillary product.

        Parameters
        ----------
        products:             list of ancillary_products rows
        demand_score:         0–100 integer from rate_recommendations
        room_rate_multiplier: S-curve multiplier from the room rate engine
        """
        recs: list[PackageRecommendation] = []

        # How much did the room rate move above rack?
        room_uplift_pct = room_rate_multiplier - 1.0   # e.g. 0.7147 for score 90

        for p in products:
            if not p.get("active"):
                continue

            base  = float(p.get("base_price") or 0)
            lo    = float(p.get("min_price") or base * 0.80)
            hi    = float(p.get("max_price") or base * 1.50)
            name  = p.get("name", "")
            ptype = p.get("product_type", "")

            if demand_score > 65:
                # ── Premium pricing ──────────────────────────────────────
                raw_lift    = room_uplift_pct * self.PACKAGE_LIFT_FACTOR
                capped_lift = min(raw_lift, self.MAX_PACKAGE_LIFT)
                rec_price   = round(base * (1 + capped_lift) / 5) * 5
                rec_price   = max(lo, min(hi, rec_price))
                chg_pct     = (rec_price - base) / base * 100

                reasoning = (
                    f"Demand is {'Peak' if demand_score >= 90 else 'Very High' if demand_score >= 76 else 'High'} "
                    f"(score {demand_score}). Room rates are {room_uplift_pct * 100:.0f}% above rack. "
                    f"Lift {name} by {capped_lift * 100:.0f}% to ${rec_price:.0f} — "
                    f"guests paying ${round(base * room_rate_multiplier / 5) * 5:.0f}/night "
                    f"are less price-sensitive on add-ons."
                )
                if raw_lift > self.MAX_PACKAGE_LIFT:
                    reasoning += (
                        f" (Capped at {self.MAX_PACKAGE_LIFT * 100:.0f}% max to protect "
                        "package attach rate.)"
                    )

                recs.append(PackageRecommendation(
                    product_id=p.get("id", ""),
                    product_name=name,
                    product_type=ptype,
                    base_price=base,
                    recommended_price=rec_price,
                    price_change_pct=round(chg_pct, 1),
                    strategy="premium_pricing",
                    bundle_with_room=False,
                    bundle_savings=0.0,
                    reasoning=reasoning,
                ))

            elif demand_score < 40:
                # ── Bundle strategy ───────────────────────────────────────
                bundle_price  = round(base * (1 - self.BUNDLE_DISCOUNT) / 5) * 5
                bundle_price  = max(lo, bundle_price)
                savings       = base - bundle_price

                reasoning = (
                    f"Demand is {'Low' if demand_score >= 21 else 'Very Low'} "
                    f"(score {demand_score}). "
                    f"Bundle {name} with a room booking at ${bundle_price:.0f} "
                    f"(save ${savings:.0f} vs à-la-carte ${base:.0f}). "
                    f"This lifts the total booking value by ${bundle_price:.0f} "
                    f"without discounting the room rate — protecting RevPAR while "
                    f"giving guests a reason to book now."
                )

                recs.append(PackageRecommendation(
                    product_id=p.get("id", ""),
                    product_name=name,
                    product_type=ptype,
                    base_price=base,
                    recommended_price=bundle_price,
                    price_change_pct=round(-self.BUNDLE_DISCOUNT * 100, 1),
                    strategy="bundle_offer",
                    bundle_with_room=True,
                    bundle_savings=savings,
                    reasoning=reasoning,
                ))

            else:
                # ── Hold ──────────────────────────────────────────────────
                recs.append(PackageRecommendation(
                    product_id=p.get("id", ""),
                    product_name=name,
                    product_type=ptype,
                    base_price=base,
                    recommended_price=base,
                    price_change_pct=0.0,
                    strategy="hold",
                    bundle_with_room=False,
                    bundle_savings=0.0,
                    reasoning=(
                        f"Normal demand (score {demand_score}). "
                        f"Hold {name} at base price ${base:.0f}. "
                        f"No premium or bundle adjustment warranted."
                    ),
                ))

        # Sort: premium_pricing first, then bundle, then hold
        order = {"premium_pricing": 0, "bundle_offer": 1, "hold": 2}
        recs.sort(key=lambda r: (order.get(r.strategy, 9), -r.base_price))
        return recs

    def get_products(self, property_id: str) -> list[dict[str, Any]]:
        resp = requests.get(
            f"{self._url}/rest/v1/ancillary_products",
            headers={**self._hdrs, "Prefer": "count=none"},
            params={"property_id": f"eq.{property_id}", "active": "eq.true",
                    "select": "id,name,product_type,base_price,min_price,"
                              "max_price,available_to_outside_guests,"
                              "available_online,description,active"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def revenue_summary(self, property_id: str, days: int = 30) -> dict[str, Any]:
        """Total ancillary revenue and unit count for the last N days."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        resp   = requests.get(
            f"{self._url}/rest/v1/ancillary_sales",
            headers={**self._hdrs, "Prefer": "count=none"},
            params={"property_id": f"eq.{property_id}",
                    "sale_date":   f"gte.{cutoff}",
                    "select":      "quantity,total_revenue,buyer_type"},
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        total_rev  = sum(float(r.get("total_revenue") or 0) for r in rows)
        total_units = sum(int(r.get("quantity") or 0) for r in rows)
        by_buyer = {}
        for r in rows:
            bt = r.get("buyer_type", "unknown")
            by_buyer[bt] = by_buyer.get(bt, 0.0) + float(r.get("total_revenue") or 0)
        return {
            "days":         days,
            "total_revenue": round(total_rev, 2),
            "total_units":   total_units,
            "by_buyer_type": {k: round(v, 2) for k, v in by_buyer.items()},
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers: resolve tenant / property
# ─────────────────────────────────────────────────────────────────────────────

def _resolve(recommender: RateRecommender, slug: str) -> tuple[str, str]:
    tenants = recommender._get("tenants", {"slug": f"eq.{slug}", "select": "id"})
    if not tenants:
        raise ValueError(f"Tenant slug {slug!r} not found")
    tid = tenants[0]["id"]
    props = recommender._get(
        "properties", {"tenant_id": f"eq.{tid}", "select": "id"}
    )
    return tid, props[0]["id"]


def _insert_quality_scores(
    recommender: RateRecommender,
    tenant_id: str,
    property_id: str,
) -> None:
    """Seed sample quality scores for Anchorage 1770 room types."""
    room_types = recommender._get_room_types(property_id)
    rt_by_name = {rt["name"]: rt for rt in room_types}

    scores = []

    # Waterfront Suite — premium finish (8–9 range, total 8.7)
    if wf := rt_by_name.get("Waterfront Suite"):
        scores.append({
            "tenant_id": tenant_id, "property_id": property_id,
            "room_type_id": wf["id"],
            "furniture_quality": 9, "linens_quality": 9, "lighting_quality": 9,
            "bathroom_quality": 9, "view_quality": 9, "amenity_score": 8,
            "staging_score": 9, "overall_aesthetic": 9,
            "total_score": 8.9,
            "notes": "Premier riverfront rooms; panoramic Beaufort River views, "
                     "premium furnishings, private balconies",
        })

    # Waterview Suite — solid quality (7–8 range, total 7.8)
    if wv := rt_by_name.get("Waterview Suite"):
        scores.append({
            "tenant_id": tenant_id, "property_id": property_id,
            "room_type_id": wv["id"],
            "furniture_quality": 8, "linens_quality": 8, "lighting_quality": 8,
            "bathroom_quality": 8, "view_quality": 8, "amenity_score": 7,
            "staging_score": 8, "overall_aesthetic": 8,
            "total_score": 7.9,
            "notes": "Elegant suites with partial river views; solid appointments",
        })

    # Garden View Room — average (6–7 range, total 6.8)
    if gv := rt_by_name.get("Garden View Room"):
        scores.append({
            "tenant_id": tenant_id, "property_id": property_id,
            "room_type_id": gv["id"],
            "furniture_quality": 7, "linens_quality": 7, "lighting_quality": 7,
            "bathroom_quality": 7, "view_quality": 6, "amenity_score": 7,
            "staging_score": 7, "overall_aesthetic": 6,
            "total_score": 6.8,
            "notes": "Comfortable rooms; garden view, reliable quality",
        })

    # Cottage — premium experience (8–9 range, total 8.5)
    if co := rt_by_name.get("Cottage Room"):
        scores.append({
            "tenant_id": tenant_id, "property_id": property_id,
            "room_type_id": co["id"],
            "furniture_quality": 9, "linens_quality": 9, "lighting_quality": 8,
            "bathroom_quality": 9, "view_quality": 8, "amenity_score": 9,
            "staging_score": 8, "overall_aesthetic": 9,
            "total_score": 8.6,
            "notes": "Private cottage; full kitchen, romantic/honeymoon, premium privacy",
        })

    if scores:
        resp = requests.post(
            f"{recommender._url}/rest/v1/property_quality_scores",
            headers={**recommender._hdrs, "Prefer": "return=minimal"},
            json=scores,
            timeout=30,
        )
        resp.raise_for_status()
        print(f"  ✓ Quality scores inserted for {len(scores)} room types\n")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI and demo
# ─────────────────────────────────────────────────────────────────────────────

def _print_table(
    rows: list[dict[str, Any]],
    title: str,
    cols: list[tuple[str, int]],  # (header, width)
) -> None:
    total_w = sum(w for _, w in cols) + len(cols) * 3 + 1
    print(f"\n{'═' * total_w}")
    print(f"  {title}")
    print(f"{'═' * total_w}")
    hdr = "  " + "  ".join(f"{h:<{w}}" for h, w in cols)
    print(hdr)
    print(f"{'─' * total_w}")
    for row in rows:
        line = "  " + "  ".join(
            f"{str(row.get(k, '')):<{w}}" for k, w in cols
        )
        print(line)
    print(f"{'═' * total_w}\n")


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(description="The Gracious Collection — Rate Engine")
    parser.add_argument("--slug",   default="anchorage-1770-demo")
    parser.add_argument("--seed-quality", action="store_true",
                        help="Insert quality scores before running")
    parser.add_argument("--update-db", action="store_true",
                        help="Write recommended_rate back to rate_recommendations")
    args = parser.parse_args()

    re = RateRecommender()
    tenant_id, property_id = _resolve(re, args.slug)
    room_types = re._get_room_types(property_id)
    rt_by_name = {rt["name"]: rt for rt in room_types}

    print(f"\n  The Gracious Collection — Rate Recommendation Engine")
    print(f"  Tenant : {args.slug}  |  Property ID : {property_id}\n")

    # ── 1. Seed quality scores ─────────────────────────────────────────
    if args.seed_quality:
        _insert_quality_scores(re, tenant_id, property_id)

    # ── 2. Update all DB recommendations ──────────────────────────────
    if args.update_db:
        print("  Updating rate_recommendations (this will take ~60 s)…")
        n = re.update_all_recommendations(tenant_id, property_id)
        print(f"  ✓ {n} recommendations updated\n")

    # ── 3. Market-calibration scenarios ───────────────────────────────
    demo_rt    = rt_by_name.get("Waterfront Suite") or room_types[0]
    wf_sat     = date(2026, 7, 18)   # Water Festival Saturday
    apr_sat    = date(2026, 4, 18)   # Normal spring Saturday
    jan_tue    = date(2027, 1, 13)   # Low-season January Tuesday

    W = 112
    SEP = f"{'═' * W}"
    print(f"\n{SEP}")
    print(f"  MARKET CALIBRATION — Waterfront Suite (base ${demo_rt['base_rate']:.0f}) — Recalibrated S-Curve + Cuthbert Ceiling")
    print(f"{SEP}")

    def _show_scenario(
        label: str,
        d: date,
        demand_override: int | None = None,
        cuthbert_sold_out_override: bool = False,
        note: str = "",
    ) -> None:
        rec = re.recommend_rate(
            tenant_id, property_id, demo_rt["id"], d,
            demand_score=demand_override,
        )
        # For sold-out override scenario: manually set cuthbert_sold_out flag effect
        # (in production this comes from DB; here we simulate it)
        if cuthbert_sold_out_override and not rec.cuthbert_sold_out:
            # Re-run with explicit sold-out boost in the demand_score
            boosted = min(100, (demand_override or rec.demand_score) + 20)
            rec = re.recommend_rate(
                tenant_id, property_id, demo_rt["id"], d,
                demand_score=boosted,
            )

        cuthbert_str = (
            f"${rec.cuthbert_rate:.0f} {'(SOLD OUT)' if rec.cuthbert_sold_out or cuthbert_sold_out_override else ''}"
            if rec.cuthbert_rate else "no data/fallback"
        )
        ceiling_flag = " ← HARD CEILING" if rec.applied_hard_ceiling else ""

        print(f"\n  ── SCENARIO: {label} ── {d.strftime('%A %B %-d, %Y')}")
        if note: print(f"     Note: {note}")
        print(f"  {'─' * 80}")
        print(f"  Demand score       : {rec.demand_score}  ({rec.demand_label})")
        print(f"  Cuthbert House     : {cuthbert_str}")
        print(f"  Rain shower prem   : {rec.bathroom_premium_applied*100:.0f}% (${rec.bathroom_premium_dollars:.0f})")
        print(f"  Quality premium    : {rec.quality_premium*100:.1f}%")
        print(f"  ─────────────────────────────────────────────────────────────────────────")
        print(f"  RECOMMENDED RATE   : ${rec.recommended_rate:.0f}/night{ceiling_flag}")
        print(f"  vs base ($378)     : {rec.rate_change_percent:+.0f}%  (${rec.rate_change_dollars:+.0f})")
        print(f"  Minimum stay       : {rec.minimum_stay_required} night(s)")
        print(f"  Direct rate        : ${rec.recommended_direct_rate:.0f}  |  OTA net: ${rec.ota_commission_analysis['net_revenue_ota']:.0f}")
        print(f"  Reasoning          : {rec.reasoning[:120]}…")

    _show_scenario(
        "1. Water Festival Saturday (★ Peak)",
        wf_sat,
        demand_override=90,
        note="Target range: $490–$540. Cuthbert not sold out → 97% ceiling applies",
    )
    _show_scenario(
        "2. Normal Saturday in April (▲ High)",
        apr_sat,
        demand_override=75,
        note="Target range: $420–$460. Spring demand, Cuthbert active",
    )
    _show_scenario(
        "3. January Tuesday low season (▽ Very Low)",
        jan_tue,
        demand_override=25,
        note="Target range: $295–$340. Low season, Cuthbert also discounting",
    )
    _show_scenario(
        "4. SCENARIO — Cuthbert SOLD OUT on Water Festival Saturday",
        wf_sat,
        demand_override=90,
        cuthbert_sold_out_override=True,
        note="When Cuthbert sells out we get +20 demand boost and 115% ceiling",
    )

    # ── 4. Bathroom premium verification ──────────────────────────────
    print(f"\n{SEP}")
    print(f"  CORRECTION 1 VERIFICATION — All bathrooms now shower_only")
    print(f"{'─' * W}")
    print(f"  {'Room Type':<22} {'Bathroom Type':<26} {'Premium':>8}  {'Description'}")
    print(f"{'─' * W}")
    for rt in room_types:
        bath_desc = rt.get("bathroom_description") or "—"
        print(
            f"  {rt['name']:<22} {(rt.get('bathroom_type') or '—'):<26} "
            f"{(float(rt.get('bathroom_premium') or 0))*100:>7.0f}%  {bath_desc}"
        )
    print(SEP)

    # ── 5. All room types for Water Festival Saturday ──────────────────
    print(f"\n{SEP}")
    print(f"  ALL ROOM TYPES — Water Festival Saturday {wf_sat}")
    print(f"{'─' * W}")
    print(f"  {'Room Type':<22} {'Score':>5} {'Rate':>7} {'vs Base':>8}  {'Bath%':>6}  {'Quality%':>9}  {'Direct':>7}  {'OTA Net':>8}  {'Ceiling?'}")
    print(f"{'─' * W}")
    for rt in room_types:
        rec = re.recommend_rate(tenant_id, property_id, rt["id"], wf_sat, demand_score=90)
        ceiling = "← hard cap" if rec.applied_hard_ceiling else ""
        print(
            f"  {rt['name']:<22} {rec.demand_score:>5}  ${rec.recommended_rate:>5.0f}  "
            f"{rec.rate_change_percent:>+6.0f}%  "
            f"{rec.bathroom_premium_applied*100:>5.0f}%  "
            f"{rec.quality_premium*100:>+8.1f}%  "
            f"${rec.recommended_direct_rate:>5.0f}  "
            f"${rec.ota_commission_analysis['net_revenue_ota']:>6.0f}  {ceiling}"
        )
    print(SEP)

    # ── 6. Package pricing optimizer ───────────────────────────────────
    # (kept as section 9 to preserve numbering from earlier phases)
    # ── 9. Package pricing optimizer ──────────────────────────────────
    pkg = PackagePricingOptimizer(re._url, re._hdrs)
    products = pkg.get_products(property_id)

    print(f"\n\n  ANCILLARY PACKAGE PRICING OPTIMIZER")

    for label, score in [("Peak (Water Festival)", 90), ("Normal (September)", 54), ("Low (January)", 30)]:
        mult = _spline_multiplier(score)
        recs_pkg = pkg.optimize(products, score, mult)

        print(f"\n  ── Demand: {label} (score {score}, room ×{mult:.3f}) ──")
        print(f"  {'Product':<28} {'Base':>6}  {'Rec $':>6}  {'Δ%':>6}  {'Strategy':<18}  Reasoning")
        print(f"  {'─' * 100}")
        for r in recs_pkg:
            strategy_tag = {
                "premium_pricing": "↑ Premium",
                "bundle_offer":    "⟲ Bundle w/ room",
                "hold":            "◆ Hold",
            }.get(r.strategy, r.strategy)
            note = ""
            if r.strategy == "bundle_offer":
                note = f"(save ${r.bundle_savings:.0f} when booked with stay)"
            print(
                f"  {r.product_name:<28} ${r.base_price:>5.0f}  "
                f"${r.recommended_price:>5.0f}  "
                f"{r.price_change_pct:>+5.1f}%  {strategy_tag:<18}  {note}"
            )

    # Revenue summary (will be $0 until sales are logged — shows the endpoint works)
    summary = pkg.revenue_summary(property_id, days=30)
    print(f"\n\n  ANCILLARY REVENUE SUMMARY — Last 30 Days")
    print(f"  {'─' * 42}")
    print(f"  Total revenue  : ${summary['total_revenue']:,.2f}")
    print(f"  Units sold     : {summary['total_units']}")
    if summary["by_buyer_type"]:
        for bt, rev in summary["by_buyer_type"].items():
            print(f"  {bt:<14} : ${rev:,.2f}")
    else:
        print(f"  (No sales recorded yet — add transactions to ancillary_sales)")
    print()

    # ── 10. S-curve illustration ───────────────────────────────────────
    print(f"  S-CURVE MULTIPLIER REFERENCE")
    print(f"  {'─' * 42}")
    print(f"  {'Score':>6}  {'Multiplier':>11}  {'Label':<12}")
    print(f"  {'─' * 42}")
    for sc in [0, 20, 35, 50, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
        mult  = _spline_multiplier(sc)
        label = RateRecommendation.label_for(sc)
        print(f"  {sc:>6}  {mult:>11.4f}  {label:<12}")
    print()


if __name__ == "__main__":
    main()
