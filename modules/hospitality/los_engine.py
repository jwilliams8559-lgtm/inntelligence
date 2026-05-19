"""Gap-night detection and length-of-stay optimization.

Synthesizes the next 90 days of bookings (deterministic, seeded per property
and date) and finds orphan single nights wedged between two stays. For each
gap, surfaces two plays: discount the gap night to fill it, or raise the
minimum-stay so the neighboring booking absorbs it.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from typing import Any


def _seeded_rng(seed: str) -> random.Random:
    h = hashlib.md5(seed.encode()).hexdigest()
    return random.Random(int(h[:12], 16))


def _generate_bookings(room_id: str, start: date, days: int = 90) -> list[tuple[date, date]]:
    """Return list of (check_in, check_out) tuples for this room."""
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


def find_gap_nights(room_id: str, room_name: str, base_rate: float,
                    start: date, days: int = 90) -> list[dict[str, Any]]:
    """Find orphan nights (gaps of 1 or 2 nights) between bookings for this room."""
    bookings = _generate_bookings(room_id, start, days)
    gaps = []
    for i in range(len(bookings) - 1):
        gap_start = bookings[i][1]                  # checkout of stay N
        gap_end   = bookings[i + 1][0]              # checkin  of stay N+1
        gap_nights = (gap_end - gap_start).days
        if gap_nights in (1, 2):
            # Two plays: discount the gap nights, or extend min-stay
            discount_pct = 20 if gap_nights == 1 else 15
            for n in range(gap_nights):
                gap_date = gap_start + timedelta(days=n)
                discount_amt = round(base_rate * discount_pct / 100)
                gap_rate = round(base_rate - discount_amt)
                gaps.append({
                    "date":             gap_date.isoformat(),
                    "room_id":          room_id,
                    "room_name":        room_name,
                    "gap_length":       gap_nights,
                    "prior_checkout":   gap_start.isoformat(),
                    "next_checkin":     gap_end.isoformat(),
                    "current_rate":     round(base_rate),
                    "recommended_rate": gap_rate,
                    "discount_pct":     discount_pct,
                    "lost_if_empty":    round(base_rate),
                    "captured_if_sold": gap_rate,
                    "alternative_min_stay_extension": gap_nights,
                })
    return gaps


def min_stay_recommendations(start: date, days: int = 90) -> list[dict[str, Any]]:
    """Identify dates where setting a 2-night min-stay would block 1-night orphans."""
    from config.settings import ROOM_TYPES

    by_date: dict[str, dict[str, int]] = {}
    for room in ROOM_TYPES:
        bookings = _generate_bookings(room["id"], start, days)
        for i in range(len(bookings) - 1):
            gap_start = bookings[i][1]
            gap_nights = (bookings[i + 1][0] - gap_start).days
            if gap_nights == 1:
                key = gap_start.isoformat()
                by_date.setdefault(key, {"orphan_count": 0, "total_rooms": 0})
                by_date[key]["orphan_count"] += 1
                by_date[key]["total_rooms"]  += 1

    total_rooms = len(ROOM_TYPES)
    recs = []
    for d, counts in sorted(by_date.items()):
        if counts["orphan_count"] >= max(2, total_rooms // 3):
            recs.append({
                "date":            d,
                "weekday":         datetime.fromisoformat(d).strftime("%a"),
                "orphan_count":    counts["orphan_count"],
                "total_rooms":     total_rooms,
                "recommendation":  "Set 2-night minimum stay",
                "reason":          f"{counts['orphan_count']}/{total_rooms} rooms would have a 1-night orphan starting this date",
            })
    return recs[:10]


def get_summary(property_config: dict[str, Any]) -> dict[str, Any]:
    from config.settings import ROOM_TYPES
    start = date.today()
    all_gaps: list[dict[str, Any]] = []
    for room in ROOM_TYPES:
        all_gaps.extend(find_gap_nights(
            room["id"], room["name"], float(room["base"]), start, 90,
        ))
    all_gaps.sort(key=lambda g: g["date"])

    # Aggregate revenue at risk vs captured if all filled
    revenue_at_risk = sum(g["lost_if_empty"] for g in all_gaps)
    revenue_captured = sum(g["captured_if_sold"] for g in all_gaps)

    min_stay = min_stay_recommendations(start, 90)

    return {
        "property":            property_config.get("name", "Property"),
        "horizon_days":        90,
        "gap_count":           len(all_gaps),
        "revenue_at_risk":     revenue_at_risk,
        "revenue_captured":    revenue_captured,
        "fill_uplift_monthly": round(revenue_captured / 3),
        "gaps":                all_gaps[:20],   # top 20 nearest
        "min_stay_recs":       min_stay,
    }
