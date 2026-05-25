"""Guest CRM demo-data engine for Bay Street Inn.

Deterministically generates a realistic roster of boutique-inn guests (seeded,
so the data is stable across requests) plus campaign segments, email templates,
campaign history, and guest analytics. No external dependencies.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

_SEED = 20260525
TODAY = date(2026, 5, 25)

FIRST = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Susan", "Richard", "Jessica", "Thomas", "Sarah",
    "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Margaret", "Matthew", "Lisa",
    "Anthony", "Betty", "Mark", "Sandra", "Donald", "Ashley", "Steven", "Emily",
    "Paul", "Kimberly", "Andrew", "Donna", "Joshua", "Michelle", "Kenneth", "Carol",
    "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa", "Edward", "Deborah",
]
LAST = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
]
# city, state, approx driving miles from Beaufort SC, weight
CITIES = [
    ("Charleston", "SC", 75, 18),
    ("Columbia", "SC", 130, 14),
    ("Beaufort", "SC", 5, 12),
    ("Charlotte", "NC", 230, 14),
    ("Atlanta", "GA", 290, 13),
    ("Raleigh", "NC", 310, 9),
    ("Washington", "DC", 510, 8),
    ("New York", "NY", 800, 6),
    ("Chicago", "IL", 950, 6),
]
ROOMS = [
    ("Waterfront", 369), ("Water View", 299), ("Garden", 249),
    ("Carriage House Suite", 469), ("Signature Suite", 519), ("Grand Parlor Suite", 629),
]
REASONS = ["Anniversary", "Vacation", "Business", "Romantic getaway", "Wedding guest",
           "Family visit", "Girls' weekend", "Honeymoon", "Birthday", "Conference"]
PREFS = ["High floor", "River view", "Quiet room", "Early check-in", "Late checkout",
         "Extra pillows", "Champagne on arrival", "Pet-friendly", "Ground floor", "King bed"]
SOURCES = [("Direct", 0.40), ("Booking.com", 0.24), ("Expedia", 0.18), ("Referral", 0.18)]


def _rng():
    return random.Random(_SEED)


def _pick_weighted(rng, options):
    total = sum(w for *_, w in options)
    r = rng.uniform(0, total)
    upto = 0
    for *rest, w in options:
        upto += w
        if r <= upto:
            return rest
    return list(options[-1][:-1])


def _build_guests() -> list[dict[str, Any]]:
    rng = _rng()
    guests = []
    n = 68
    for i in range(n):
        first = rng.choice(FIRST)
        last = rng.choice(LAST)
        city, state, dist = _pick_weighted(rng, [(c, s, d, w) for c, s, d, w in CITIES])
        num_stays = rng.choices([1, 2, 3, 4, 5, 6, 8, 11], weights=[34, 22, 14, 9, 7, 6, 5, 3])[0]
        fav_room, fav_rate = rng.choice(ROOMS)

        # Generate stay history (most recent first)
        stays = []
        cursor = TODAY - timedelta(days=rng.randint(10, 240))
        for s in range(num_stays):
            nights = rng.choices([1, 2, 3, 4, 5], weights=[12, 38, 28, 14, 8])[0]
            room, base = rng.choice(ROOMS)
            rate = round(base * rng.uniform(0.92, 1.28) / 5) * 5
            total = rate * nights
            stays.append({
                "date": cursor.isoformat(),
                "room": room,
                "nights": nights,
                "rate_paid": rate,
                "total": total,
                "reason": rng.choice(REASONS),
            })
            cursor -= timedelta(days=rng.randint(90, 520))
        stays.sort(key=lambda s: s["date"], reverse=True)

        lifetime_spend = sum(s["total"] for s in stays)
        last_stay = stays[0]["date"]
        days_since = (TODAY - date.fromisoformat(last_stay)).days
        avg_spend = round(lifetime_spend / num_stays)

        if num_stays >= 5 or lifetime_spend >= 6000:
            status = "VIP"
        elif days_since > 180:
            status = "Lapsed"
        elif num_stays == 1 and days_since <= 120:
            status = "New"
        else:
            status = "Regular"

        source = _pick_weighted(rng, [(s, w) for s, w in SOURCES])[0]
        prefs = rng.sample(PREFS, k=rng.randint(1, 3))
        guests.append({
            "id": f"g{i+1:03d}",
            "name": f"{first} {last}",
            "first": first, "last": last,
            "email": f"{first.lower()}.{last.lower()}@example.com",
            "phone": f"({rng.randint(200,989)}) {rng.randint(200,989)}-{rng.randint(1000,9999)}",
            "city": city, "state": state, "distance_miles": dist,
            "num_stays": num_stays,
            "lifetime_spend": lifetime_spend,
            "avg_spend": avg_spend,
            "last_stay": last_stay,
            "days_since_stay": days_since,
            "favorite_room": fav_room,
            "status": status,
            "primary_reason": stays[0]["reason"],
            "preferences": prefs,
            "booking_source": source,
            "lead_time_days": rng.randint(5, 75),
            "stays": stays,
            "notes": "",
        })
    return guests


# Built once at import — stable across requests.
GUESTS: list[dict[str, Any]] = _build_guests()
_BY_ID = {g["id"]: g for g in GUESTS}


def guest_summaries() -> list[dict[str, Any]]:
    keys = ("id", "name", "last_stay", "num_stays", "lifetime_spend", "city", "state",
            "distance_miles", "favorite_room", "status", "days_since_stay")
    return [{k: g[k] for k in keys} for g in GUESTS]


def guest_profile(gid: str) -> dict[str, Any] | None:
    return _BY_ID.get(gid)


def segments() -> list[dict[str, Any]]:
    defs = [
        ("vip", "VIP Guests", lambda g: g["status"] == "VIP"),
        ("lapsed", "Lapsed (6+ months)", lambda g: g["days_since_stay"] > 180),
        ("anniversary", "Anniversary Guests", lambda g: any(s["reason"] in ("Anniversary", "Honeymoon", "Romantic getaway") for s in g["stays"])),
        ("local", "Local (within 100 mi)", lambda g: g["distance_miles"] <= 100),
        ("repeat", "Repeat Guests", lambda g: g["num_stays"] > 1),
        ("onetime", "One-time Guests", lambda g: g["num_stays"] == 1),
    ]
    return [{"id": sid, "name": name, "count": sum(1 for g in GUESTS if fn(g))} for sid, name, fn in defs]


def templates() -> list[dict[str, Any]]:
    return [
        {"id": "winback", "name": "Win-back Offer", "subject": "We miss you at The Bay Street Inn",
         "preview": "It's been a while — enjoy 15% off your next riverfront escape in Beaufort."},
        {"id": "anniversary", "name": "Anniversary Special", "subject": "Celebrate your anniversary with us",
         "preview": "Champagne, a river-view room, and a complimentary upgrade await."},
        {"id": "lastminute", "name": "Last Minute Deal", "subject": "This weekend in Beaufort?",
         "preview": "A few rooms just opened — book in the next 48 hours for a special rate."},
        {"id": "seasonal", "name": "Seasonal Promotion", "subject": "Lowcountry spring is calling",
         "preview": "Our favorite season on the water — packages now available."},
        {"id": "event", "name": "Event Notification", "subject": "Beaufort Water Festival weekend",
         "preview": "Book early — our peak weekend sells out fast."},
        {"id": "thankyou", "name": "Thank You Note", "subject": "Thank you for staying with us",
         "preview": "It was a pleasure hosting you. We'd love a review — and to welcome you back."},
    ]


def campaign_history() -> list[dict[str, Any]]:
    return [
        {"id": "c1", "name": "Spring Win-back", "segment": "Lapsed (6+ months)", "template": "Win-back Offer",
         "sent_date": "2026-04-12", "recipients": 22, "open_rate": 47, "bookings": 5},
        {"id": "c2", "name": "Anniversary March", "segment": "Anniversary Guests", "template": "Anniversary Special",
         "sent_date": "2026-03-01", "recipients": 18, "open_rate": 62, "bookings": 7},
        {"id": "c3", "name": "Water Festival Heads-up", "segment": "Repeat Guests", "template": "Event Notification",
         "sent_date": "2026-05-02", "recipients": 41, "open_rate": 54, "bookings": 11},
    ]


def analytics() -> dict[str, Any]:
    from collections import defaultdict
    src_rev, src_cnt = defaultdict(int), defaultdict(int)
    lead_by_status, lead_cnt = defaultdict(int), defaultdict(int)
    geo = defaultdict(lambda: {"count": 0, "spend": 0, "distance": 0})
    for g in GUESTS:
        src_cnt[g["booking_source"]] += 1
        src_rev[g["booking_source"]] += g["lifetime_spend"]
        lead_by_status[g["status"]] += g["lead_time_days"]
        lead_cnt[g["status"]] += 1
        key = f"{g['city']}, {g['state']}"
        geo[key]["count"] += 1
        geo[key]["spend"] += g["lifetime_spend"]
        geo[key]["distance"] = g["distance_miles"]

    sources = [{"source": s, "guests": src_cnt[s], "revenue": src_rev[s]} for s in src_cnt]
    lead_times = [{"status": s, "avg_lead_days": round(lead_by_status[s] / lead_cnt[s])} for s in lead_by_status]
    geography = sorted(
        [{"location": k, **v} for k, v in geo.items()],
        key=lambda x: x["count"], reverse=True,
    )
    sensitivity = [
        {"segment": "VIP", "sensitivity": "Low", "note": "Books premium rooms; rate-inelastic"},
        {"segment": "Regular", "sensitivity": "Medium", "note": "Responds to packages and perks"},
        {"segment": "New", "sensitivity": "High", "note": "Comparison-shops; first-stay discounts convert"},
        {"segment": "Lapsed", "sensitivity": "High", "note": "Win-back offers needed to re-engage"},
    ]
    return {
        "sources": sources,
        "lead_times": lead_times,
        "geography": geography,
        "price_sensitivity": sensitivity,
        "cancellation_rate_pct": 6.8,
        "total_guests": len(GUESTS),
    }
