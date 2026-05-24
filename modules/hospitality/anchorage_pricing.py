"""
modules/hospitality/anchorage_pricing.py

Dynamic pricing engine for Bay Street Inn
1103 Bay Street, Beaufort SC 29902

Generates optimal nightly rates for 14 rentable rooms based on:
  - Lead time to arrival + live occupancy
  - Beaufort SC local events calendar (full annual)
  - Competitor rate benchmarks (5-property set)
  - Weekend demand premiums
  - Seasonal demand curves

CLI usage:
    python -m modules.hospitality.anchorage_pricing --report
    python -m modules.hospitality.anchorage_pricing --calendar --days 60
    python -m modules.hospitality.anchorage_pricing --report --date 2026-07-20
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Resolve project root when executed as __main__ or imported
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import DATA_EXPORTS_DIR  # noqa: E402

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Room Inventory
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Room:
    room_id:     str
    name:        str
    tier:        str
    rack_low:    float
    rack_high:   float
    description: str
    max_guests:  int = 2


ROOM_INVENTORY: Dict[str, Room] = {
    # ── Waterfront Tier — direct Beaufort River views ($389–$459) ────────────
    "201": Room("201", "Waterfront 201", "waterfront", 389, 459,
                "Direct river views, king bed, premium furnishings"),
    "202": Room("202", "Waterfront 202", "waterfront", 389, 459,
                "Direct river views, king bed, private balcony access"),
    "203": Room("203", "Waterfront 203", "waterfront", 399, 459,
                "Direct river views, private balcony, corner light"),
    "204": Room("204", "Waterfront 204", "waterfront", 409, 459,
                "Direct river views, corner suite, sitting area"),

    # ── Water View Tier — partial river views ($319–$369) ────────────────────
    "301": Room("301", "Water View 301", "water_view", 319, 369,
                "Partial river views, queen bed"),
    "302": Room("302", "Water View 302", "water_view", 319, 369,
                "Partial river views, king bed"),
    "303": Room("303", "Water View 303", "water_view", 329, 369,
                "Partial river views, sitting area, clawfoot tub"),
    "304": Room("304", "Water View 304", "water_view", 319, 359,
                "Partial river views, flexible twin/king configuration"),
    "305": Room("305", "Water View 305", "water_view", 329, 369,
                "Partial river views, clawfoot tub, updated bath"),

    # ── Garden / Standard Tier — garden views ($269–$299) ───────────────────
    "101": Room("101", "Garden Room 101", "garden", 269, 299,
                "Garden views, queen bed, ground-floor accessibility"),
    "102": Room("102", "Garden Room 102", "garden", 269, 299,
                "Garden views, king bed"),
    "103": Room("103", "Garden Room 103", "garden", 279, 299,
                "Garden views, king bed, private patio"),
    "104": Room("104", "Garden Room 104", "garden", 269, 289,
                "Garden views, twin beds, ideal for extended stays"),

    # ── Private Cottage — most premium ($489–$549) ───────────────────────────
    "cottage": Room("cottage", "Private Cottage", "cottage", 489, 549,
                    "Secluded private cottage, full kitchen, romantic/honeymoon, "
                    "outdoor seating"),
}

# Conference room — NOT in rental inventory, tracked separately
CONFERENCE_ROOM = {
    "room_id": "conf",
    "name": "Conference Room",
    "use": "Executive meetings, wine tastings, private events",
    "capacity": 20,
}

RENTABLE_ROOM_IDS = list(ROOM_INVENTORY.keys())  # 14 rooms

# Max discount floor: never go below 85% of rack_low
TIER_FLOOR_PCT = 0.85

# ─────────────────────────────────────────────────────────────────────────────
#  Competitor Set
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Competitor:
    name:      str
    base_low:  float   # low-season weekday typical rate
    base_high: float   # peak-season weekend typical rate
    url_hint:  str     # integration point for live scraping


COMPETITORS: Dict[str, Competitor] = {
    "rhett_house":    Competitor("Rhett House Inn",              239, 439, "rhethouse.com"),
    "city_loft":      Competitor("City Loft Hotel",              169, 295, "citylofthotel.com"),
    "beaufort_inn":   Competitor("Beaufort Inn",                 199, 375, "beaufortinn.com"),
    "cuthbert_house": Competitor("Cuthbert House Inn",           249, 425, "cuthberthouseinn.com"),
    "bay_inn_607":    Competitor("607 Bay Inn",                  189, 349, "booking.com"),
    "airbnb_avg":     Competitor("Airbnb Near Bay Street (avg)", 149, 325, "airbnb.com"),
}

# ─────────────────────────────────────────────────────────────────────────────
#  Seasonal Demand Index  (applied to rack midpoint as baseline)
# ─────────────────────────────────────────────────────────────────────────────

SEASONAL_INDEX: Dict[int, float] = {
    1:  0.88,  # January  — low season, post-holiday
    2:  0.90,  # February — low/shoulder, Film Festival lifts it
    3:  0.96,  # March    — shoulder, spring shoulder
    4:  1.05,  # April    — spring peak, Taste of Beaufort
    5:  1.10,  # May      — festival season opens, Gullah Festival
    6:  1.07,  # June     — summer, Music Festival
    7:  1.18,  # July     — peak month, Water Festival + 4th July
    8:  1.06,  # August   — late summer
    9:  0.96,  # September — shoulder
    10: 1.09,  # October  — fall festival season (Shrimp, OctoPRfest)
    11: 0.94,  # November — shoulder
    12: 1.01,  # December — holiday uptick
}

# ─────────────────────────────────────────────────────────────────────────────
#  Beaufort SC Annual Events Calendar
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LocalEvent:
    name:       str
    month:      int
    day_start:  int
    day_end:    int
    multiplier: float   # pricing multiplier during event (e.g. 1.30 = +30%)
    lead_days:  int = 2 # N days before start also carry a partial premium
    notes:      str = ""


ANNUAL_EVENTS: List[LocalEvent] = [
    # ── January ─────────────────────────────────────────────────────────────
    LocalEvent("Pelican Plunge",                       1,  1,  2, 1.20, 1,
               "New Year's Day polar plunge, waterfront party"),
    LocalEvent("Beaufort Oyster Festival",             1, 17, 19, 1.30, 3,
               "3-day waterfront oyster celebration, major draw"),
    LocalEvent("Beaufort International Film Festival", 1, 28, 31, 1.25, 3,
               "Independent film screenings, Q&As, citywide events"),

    # ── February ────────────────────────────────────────────────────────────
    LocalEvent("Bands Brews and BBQ",                  2, 13, 15, 1.25, 2,
               "Valentine's weekend music and food festival"),

    # ── April ───────────────────────────────────────────────────────────────
    LocalEvent("A Taste of Beaufort",                  4, 24, 26, 1.25, 2,
               "Culinary festival on the waterfront"),

    # ── May ─────────────────────────────────────────────────────────────────
    LocalEvent("Soft Shell Crab Festival",             5,  1,  4, 1.25, 2,
               "Annual waterfront seafood festival, first weekend of May"),
    LocalEvent("Original Gullah Festival",             5, 23, 26, 1.35, 3,
               "Memorial Day weekend — largest Gullah-Geechee cultural event in nation"),

    # ── June ────────────────────────────────────────────────────────────────
    LocalEvent("Music Festival of the Lowcountry",    6, 19, 22, 1.25, 2,
               "Juneteenth weekend multi-genre music celebration"),

    # ── July ────────────────────────────────────────────────────────────────
    LocalEvent("4th of July Celebrations",            7,  3,  6, 1.35, 2,
               "Independence Day waterfront fireworks and festivities"),
    LocalEvent("Black Boses Freedom Festival",         7,  4,  6, 1.25, 1,
               "Cultural freedom festival, July 4 weekend"),
    LocalEvent("Annual Beaufort Water Festival",       7, 18, 27, 1.30, 3,
               "10-day flagship festival — largest annual event in Beaufort"),

    # ── October ─────────────────────────────────────────────────────────────
    LocalEvent("OctoPRfest",                          10,  2,  4, 1.20, 2,
               "Oktoberfest-style celebration, first weekend"),
    LocalEvent("Annual Beaufort Shrimp Festival",     10,  9, 12, 1.30, 3,
               "Major waterfront seafood festival, second weekend"),
    LocalEvent("Fall Festival of Houses and Gardens", 10, 16, 19, 1.25, 2,
               "Historic homes and gardens tours"),

    # ── November ────────────────────────────────────────────────────────────
    LocalEvent("Penn Center Heritage Days",           11,  7,  9, 1.25, 2,
               "Gullah-Geechee cultural heritage celebration, St Helena Island"),

    # ── December ────────────────────────────────────────────────────────────
    LocalEvent("Night on the Town",                   12,  5,  6, 1.20, 1,
               "Downtown holiday kickoff celebration"),
    LocalEvent("Christmas to New Year's Holiday Peak",12, 23, 31, 1.30, 5,
               "Peak holiday travel window"),
]

# Every first Friday of the month — downtown art walk
FIRST_FRIDAY_MULT = 1.15

# Downtown Farmers Market — every Saturday, May through October
FARMERS_MARKET_MONTHS = set(range(5, 11))
FARMERS_MARKET_MULT = 1.08

# Parris Island USMC Recruit Graduations — approximately every 2 weeks on Fridays
# ISO week numbers; replace with official MCRD schedule for production
PARRIS_ISLAND_GRAD_ISO_WEEKS = {
    5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27,
    29, 31, 33, 35, 37, 39, 41, 43, 45, 47,
}
PARRIS_ISLAND_MULT = 1.20


# ─────────────────────────────────────────────────────────────────────────────
#  Pricing Engine
# ─────────────────────────────────────────────────────────────────────────────

class AnchoragePricingEngine:
    """
    Dynamic pricing engine for Bay Street Inn.

    All public methods return plain dicts or DataFrames — no side effects
    except generate_daily_report() and generate_pricing_calendar() which
    export CSVs to data/exports/.
    """

    PROPERTY_NAME    = "Bay Street Inn"
    PROPERTY_ADDRESS = "1103 Bay Street, Beaufort SC 29902"

    # Occupancy targets
    OCC_TARGET_LOW  = 0.70
    OCC_TARGET_HIGH = 0.85

    # ------------------------------------------------------------------ #
    #  1. Event multiplier                                                 #
    # ------------------------------------------------------------------ #

    def get_event_multiplier(self, check_date: date) -> Tuple[float, List[str]]:
        """
        Returns (multiplier, active_event_names) for a given date.

        Logic:
          - Annual events apply on their dates and lead_days before start
            (lead-up carries 50% of the full premium)
          - Monthly recurring events (First Friday, Farmers Market) apply
            on their specific days
          - Parris Island graduation Fridays apply separately
          - When multiple events overlap, the highest single multiplier wins
            (they don't compound — Beaufort isn't that big)
        """
        active: List[str] = []
        max_mult = 1.0

        year = check_date.year

        for evt in ANNUAL_EVENTS:
            try:
                evt_start = date(year, evt.month, evt.day_start)
                evt_end   = date(year, evt.month, evt.day_end)
            except ValueError:
                continue  # Feb 29, etc.

            premium_start = evt_start - timedelta(days=evt.lead_days)

            if premium_start <= check_date <= evt_end:
                if check_date < evt_start:
                    # Lead-up: partial premium
                    mult = 1.0 + (evt.multiplier - 1.0) * 0.50
                else:
                    mult = evt.multiplier

                active.append(evt.name)
                max_mult = max(max_mult, mult)

        # First Friday (first Friday of each month)
        if check_date.weekday() == 4 and check_date.day <= 7:
            active.append("First Friday Art Walk")
            max_mult = max(max_mult, FIRST_FRIDAY_MULT)

        # Downtown Farmers Market Saturdays (May–October)
        if check_date.month in FARMERS_MARKET_MONTHS and check_date.weekday() == 5:
            active.append("Downtown Farmers Market")
            max_mult = max(max_mult, FARMERS_MARKET_MULT)

        # Parris Island USMC graduation Fridays
        iso_week = check_date.isocalendar()[1]
        if check_date.weekday() == 4 and iso_week in PARRIS_ISLAND_GRAD_ISO_WEEKS:
            active.append("Parris Island USMC Graduation")
            max_mult = max(max_mult, PARRIS_ISLAND_MULT)

        return round(max_mult, 4), active

    # ------------------------------------------------------------------ #
    #  2. Competitor rates                                                 #
    # ------------------------------------------------------------------ #

    def get_competitor_rates(self, check_in_date: date) -> Dict[str, float]:
        """
        Returns estimated competitor rates for a given date.

        PRODUCTION INTEGRATION NOTE:
          Replace this method body with one of:
            • OTA Insight / Lighthouse API  (recommended rate-shopping SaaS)
            • RateGain Intelligence API
            • Expedia Partner Central / Booking.com Connectivity APIs
            • Custom Selenium scraper with proxy rotation

          Each should return {competitor_name: nightly_rate} for the date.

        Current implementation: calibrated seasonal + event demand model
        based on known Beaufort SC boutique hotel rate ranges. Deterministic
        per date (no randomness) so reports are reproducible.
        """
        seasonal    = SEASONAL_INDEX.get(check_in_date.month, 1.0)
        is_weekend  = check_in_date.weekday() in (4, 5)
        event_mult, _ = self.get_event_multiplier(check_in_date)

        weekend_bump  = 1.15 if is_weekend else 1.0
        # Competitors feel events too, but with less local intel — dampen slightly
        comp_event    = 1.0 + (event_mult - 1.0) * 0.70
        overall       = seasonal * max(weekend_bump, comp_event)

        rates: Dict[str, float] = {}
        for key, comp in COMPETITORS.items():
            base = (comp.base_low + comp.base_high) / 2.0 * overall
            # Deterministic ±3% market noise keyed to (date × competitor)
            noise_seed  = (check_in_date.toordinal() * 7 + hash(key)) % 100
            noise_factor = 1.0 + (noise_seed - 50) * 0.0006
            rates[comp.name] = round(base * noise_factor / 5) * 5  # nearest $5

        return rates

    # ------------------------------------------------------------------ #
    #  3. Single-room rate calculator                                      #
    # ------------------------------------------------------------------ #

    def calculate_room_rate(
        self,
        room_id: str,
        check_in_date: date,
        occupancy_rate: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Returns the optimal nightly rate for one room on one date.

        Dynamic adjustment rules (in priority order):
          90+ days out  → rack rate; +10% if event detected early
          60–89 days    → rack rate
          30–59 days    → rack rate (monitor occupancy)
          14–29 days    → -5% if occupancy < 70%
           7–13 days    → -10% if occupancy < 70%
            3–6 days    → -15% (floor) if occupancy < 65%
           0–2 days     → -15% floor if < 65%, else slight -3%

          Weekend       → +15% (Fri / Sat nights)
          Event active  → event multiplier overrides any discount;
                          at 90+ days the early event premium is capped at +10%
          Absolute floor → max(15% discount below rack_low, applied last)
        """
        if room_id not in ROOM_INVENTORY:
            raise KeyError(f"Unknown room_id: {room_id!r}")

        room    = ROOM_INVENTORY[room_id]
        today   = date.today()
        days_out = max(0, (check_in_date - today).days)

        rack_mid   = (room.rack_low + room.rack_high) / 2.0
        rack_floor = room.rack_low * TIER_FLOOR_PCT

        seasonal_mult  = SEASONAL_INDEX.get(check_in_date.month, 1.0)
        seasonal_base  = rack_mid * seasonal_mult

        event_mult, active_events = self.get_event_multiplier(check_in_date)
        has_event = event_mult > 1.0

        # ── Lead-time + occupancy factor ──────────────────────────────────
        reasoning: List[str] = []
        lead_factor: float

        if days_out >= 90:
            lead_factor = 1.10 if has_event else 1.0
            tag = "early event +10%" if has_event else "rack rate"
            reasoning.append(f"{days_out}d out → {tag}")

        elif days_out >= 60:
            lead_factor = 1.0
            reasoning.append(f"{days_out}d out → rack rate")

        elif days_out >= 30:
            lead_factor = 1.0
            reasoning.append(f"{days_out}d out → rack rate, monitoring occ")

        elif days_out >= 14:
            if occupancy_rate < self.OCC_TARGET_LOW:
                lead_factor = 0.95
                reasoning.append(
                    f"{days_out}d out, occ {occupancy_rate:.0%} < 70% → −5%"
                )
            else:
                lead_factor = 1.0
                reasoning.append(
                    f"{days_out}d out, occ {occupancy_rate:.0%} ≥ 70% → rack"
                )

        elif days_out >= 7:
            if occupancy_rate < self.OCC_TARGET_LOW:
                lead_factor = 0.90
                reasoning.append(
                    f"{days_out}d out, occ {occupancy_rate:.0%} < 70% → −10%"
                )
            else:
                lead_factor = 1.0
                reasoning.append(
                    f"{days_out}d out, occ {occupancy_rate:.0%} ≥ 70% → rack"
                )

        elif days_out >= 3:
            if occupancy_rate < 0.65:
                lead_factor = 0.85
                reasoning.append(
                    f"{days_out}d out, occ {occupancy_rate:.0%} < 65% → −15% (floor)"
                )
            else:
                lead_factor = 1.0
                reasoning.append(
                    f"{days_out}d out, occ {occupancy_rate:.0%} ≥ 65% → rack"
                )

        else:  # 0–2 days
            if occupancy_rate < 0.65:
                lead_factor = 0.85
                reasoning.append(
                    f"Last-minute ({days_out}d), occ {occupancy_rate:.0%} < 65% → −15%"
                )
            else:
                lead_factor = 0.97
                reasoning.append(
                    f"Last-minute ({days_out}d), slight −3% to close"
                )

        # ── Events override discounts ──────────────────────────────────────
        if has_event:
            if days_out >= 90:
                effective_demand = 1.10  # capped early premium
            else:
                effective_demand = max(lead_factor, event_mult)
            reasoning.append(f"Events: {', '.join(active_events)} (×{effective_demand:.2f})")
        else:
            effective_demand = lead_factor

        # ── Weekend premium ────────────────────────────────────────────────
        is_weekend = check_in_date.weekday() in (4, 5)
        weekend_mult = 1.15 if is_weekend else 1.0
        if is_weekend:
            reasoning.append("Weekend +15% (Fri/Sat)")

        # ── Compute rate ───────────────────────────────────────────────────
        raw_rate = seasonal_base * effective_demand * weekend_mult
        rate     = max(raw_rate, rack_floor)          # enforce floor
        rate     = round(rate / 5) * 5                # round to nearest $5

        # ── Metrics ───────────────────────────────────────────────────────
        vs_rack_pct = round((rate - rack_mid) / rack_mid * 100, 1)

        comp_rates  = self.get_competitor_rates(check_in_date)
        comp_avg    = sum(comp_rates.values()) / len(comp_rates)
        vs_comp_pct = round((rate - comp_avg) / comp_avg * 100, 1)

        return {
            "room_id":            room_id,
            "room_name":          room.name,
            "tier":               room.tier,
            "check_in_date":      check_in_date.isoformat(),
            "day_of_week":        check_in_date.strftime("%A"),
            "days_out":           days_out,
            "rate":               rate,
            "rack_low":           room.rack_low,
            "rack_high":          room.rack_high,
            "rack_mid":           rack_mid,
            "rack_floor":         round(rack_floor, 2),
            "seasonal_index":     seasonal_mult,
            "event_multiplier":   event_mult,
            "active_events":      active_events,
            "is_weekend":         is_weekend,
            "occupancy_rate":     occupancy_rate,
            "effective_demand":   round(effective_demand, 4),
            "competitor_rates":   comp_rates,
            "competitor_avg":     round(comp_avg, 2),
            "rate_vs_rack_pct":   vs_rack_pct,
            "rate_vs_comp_pct":   vs_comp_pct,
            "reasoning":          " | ".join(reasoning),
        }

    # ------------------------------------------------------------------ #
    #  4. 90-day pricing calendar                                          #
    # ------------------------------------------------------------------ #

    def generate_pricing_calendar(
        self,
        days_ahead: int = 90,
        base_occupancy: float = 0.75,
        occupancy_by_date: Optional[Dict[date, float]] = None,
    ) -> pd.DataFrame:
        """
        Generates a pricing grid for all 14 rooms across the next N days.

        Parameters
        ----------
        days_ahead:        how many days forward to project
        base_occupancy:    default occupancy assumption when not in occupancy_by_date
        occupancy_by_date: optional per-date occupancy overrides {date: float}
                           (connect to PMS for live data in production)

        Returns a DataFrame with one row per (room × date), exported to CSV.
        """
        logger.info(
            f"Generating {days_ahead}-day pricing calendar for "
            f"{len(ROOM_INVENTORY)} rooms"
        )
        today  = date.today()
        rows: List[Dict[str, Any]] = []

        for day_offset in range(days_ahead):
            check_in = today + timedelta(days=day_offset)
            occ = (
                occupancy_by_date.get(check_in, base_occupancy)
                if occupancy_by_date
                else base_occupancy
            )
            event_mult, active_events = self.get_event_multiplier(check_in)
            comp_rates = self.get_competitor_rates(check_in)
            comp_avg   = round(sum(comp_rates.values()) / len(comp_rates), 2)

            for room_id in ROOM_INVENTORY:
                r = self.calculate_room_rate(room_id, check_in, occ)
                rows.append({
                    "date":             check_in.isoformat(),
                    "day_of_week":      check_in.strftime("%A"),
                    "days_out":         day_offset,
                    "room_id":          room_id,
                    "room_name":        r["room_name"],
                    "tier":             r["tier"],
                    "rack_low":         r["rack_low"],
                    "rack_high":        r["rack_high"],
                    "recommended_rate": r["rate"],
                    "rate_vs_rack_pct": r["rate_vs_rack_pct"],
                    "occupancy_assumed":f"{occ:.0%}",
                    "is_weekend":       r["is_weekend"],
                    "active_events":    "; ".join(active_events),
                    "event_multiplier": event_mult,
                    "competitor_avg":   comp_avg,
                    "rate_vs_comp_pct": r["rate_vs_comp_pct"],
                    "reasoning":        r["reasoning"],
                })

        df = pd.DataFrame(rows)
        path = self._export_csv(df, f"bay_street_inn_calendar_{days_ahead}d")
        logger.info(f"Pricing calendar exported → {path}  ({len(df):,} rows)")
        return df

    # ------------------------------------------------------------------ #
    #  5. Daily morning report                                             #
    # ------------------------------------------------------------------ #

    def generate_daily_report(
        self,
        target_date: Optional[date] = None,
        occupancy_rate: float = 0.75,
    ) -> pd.DataFrame:
        """
        Morning pricing report for a single date across all 14 rooms.
        Exports to data/exports/bay_street_inn_daily_report_YYYYMMDD.csv.
        """
        report_date = target_date or date.today()
        logger.info(f"Generating daily pricing report for {report_date}")

        rows = [
            self.calculate_room_rate(room_id, report_date, occupancy_rate)
            for room_id in ROOM_INVENTORY
        ]
        df = pd.DataFrame(rows)

        # Flatten competitor_rates dict into separate columns
        comp_df = pd.json_normalize(df["competitor_rates"])
        df = pd.concat([df.drop(columns=["competitor_rates"]), comp_df], axis=1)

        path = self._export_csv(
            df, f"bay_street_inn_daily_report_{report_date.strftime('%Y%m%d')}"
        )
        logger.info(f"Daily report exported → {path}")
        return df

    # ------------------------------------------------------------------ #
    #  Export helper                                                       #
    # ------------------------------------------------------------------ #

    def _export_csv(self, df: pd.DataFrame, stem: str) -> str:
        os.makedirs(DATA_EXPORTS_DIR, exist_ok=True)
        ts   = datetime.utcnow().strftime("%H%M%S")
        path = os.path.join(DATA_EXPORTS_DIR, f"{stem}_{ts}.csv")
        df.to_csv(path, index=False)
        return path


