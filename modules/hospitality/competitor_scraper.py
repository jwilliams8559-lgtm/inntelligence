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
        "607 Bay Inn":             {"base": 295, "weekend_mult": 1.18},
        "Airbnb Near Bay (avg)":   {"base": 265, "weekend_mult": 1.12},
        "Beaufort Inn":            {"base": 315, "weekend_mult": 1.16},
        "City Loft Hotel":         {"base": 255, "weekend_mult": 1.14},
        "Cuthbert House Inn":      {"base": 375, "weekend_mult": 1.17},
        "Rhett House Inn":         {"base": 375, "weekend_mult": 1.18},
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
        """Competitors who dropped > 15% (30-day forward vs 30-day-then-minus-14 forward)."""
        today = date.today()
        alerts = []
        for comp in COMPETITORS:
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
