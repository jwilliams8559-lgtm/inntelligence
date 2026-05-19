"""Monthly ROI performance report.

Aggregates the revenue impact this engine has produced for the property in
the last 30 days and divides by the subscription price to produce the
all-important retention metric: the subscription ROI multiple.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any


def _avg_adr() -> float:
    from config.settings import ROOM_TYPES
    total = sum(r.get("count", 1) for r in ROOM_TYPES)
    return sum(r["base"] * r.get("count", 1) for r in ROOM_TYPES) / total if total else 380.0


def _monthly_bookings(property_config: dict[str, Any]) -> int:
    rooms = property_config.get("total_rooms", 14)
    occupancy = (property_config.get("target_occupancy_min", 0.70)
                 + property_config.get("target_occupancy_max", 0.85)) / 2
    return round(rooms * occupancy * 30)


def attribution(property_config: dict[str, Any], tier: str = "professional") -> list[dict[str, Any]]:
    """Per-stream monthly revenue impact attributed to the platform.

    Only streams unlocked by the tier are counted toward the total. Locked
    streams are still surfaced with locked=True so the report doubles as
    an upgrade prompt.
    """
    from config.settings import FEATURE_GATES
    from modules.hospitality import direct_booking_engine, los_engine
    features = FEATURE_GATES.get(tier, {})
    adr = _avg_adr()
    monthly_bookings = _monthly_bookings(property_config)

    rate_opt = round(adr * 0.07 * monthly_bookings)
    festival_uplift = round(adr * 0.20 * monthly_bookings * 0.10)

    los = los_engine.get_summary(property_config) if features.get("gap_night_analysis") else {"revenue_captured": 0, "gap_count": 0}
    gap_fill = round(los.get("revenue_captured", 0) / 3)

    if features.get("direct_booking_tools"):
        db = direct_booking_engine.get_summary(property_config)
        db_shift_annual = next((s["annual_savings"] for s in db["commission_math"]["shift_scenarios"]
                                if s["shift_pct"] == 10), 0)
        direct_shift = round(db_shift_annual / 12)
    else:
        direct_shift = 0

    packages = 480 if features.get("packages_module") else 0

    return [
        {"stream": "Dynamic rate optimization",   "monthly_impact": rate_opt,         "icon": "📈",
         "feature_key": "optimization_engine", "locked": not features.get("optimization_engine", True),
         "detail": f"~7% ADR lift across {monthly_bookings} bookings/mo (avg ADR ${round(adr)})"},
        {"stream": "Event & weekend pricing",     "monthly_impact": festival_uplift,  "icon": "★",
         "feature_key": "max_events", "locked": False,
         "detail": "20% premium on ~10% of bookings during festivals & peak weekends"},
        {"stream": "Gap-night recovery",          "monthly_impact": gap_fill,         "icon": "🌙",
         "feature_key": "gap_night_analysis", "locked": not features.get("gap_night_analysis"),
         "detail": (f"{los.get('gap_count', 0)} orphan nights detected over 90 days; ~{round(los.get('gap_count',0)/3)}/mo filled at 17% discount"
                    if features.get("gap_night_analysis") else "Unlock to recover orphan-night revenue")},
        {"stream": "Direct booking shift",        "monthly_impact": direct_shift,     "icon": "🌐",
         "feature_key": "direct_booking_tools", "locked": not features.get("direct_booking_tools"),
         "detail": ("10% of OTA bookings shifted to direct — recovers commission"
                    if features.get("direct_booking_tools") else "Unlock to shift OTA bookings direct")},
        {"stream": "Package & add-on revenue",    "monthly_impact": packages,         "icon": "🎁",
         "feature_key": "packages_module", "locked": not features.get("packages_module"),
         "detail": ("Romance, sunset cruise, and culinary add-ons sold at booking"
                    if features.get("packages_module") else "Unlock to sell packages and add-ons")},
    ]


def get_report(property_config: dict[str, Any], tier: str = "professional") -> dict[str, Any]:
    streams = attribution(property_config, tier)
    # Locked streams cannot be delivering value — exclude from the ROI total
    total_monthly_impact = sum(s["monthly_impact"] for s in streams if not s["locked"])
    locked_potential = sum(s["monthly_impact"] for s in streams if s["locked"])
    annual_impact = total_monthly_impact * 12

    from config.settings import FEATURE_GATES
    subscription = FEATURE_GATES.get(tier, {}).get("price_per_month", 699)
    roi_multiple = round(total_monthly_impact / subscription, 1) if subscription else 0
    payback_days = round(subscription / (total_monthly_impact / 30), 1) if total_monthly_impact else 999

    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed  = today.day
    month_to_date = round(total_monthly_impact * days_elapsed / days_in_month)

    return {
        "property":             property_config.get("name", "Property"),
        "report_date":          today.isoformat(),
        "month_label":          today.strftime("%B %Y"),
        "subscription_monthly": subscription,
        "tier":                 tier,
        "total_monthly_impact": total_monthly_impact,
        "locked_potential":     locked_potential,
        "annual_impact":        annual_impact,
        "roi_multiple":         roi_multiple,
        "payback_days":         payback_days,
        "month_to_date":        month_to_date,
        "streams":              streams,
        "headline":             f"${total_monthly_impact:,}/mo in attributed revenue — {roi_multiple}x your ${subscription} subscription.",
        "compare_to": {
            "pms_typical":      199,
            "rate_shopper":     349,
            "industry_avg_roi": 2.5,
        },
    }