# ─────────────────────────────────────────────────────────────────────────────
#  CLI report formatter
# ─────────────────────────────────────────────────────────────────────────────

def _print_report(df: pd.DataFrame, engine: AnchoragePricingEngine, report_date: date) -> None:
    """Renders a rich terminal report from the daily report DataFrame."""
    W = 84
    sep  = "═" * W
    thin = "─" * W

    # ── Header ────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print(f"  {engine.PROPERTY_NAME.upper()} — DYNAMIC PRICING REPORT")
    print(f"  {engine.PROPERTY_ADDRESS}")
    print(f"  Report Date: {report_date.strftime('%A, %B %d, %Y')}  |  "
          f"Generated: {datetime.utcnow().strftime('%H:%M UTC')}")
    print(sep)

    # ── Conditions panel ──────────────────────────────────────────────────
    occ         = df["occupancy_rate"].iloc[0]
    season_idx  = df["seasonal_index"].iloc[0]
    event_mult  = df["event_multiplier"].iloc[0]
    active_evts = df["active_events"].iloc[0]

    occ_status = (
        "ABOVE TARGET" if occ > engine.OCC_TARGET_HIGH else
        "IN TARGET BAND" if occ >= engine.OCC_TARGET_LOW else
        "BELOW TARGET — discounting active"
    )

    print(f"\n  TODAY'S CONDITIONS")
    print(f"  {'Estimated Occupancy:':<28} {occ:.0%}  ({occ_status})")
    print(f"  {'Target Band:':<28} {engine.OCC_TARGET_LOW:.0%} – {engine.OCC_TARGET_HIGH:.0%}")
    print(f"  {'Seasonal Index:':<28} {season_idx:.2f}  ({report_date.strftime('%B')} demand)")
    if active_evts:
        print(f"  {'Active Events:':<28} {active_evts}")
        print(f"  {'Event Multiplier:':<28} ×{event_mult:.2f}")
    else:
        print(f"  {'Active Events:':<28} None")

    # ── Rate table ────────────────────────────────────────────────────────
    print(f"\n  RECOMMENDED RATES — ALL 14 ROOMS")
    print(thin)
    hdr = (
        f"  {'Room':<14} {'Tier':<12} {'Rate':>6}  "
        f"{'Rack':>10}  {'vs Rack':>8}  {'vs Comp':>8}  {'Action':<10}"
    )
    print(hdr)
    print(thin)

    tier_order = {"cottage": 0, "waterfront": 1, "water_view": 2, "garden": 3}
    sorted_df  = df.sort_values("tier", key=lambda s: s.map(tier_order))

    for _, row in sorted_df.iterrows():
        rack_range = f"${row['rack_low']:.0f}–${row['rack_high']:.0f}"
        vs_rack    = f"{row['rate_vs_rack_pct']:+.1f}%"
        vs_comp    = f"{row['rate_vs_comp_pct']:+.1f}%"
        rate_val   = float(row["rate"])
        rack_mid   = float(row["rack_mid"])
        action     = (
            "PREMIUM" if rate_val > rack_mid * 1.10 else
            "HOLD"    if rate_val >= rack_mid * 0.98 else
            "DISCOUNT"
        )
        print(
            f"  {row['room_id']:<14} {row['tier']:<12} ${rate_val:>5.0f}  "
            f"{rack_range:>10}  {vs_rack:>8}  {vs_comp:>8}  {action:<10}"
        )

    print(thin)

    # ── Competitor panel ──────────────────────────────────────────────────
    comp_cols = [c for c in df.columns if c in {c.name for c in COMPETITORS.values()}]
    if not comp_cols:
        # Fallback: use competitor_avg
        pass

    print(f"\n  COMPETITOR BENCHMARKS  (estimated — integrate OTA Insight for live rates)")
    print(thin)
    comp_rates = engine.get_competitor_rates(report_date)
    for name, rate_c in sorted(comp_rates.items(), key=lambda x: -x[1]):
        print(f"  {'  ' + name:<40} ${rate_c:.0f}")

    comp_avg = sum(comp_rates.values()) / len(comp_rates)
    our_avg  = df["rate"].mean()
    print(thin)
    print(f"  {'Competitor Average:':<40} ${comp_avg:.0f}")
    print(f"  {'Bay Street Inn Average (recommended):':<40} ${our_avg:.0f}")
    print(f"  {'Premium over comp set:':<40} {(our_avg - comp_avg) / comp_avg * 100:+.1f}%")

    # ── Reasoning summary (top 3 rooms) ───────────────────────────────────
    print(f"\n  RATE REASONING — TOP ROOMS")
    print(thin)
    for _, row in sorted_df.head(4).iterrows():
        print(f"  {row['room_name']}: ${row['rate']:.0f}")
        for part in str(row["reasoning"]).split(" | "):
            print(f"    • {part}")

    print(f"\n{sep}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry point:  python -m modules.hospitality.anchorage_pricing --report
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="anchorage_pricing",
        description="Bay Street Inn — Dynamic Pricing Engine",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print today's full pricing report for all 14 rooms (default action)",
    )
    parser.add_argument(
        "--calendar",
        action="store_true",
        help="Generate and export the N-day pricing calendar CSV",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        metavar="N",
        help="Days ahead for --calendar (default: 90)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Override report date (default: today)",
    )
    parser.add_argument(
        "--occupancy",
        type=float,
        default=0.75,
        metavar="0.0-1.0",
        help="Assumed current occupancy rate (default: 0.75)",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,  # keep CLI output clean
        format="%(levelname)s | %(message)s",
    )

    args   = _parse_args()
    engine = AnchoragePricingEngine()

    # Resolve target date
    target_date: date
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"ERROR: invalid date format {args.date!r} — use YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
    else:
        target_date = date.today()

    occ = max(0.0, min(1.0, args.occupancy))

    if args.calendar:
        print(f"Generating {args.days}-day pricing calendar…", flush=True)
        cal = engine.generate_pricing_calendar(days_ahead=args.days, base_occupancy=occ)
        print(f"Exported {len(cal):,} rows  ({len(ROOM_INVENTORY)} rooms × {args.days} days)")

    # Default to report if neither flag or both
    if args.report or not args.calendar:
        df = engine.generate_daily_report(target_date=target_date, occupancy_rate=occ)
        _print_report(df, engine, target_date)


if __name__ == "__main__":
    main()
