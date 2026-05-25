"""F&B Yield Management Engine.

Tracks restaurant covers, bar guests, RevPASH (Revenue Per Available Seat
Hour — the F&B equivalent of RevPAR), and emits recommendations tied to
the room demand engine. Deterministic synthetic data so demos are
reproducible per (tenant, date).

This engine sits beside the legacy FBEngine (which only computes a
monthly revenue rollup) and powers the new fb_yield_module dashboard.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import Any

SERVICE_TYPES = {
    "prix_fixe":     "Prix Fixe Menu",
    "a_la_carte":    "À La Carte",
    "happy_hour":    "Happy Hour",
    "private_event": "Private Event / Buyout",
    "brunch":        "Brunch",
    "tasting":       "Wine / Tasting Menu",
}


def _seeded_rng(seed: str) -> random.Random:
    h = hashlib.md5(seed.encode()).hexdigest()
    return random.Random(int(h[:12], 16))


def _is_water_festival(d: date) -> bool:
    return date(d.year, 7, 17) <= d <= date(d.year, 7, 26)


# Demo tenant gets exact, deterministic day-of-week numbers so the F&B Yield
# screen always shows the curated figures (weekday() key: Mon=0 .. Sun=6).
DEMO_FNB_TENANT = "bay-street-inn-demo"
# The Parlor at Bay Street Inn — (covers, avg_check); revenue = covers * check.
PARLOR_DOW = {
    0: (38, 52.0), 1: (44, 54.0), 2: (51, 56.0), 3: (68, 61.0),
    4: (87, 74.0), 5: (96, 82.0), 6: (71, 65.0),
}
# The Rooftop at Bay Street Inn — open Thu–Sun; (guests, avg_spend).
ROOFTOP_DOW = {
    3: (28, 38.0), 4: (44, 52.0), 5: (51, 58.0), 6: (32, 41.0),
}

# Spec-shaped day-of-week arrays returned by /api/fnb/daily?outlet= for the demo.
RESTAURANT_DOW_SPEC = [
    {"day": "Monday",    "covers": 38, "avg_check": 52, "revenue": 1976, "occ_pct": 38},
    {"day": "Tuesday",   "covers": 44, "avg_check": 54, "revenue": 2376, "occ_pct": 44},
    {"day": "Wednesday", "covers": 51, "avg_check": 56, "revenue": 2856, "occ_pct": 51},
    {"day": "Thursday",  "covers": 68, "avg_check": 61, "revenue": 4148, "occ_pct": 68},
    {"day": "Friday",    "covers": 87, "avg_check": 74, "revenue": 6438, "occ_pct": 87},
    {"day": "Saturday",  "covers": 96, "avg_check": 82, "revenue": 7872, "occ_pct": 96},
    {"day": "Sunday",    "covers": 71, "avg_check": 65, "revenue": 4615, "occ_pct": 71},
]
ROOFTOP_DOW_SPEC = [
    {"day": "Thursday",  "guests": 28, "avg_spend": 38, "revenue": 1064, "occ_pct": 51},
    {"day": "Friday",    "guests": 44, "avg_spend": 52, "revenue": 2288, "occ_pct": 80},
    {"day": "Saturday",  "guests": 51, "avg_spend": 58, "revenue": 2958, "occ_pct": 93},
    {"day": "Sunday",    "guests": 32, "avg_spend": 41, "revenue": 1312, "occ_pct": 58},
]
SUMMARY_SPEC = {
    "monthly_revenue":     126000,
    "restaurant_monthly":  98000,
    "bar_monthly":         28000,
    "revpash":             24.50,
    "avg_check":           62.40,
    "total_monthly_covers": 2800,
}
RECOMMENDATIONS_SPEC = [
    {
        "priority": "HIGH",
        "date": "Tuesday June 2",
        "title": "Midweek Yield Gap — The Parlor at 44%",
        "action": ("Launch $38 prix fixe dinner for Tuesday-Wednesday. Partner with "
                   "local wine shop for paired selections. Promote to hotel guests "
                   "and Beaufort locals via email."),
        "revenue_lift": 920,
        "lift_label": "+$920/week",
    },
    {
        "priority": "HIGH",
        "date": "Ongoing Thu-Sun",
        "title": "Rooftop Minimum Spend — Peak Nights",
        "action": ("Apply $25 minimum spend Thursday-Saturday on The Rooftop. "
                   "Estimated impact: $18 more per guest on 44 Friday guests."),
        "revenue_lift": 2376,
        "lift_label": "+$2,376/month",
    },
    {
        "priority": "MEDIUM",
        "date": "July 17-26",
        "title": "Water Festival F&B Strategy",
        "action": ("Prix fixe dinner $85 per person Friday-Saturday. Rooftop "
                   "reservation required, $30 minimum. Add porch seating all 10 days "
                   "for dinner service weather permitting."),
        "revenue_lift": 8400,
        "lift_label": "+$8,400 over festival",
    },
    {
        "priority": "MEDIUM",
        "date": "Ongoing",
        "title": "Porch Breakfast for Two Package",
        "action": ("Add $45 Porch Breakfast for Two as an upsell at check-in. Served "
                   "on the front porches overlooking Bay Street. Target couples and "
                   "anniversary guests."),
        "revenue_lift": 1260,
        "lift_label": "+$1,260/month",
    },
]

# Map the spec's outlet aliases to internal outlet ids.
_OUTLET_ALIAS = {"restaurant": "rsc_restaurant", "rsc_restaurant": "rsc_restaurant",
                 "rooftop_bar": "rooftop_bar", "bar": "rooftop_bar", "rooftop": "rooftop_bar"}


class FNBEngine:

    # ── Spec-shaped API responses (single source for the dashboard + curl) ──

    def dow_daily(self, tenant_id: str, outlet: str) -> list[dict[str, Any]]:
        """Day-of-week array for an outlet, matching the documented API
        contract. Demo tenant returns the curated spec arrays."""
        oid = _OUTLET_ALIAS.get(outlet, outlet)
        if tenant_id == DEMO_FNB_TENANT:
            return ROOFTOP_DOW_SPEC if oid == "rooftop_bar" else RESTAURANT_DOW_SPEC
        # Non-demo: aggregate the generated per-date data into a DOW array.
        data = self.generate_demo_data(tenant_id, date.today(), 30)
        rows = data.get("outlets", {}).get(oid, [])
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        out = []
        for day in order:
            drows = [r for r in rows if r.get("day_of_week") == day]
            if not drows:
                continue
            n = len(drows)
            if oid == "rooftop_bar":
                out.append({"day": day,
                            "guests": round(sum(r["guests"] for r in drows) / n),
                            "avg_spend": round(sum(r["avg_spend"] for r in drows) / n),
                            "revenue": round(sum(r["revenue"] for r in drows) / n),
                            "occ_pct": round(sum(r["capacity_pct"] for r in drows) / n)})
            else:
                out.append({"day": day,
                            "covers": round(sum(r["covers"] for r in drows) / n),
                            "avg_check": round(sum(r["avg_check"] for r in drows) / n),
                            "revenue": round(sum(r["revenue"] for r in drows) / n),
                            "occ_pct": round(sum(r["covers_capacity_pct"] for r in drows) / n)})
        return out

    def summary_flat(self, tenant_id: str) -> dict[str, Any]:
        """Flat monthly summary matching the documented API contract."""
        if tenant_id == DEMO_FNB_TENANT:
            return dict(SUMMARY_SPEC)
        s = self.compute_summary(tenant_id, 30)
        if not s.get("enabled"):
            return {"enabled": False}
        r, b = s["restaurant"], s["bar"]
        return {
            "monthly_revenue":      round(r["total_revenue"] + b["total_revenue"]),
            "restaurant_monthly":   round(r["total_revenue"]),
            "bar_monthly":          round(b["total_revenue"]),
            "revpash":              r["avg_revpash"],
            "avg_check":            r["avg_check"],
            "total_monthly_covers": r["total_covers"],
        }


    # ── Demo data generation ────────────────────────────────────────

    def generate_demo_data(self, tenant_id: str, start_date: date, days: int = 90) -> dict[str, Any]:
        from config.settings import get_fnb_config
        config = get_fnb_config(tenant_id)
        if not config.get("enabled"):
            return {"enabled": False}

        rsc = next((o for o in config["outlets"] if o["id"] == "rsc_restaurant"), None)
        bar = next((o for o in config["outlets"] if o["id"] == "rooftop_bar"), None)

        restaurant_data: list[dict[str, Any]] = []
        bar_data:        list[dict[str, Any]] = []

        for i in range(days):
            d = start_date + timedelta(days=i)
            rng = _seeded_rng(f"{tenant_id}-{d.isoformat()}")
            dow = d.weekday()
            is_wf      = _is_water_festival(d)
            is_weekend = dow in (4, 5)

            if rsc:
                seats = rsc["seats"]
                if tenant_id == DEMO_FNB_TENANT:
                    # Exact curated day-of-week figures for the demo property.
                    covers, avg_check = PARLOR_DOW[dow]
                    service = "prix_fixe" if is_wf else "a_la_carte"
                else:
                    base_occ = (
                        0.95 if is_wf else
                        0.88 if is_weekend else
                        0.72 if dow == 3 else
                        0.52 if dow in (1, 2) else
                        0.65
                    )
                    covers = max(0, min(seats, int(seats * base_occ * rng.uniform(0.9, 1.05))))

                    if is_wf:
                        service, avg_check = "prix_fixe", 88.00
                    elif is_weekend:
                        service, avg_check = "a_la_carte", 78.00 + rng.uniform(-8, 12)
                    else:
                        service, avg_check = "a_la_carte", 62.00 + rng.uniform(-6, 8)

                revenue    = round(covers * avg_check, 2)
                hours_open = 3.5
                revpash    = round(revenue / (seats * hours_open), 2) if seats else 0.0
                walk_in_pct = rng.uniform(0.10, 0.35)
                walk_ins   = max(0, int(covers * walk_in_pct))
                reservations = max(0, covers - walk_ins)

                restaurant_data.append({
                    "date":                 d.isoformat(),
                    "day_of_week":          d.strftime("%A"),
                    "outlet_id":            "rsc_restaurant",
                    "covers":               covers,
                    "covers_capacity_pct":  round(covers / seats * 100, 1) if seats else 0,
                    "avg_check":            round(avg_check, 2),
                    "revenue":              revenue,
                    "service_type":         service,
                    "hours_open":           hours_open,
                    "revpash":              revpash,
                    "no_shows":             max(0, int(covers * rng.uniform(0, 0.06))),
                    "walk_ins":             walk_ins,
                    "reservations":         reservations,
                    "private_event":        False,
                    "notes":                "Prix fixe only" if is_wf else "",
                })

            if bar and dow in (3, 4, 5, 6):
                capacity = bar["capacity"]
                if tenant_id == DEMO_FNB_TENANT:
                    guests, avg_spend = ROOFTOP_DOW[dow]
                    weather_factor = 1.0
                else:
                    base_occ = (
                        0.92 if is_wf else
                        0.85 if dow == 5 else
                        0.78 if dow == 4 else
                        0.62 if dow == 3 else
                        0.70
                    )
                    weather_factor = rng.uniform(0.75, 1.0)
                    guests = max(0, min(capacity, int(capacity * base_occ * weather_factor)))

                    if is_wf or is_weekend:
                        avg_spend = bar["min_spend_peak"] * rng.uniform(1.3, 1.8)
                    else:
                        avg_spend = bar["avg_spend_per_guest"] * rng.uniform(0.85, 1.1)

                revenue    = round(guests * avg_spend, 2)
                hours_open = 6.5
                bar_data.append({
                    "date":                 d.isoformat(),
                    "day_of_week":          d.strftime("%A"),
                    "outlet_id":            "rooftop_bar",
                    "guests":               guests,
                    "capacity_pct":         round(guests / capacity * 100, 1) if capacity else 0,
                    "avg_spend":            round(avg_spend, 2),
                    "revenue":              revenue,
                    "min_spend_applied":    is_wf or is_weekend,
                    "hours_open":           hours_open,
                    "revpash":              round(revenue / (capacity * hours_open), 2) if capacity else 0.0,
                    "private_buyout":       False,
                    "weather_flag":         weather_factor < 0.8,
                })

        return {
            "enabled": True,
            "outlets": {
                "rsc_restaurant": restaurant_data,
                "rooftop_bar":    bar_data,
            },
        }

    # ── KPI summary ────────────────────────────────────────────────

    def compute_summary(self, tenant_id: str, period_days: int = 30) -> dict[str, Any]:
        data = self.generate_demo_data(tenant_id, date.today(), period_days)
        if not data.get("enabled"):
            return {"enabled": False}

        rsc = data["outlets"].get("rsc_restaurant", [])
        bar = data["outlets"].get("rooftop_bar", [])

        rsc_rev    = sum(d["revenue"] for d in rsc)
        rsc_covers = sum(d["covers"]  for d in rsc)
        rsc_avg_check = rsc_rev / rsc_covers if rsc_covers else 0
        rsc_avg_occ   = (sum(d["covers_capacity_pct"] for d in rsc) / len(rsc)) if rsc else 0
        rsc_revpash   = (sum(d["revpash"] for d in rsc) / len(rsc)) if rsc else 0

        bar_rev     = sum(d["revenue"] for d in bar)
        bar_guests  = sum(d["guests"]  for d in bar)
        bar_avg_occ = (sum(d["capacity_pct"] for d in bar) / len(bar)) if bar else 0

        total_fnb_rev = rsc_rev + bar_rev
        rsc_sorted    = sorted(rsc, key=lambda x: x["revenue"], reverse=True)
        top_days      = rsc_sorted[:3]
        low_days      = [d for d in rsc_sorted[-5:] if d["covers_capacity_pct"] < 60][:3]

        # Day-of-week aggregation (Mon..Sun)
        dow_buckets: dict[str, list] = {n: [] for n in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]}
        for d in rsc:
            dow_buckets[d["day_of_week"]].append(d)
        dow_table = []
        for name in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]:
            rows = dow_buckets[name]
            if not rows: continue
            avg_covers   = sum(r["covers"]   for r in rows) / len(rows)
            avg_check    = sum(r["avg_check"] for r in rows) / len(rows)
            avg_revenue  = sum(r["revenue"]  for r in rows) / len(rows)
            avg_occ      = sum(r["covers_capacity_pct"] for r in rows) / len(rows)
            dow_table.append({
                "day":           name,
                "avg_covers":    round(avg_covers),
                "avg_check":     round(avg_check, 2),
                "avg_revenue":   round(avg_revenue, 2),
                "avg_occ_pct":   round(avg_occ, 1),
                "is_yield_gap":  avg_occ < 55,
            })

        # Room → F&B correlation buckets (use room ADR proxy via day-of-week alignment with demand_engine)
        from modules.hospitality.demand_engine import DemandEngine
        eng = DemandEngine()
        buckets = {"<50":[], "50-70":[], "70-85":[], "85+":[]}
        for r in rsc:
            d = date.fromisoformat(r["date"])
            fc = eng.forecast(d)
            occ = fc.score  # use demand score as proxy for room occupancy
            if   occ < 50: buckets["<50"].append(r["revenue"])
            elif occ < 70: buckets["50-70"].append(r["revenue"])
            elif occ < 85: buckets["70-85"].append(r["revenue"])
            else:          buckets["85+"].append(r["revenue"])
        correlation = [
            {"bucket": k, "avg_fnb_revenue": round(sum(v)/len(v), 2) if v else 0, "nights": len(v)}
            for k, v in buckets.items()
        ]

        rooms_count = 19   # Bay Street Inn
        return {
            "enabled":           True,
            "period_days":       period_days,
            "total_fnb_revenue": round(total_fnb_rev, 2),
            "restaurant": {
                "total_revenue":     round(rsc_rev, 2),
                "total_covers":      rsc_covers,
                "avg_check":         round(rsc_avg_check, 2),
                "avg_occupancy_pct": round(rsc_avg_occ, 1),
                "avg_revpash":       round(rsc_revpash, 2),
                "top_days":          top_days,
                "low_days":          low_days,
                "dow_table":         dow_table,
            },
            "bar": {
                "total_revenue":     round(bar_rev, 2),
                "total_guests":      bar_guests,
                "avg_occupancy_pct": round(bar_avg_occ, 1),
                "operating_nights":  len(bar),
            },
            "combined_per_room_per_day": round(total_fnb_rev / period_days / rooms_count, 2),
            "room_fnb_correlation":      correlation,
            "industry_benchmark_revpash": {"low": 18, "high": 28},
        }

    # ── Recommendations ────────────────────────────────────────────

    def generate_recommendations(self, tenant_id: str) -> list[dict[str, Any]]:
        from config.settings import get_fnb_config
        config = get_fnb_config(tenant_id)
        if not config.get("enabled"):
            return []

        if tenant_id == DEMO_FNB_TENANT:
            # Four curated cards matching the documented API contract.
            return [dict(c) for c in RECOMMENDATIONS_SPEC]

        from modules.hospitality.demand_engine import DemandEngine
        engine = DemandEngine()
        today  = date.today()
        recs: list[dict[str, Any]] = []

        for i in range(14):
            d   = today + timedelta(days=i)
            fc  = engine.forecast(d)
            dow = d.weekday()
            is_weekend = dow in (4, 5)

            if fc.score >= 85:
                recs.append({
                    "outlet":              "rsc_restaurant",
                    "outlet_name":         "The Parlor at Bay Street Inn",
                    "date":                d.isoformat(),
                    "date_label":          d.strftime("%a %b %-d"),
                    "days_away":           i,
                    "demand_score":        fc.score,
                    "demand_label":        fc.label,
                    "type":                "premium_service",
                    "priority":            "high",
                    "title":               "Prix Fixe Menu Recommended",
                    "action": (
                        f"Room demand is {fc.label} ({fc.score}/100)"
                        f"{' — ' + fc.event_name if fc.event_name else ''}. "
                        f"Run a prix fixe dinner at $85/person (vs $72 avg check). "
                        f"Require reservations. Est. revenue lift: +${(85-72)*40:,} "
                        f"(40 covers × +$13 avg check)."
                    ),
                    "est_revenue_lift":         (85 - 72) * 40,
                    "recommended_avg_check":    85.00,
                    "bar_action": (
                        f"Apply $25 minimum spend on rooftop bar. "
                        f"Est. bar lift: +${int(25 * 0.3 * 40):,}."
                    ),
                })
            elif fc.score <= 45 and dow in (1, 2):
                recs.append({
                    "outlet":              "rsc_restaurant",
                    "outlet_name":         "The Parlor at Bay Street Inn",
                    "date":                d.isoformat(),
                    "date_label":          d.strftime("%a %b %-d"),
                    "days_away":           i,
                    "demand_score":        fc.score,
                    "demand_label":        fc.label,
                    "type":                "fill_strategy",
                    "priority":            "medium",
                    "title":               "Low Demand — Drive Local Traffic",
                    "action": (
                        f"Room demand is {fc.label} ({fc.score}/100). "
                        f"Recommend: $35 prix fixe lunch to attract locals, "
                        f"4–6pm happy hour (half-price house wine). "
                        f"Consider a 'Dinner + Stay' package combining "
                        f"room + dinner at a 10% combined discount — "
                        f"fills rooms AND restaurant simultaneously."
                    ),
                    "est_revenue_lift":      480,
                    "recommended_avg_check": 45.00,
                    "bar_action":            "4–6pm happy hour: half-price house wine and signature cocktails.",
                })
            elif is_weekend and fc.score >= 65:
                recs.append({
                    "outlet":              "rooftop_bar",
                    "outlet_name":         "Rooftop Bar",
                    "date":                d.isoformat(),
                    "date_label":          d.strftime("%a %b %-d"),
                    "days_away":           i,
                    "demand_score":        fc.score,
                    "demand_label":        fc.label,
                    "type":                "minimum_spend",
                    "priority":            "medium",
                    "title":               "Apply Rooftop Minimum Spend",
                    "action": (
                        f"Weekend with {fc.label} demand ({fc.score}/100). "
                        f"Apply $25 minimum spend on rooftop bar. "
                        f"Estimated guests: 42–55. "
                        f"Est. revenue at minimum: ${25*48:,}–${25*55:,}."
                    ),
                    "est_revenue_lift":       (25 - 20) * 48,
                    "recommended_min_spend":  25.00,
                    "bar_action":             "Set $25 minimum spend via POS at open.",
                })

        return recs

    # ── Private event pricing ──────────────────────────────────────

    def private_event_pricing(self, tenant_id: str, outlet_id: str,
                              guest_count: int, hours: float, event_date: str) -> dict[str, Any]:
        from config.settings import get_fnb_outlet
        outlet = get_fnb_outlet(tenant_id, outlet_id)
        if not outlet:
            return {"error": "Outlet not found"}

        from modules.hospitality.demand_engine import DemandEngine
        engine = DemandEngine()
        try:
            ev_date = date.fromisoformat(event_date)
            fc      = engine.forecast(ev_date)
            demand_score, demand_label = fc.score, fc.label
        except (TypeError, ValueError):
            demand_score, demand_label = 50, "Normal"

        if outlet["type"] == "bar":
            base_rate    = outlet.get("private_buyout_rate", 1800)
            premium_mult = 1.3 if demand_score >= 80 else 1.0
            buyout_rate  = base_rate * premium_mult
            per_head     = buyout_rate / max(guest_count, 1)
            min_spend    = max(buyout_rate, guest_count * 45)
            return {
                "outlet":        outlet["name"],
                "event_date":    event_date,
                "guest_count":   guest_count,
                "hours":         hours,
                "demand_score":  demand_score,
                "demand_label":  demand_label,
                "pricing": {
                    "buyout_rate":         round(buyout_rate, 2),
                    "per_head_equivalent": round(per_head, 2),
                    "minimum_spend":       round(min_spend, 2),
                    "recommended_rate":    round(max(buyout_rate, min_spend), 2),
                    "premium_applied":     premium_mult > 1.0,
                },
                "opportunity_cost": {
                    "note": (
                        f"Rooftop bar would normally generate ~$"
                        f"{int(outlet['avg_spend_per_guest'] * outlet['capacity'])} "
                        f"on an open {demand_label} night. Buyout rate covers "
                        f"this plus margin."
                        if demand_score >= 65
                        else "Low demand night — buyout captures revenue that might not materialize."
                    ),
                },
            }
        else:
            seats         = outlet.get("seats", 48)
            base_per_head = 95 if demand_score >= 80 else 78
            return {
                "outlet":       outlet["name"],
                "event_date":   event_date,
                "guest_count":  min(guest_count, seats),
                "hours":        hours,
                "demand_score": demand_score,
                "demand_label": demand_label,
                "pricing": {
                    "per_head_minimum":  base_per_head,
                    "total_minimum":     round(guest_count * base_per_head, 2),
                    "room_fee":          250.00,
                    "recommended_total": round(guest_count * base_per_head + 250, 2),
                    "premium_applied":   demand_score >= 80,
                },
            }

    # ── RevPASH series ─────────────────────────────────────────────

    def revpash_series(self, tenant_id: str, days: int = 30) -> dict[str, Any]:
        from config.settings import get_fnb_config
        if not get_fnb_config(tenant_id).get("enabled"):
            return {"enabled": False}
        data = self.generate_demo_data(tenant_id, date.today() - timedelta(days=days), days)
        out: dict[str, Any] = {"enabled": True}
        for outlet_id, daily in data.get("outlets", {}).items():
            out[outlet_id] = {
                "dates":  [d["date"] for d in daily],
                "values": [d["revpash"] for d in daily],
                "avg":    round(sum(d["revpash"] for d in daily) / len(daily), 2) if daily else 0,
            }
        return out
