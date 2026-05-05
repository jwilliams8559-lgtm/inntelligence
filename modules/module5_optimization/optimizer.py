"""
modules/module5_optimization/optimizer.py

Revenue optimization engine for Anchorage 1770 Inn.

Inputs: Module 4 predictions + 90-day pricing calendar
Outputs: Ranked list of revenue-positive actions including:
  - Midweek specials (3 nights for price of 2) when occupancy < 70%
  - Package bundle recommendations (Romance, Anniversary, Adventure)
  - Revenue impact projections for each action vs doing nothing
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import TenantConfig

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Package definitions
# ─────────────────────────────────────────────────────────────────────────────

PACKAGES: Dict[str, Dict[str, Any]] = {
    "romance": {
        "name": "Romance Package",
        "tagline": "Room · Dinner for Two · Bottle of Wine",
        "description": (
            "Curated romantic experience: premium room, in-room dining for two, "
            "and a selected South Carolina wine. Popular for anniversaries and proposals."
        ),
        "premium": 85,
        "target_tiers": {"waterfront", "cottage"},
        "best_lead_days": range(14, 90),   # book 14–90 days out
        "event_boost": True,               # package sells best around events
        "estimated_conversion": 0.28,      # 28% of eligible guests upgrade
        "emoji": "💑",
    },
    "anniversary": {
        "name": "Anniversary Package",
        "tagline": "Room · Fresh Flowers · Champagne",
        "description": (
            "In-room fresh floral arrangement from a local Beaufort florist "
            "and chilled champagne waiting on arrival."
        ),
        "premium": 65,
        "target_tiers": {"waterfront", "water_view", "cottage"},
        "best_lead_days": range(7, 60),
        "event_boost": False,
        "estimated_conversion": 0.22,
        "emoji": "🥂",
    },
    "adventure": {
        "name": "Adventure Package",
        "tagline": "Room · Kayak Rental · Lowcountry Packed Lunch",
        "description": (
            "Full-day kayak rental on the Beaufort River estuary with a "
            "packed Lowcountry lunch to enjoy on the water. Available May–October."
        ),
        "premium": 75,
        "target_tiers": {"water_view", "garden", "cottage"},
        "best_lead_days": range(7, 90),
        "event_boost": False,
        "available_months": set(range(5, 11)),  # May–October only
        "estimated_conversion": 0.18,
        "emoji": "🚣",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
#  Optimizer
# ─────────────────────────────────────────────────────────────────────────────

class PricingOptimizer:
    """
    Revenue optimization engine.

    Can be used two ways:
      1. As Module 5 in the pipeline:   optimizer.optimize(predictions)
      2. Standalone / Flask dashboard:  optimizer.analyze(calendar_df)
    """

    OCC_TRIGGER       = 0.70   # midweek special triggers below this
    OCC_CRISIS        = 0.65   # deep-discount floor trigger
    MIDWEEK_DAYS      = {6, 0, 1, 2, 3}   # Sun(6), Mon(0), Tue(1), Wed(2), Thu(3)
    LOOKAHEAD_DAYS    = 14     # window for midweek special detection
    MIN_SPECIAL_NIGHTS = 3

    def __init__(self) -> None:
        # Import here to avoid circular at module level
        from modules.hospitality.anchorage_pricing import AnchoragePricingEngine
        self._engine = AnchoragePricingEngine()

    # ------------------------------------------------------------------ #
    #  Pipeline entry point                                                #
    # ------------------------------------------------------------------ #

    def optimize(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Module 5 pipeline entry point.
        Wraps analyze() and attaches ML metrics from Module 4.
        """
        logger.info("Module 5: running optimization analysis")
        cal_df = self._engine.generate_pricing_calendar(days_ahead=90)
        result  = self.analyze(cal_df)
        result["ml_metrics"]   = predictions.get("metrics", {})
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"Optimization complete — "
            f"{result['total_midweek_windows']} midweek windows, "
            f"{result['total_package_opportunities']} package opportunities, "
            f"${result['estimated_total_uplift']:,.0f} estimated uplift"
        )
        return result

    # ------------------------------------------------------------------ #
    #  Core analysis                                                       #
    # ------------------------------------------------------------------ #

    def analyze(
        self,
        calendar_df: Optional[pd.DataFrame] = None,
        occupancy_rate: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Full optimization analysis on a pricing calendar DataFrame.
        Generates calendar internally if not provided.
        """
        if calendar_df is None:
            calendar_df = self._engine.generate_pricing_calendar(
                days_ahead=90, base_occupancy=occupancy_rate
            )

        midweek_specials = self._find_midweek_specials(calendar_df, occupancy_rate)
        packages         = self._find_package_opportunities(calendar_df)

        all_actions: List[Dict[str, Any]] = []
        for s in midweek_specials:
            all_actions.append({"type": "midweek_special", **s})
        for p in packages:
            all_actions.append({"type": "package", **p})

        all_actions.sort(key=lambda x: x.get("revenue_impact", 0), reverse=True)

        total_uplift = sum(
            a.get("revenue_impact", 0) for a in all_actions[:15]
        )

        return {
            "midweek_specials":           midweek_specials,
            "packages":                   packages,
            "ranked_actions":             all_actions[:20],
            "total_midweek_windows":      len(midweek_specials),
            "total_package_opportunities":len(packages),
            "estimated_total_uplift":     round(total_uplift, 2),
        }

    # ------------------------------------------------------------------ #
    #  Midweek special detection                                           #
    # ------------------------------------------------------------------ #

    def _find_midweek_specials(
        self, cal_df: pd.DataFrame, occupancy_rate: float
    ) -> List[Dict[str, Any]]:
        """
        Identifies Sun–Thu windows in the next 14 days where occupancy is
        projected below 70% and a 3-for-2 special would generate positive revenue.

        Strategy: 3 nights for price of 2 (33% effective discount).
        Logic: an empty room earns $0 — any booking at 2/3 rate is net positive.
        """
        today = date.today()
        cutoff = today + timedelta(days=self.LOOKAHEAD_DAYS)
        specials: List[Dict[str, Any]] = []

        # Filter to next 14 days, midweek check-ins
        window_df = cal_df[
            (pd.to_datetime(cal_df["date"]).dt.date >= today)
            & (pd.to_datetime(cal_df["date"]).dt.date <= cutoff)
        ].copy()

        if window_df.empty:
            return specials

        window_df["_date"] = pd.to_datetime(window_df["date"]).dt.date
        window_df["_weekday"] = pd.to_datetime(window_df["date"]).dt.weekday

        # Only trigger if occupancy assumption is below target
        if occupancy_rate >= self.OCC_TRIGGER:
            occ_gap = self.OCC_TRIGGER - occupancy_rate
            # Still show specials if we're within 5% of trigger
            if occ_gap < -0.05:
                logger.debug(
                    f"Occupancy {occupancy_rate:.0%} comfortably above target — "
                    "midweek specials not triggered"
                )
                return specials

        # Find consecutive midweek runs (≥ 3 nights) for each tier
        for tier in ["garden", "water_view", "waterfront", "cottage"]:
            tier_df = window_df[window_df["tier"] == tier].copy()
            tier_df = tier_df.sort_values("_date")

            # Group consecutive midweek dates
            midweek_dates = [
                d for d in tier_df["_date"].unique()
                if d.weekday() in self.MIDWEEK_DAYS
            ]

            # Build consecutive runs of ≥ 3 nights
            runs = self._consecutive_runs(midweek_dates, min_len=self.MIN_SPECIAL_NIGHTS)

            for run in runs:
                run_df = tier_df[tier_df["_date"].isin(run)]
                avg_rate = run_df["recommended_rate"].mean()
                rooms_in_tier = run_df["room_id"].nunique()

                # Revenue math
                normal_3n_rev   = avg_rate * 3 * occupancy_rate
                special_2n_rate = round(avg_rate / 5) * 5  # same nightly rate
                special_total   = special_2n_rate * 2       # 2 nights charged
                # Assume special converts 60% of otherwise-empty bookings
                # P(booking without special) ≈ occupancy_rate - 0.30 buffer
                baseline_rev    = avg_rate * 3 * max(occupancy_rate - 0.30, 0)
                revenue_impact  = round((special_total - baseline_rev) * rooms_in_tier, 2)

                start_d, end_d = run[0], run[-1]
                specials.append({
                    "date_start":        start_d.isoformat(),
                    "date_end":          end_d.isoformat(),
                    "date_range":        (
                        f"{start_d.strftime('%b %d')}–{end_d.strftime('%b %d')} "
                        f"({start_d.strftime('%a')}–{end_d.strftime('%a')})"
                    ),
                    "nights":            len(run),
                    "tier":              tier,
                    "rooms_affected":    rooms_in_tier,
                    "avg_nightly_rate":  round(avg_rate, 2),
                    "special_total_charged": special_total,
                    "guest_savings":     round(avg_rate * 3 - special_total, 2),
                    "revenue_impact":    revenue_impact,
                    "trigger":           f"Occ {occupancy_rate:.0%} ≤ {self.OCC_TRIGGER:.0%} target",
                    "action":            (
                        f"Activate 3-for-2 midweek special — "
                        f"${special_total:.0f} for 3 nights "
                        f"(save ${avg_rate:.0f})"
                    ),
                })

        specials.sort(key=lambda x: x["revenue_impact"], reverse=True)
        return specials

    @staticmethod
    def _consecutive_runs(dates: List[date], min_len: int = 3) -> List[List[date]]:
        """Group sorted dates into consecutive runs of at least min_len."""
        if not dates:
            return []
        runs: List[List[date]] = []
        current = [dates[0]]
        for d in dates[1:]:
            if (d - current[-1]).days == 1:
                current.append(d)
            else:
                if len(current) >= min_len:
                    runs.append(current)
                current = [d]
        if len(current) >= min_len:
            runs.append(current)
        return runs

    # ------------------------------------------------------------------ #
    #  Package opportunity detection                                       #
    # ------------------------------------------------------------------ #

    def _find_package_opportunities(
        self, cal_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Recommends packages for dates/tiers where demand conditions
        indicate guests are seeking enhanced experiences:
          - Event dates → Romance / Anniversary
          - Weekend arrivals → Romance
          - May–Oct + any date → Adventure
        """
        today = date.today()
        opportunities: List[Dict[str, Any]] = []

        cal_df = cal_df.copy()
        cal_df["_date"] = pd.to_datetime(cal_df["date"]).dt.date
        cal_df["_month"] = pd.to_datetime(cal_df["date"]).dt.month
        cal_df["_weekday"] = pd.to_datetime(cal_df["date"]).dt.weekday
        cal_df["_days_out"] = (cal_df["_date"] - today).apply(lambda x: x.days)

        for pkg_id, pkg in PACKAGES.items():
            # Filter to target tiers
            pkg_df = cal_df[cal_df["tier"].isin(pkg["target_tiers"])].copy()

            # Lead time filter
            lead_range = pkg["best_lead_days"]
            pkg_df = pkg_df[
                pkg_df["_days_out"].between(lead_range.start, lead_range.stop)
            ]

            # Seasonal availability
            if "available_months" in pkg:
                pkg_df = pkg_df[pkg_df["_month"].isin(pkg["available_months"])]

            if pkg_df.empty:
                continue

            # Score each date: event multiplier + weekend boost
            pkg_df["_score"] = (
                (pkg_df["event_multiplier"] - 1.0) * 3.0
                + pkg_df["is_weekend"].astype(float) * 0.5
                + (pkg_df["recommended_rate"] / pkg_df["rack_high"]) * 0.5
            )

            # Take top 5 unique date windows
            top_dates = (
                pkg_df.sort_values("_score", ascending=False)
                .drop_duplicates("date")
                .head(5)
            )

            for _, row in top_dates.iterrows():
                base_rate     = float(row["recommended_rate"])
                package_rate  = base_rate + pkg["premium"]
                conversion    = pkg["estimated_conversion"]
                revenue_per_booking = pkg["premium"]
                rooms_eligible = len(
                    cal_df[
                        (cal_df["date"] == row["date"])
                        & (cal_df["tier"].isin(pkg["target_tiers"]))
                    ]
                )
                expected_revenue = round(
                    revenue_per_booking * conversion * rooms_eligible, 2
                )

                reason_parts = []
                if float(row["event_multiplier"]) > 1.0:
                    reason_parts.append(f"event demand ×{row['event_multiplier']:.2f}")
                if row["is_weekend"]:
                    reason_parts.append("weekend arrival")
                if row["_score"] > 1.0:
                    reason_parts.append("high rate environment")

                opportunities.append({
                    "package_id":         pkg_id,
                    "package_name":       pkg["name"],
                    "emoji":              pkg["emoji"],
                    "tagline":            pkg["tagline"],
                    "description":        pkg["description"],
                    "premium":            pkg["premium"],
                    "date":               row["date"],
                    "day_of_week":        row["day_of_week"],
                    "days_out":           int(row["_days_out"]),
                    "target_tiers":       list(pkg["target_tiers"]),
                    "rooms_eligible":     rooms_eligible,
                    "base_rate_example":  base_rate,
                    "package_rate":       package_rate,
                    "active_events":      row["active_events"],
                    "revenue_impact":     expected_revenue,
                    "conversion_rate":    conversion,
                    "reason":             "; ".join(reason_parts) or "standard opportunity",
                    "action": (
                        f"Offer {pkg['name']} at ${package_rate:.0f} "
                        f"(+${pkg['premium']} over ${base_rate:.0f} base)"
                    ),
                })

        opportunities.sort(key=lambda x: x["revenue_impact"], reverse=True)
        return opportunities[:20]
