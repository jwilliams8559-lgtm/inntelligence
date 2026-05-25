"""
Rate Recommendation Engine — S-Curve Pricing Algorithm
Maps demand score 0-100 to rate multiplier using cubic interpolation.
"""
from datetime import date
from dataclasses import dataclass
from typing import Optional


@dataclass
class RateRecommendation:
    room_id: str
    room_name: str
    target_date: str
    recommended_rate: float
    rack_low: float
    rack_high: float
    current_rate: float
    rate_change_dollars: float
    rate_change_pct: float
    demand_score: int
    demand_label: str
    confidence: int
    reasoning: str
    minimum_stay: Optional[int]
    comp_avg: Optional[float]
    competitive_position: str  # Premium / At Market / Below Market


class RateEngine:
    # S-curve control points: (demand_score, multiplier)
    CURVE = [
        (0,   0.75),
        (25,  0.88),
        (50,  1.00),
        (65,  1.15),
        (75,  1.30),
        (85,  1.55),
        (95,  1.90),
        (100, 2.10),
    ]

    def multiplier(self, score: int) -> float:
        score = max(0, min(100, score))
        for i in range(len(self.CURVE) - 1):
            s0, m0 = self.CURVE[i]
            s1, m1 = self.CURVE[i + 1]
            if s0 <= score <= s1:
                t = (score - s0) / (s1 - s0)
                # Cubic ease (smoothstep)
                t = t * t * (3 - 2 * t)
                return m0 + t * (m1 - m0)
        return 1.0

    @staticmethod
    def round_to_5(rate: float) -> float:
        return round(rate / 5) * 5

    def recommend(self, room: dict, demand_score: int, demand_label: str,
                  demand_drivers: list, confidence: int,
                  comp_rates: list = None, target_date: date = None) -> RateRecommendation:

        base = room["base"]
        lo   = room["min"]
        hi   = room["max"]

        mult  = self.multiplier(demand_score)
        raw   = base * mult
        final = self.round_to_5(max(lo, min(hi, raw)))

        # Competitive adjustment
        comp_avg = None
        comp_pos = "At Market"
        if comp_rates:
            comp_avg = sum(comp_rates) / len(comp_rates)
            if final > comp_avg * 1.25 and demand_score < 70:
                final = self.round_to_5(min(final, comp_avg * 1.15))
            if final < comp_avg * 0.80 and demand_score >= 40:
                final = self.round_to_5(max(final, comp_avg * 0.85))
            pct_vs_comp = (final - comp_avg) / comp_avg
            if pct_vs_comp > 0.12:
                comp_pos = "Premium"
            elif pct_vs_comp < -0.12:
                comp_pos = "Below Market"
            else:
                comp_pos = "At Market"

        # Minimum stay rule
        min_stay = None
        if target_date:
            dow = target_date.weekday()
            if dow in (4, 5) and demand_score >= 60:
                min_stay = 2

        # Rate change vs base (rack midpoint)
        rack_mid = base
        change_dollars = final - rack_mid
        change_pct = (change_dollars / rack_mid) * 100

        # Rack display range
        rack_low = int(base * 0.78)
        rack_high = int(base * 1.12)

        # Plain-English reasoning
        reason_parts = [f"Demand is {demand_label} (score {demand_score}/100)."]
        if demand_drivers:
            reason_parts.append(demand_drivers[0] + ".")
        if change_dollars > 0:
            reason_parts.append(
                f"Rate of ${int(final):,} is ${int(change_dollars):+,} above base rack, capturing strong demand."
            )
        elif change_dollars < 0:
            reason_parts.append(
                f"Rate of ${int(final):,} is ${int(abs(change_dollars)):,} below rack to stimulate occupancy."
            )
        if comp_avg:
            reason_parts.append(
                f"Comp set average is ${int(comp_avg):,} — you are {comp_pos.lower()}."
            )
        reasoning = " ".join(reason_parts)

        return RateRecommendation(
            room_id=room["id"],
            room_name=room["name"],
            target_date=target_date.isoformat() if target_date else "",
            recommended_rate=final,
            rack_low=rack_low,
            rack_high=rack_high,
            current_rate=rack_mid,
            rate_change_dollars=change_dollars,
            rate_change_pct=change_pct,
            demand_score=demand_score,
            demand_label=demand_label,
            confidence=confidence,
            reasoning=reasoning,
            minimum_stay=min_stay,
            comp_avg=comp_avg,
            competitive_position=comp_pos,
        )
