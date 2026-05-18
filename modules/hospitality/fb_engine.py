"""
F&B Engine — Restaurant + bar + events monthly revenue tracker.
"""
from config.settings import FB_CONFIG


class FBEngine:

    @staticmethod
    def monthly_revenue() -> dict:
        c = FB_CONFIG
        restaurant = int(c["covers_per_night"] * c["avg_check"] * c["nights_open_per_week"] * 4.3)
        bar        = int(c["bar_avg_daily_revenue"] * 30)
        events     = int(c["event_avg_revenue"] * c["event_nights_per_month"])
        total      = restaurant + bar + events
        return {
            "restaurant": restaurant,
            "bar":        bar,
            "events":     events,
            "total":      total,
            "restaurant_name": c["restaurant_name"],
        }

    @staticmethod
    def total() -> int:
        return FBEngine.monthly_revenue()["total"]
