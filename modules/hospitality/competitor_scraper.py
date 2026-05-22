"""
Competitor Rate Scraper — The Gracious Collection v2.
NOTE: 607 Bay Inn and Cuthbert House Inn are TWO SEPARATE competitors.
Never combine them on one row. Total competitor count: 6.

The legacy 1,000-line scraper (Booking.com / Expedia JSON-LD fallback
chain) lives in `competitor_scraper_legacy.py` and is still imported
by the older /api/dashboard route. This v2 class powers the new
dashboard at `/`.
"""
import random
from datetime import date, timedelta

from config.settings import COMPETITORS


class CompetitorScraper:
    """
    Returns synthetic competitor rates that follow realistic Beaufort SC
    seasonal and weekend patterns. Replace with live OTA API calls in production.
    """

    BASE_RATES = {
        "607 Bay Inn":             {"base": 195, "weekend_mult": 1.18},  # STR
        "Airbnb Near Bay (avg)":   {"base": 175, "weekend_mult": 1.12},  # STR
        "Beaufort Inn":            {"base": 315, "weekend_mult": 1.16},
        "City Loft Hotel":         {"base": 255, "weekend_mult": 1.14},
        "Cuthbert House Inn":      {"base": 375, "weekend_mult": 1.17},
        "Rhett House Inn":         {"base": 375, "weekend_mult": 1.18},
        "Montage Palmetto Bluff":  {"base": 825, "weekend_mult": 1.22},  # luxury ceiling
        "Hampton Inn Beaufort":    {"base": 165, "weekend_mult": 1.10},  # budget anchor
    }

    def __init__(self, seed: int | None = 42) -> None:
        # Deterministic per-instance so each request gets the same noise.
        self._rng = random.Random(seed)

    def _rate_for_date(self, comp_name: str, target: date) -> int:
        cfg = self.BASE_RATES.get(comp_name, {"base": 300, "weekend_mult": 1.15})
        base = cfg["base"]
        dow = target.weekday()
        if dow in (4, 5):
            base = int(base * cfg["weekend_mult"])
        if target.month == 7:
            base = int(base * 1.22)
        elif target.month in (6, 8):
            base = int(base * 1.12)
        elif target.month in (11, 1, 2):
            base = int(base * 0.88)
        # Deterministic per (comp, date) noise so charts don't jitter
        rng = random.Random(hash((comp_name, target.toordinal())))
        base += rng.randint(-5, 5)
        return max(199, base)

    def get_7day_snapshot(self, check_in: date | None = None) -> dict:
        if check_in is None:
            check_in = date.today()
        dates = [check_in + timedelta(days=i) for i in range(7)]
        result = {
            "dates":        [d.isoformat() for d in dates],
            "date_labels":  [d.strftime("%a %b %-d") for d in dates],
            "competitors":  {},
        }
        for comp in COMPETITORS:
            result["competitors"][comp["name"]] = [
                self._rate_for_date(comp["name"], d) for d in dates
            ]
        return result

    def get_current_snapshot(self) -> dict:
        """Today's rates per competitor — used by market intelligence panel."""
        today = date.today()
        return {
            comp["name"]: int(self._rate_for_date(comp["name"], today))
            for comp in COMPETITORS
        }

    def get_current_snapshot_typed(self, room_category: str | None = None,
                                   target: date | None = None) -> list[dict]:
        """Per-competitor rates with property_type so the rate_engine can
        weight correctly. When room_category is supplied, each competitor's
        base rate is adjusted by COMPETITOR_ROOM_TYPES.rate_premium_vs_base
        for that category — so a Waterfront query sees Cuthbert at ~$482
        not the property-blended base ~$377. STRs and competitors with no
        room-type mapping retain their base rate.
        """
        from config.settings import COMPETITOR_ROOM_TYPES
        d = target or date.today()
        out: list[dict] = []
        for comp in COMPETITORS:
            base_rate = int(self._rate_for_date(comp["name"], d))
            adjusted  = base_rate
            has_equiv = False
            if room_category:
                mapping = COMPETITOR_ROOM_TYPES.get(comp["name"], {})
                equiv   = mapping.get(room_category)
                if equiv and equiv.get("rate_premium_vs_base") is not None:
                    adjusted  = int(base_rate * (1 + equiv["rate_premium_vs_base"]))
                    has_equiv = True
            else:
                has_equiv = True   # no category filter → everyone counts
            out.append({
                "name":           comp["name"],
                "rate":           adjusted,
                "base_rate":      base_rate,
                "property_type":  comp.get("property_type", "upscale_hotel"),
                "has_equivalent": has_equiv,
            })
        return out

    # ── Legacy compatibility shims (called by the original /api/dashboard route) ──

    def get_availability_snapshot(self, check_in: date | None = None) -> dict:
        """Legacy shape: {name: {indicator, est_occupancy, availability_status}}."""
        check_in = check_in or date.today()
        out: dict = {}
        for comp in COMPETITORS:
            color = comp.get("avail_color", "green")
            est = 0.55 if color == "green" else 0.80 if color == "yellow" else 0.92
            out[comp["name"]] = {
                "indicator":            color,
                "est_occupancy":        est,
                "availability_status":  {"green": "Good", "yellow": "Limited", "red": "Sold Out"}[color],
            }
        return out

    def get_compression_data(self, forward_days: int = 30) -> dict:
        """Legacy shape: forward compression scoring."""
        today = date.today()
        scores = []
        for i in range(forward_days):
            d = today + timedelta(days=i)
            rates = [self._rate_for_date(c["name"], d) for c in COMPETITORS]
            avg = sum(rates) / max(1, len(rates))
            scores.append({"date": d.isoformat(), "avg_comp_rate": int(avg)})
        avg_now = sum(s["avg_comp_rate"] for s in scores[:7]) / 7 if scores else 0
        avg_forward = sum(s["avg_comp_rate"] for s in scores[7:]) / max(1, (forward_days - 7))
        return {
            "compression_score":      int(min(10, max(1, (avg_now / max(1, avg_forward)) * 5))),
            "compression_label":      "Normal",
            "next_7_avg":             int(avg_now),
            "forward_avg":            int(avg_forward),
            "daily":                  scores,
        }

    def detect_rate_drops(self) -> list:
        """Competitors who dropped > 15% over a 14-day window.

        Skips airbnb_str and budget_hotel property types — a boutique inn
        should never reactive-price against an STR or budget anchor.
        """
        today = date.today()
        alerts = []
        for comp in COMPETITORS:
            ptype = comp.get("property_type", "boutique_inn")
            if ptype in ("airbnb_str", "budget_hotel"):
                continue
            rate_now = self._rate_for_date(comp["name"], today + timedelta(days=30))
            rate_14d = self._rate_for_date(comp["name"], today + timedelta(days=30) - timedelta(days=14))
            if rate_14d > 0 and (rate_14d - rate_now) / rate_14d > 0.15:
                alerts.append({
                    "competitor":   comp["name"],
                    "rate_now":     int(rate_now),
                    "rate_14d_ago": int(rate_14d),
                    "drop_pct":     int(((rate_14d - rate_now) / rate_14d) * 100),
                })
        return alerts

    def generate_response_recommendation(self, competitor_name: str,
                                         their_new_rate: float,
                                         their_old_rate: float,
                                         your_rate: float,
                                         target_date: str) -> dict:
        """Build a competitive-response recommendation gated on demand_engine score.

        Decision logic (spec):
          demand >= 75               → hold (premium supported)
          55 <= demand < 75, prem<=20→ hold (acceptable gap)
          55 <= demand < 75, prem>20 → partial_match (drop to 12% above)
          demand < 55                → match (drop to 5% above)
        """
        from datetime import date as _date
        from modules.hospitality.demand_engine import DemandEngine

        engine = DemandEngine()
        try:
            tgt = _date.fromisoformat(target_date)
        except (TypeError, ValueError):
            tgt = _date.today()
        fc = engine.forecast(tgt)
        demand_score = fc.score
        demand_label = fc.label

        drop_pct = ((their_old_rate - their_new_rate) / their_old_rate * 100) if their_old_rate else 0
        your_premium_pct = ((your_rate - their_new_rate) / their_new_rate * 100) if their_new_rate else 0

        if demand_score >= 75:
            action = "hold"
            rationale = f"Demand score is {demand_score} ({demand_label}) — market supports your premium. Hold rate."
        elif demand_score >= 55 and your_premium_pct <= 20:
            action = "hold"
            rationale = f"Normal demand ({demand_score}, {demand_label}). {your_premium_pct:.0f}% premium is within acceptable range given quality differential. Hold rate."
        elif demand_score >= 55 and your_premium_pct > 20:
            action = "partial_match"
            partial_rate = round(their_new_rate * 1.12 / 5) * 5
            rationale = (f"Premium of {your_premium_pct:.0f}% is high for normal demand ({demand_score}, {demand_label}). "
                         f"Consider ${partial_rate} — still 12% above {competitor_name}.")
        else:
            action = "match"
            match_rate = round(their_new_rate * 1.05 / 5) * 5
            rationale = (f"Low demand ({demand_score}, {demand_label}) and large premium. "
                         f"Consider matching at ${match_rate} — 5% above {competitor_name} to maintain positioning.")

        options = [
            {"id": "hold",    "label": "Hold Rate",
             "rate":          round(your_rate),
             "description":   f"Keep at ${round(your_rate)}. Premium position."},
            {"id": "partial", "label": "Partial Adjustment",
             "rate":          round(your_rate * 0.95 / 5) * 5,
             "description":   "Narrow the gap without full match."},
            {"id": "match",   "label": "Match + Small Premium",
             "rate":          round(their_new_rate * 1.05 / 5) * 5,
             "description":   f"Stay 5% above {competitor_name}."},
        ]

        return {
            "competitor":         competitor_name,
            "their_old_rate":     round(their_old_rate),
            "their_new_rate":     round(their_new_rate),
            "drop_pct":           round(drop_pct, 1),
            "your_rate":          round(your_rate),
            "your_premium_pct":   round(your_premium_pct, 1),
            "demand_score":       demand_score,
            "demand_label":       demand_label,
            "recommended_action": action,
            "rationale":          rationale,
            "options":            options,
            "target_date":        target_date,
        }

    def competitive_response_options(self) -> list:
        """Wrap every detected rate-drop alert with a demand-gated recommendation."""
        from config.settings import ROOM_TYPES
        from datetime import date as _date, timedelta as _td

        avg_our_rate = (sum(r["base"] * r.get("count", 1) for r in ROOM_TYPES) /
                        sum(r.get("count", 1) for r in ROOM_TYPES)) if ROOM_TYPES else 419
        drops = self.detect_rate_drops()
        if not drops and COMPETITORS:
            # Demo fallback: synthesize a soft drop on the cheapest BOUTIQUE
            # competitor (not the cheapest overall — which would be an STR
            # whose rate is not a legitimate pricing target for a boutique inn).
            today = _date.today()
            peer_comps = [c for c in COMPETITORS if c.get("property_type") == "boutique_inn"]
            if peer_comps:
                cheapest = min(peer_comps, key=lambda c: self._rate_for_date(c["name"], today + _td(days=14)))
                now_rate = int(self._rate_for_date(cheapest["name"], today + _td(days=14)))
                drops = [{
                    "competitor":   cheapest["name"],
                    "rate_now":     now_rate,
                    "rate_14d_ago": int(now_rate / 0.83),
                    "drop_pct":     17,
                }]
        target_date = (_date.today() + _td(days=30)).isoformat()
        return [
            self.generate_response_recommendation(
                competitor_name=d["competitor"],
                their_new_rate=d["rate_now"],
                their_old_rate=d["rate_14d_ago"],
                your_rate=avg_our_rate,
                target_date=target_date,
            )
            for d in drops
        ]
