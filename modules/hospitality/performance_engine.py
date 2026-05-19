"""Monthly ROI performance report.

Concrete-metric shape: this-month vs last-year on occupancy/RevPAR/revenue,
engine contribution counts, top 3 wins, missed opportunities, and a
subscription ROI multiple. Demo data is deterministic per tier so the
report stays consistent across reloads.
"""
from __future__ import annotations

from datetime import date
from typing import Any

SUBSCRIPTION_COST = {
    "essentials":   399,
    "professional": 699,
    "portfolio":   1199,
    "enterprise":  2400,
}


def get_report(property_config: dict[str, Any] | None = None, tier: str = "professional") -> dict[str, Any]:
    today = date.today()
    period = today.strftime("%B %Y")
    subscription_cost = SUBSCRIPTION_COST.get(tier, 699)

    # Scale demo numbers slightly per tier so each demo account sees consistent figures
    scale = {"essentials": 0.65, "professional": 1.0, "portfolio": 1.5, "enterprise": 2.4}.get(tier, 1.0)

    occupancy_this_month = round(92.1, 1)
    occupancy_last_year  = round(87.3, 1)
    revpar_this_month    = round(409 * scale)
    revpar_last_year     = round(348 * scale)
    revenue_this_month   = round(66906 * scale)
    revenue_last_year    = round(57240 * scale)

    revenue_change = revenue_this_month - revenue_last_year
    occupancy_change_pct = round(occupancy_this_month - occupancy_last_year, 1)
    revpar_change_pct = round((revpar_this_month - revpar_last_year) / revpar_last_year * 100, 1) if revpar_last_year else 0.0

    # Engine contribution counts — scale with tier
    rates_recommended = round(360 * scale)
    rates_approved    = round(312 * scale)
    rates_auto        = round(48  * scale)
    approval_rate_pct = round(rates_approved / rates_recommended * 100) if rates_recommended else 0
    estimated_revenue_lift = round(4840 * scale)

    direct_pct_this_month = 38
    direct_pct_last_month = 33
    commission_saved      = round(1240 * scale)

    top_wins = [
        {
            "date":              "Jul 20",
            "event":             "Water Festival",
            "rate_recommended":  round(535 * scale),
            "rate_prior_year":   round(378 * scale),
            "lift_per_night":    round(157 * scale),
            "room":              "Waterfront Suite",
        },
        {
            "date":              "May 23",
            "event":             "Memorial Day Weekend",
            "rate_recommended":  round(495 * scale),
            "rate_prior_year":   round(378 * scale),
            "lift_per_night":    round(117 * scale),
            "room":              "Waterfront Suite",
        },
        {
            "date":              "Jun 5",
            "event":             "First Friday Art Walk",
            "rate_recommended":  round(450 * scale),
            "rate_prior_year":   round(378 * scale),
            "lift_per_night":    round(72  * scale),
            "room":              "Multiple rooms",
        },
    ]

    missed_opportunities = [
        {
            "date":                      "Jun 14-15",
            "reason":                    "Rate recommendation not approved in time",
            "estimated_missed_revenue":  round(340 * scale),
        },
    ]

    total_value = estimated_revenue_lift + commission_saved
    roi_multiple = round(total_value / subscription_cost, 1) if subscription_cost else 0.0
    roi_pct      = round((total_value - subscription_cost) / subscription_cost * 100) if subscription_cost else 0

    return {
        "period":             period,
        "subscription_cost":  subscription_cost,
        "tier":               tier,
        "metrics": {
            "occupancy_this_month":     occupancy_this_month,
            "occupancy_last_year":      occupancy_last_year,
            "occupancy_change_pct":     occupancy_change_pct,
            "revpar_this_month":        revpar_this_month,
            "revpar_last_year":         revpar_last_year,
            "revpar_change_pct":        revpar_change_pct,
            "total_revenue_this_month": revenue_this_month,
            "total_revenue_last_year":  revenue_last_year,
            "revenue_change":           revenue_change,
        },
        "engine_contribution": {
            "rates_recommended":      rates_recommended,
            "rates_approved":         rates_approved,
            "rates_auto_published":   rates_auto,
            "approval_rate_pct":      approval_rate_pct,
            "estimated_revenue_lift": estimated_revenue_lift,
        },
        "direct_booking": {
            "direct_pct_this_month":  direct_pct_this_month,
            "direct_pct_last_month":  direct_pct_last_month,
            "commission_saved":       commission_saved,
        },
        "top_wins":             top_wins,
        "missed_opportunities": missed_opportunities,
        "subscription_roi": {
            "engine_revenue_contribution": estimated_revenue_lift,
            "direct_booking_savings":      commission_saved,
            "total_value":                 total_value,
            "subscription_cost":           subscription_cost,
            "roi_multiple":                roi_multiple,
            "roi_pct":                     roi_pct,
        },
    }
