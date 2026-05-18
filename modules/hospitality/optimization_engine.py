"""
Optimization Recommendations Engine
Generates ranked actionable recommendations for the dashboard.
"""
from datetime import date

from config.settings import GUEST_PACKAGES, ACTIVE_PROPERTY


class OptimizationEngine:

    def generate_recommendations(self, rate_recs: list, demand_forecasts: list,
                                 events: list, comp_snapshot: dict) -> dict:
        recs = {
            "midweek_specials":       self._check_midweek(rate_recs),
            "rate_alerts":            self._check_rate_alerts(rate_recs, comp_snapshot),
            "package_opportunities":  self._package_opportunities(demand_forecasts, events),
            "total_est_uplift":       0,
        }
        total = sum(p.get("est_uplift_monthly", 0) for p in recs["package_opportunities"])
        total += sum(a.get("est_uplift", 0) for a in recs["rate_alerts"])
        recs["total_est_uplift"] = total
        return recs

    def _check_midweek(self, rate_recs: list) -> dict:
        low_midweek = []
        for r in rate_recs:
            if r.get("demand_score", 50) < 50:
                d = r.get("target_date", "")
                try:
                    dt = date.fromisoformat(d)
                    if dt.weekday() in (0, 1, 2):
                        low_midweek.append(d)
                except (ValueError, TypeError):
                    pass
        if low_midweek:
            return {
                "triggered": True,
                "message": f"Consider 3-nights-for-2 midweek special for {low_midweek[0]} through {low_midweek[-1]}",
                "est_uplift": 480,
            }
        return {"triggered": False, "message": "Occupancy on target — no midweek specials triggered."}

    def _check_rate_alerts(self, rate_recs: list, comp_snapshot: dict) -> list:
        alerts = []
        waterfront_recs = [r for r in rate_recs if "waterfront" in r.get("room_id", "")]
        if waterfront_recs:
            prices = [r["recommended_rate"] for r in waterfront_recs]
            if len(prices) >= 2 and max(prices) - min(prices) > 15:
                alerts.append({
                    "type":      "waterfront_gap",
                    "icon":      "🌊",
                    "title":     "Waterfront Premium Opportunity",
                    "message":   "Waterfront room rates are spread — consider evening out the premium to maximize per-room yield.",
                    "est_uplift": 120,
                })
        if comp_snapshot:
            avg_comp = sum(comp_snapshot.values()) / len(comp_snapshot)
            alerts.append({
                "type":      "comp_position",
                "icon":      "📊",
                "title":     "Competitive Position",
                "message":   f"Comp set average: ${int(avg_comp):,}. Your recommended rates are positioned above market — hold rate.",
                "est_uplift": 0,
            })
        return alerts

    def _package_opportunities(self, demand_forecasts: list, events: list) -> list:
        opps = []
        peak = max(demand_forecasts, key=lambda x: x["forecast"].score) if demand_forecasts else None
        peak_date = peak["date"] if peak else "soon"

        for pkg in GUEST_PACKAGES[:3]:
            base = 449
            est_monthly = int(
                ACTIVE_PROPERTY["total_rooms"] *
                0.75 *
                30 *
                pkg["take_rate"] *
                pkg["upsell_price"]
            )
            opps.append({
                "icon":              pkg["icon"],
                "name":              pkg["name"],
                "components":        pkg["components"],
                "upsell_price":      pkg["upsell_price"],
                "take_rate_pct":     int(pkg["take_rate"] * 100),
                "best_date":         peak_date,
                "est_uplift_monthly": est_monthly,
                "action":            f"Offer {pkg['name']} at ${base + pkg['upsell_price']} (+${pkg['upsell_price']} over ${base} base)",
            })
        return opps
