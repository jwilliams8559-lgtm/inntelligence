"""
Events Engine — Multi-source event aggregator for The Gracious Collection.
Phase 1: hardcoded KNOWN_ANNUAL_EVENTS only.
Phase 2: pluggable connectors for Eventbrite, RSS feeds, Chamber calendars.
"""
from datetime import date, timedelta

from config.settings import EVENT_SOURCES, KNOWN_ANNUAL_EVENTS


class EventsEngine:
    """Aggregates events from configured sources (hardcoded + future API)."""

    def upcoming(self, today: date | None = None, days_ahead: int = 120) -> list:
        today = today or date.today()
        out = []
        for ev in KNOWN_ANNUAL_EVENTS:
            for year in (today.year, today.year + 1):
                ev_date = date(year, ev["month"], ev["day"])
                days_away = (ev_date - today).days
                if 0 <= days_away <= days_ahead:
                    out.append({**ev, "date": ev_date.isoformat(), "days_away": days_away})
        out.sort(key=lambda x: x["days_away"])
        return out

    def enabled_sources(self) -> list:
        return [{"key": k, **v} for k, v in EVENT_SOURCES.items() if v.get("enabled")]

    def all_sources(self) -> list:
        return [{"key": k, **v} for k, v in EVENT_SOURCES.items()]
