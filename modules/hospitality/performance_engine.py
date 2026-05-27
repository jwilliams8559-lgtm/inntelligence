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
    "starter":      399,
    "professional": 699,
    "enterprise":  1200,
    "premium":     2400,
}


def _canonical_rate_for(date_str: str, room_name: str) -> int | None:
    """Look up the DB-canonical recommended_rate for the demo property on
    a given date + room name. Used so top_wins reflect what the customer
    actually sees on the Rate Calendar — not hardcoded demo numbers.
    Returns None if the rec doesn't exist."""
    import os
    import requests
    from datetime import date as _date, datetime as _dt
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (sb_url and sb_key):
        return None
    # Parse "Jul 20" → date object using the current year
    today = _date.today()
    for year in (today.year, today.year + 1):
        try:
            d = _dt.strptime(f"{date_str} {year}", "%b %d %Y").date()
        except ValueError:
            continue
        if d >= today:
            target_date = d
            break
    else:
        return None
    h = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}"}
    try:
        props = requests.get(
            f"{sb_url}/rest/v1/properties",
            params={"select": "id", "limit": 1,
                    "tenant_id": f"in.({_demo_tenant_id_csv(sb_url, sb_key)})"},
            headers=h, timeout=10,
        ).json()
        if not props:
            return None
        pid = props[0]["id"]
        rts = requests.get(
            f"{sb_url}/rest/v1/room_types",
            params={"property_id": f"eq.{pid}",
                    "name":        f"eq.{room_name}",
                    "select":      "id", "limit": 1},
            headers=h, timeout=10,
        ).json()
        if not rts:
            return None
        rt_id = rts[0]["id"]
        recs = requests.get(
            f"{sb_url}/rest/v1/rate_recommendations",
            params={"property_id":  f"eq.{pid}",
                    "room_type_id": f"eq.{rt_id}",
                    "target_date":  f"eq.{target_date.isoformat()}",
                    "select":       "recommended_rate", "limit": 1},
            headers=h, timeout=10,
        ).json()
        if recs and recs[0].get("recommended_rate") is not None:
            return int(recs[0]["recommended_rate"])
    except requests.RequestException:
        pass
    return None


def _demo_tenant_id_csv(sb_url: str, sb_key: str) -> str:
    """Resolve the demo tenant id once per call."""
    import os
    import requests
    slug = os.environ.get("TGC_DEMO_TENANT_SLUG", "bay-street-inn-demo")
    try:
        rows = requests.get(
            f"{sb_url}/rest/v1/tenants",
            params={"slug": f"eq.{slug}", "select": "id"},
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
            timeout=10,
        ).json()
        return ",".join(r["id"] for r in rows) or "00000000-0000-0000-0000-000000000000"
    except requests.RequestException:
        return "00000000-0000-0000-0000-000000000000"


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
    # Monthly revenue lift — matches the Product Tour math (15% lift on a typical
    # boutique inn ≈ $1,244/mo) so the dashboard ROI and the Tour tell one story.
    estimated_revenue_lift = round(1244 * scale)

    direct_pct_this_month = 38
    direct_pct_last_month = 33
    commission_saved      = round(1240 * scale)

    # Top wins — SINGLE SOURCE OF TRUTH. Each win cites a specific (date,
    # room) pair and MUST report the rate the customer would see on the
    # Rate Calendar for that same cell. Hardcoded numbers here previously
    # diverged from rate_recommendations and broke the integrity check.
    _wins_spec = [
        ("Jul 20", "Water Festival",          "Waterfront Suite", 378),
        ("May 23", "Memorial Day Weekend",    "Waterfront Suite", 378),
        ("Jun 5",  "First Friday Art Walk",   "Waterfront Suite", 378),
    ]
    top_wins = []
    for date_str, event, room, prior_year in _wins_spec:
        recommended = _canonical_rate_for(date_str, room)
        if recommended is None:
            # No DB rec for this date — omit the win rather than fabricate
            continue
        top_wins.append({
            "date":              date_str,
            "event":             event,
            "rate_recommended":  recommended,
            "rate_prior_year":   round(prior_year * scale),
            "lift_per_night":    recommended - round(prior_year * scale),
            "room":              room,
        })

    missed_opportunities = [
        {
            "date":                      "Jun 14-15",
            "reason":                    "Rate recommendation not approved in time",
            "estimated_missed_revenue":  round(340 * scale),
        },
    ]

    # Total-property ROI: the return is across ALL revenue streams, not room
    # rates alone. Conservative annual figures for a 19-room waterfront inn.
    total_value = estimated_revenue_lift
    roi_breakdown = {
        "room_revenue_lift":        60000,
        "direct_booking_savings":    7000,
        "crm_repeat_bookings":       7500,
        "package_optimization":      4000,
        "gift_shop_fb_improvement": 15000,
    }
    total_annual_lift   = sum(roi_breakdown.values())          # 93,500
    annual_subscription = subscription_cost * 12               # 8,388 at $699/mo
    net_annual_benefit  = total_annual_lift - annual_subscription
    roi_multiple = round(total_annual_lift / annual_subscription, 1) if annual_subscription else 0.0
    roi_pct      = round((total_annual_lift - annual_subscription) / annual_subscription * 100) if annual_subscription else 0

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
            "roi_label":                   "11.1x total return",
            "roi_subtitle":                "Across all revenue streams",
            "total_annual_lift":           total_annual_lift,
            "annual_subscription":         annual_subscription,
            "net_annual_benefit":          net_annual_benefit,
            "breakdown":                   roi_breakdown,
        },
    }
