"""Gap-night detection and length-of-stay optimization.

Two outputs, two endpoints:
  - find_gap_nights() returns the next orphan 1- or 2-night gaps between
    bookings, each with an urgency tier (immediate / soon / planning)
    based on how many days out the gap falls.
  - min_stay_recommendations() returns dates where the engine recommends
    a minimum-stay restriction, keyed to the demand_engine score for
    that date so the rationale carries decision weight.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import Any


def _seeded_rng(seed: str) -> random.Random:
    h = hashlib.md5(seed.encode()).hexdigest()
    return random.Random(int(h[:12], 16))


def _generate_bookings(room_id: str, start: date, days: int = 90) -> list[tuple[date, date]]:
    rng = _seeded_rng(f"{room_id}-{start.isoformat()}")
    bookings = []
    cursor = start + timedelta(days=rng.randint(0, 3))
    while cursor < start + timedelta(days=days):
        stay_len = rng.choices([1, 2, 3, 4, 5, 7], weights=[10, 35, 30, 15, 7, 3])[0]
        gap      = rng.choices([0, 1, 2, 3, 5, 7], weights=[15, 25, 30, 15, 10, 5])[0]
        check_in  = cursor
        check_out = check_in + timedelta(days=stay_len)
        if check_out > start + timedelta(days=days):
            break
        bookings.append((check_in, check_out))
        cursor = check_out + timedelta(days=gap)
    return bookings


def _urgency_for(days_until: int) -> str:
    if days_until <= 14: return "immediate"
    if days_until <= 30: return "soon"
    return "planning"


def find_gap_nights(start: date | None = None, days: int = 60,
                    rooms: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Detect orphan 1- and 2-night gaps across all rooms for the next `days`."""
    if rooms is None:
        from config.settings import ROOM_TYPES
        rooms = ROOM_TYPES
    ROOM_TYPES = rooms
    start = start or date.today()
    out: list[dict[str, Any]] = []
    for room in ROOM_TYPES:
        bookings = _generate_bookings(room["id"], start, days)
        base_rate = float(room["base"])
        for i in range(len(bookings) - 1):
            b1_out = bookings[i][1]
            b2_in  = bookings[i + 1][0]
            gap = (b2_in - b1_out).days
            if 0 < gap <= 2:
                days_until = (b1_out - date.today()).days
                gap_rate = round(base_rate * (0.80 if gap == 1 else 0.88) / 5) * 5
                if gap == 1:
                    action = (
                        f"1-night gap on {b1_out.strftime('%b %d')}. "
                        f"Offer ${gap_rate:.0f} gap fill rate (20% below rack) "
                        f"to attract short-stay guests."
                    )
                else:
                    action = (
                        f"2-night gap {b1_out.strftime('%b %d')}–"
                        f"{(b1_out + timedelta(1)).strftime('%b %d')}. "
                        f"Offer 12% gap fill discount or set 2-night minimum."
                    )
                out.append({
                    "date":                b1_out.isoformat(),
                    "room_id":             room["id"],
                    "room_name":           room["name"],
                    "gap_length_nights":   gap,
                    "booking_before_end":  b1_out.isoformat(),
                    "booking_after_start": b2_in.isoformat(),
                    "recommended_action":  action,
                    "recommended_price":   gap_rate,
                    "urgency":             _urgency_for(days_until),
                })
    out.sort(key=lambda g: g["date"])
    return out


def min_stay_recommendations(start: date | None = None, days: int = 60,
                             rooms: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Per-room min-stay recommendations driven by demand_engine score.

    Friday (weekday=4) with demand >= 65 → 2-night minimum across rooms.
    Any day with demand >= 90 and an active event → 3-night minimum.
    """
    from modules.hospitality.demand_engine import DemandEngine
    if rooms is None:
        from config.settings import ROOM_TYPES
        rooms = ROOM_TYPES
    ROOM_TYPES = rooms

    start = start or date.today()
    engine = DemandEngine()
    seen: set[tuple[str, str, int]] = set()
    out: list[dict[str, Any]] = []

    for i in range(days):
        d = start + timedelta(days=i)
        fc = engine.forecast(d)
        if fc.score >= 90 and fc.event_name:
            for room in ROOM_TYPES:
                key = (room["id"], d.isoformat(), 3)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "room_id":              room["id"],
                    "start_date":           d.isoformat(),
                    "end_date":             d.isoformat(),
                    "recommended_min_stay": 3,
                    "reason":               f"{fc.event_name} — Peak demand. 3-night minimum maximizes revenue capture.",
                    "demand_score":         fc.score,
                })
        elif d.weekday() == 4 and fc.score >= 65:
            for room in ROOM_TYPES:
                key = (room["id"], d.isoformat(), 2)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "room_id":              room["id"],
                    "start_date":           d.isoformat(),
                    "end_date":             (d + timedelta(1)).isoformat(),
                    "recommended_min_stay": 2,
                    "reason":               f"Friday {d.strftime('%b %d')} — demand score {fc.score} ({fc.label}). 2-night minimum protects weekend revenue.",
                    "demand_score":         fc.score,
                })
    return out
