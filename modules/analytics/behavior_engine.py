"""Guest behavior tracking — booking sources, cancellations, price sensitivity.

Three modules driven by the same demand_engine + tenant config so the
output reflects the demo property. In production, the source data comes
from the PMS booking feed and the rate-publish audit log; here we use
deterministic synthetic data so the dashboards are demo-stable.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


_BOOKING_SOURCES_DEMO = {
    "Booking.com": {"bookings": 31, "revenue": 14880, "commission_pct": 15},
    "Direct":      {"bookings": 28, "revenue": 14560, "commission_pct": 0},
    "Expedia":     {"bookings": 18, "revenue": 8280,  "commission_pct": 18},
    "Airbnb":      {"bookings": 12, "revenue": 5040,  "commission_pct": 3},
    "VRBO":        {"bookings": 6,  "revenue": 2940,  "commission_pct": 5},
    "Phone/Email": {"bookings": 5,  "revenue": 2400,  "commission_pct": 0},
    "Hotels.com":  {"bookings": 4,  "revenue": 1680,  "commission_pct": 18},
    "Agoda":       {"bookings": 2,  "revenue": 840,   "commission_pct": 15},
}


class BehaviorEngine:

    # ── Booking sources ────────────────────────────────────────────

    def booking_source_breakdown(self, tenant_id: str, days: int = 30) -> dict[str, Any]:
        sources = {name: dict(data) for name, data in _BOOKING_SOURCES_DEMO.items()}
        total_bookings   = sum(s["bookings"] for s in sources.values())
        total_revenue    = sum(s["revenue"]  for s in sources.values())
        total_commission = sum(s["revenue"] * s["commission_pct"] / 100 for s in sources.values())

        for data in sources.values():
            data["pct_bookings"]    = round(data["bookings"] / total_bookings * 100, 1)
            data["pct_revenue"]     = round(data["revenue"]  / total_revenue  * 100, 1)
            data["commission_cost"] = round(data["revenue"] * data["commission_pct"] / 100)
            data["net_revenue"]     = data["revenue"] - data["commission_cost"]

        direct_pct = sources["Direct"]["pct_bookings"]
        booking_com_rev = sources["Booking.com"]["revenue"]
        booking_com_bk  = sources["Booking.com"]["bookings"]
        shift_savings   = int(booking_com_rev * 0.15 / max(booking_com_bk, 1) * 10)
        shift_revenue   = 48 * 10  # rough net revenue per direct shift

        return {
            "period_days":           days,
            "total_bookings":        total_bookings,
            "total_revenue":         total_revenue,
            "total_commission_paid": round(total_commission),
            "direct_booking_pct":    direct_pct,
            "sources":               sources,
            "insight": {
                "headline":   f"You are paying ${int(total_commission):,} in OTA commissions this month",
                "opportunity": (
                    f"If you shifted 10 more bookings to direct (from Booking.com), "
                    f"you would save ${shift_savings:,} in commissions and net "
                    f"${shift_revenue:,} more in revenue."
                ),
                "direct_vs_industry": (
                    "Your direct booking rate is "
                    + ("above" if direct_pct > 25 else "below")
                    + " the boutique inn average of 25%."
                ),
            },
        }

    # ── Cancellations ──────────────────────────────────────────────

    def cancellation_analysis(self, tenant_id: str, days: int = 90) -> dict[str, Any]:
        cancellations = [
            {"date": "2026-04-12", "room": "Waterfront Suite",   "booked_rate": 378, "nights": 2,
             "lead_time_days": 45, "days_before_checkin": 22, "source": "Booking.com",
             "demand_score_at_cancel": 62, "reason": "Policy change"},
            {"date": "2026-04-18", "room": "Water View Suite",   "booked_rate": 295, "nights": 1,
             "lead_time_days": 12, "days_before_checkin": 8,  "source": "Expedia",
             "demand_score_at_cancel": 44, "reason": "Guest plans changed"},
            {"date": "2026-04-28", "room": "Garden View Room",   "booked_rate": 265, "nights": 3,
             "lead_time_days": 30, "days_before_checkin": 15, "source": "Direct",
             "demand_score_at_cancel": 71, "reason": "Weather concern"},
            {"date": "2026-05-03", "room": "Waterfront Suite",   "booked_rate": 420, "nights": 2,
             "lead_time_days": 8,  "days_before_checkin": 5,  "source": "Booking.com",
             "demand_score_at_cancel": 78, "reason": "Rate found cheaper"},
            {"date": "2026-05-10", "room": "Private Cottage",    "booked_rate": 489, "nights": 4,
             "lead_time_days": 60, "days_before_checkin": 38, "source": "Direct",
             "demand_score_at_cancel": 55, "reason": "Family emergency"},
        ]
        total_lost = sum(c["booked_rate"] * c["nights"] for c in cancellations)
        avg_before = sum(c["days_before_checkin"] for c in cancellations) / len(cancellations)

        by_source: dict[str, int] = defaultdict(int)
        for c in cancellations: by_source[c["source"]] += 1

        windows = {"0-7 days": 0, "8-14 days": 0, "15-30 days": 0, "30+ days": 0}
        for c in cancellations:
            d = c["days_before_checkin"]
            if   d <= 7:  windows["0-7 days"]   += 1
            elif d <= 14: windows["8-14 days"]  += 1
            elif d <= 30: windows["15-30 days"] += 1
            else:         windows["30+ days"]   += 1

        return {
            "period_days":             days,
            "total_cancellations":     len(cancellations),
            "total_lost_revenue":      total_lost,
            "avg_days_before_checkin": round(avg_before, 1),
            "cancellation_rate_pct":   7.3,
            "by_source":               dict(by_source),
            "by_window":               windows,
            "cancellations":           cancellations,
            "insight": {
                "headline":      f"{len(cancellations)} cancellations costing ${total_lost:,} in {days} days",
                "recommendation": (
                    f"Most cancellations happen {int(avg_before)} days before check-in. "
                    "Consider a stricter non-refundable rate (10% discount) for bookings "
                    "more than 30 days out — it reduces cancellation risk significantly."
                ),
                "high_demand_cancellations": sum(1 for c in cancellations if c["demand_score_at_cancel"] >= 70),
            },
        }

    # ── Price sensitivity ──────────────────────────────────────────

    def price_sensitivity_analysis(self, tenant_id: str) -> dict[str, Any]:
        events = [
            {
                "date": "2026-04-10", "room": "Waterfront Suite",
                "rate_change": "+$42 (15% increase)",
                "rate_before": 278, "rate_after": 320,
                "bookings_7d_before": 3, "bookings_7d_after": 4,
                "pace_change_pct": +33,
                "interpretation":  "Rate increase absorbed — demand was inelastic at this level",
                "recommendation":  "Room can support further rate increases",
            },
            {
                "date": "2026-04-22", "room": "Garden View Room",
                "rate_change": "+$25 (10% increase)",
                "rate_before": 245, "rate_after": 270,
                "bookings_7d_before": 5, "bookings_7d_after": 3,
                "pace_change_pct": -40,
                "interpretation":  "Booking pace dropped after rate increase — demand elastic",
                "recommendation":  "Consider reverting to $255-265 range for this room type",
            },
            {
                "date": "2026-05-01", "room": "Waterfront Suite",
                "rate_change": "+$157 (Water Festival premium applied)",
                "rate_before": 378, "rate_after": 535,
                "bookings_7d_before": 2, "bookings_7d_after": 6,
                "pace_change_pct": +200,
                "interpretation":  "Festival premium drove accelerated bookings — demand highly inelastic",
                "recommendation":  "Apply festival premium earlier next year (90 days out vs 14 days)",
            },
        ]
        elastic   = sum(1 for e in events if e["pace_change_pct"] < 0)
        inelastic = sum(1 for e in events if e["pace_change_pct"] >= 0)
        return {
            "total_events_tracked": len(events),
            "elastic_responses":    elastic,
            "inelastic_responses":  inelastic,
            "sensitivity_summary": (
                "Demand is generally inelastic for Waterfront Suite — rate increases do not reduce bookings. "
                "Garden View shows higher price sensitivity — increases above $265 slow booking pace."
            ),
            "events": events,
            "insight": {
                "headline":              "Price sensitivity varies significantly by room type",
                "waterfront_elasticity": "Inelastic — raise rates confidently",
                "garden_elasticity":     "Elastic — stay near $255-265 floor",
                "festival_elasticity":   "Highly inelastic — apply premium earlier",
            },
        }

    def combined_behavior_report(self, tenant_id: str) -> dict[str, Any]:
        return {
            "booking_sources":   self.booking_source_breakdown(tenant_id),
            "cancellations":     self.cancellation_analysis(tenant_id),
            "price_sensitivity": self.price_sensitivity_analysis(tenant_id),
            "generated_at":      datetime.now().isoformat(),
        }
