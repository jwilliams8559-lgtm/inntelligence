"""
Reputation & Review Intelligence Engine.
Demo uses deterministic synthetic data — production wires to a review
aggregator (ReviewPro, RateGain, Revinate) or direct platform APIs.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

REVIEW_PLATFORMS = ["tripadvisor", "google", "booking_com", "expedia"]

_POSITIVE_KEYWORDS = [
    "beautiful location", "personal service", "comfortable beds",
    "amazing views", "wonderful staff", "historic charm",
    "perfect for couples", "great breakfast", "clean rooms",
    "highly recommend",
]
_NEGATIVE_KEYWORDS = [
    "parking difficult", "WiFi spotty", "street noise",
    "small bathroom", "no elevator",
]


def _seeded_rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16))


def _generate_reviews(property_name: str, months: int = 12) -> list:
    """Deterministic 12-month review history with a small dip at month 8."""
    rng = _seeded_rng(property_name)
    base = {"tripadvisor": 4.7, "google": 4.8, "booking_com": 9.1, "expedia": 4.6}
    today = date.today()
    out: list = []
    for m in range(months, 0, -1):
        d = today - timedelta(days=m * 30)
        dip = -0.15 if m == 8 else 0
        trend = (months - m) * 0.01
        for p in REVIEW_PLATFORMS:
            scale_max = 10.0 if p == "booking_com" else 5.0
            score = round(min(scale_max, base[p] + trend + dip + rng.uniform(-0.05, 0.05)), 1)
            count = rng.randint(8, 25)
            n_pos = max(2, int(score * 2))
            n_neg = max(0, int((5 - score) * 1.5))
            out.append({
                "date":               d.isoformat(),
                "platform":           p,
                "score":              score,
                "review_count":       count,
                "sentiment_keywords": {
                    "positive": rng.sample(_POSITIVE_KEYWORDS, min(n_pos, len(_POSITIVE_KEYWORDS))),
                    "negative": rng.sample(_NEGATIVE_KEYWORDS, min(n_neg, len(_NEGATIVE_KEYWORDS))),
                },
            })
    return out


class ReputationEngine:
    """Per-platform scores + competitor comparison + pricing power."""

    def get_reputation_summary(self, property_config: dict, competitors: list) -> dict:
        reviews = _generate_reviews(property_config["name"])

        your_scores: dict = {}
        for p in REVIEW_PLATFORMS:
            plat = sorted([r for r in reviews if r["platform"] == p], key=lambda r: r["date"])
            if not plat:
                continue
            latest    = plat[-1]
            three_ago = plat[-4] if len(plat) >= 4 else plat[0]
            your_scores[p] = {
                "current":      latest["score"],
                "trend_3mo":    round(latest["score"] - three_ago["score"], 2),
                "review_count": sum(r["review_count"] for r in plat),
                "history":      [{"date": r["date"], "score": r["score"]} for r in plat],
            }

        comp_baselines = {
            "Cuthbert House Inn": 4.5, "Rhett House Inn": 4.4,
            "607 Bay Inn": 4.0, "Beaufort Inn": 4.2,
            "City Loft Hotel": 4.1, "Airbnb Near Bay (avg)": 4.3,
        }
        comp_scores: dict = {}
        for c in competitors:
            name = c["name"]
            rng  = _seeded_rng(f"comp:{name}")
            base = comp_baselines.get(name, 4.2)
            comp_scores[name] = {
                "tripadvisor": round(base + rng.uniform(-0.1, 0.1), 1),
                "google":      round(base + 0.1 + rng.uniform(-0.1, 0.1), 1),
                "booking_com": round((base + 0.2) * 2, 1),
            }

        ta_score      = your_scores.get("tripadvisor", {}).get("current", 4.5)
        pricing_power = max(0, min(100, int((ta_score - 3.5) / 1.5 * 100)))
        rate_premium  = max(0, int((ta_score - 4.0) * 20))

        return {
            "your_scores":                your_scores,
            "competitor_scores":          comp_scores,
            "pricing_power_score":        pricing_power,
            "rate_premium_justified_pct": rate_premium,
            "monthly_history":            reviews,
            "alerts":                     self._alerts(your_scores),
            "keywords": {
                "positive":        _POSITIVE_KEYWORDS[:5],
                "negative":        _NEGATIVE_KEYWORDS[:2],
                "competitor_gaps": [
                    "Guests mention Cuthbert House parking issues",
                    "Rhett House WiFi complaints growing",
                ],
            },
        }

    @staticmethod
    def _alerts(your_scores: dict) -> list:
        alerts: list = []
        ta = your_scores.get("tripadvisor", {})
        trend = ta.get("trend_3mo", 0)
        if trend < -0.1:
            alerts.append({
                "severity": "warning",
                "message":  f"TripAdvisor rating trending down {abs(trend):.1f} points "
                            f"over 3 months. Review recent guest feedback.",
            })
        if trend > 0.1:
            alerts.append({
                "severity": "positive",
                "message":  f"TripAdvisor rating up {trend:.1f} points — pricing power "
                            f"growing. Consider base rate increase.",
            })
        return alerts
