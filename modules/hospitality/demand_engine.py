"""
Demand Forecasting Engine — The Gracious Collection
Produces demand scores 0-100 for each room type / date combination.
"""
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Optional

from config.settings import KNOWN_ANNUAL_EVENTS, ACTIVE_PROPERTY


@dataclass
class DemandForecast:
    score: int            # 0-100
    label: str            # Very Low / Low / Normal / High / Very High / Peak
    drivers: list         # top 3 plain-English reasons
    confidence: int       # 0-100
    event_name: Optional[str] = None
    event_nudge_pct: Optional[int] = None


class DemandEngine:
    LABELS = [
        (0,  20,  "Very Low"),
        (21, 40,  "Low"),
        (41, 60,  "Normal"),
        (61, 75,  "High"),
        (76, 89,  "Very High"),
        (90, 100, "Peak"),
    ]

    def score_to_label(self, score: int) -> str:
        for lo, hi, label in self.LABELS:
            if lo <= score <= hi:
                return label
        return "Normal"

    def get_events_for_date(self, target: date) -> list:
        """Return all known events active on target date."""
        matches = []
        for ev in KNOWN_ANNUAL_EVENTS:
            ev_date = date(target.year, ev["month"], ev["day"])
            duration = ev.get("duration_days", 1)
            if ev_date <= target <= (ev_date + timedelta(days=duration - 1)):
                matches.append(ev)
        return matches

    def day_of_week_score(self, target: date) -> tuple:
        """Weekend premium scoring."""
        dow = target.weekday()  # 0=Mon 6=Sun
        if dow in (4, 5):
            return 72, f"{'Friday' if dow == 4 else 'Saturday'} night commands strong demand"
        if dow == 6:
            return 60, "Sunday — moderate leisure demand"
        if dow in (0, 1):
            return 38, "Monday/Tuesday — weakest demand days"
        return 50, "Mid-week — average demand"

    def seasonal_score(self, target: date) -> tuple:
        """Beaufort SC seasonal pattern."""
        m = target.month
        seasonal = {1: 35, 2: 45, 3: 52, 4: 62, 5: 74,
                    6: 78, 7: 88, 8: 82, 9: 70, 10: 60,
                    11: 42, 12: 48}
        score = seasonal.get(m, 50)
        month_name = target.strftime("%B")
        if score >= 75:
            reason = f"{month_name} is peak season in Beaufort — historically 80%+ occupancy"
        elif score >= 60:
            reason = f"{month_name} is strong shoulder season"
        else:
            reason = f"{month_name} is slower season — leisure travel drops"
        return score, reason

    def event_score(self, target: date) -> tuple:
        """Score based on known local events."""
        events = self.get_events_for_date(target)
        if not events:
            return 0, None, None
        best = max(events, key=lambda e: e["pricing_nudge"])
        score = min(40, best["pricing_nudge"] * 1.5)
        reason = f"{best['name']} ({best['source']}) — historically drives {best['pricing_nudge']}%+ rate premium"
        return score, reason, best

    def forecast(self, target: date) -> DemandForecast:
        days_out = (target - date.today()).days

        dow_score, dow_reason = self.day_of_week_score(target)
        seasonal_score, seasonal_reason = self.seasonal_score(target)
        event_raw, event_reason, event_obj = self.event_score(target)

        lead_modifier = 1.0
        if days_out > 60:
            lead_modifier = 0.92
        if days_out > 90:
            lead_modifier = 0.85

        pace_bonus = 8 if target.month in (6, 7, 8) else 0

        composite = (
            dow_score      * 0.30 +
            seasonal_score * 0.40 +
            event_raw      * 0.20 +
            pace_bonus     * 0.10
        ) * lead_modifier

        score = max(0, min(100, int(composite)))
        label = self.score_to_label(score)

        drivers = []
        if event_reason:
            drivers.append(event_reason)
        drivers.append(seasonal_reason)
        drivers.append(dow_reason)
        drivers = drivers[:3]

        confidence = 75 if days_out <= 30 else 60 if days_out <= 60 else 50

        return DemandForecast(
            score=score,
            label=label,
            drivers=drivers,
            confidence=confidence,
            event_name=event_obj["name"] if event_obj else None,
            event_nudge_pct=event_obj["pricing_nudge"] if event_obj else None,
        )

    def forecast_range(self, start: date, days: int = 90) -> list:
        return [
            {"date": (start + timedelta(days=i)).isoformat(),
             "forecast": self.forecast(start + timedelta(days=i))}
            for i in range(days)
        ]
