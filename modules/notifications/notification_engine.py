"""INNtelligence notification engine.

Surfaces five notification delivery modes:
  push (PWA browser push) · modal (in-app full-screen prompt)
  · banner (in-app top banner) · badge (PWA icon count) · sound (opt-in chime)

Each notification carries a priority (critical/high/medium/low) that maps to
the delivery modes the UI should activate. CRITICAL events trigger a modal +
chime. HIGH events get push + banner. MEDIUM banner only. LOW badge only.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any


class NotificationType(Enum):
    PUSH   = "push"
    MODAL  = "modal"
    BANNER = "banner"
    BADGE  = "badge"


class NotificationPriority(Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class NotificationCategory(Enum):
    RATE_SURGE         = "rate_surge"
    COMPETITOR_EVENT   = "competitor_event"
    FESTIVAL_COUNTDOWN = "festival_countdown"
    GAP_NIGHT          = "gap_night"
    BOOKING_PACE       = "booking_pace"
    REVIEW_ALERT       = "review_alert"
    AUTOPILOT          = "autopilot"
    SYSTEM             = "system"


def _build(title: str, body: str, category: NotificationCategory,
           priority: NotificationPriority, types: list[NotificationType],
           action_url: str | None = None, data: dict | None = None,
           ttl_hours: int = 24) -> dict[str, Any]:
    now = datetime.now()
    return {
        "id":         f"notif_{int(now.timestamp() * 1000)}",
        "title":      title,
        "body":       body,
        "category":   category.value,
        "priority":   priority.value,
        "types":      [t.value for t in types],
        "action_url": action_url,
        "data":       data or {},
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
        "read":       False,
        "dismissed":  False,
        "sound":      priority in (NotificationPriority.CRITICAL, NotificationPriority.HIGH),
    }


_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class NotificationEngine:

    def generate_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        from modules.hospitality.demand_engine import DemandEngine

        notifications: list[dict[str, Any]] = []
        today  = date.today()
        engine = DemandEngine()

        # Rate surge / festival countdown ── first peak day in next 7
        for i in range(7):
            d  = today + timedelta(days=i)
            fc = engine.forecast(d)
            if fc.score >= 85:
                pri = NotificationPriority.CRITICAL if i <= 2 else NotificationPriority.HIGH
                notifications.append(_build(
                    title=f"⚡ Rate Surge — {d.strftime('%b %-d')}",
                    body=(
                        f"Demand score {fc.score}/100"
                        + (f" · {fc.event_name}" if fc.event_name else "")
                        + ". Waterfront recommendation: $535. Approve now?"
                    ),
                    category=NotificationCategory.RATE_SURGE,
                    priority=pri,
                    types=[NotificationType.PUSH, NotificationType.MODAL,
                           NotificationType.BANNER, NotificationType.BADGE],
                    action_url="/calendar",
                    data={"date": d.isoformat(), "demand_score": fc.score,
                          "event_name": fc.event_name},
                ))
                break

        # Festival countdown 1–14 days
        wf_start = date(today.year, 7, 17)
        days_to_wf = (wf_start - today).days
        if 1 <= days_to_wf <= 14:
            pri = NotificationPriority.CRITICAL if days_to_wf <= 3 else NotificationPriority.HIGH
            notifications.append(_build(
                title=f"⏰ Water Festival in {days_to_wf} day{'s' if days_to_wf != 1 else ''}",
                body=("Waterfront Suite rates not yet at festival premium. "
                      "Competitors charging $560+. Recommend $535 · 3-night min."),
                category=NotificationCategory.FESTIVAL_COUNTDOWN,
                priority=pri,
                types=[NotificationType.PUSH, NotificationType.MODAL,
                       NotificationType.BANNER, NotificationType.BADGE],
                action_url="/calendar",
                data={"days_away": days_to_wf, "festival": "Water Festival"},
            ))

        # Competitor SOLD OUT
        notifications.append(_build(
            title="🏆 Competitor Alert — Cuthbert House SOLD OUT",
            body=("Cuthbert House Inn is sold out Jul 19–21 at $560. "
                  "You are the premium boutique alternative. Hold or raise rates?"),
            category=NotificationCategory.COMPETITOR_EVENT,
            priority=NotificationPriority.HIGH,
            types=[NotificationType.PUSH, NotificationType.BANNER, NotificationType.BADGE],
            action_url="/competitive",
            data={"competitor": "Cuthbert House Inn", "dates": "Jul 19–21", "comp_rate": 560},
        ))

        # Gap nights
        notifications.append(_build(
            title="📅 3 Gap Nights Need Attention",
            body=("Jun 15, Jun 22, Jul 2 are isolated nights between bookings. "
                  "Discounted rates recommended to fill before expiry."),
            category=NotificationCategory.GAP_NIGHT,
            priority=NotificationPriority.MEDIUM,
            types=[NotificationType.BANNER, NotificationType.BADGE],
            action_url="/demand",
            data={"gap_count": 3, "urgency": "immediate"},
        ))

        # Booking pace
        notifications.append(_build(
            title="📈 Booking Pace +23% vs Last Year",
            body=("This week's bookings are running 23% ahead of last year. "
                  "Consider raising rates 5–8% on remaining open dates."),
            category=NotificationCategory.BOOKING_PACE,
            priority=NotificationPriority.MEDIUM,
            types=[NotificationType.BANNER],
            action_url="/demand",
            data={"pace_vs_ly": 23},
        ))

        # Review alert
        notifications.append(_build(
            title="⭐ New 5-Star TripAdvisor Review",
            body=("“The most romantic inn on the East Coast.” "
                  "Pricing Power Score updated to 84/100 (+1)."),
            category=NotificationCategory.REVIEW_ALERT,
            priority=NotificationPriority.LOW,
            types=[NotificationType.BADGE],
            action_url="/reputation",
            data={"platform": "TripAdvisor", "rating": 5, "new_power_score": 84},
        ))

        # De-dupe + sort
        notifications.sort(key=lambda n: _PRIORITY_ORDER.get(n["priority"], 99))
        # Stable, unique IDs across the response by appending an index
        for i, n in enumerate(notifications):
            n["id"] = f"notif_{int(time.time() * 1000)}_{i}"
        return notifications

    def get_badge_count(self, tenant_id: str, pending_rates: int = 363) -> int:
        """Pending rate approvals + unread CRITICAL/HIGH notifications."""
        notifs = self.generate_for_tenant(tenant_id)
        unread_high = sum(1 for n in notifs
                          if not n["read"] and n["priority"] in ("critical", "high"))
        return pending_rates + unread_high

    def mark_read(self, tenant_id: str, notif_id: str) -> bool:
        # Demo: stateless. Production: persist to per-tenant store.
        return True

    def mark_dismissed(self, tenant_id: str, notif_id: str) -> bool:
        return True
