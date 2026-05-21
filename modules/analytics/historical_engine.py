"""Historical trend engine — 24 months of monthly KPIs + competitive history.

Deterministic synthetic series anchored to Anchorage 1770: realistic
Beaufort SC seasonal pattern, current-year ~8% above prior-year on ADR/
RevPAR, direct-booking percent improving over time. Designed so the
charts on the Historical screen look credible without a Supabase warehouse.
"""
from __future__ import annotations

import hashlib
import random
from calendar import monthrange
from datetime import date, timedelta
from typing import Any

# Multipliers indexed Jan..Dec
SEASONAL_ADR = [0.82, 0.85, 0.92, 1.05, 1.18, 1.22, 1.45, 1.38, 1.15, 1.08, 0.88, 0.90]
SEASONAL_OCC = [0.38, 0.42, 0.52, 0.65, 0.78, 0.84, 0.96, 0.88, 0.72, 0.62, 0.44, 0.50]


def _months_back(today: date, n: int) -> date:
    """Return first-of-month n months before `today`."""
    total = today.year * 12 + today.month - 1 - n
    y, mo = divmod(total, 12)
    return date(y, mo + 1, 1)


class HistoricalEngine:

    BASE_ADR = 298
    ROOMS    = 14

    def monthly_kpi_trend(self, tenant_id: str, months: int = 24) -> dict[str, Any]:
        today = date.today()
        out: list[dict[str, Any]] = []

        for i in range(months - 1, -1, -1):
            m_date = _months_back(today, i)
            mi = m_date.month - 1
            is_current_year = i < 12

            year_mult = 1.08 if is_current_year else 1.0
            adr = round(self.BASE_ADR * SEASONAL_ADR[mi] * year_mult)
            occ = round(min(SEASONAL_OCC[mi] * year_mult * 100, 100), 1)
            revpar = round(adr * occ / 100)
            days_in_month = monthrange(m_date.year, m_date.month)[1]
            revenue = round(adr * occ / 100 * self.ROOMS * days_in_month)
            direct_pct = round(22 + (4 if is_current_year else 0), 1)

            out.append({
                "month":            m_date.strftime("%b %Y"),
                "month_iso":        m_date.strftime("%Y-%m"),
                "adr":              adr,
                "occupancy":        occ,
                "revpar":           revpar,
                "revenue":          revenue,
                "direct_pct":       direct_pct,
                "is_current_year":  is_current_year,
            })

        current = [d for d in out if d["is_current_year"]]
        prior   = [d for d in out if not d["is_current_year"]]

        def _avg(rows, key): return sum(r[key] for r in rows) / max(len(rows), 1)
        cy_rev, py_rev = _avg(current, "revpar"),    _avg(prior, "revpar")
        cy_adr, py_adr = _avg(current, "adr"),       _avg(prior, "adr")
        cy_occ, py_occ = _avg(current, "occupancy"), _avg(prior, "occupancy")

        yoy_revpar = round((cy_rev - py_rev) / py_rev * 100, 1) if py_rev else 0.0
        yoy_adr    = round((cy_adr - py_adr) / py_adr * 100, 1) if py_adr else 0.0
        yoy_occ    = round(cy_occ - py_occ, 1)

        # Build paired prior-vs-current series for chart consumption
        paired = []
        for c in current:
            cm = int(c["month_iso"].split("-")[1])
            cy_year = int(c["month_iso"].split("-")[0])
            py = next((p for p in prior if int(p["month_iso"].split("-")[1]) == cm), None)
            paired.append({
                "month_label":     c["month"][:3],
                "current_adr":     c["adr"],
                "prior_adr":       py["adr"]   if py else None,
                "current_revpar":  c["revpar"],
                "prior_revpar":    py["revpar"] if py else None,
                "current_occ":     c["occupancy"],
                "prior_occ":       py["occupancy"] if py else None,
                "current_revenue": c["revenue"],
                "prior_revenue":   py["revenue"] if py else None,
                "month_order":     cy_year * 100 + cm,
            })
        paired.sort(key=lambda x: x["month_order"])

        return {
            "months_requested": months,
            "monthly_data":     out,
            "current_year":     current,
            "prior_year":       prior,
            "paired":           paired,
            "direct_pct_now":   current[-1]["direct_pct"] if current else 0,
            "direct_pct_prior": prior[-1]["direct_pct"]   if prior   else 0,
            "yoy_summary": {
                "revpar_growth_pct": yoy_revpar,
                "adr_growth_pct":    yoy_adr,
                "occ_growth_pts":    yoy_occ,
                "headline":          f"RevPAR up {yoy_revpar}% YoY · ADR up {yoy_adr}% · Occupancy +{yoy_occ} pts",
            },
        }

    def competitive_positioning_history(self, tenant_id: str, days: int = 90) -> dict[str, Any]:
        today = date.today()
        rng = random.Random(int(hashlib.md5(f"{tenant_id}-compxoxo-{days}".encode()).hexdigest()[:8], 16))
        history: list[dict[str, Any]] = []
        base_your, base_comp = 290, 275

        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            is_weekend = d.weekday() in (4, 5)
            your_adj = base_your + (45 if is_weekend else 0) + rng.randint(-15, 25)
            comp_adj = base_comp + (40 if is_weekend else 0) + rng.randint(-20, 20)
            premium  = round((your_adj - comp_adj) / comp_adj * 100, 1)
            history.append({
                "date":         d.isoformat(),
                "your_rate":    your_adj,
                "comp_avg":     comp_adj,
                "premium_pct":  premium,
                "above_market": your_adj > comp_adj,
            })

        avg_premium = sum(h["premium_pct"] for h in history) / len(history)
        days_above  = sum(1 for h in history if h["above_market"])

        insight = (
            f"You priced above the comp set average {days_above} of {days} days "
            f"({round(days_above/days*100)}%). Average premium: {round(avg_premium, 1)}%. "
            + ("Strong pricing power maintained." if avg_premium > 5
               else "Consider raising rates — demand supports a larger premium.")
        )
        return {
            "days_requested":    days,
            "history":           history,
            "avg_premium_pct":   round(avg_premium, 1),
            "days_above_market": days_above,
            "days_below_market": days - days_above,
            "insight":           insight,
        }
