#!/usr/bin/env python3
"""One-shot DB rebrand: Anchorage 1770 Inn -> Bay Street Inn.

Rename-in-place strategy: keep tenant_id + property_id + room_type_id
stable so the 336 validated rate_recommendations, competitor_rates, and
guest rows all stay linked. Only the labels, slug, counts, and base
rates change.

Room hierarchy reorders. Old DB tier 3/4 were Cottage(295) >= Garden(295);
new tiers are Garden(275) > Classic(245). The room_type rows are renamed
in place:
    Waterfront Suite  -> Waterfront Suite   base 395  count 4   (id a64a83ec)
    Waterview Suite   -> Water View Room    base 335  count 5   (id 99e44c4a)
    Garden View Room  -> Garden Room        base 275  count 6   (id 711e438c)
    Cottage Room      -> Classic Room       base 245  count 4   (id b179c14d)

Competitors: ADD Anchorage 1770 Inn + Two Suns Inn (with 90-day rates).
The 27 other discovered competitors are left intact.
"""
from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_KEY"]
H   = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
       "Content-Type": "application/json"}

TENANT_ID   = "357afb97-1c29-427d-b58e-63d2fcc90f97"
PROPERTY_ID = "a8643b53-b116-4aa2-a102-cc972a83e5ae"

ROOM_RENAMES = {
    "a64a83ec-e01a-4591-9354-9dcc8c05937f": {
        "name": "Waterfront Suite", "base_rate": 395, "total_count": 4,
        "description": ("Premier front-of-house suites with direct Beaufort River "
                        "views and private access to the signature wraparound "
                        "porches. The finest rooms in Beaufort."),
    },
    "99e44c4a-54e0-4bdd-8888-51bf189a8cc7": {
        "name": "Water View Room", "base_rate": 335, "total_count": 5,
        "description": ("Side-facing rooms with partial river views. Beautifully "
                        "appointed with premium furnishings and all amenities."),
    },
    "711e438c-ea31-4108-9a1c-5f2493496675": {
        "name": "Garden Room", "base_rate": 275, "total_count": 6,
        "description": ("Rear-facing rooms overlooking the inn's private garden "
                        "courtyard. Quiet, comfortable, and elegantly furnished."),
    },
    "b179c14d-c0f6-4cbb-8e1d-82c5f2202cac": {
        "name": "Classic Room", "base_rate": 245, "total_count": 4,
        "description": ("Well-appointed entry-tier rooms offering the full Bay "
                        "Street Inn experience at the most accessible price point."),
    },
}


def _patch(table: str, where: dict, body: dict) -> None:
    r = requests.patch(f"{URL}/rest/v1/{table}",
                       headers={**H, "Prefer": "return=minimal"},
                       params=where, json=body, timeout=20)
    r.raise_for_status()


def _seed_competitor(name: str, category: str, tier: int, base: float,
                     weekend: float, ta: float, notes: str,
                     water_festival_soldout: bool) -> None:
    # Upsert the competitor_properties row (skip if already present)
    existing = requests.get(f"{URL}/rest/v1/competitor_properties",
                            params={"property_id": f"eq.{PROPERTY_ID}",
                                    "competitor_name": f"eq.{name}",
                                    "select": "id"},
                            headers=H).json()
    if existing:
        cid = existing[0]["id"]
        _patch("competitor_properties", {"id": f"eq.{cid}"},
               {"property_category": category, "property_tier": tier,
                "trip_advisor_rating": ta, "active": True})
    else:
        r = requests.post(f"{URL}/rest/v1/competitor_properties",
                          headers={**H, "Prefer": "return=representation"},
                          json={
                              "tenant_id": TENANT_ID, "property_id": PROPERTY_ID,
                              "name": name, "competitor_name": name,
                              "property_category": category, "property_tier": tier,
                              "trip_advisor_rating": ta, "active": True,
                              "notes": notes,
                          }, timeout=20)
        r.raise_for_status()
        cid = r.json()[0]["id"]

    # Seed 90 days of competitor_rates (idempotent: delete then insert)
    today = datetime.date.today()
    requests.delete(f"{URL}/rest/v1/competitor_rates",
                    headers=H,
                    params={"competitor_id": f"eq.{cid}",
                            "rate_date": f"gte.{today.isoformat()}"}).close()
    rows = []
    for i in range(91):
        d = today + datetime.timedelta(days=i)
        is_weekend = d.weekday() in (4, 5)
        rate = weekend if is_weekend else base
        sold_out = False
        if water_festival_soldout and datetime.date(2026, 7, 17) <= d <= datetime.date(2026, 7, 26):
            rate = round(weekend * 1.15)
            sold_out = True
        rows.append({
            "tenant_id": TENANT_ID, "property_id": PROPERTY_ID,
            "competitor_id": cid, "rate_date": d.isoformat(),
            "rate_amount": float(rate), "is_sold_out": sold_out,
            "is_stale": False, "platform": "booking.com",
            "room_description": "Standard room (estimated)",
        })
    for j in range(0, len(rows), 200):
        r = requests.post(f"{URL}/rest/v1/competitor_rates",
                          headers={**H, "Prefer": "return=minimal"},
                          json=rows[j:j + 200], timeout=30)
        r.raise_for_status()
    print(f"  seeded competitor {name}: {len(rows)} rates")


def main() -> int:
    # 1. tenant rename
    _patch("tenants", {"id": f"eq.{TENANT_ID}"},
           {"name": "Bay Street Inn Demo", "slug": "bay-street-inn-demo"})
    print("tenant renamed -> Bay Street Inn Demo / bay-street-inn-demo")

    # 2. property rename
    _patch("properties", {"id": f"eq.{PROPERTY_ID}"},
           {"name": "Bay Street Inn", "address": "Bay Street",
            "total_rooms": 19})
    print("property renamed -> Bay Street Inn (19 rooms)")

    # 3. room type renames
    for rt_id, body in ROOM_RENAMES.items():
        _patch("room_types", {"id": f"eq.{rt_id}"}, body)
        print(f"  room type {rt_id[:8]} -> {body['name']} ${body['base_rate']} x{body['total_count']}")

    # 4. add the two narration-required competitors
    _seed_competitor("Anchorage 1770 Inn", "boutique_inn", 1, 378, 480, 4.8,
                     "Historic boutique inn on Bay Street, direct river views. "
                     "Former demo property; now a direct boutique competitor.",
                     water_festival_soldout=True)
    _seed_competitor("Two Suns Inn", "boutique_inn", 1, 225, 295, 4.3,
                     "Historic B&B on Bay Street, 6 rooms. Smaller direct comp.",
                     water_festival_soldout=False)

    print("DB rebrand complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
