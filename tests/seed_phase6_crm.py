"""
Seed 15 demo guests + 3 sample campaigns for Anchorage 1770 Demo.
Idempotent — re-running merges by email_hash rather than duplicating.

Run:
    python -m tests.seed_phase6_crm
"""
from __future__ import annotations

import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from engine.crm import (
    create_draft_campaign, send_campaign, update_guest_segments, upsert_guest,
)
from engine.crm.guest_manager import _sb_get, _sb_post


def main() -> None:
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=none"}
    tenants = requests.get(f"{sb}/rest/v1/tenants", headers=h,
                          params={"slug": "eq.anchorage-1770-demo",
                                  "select": "id"}, timeout=10).json()
    tid = tenants[0]["id"]
    props = requests.get(f"{sb}/rest/v1/properties", headers=h,
                         params={"tenant_id": f"eq.{tid}", "select": "id,name",
                                 "limit": "1"}, timeout=10).json()
    pid = props[0]["id"]

    today = date.today()
    rng = random.Random(2026)

    # 15 guests across all segments
    guest_specs = [
        # 3 VIP (3+ stays, high revenue)
        {"first_name":"Margaret","last_name":"Whitfield","email":"margaret.whitfield@example.com",
         "home_city":"Charleston","home_state":"SC",
         "total_stays":6,"total_nights":18,"total_revenue":7250,
         "preferred_room_type":"Waterfront Suite","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=44)).isoformat(),
         "marketing_consent":True,"tags":[]},
        {"first_name":"Robert","last_name":"Pemberton","email":"rpemberton@example.com",
         "home_city":"Atlanta","home_state":"GA",
         "total_stays":4,"total_nights":14,"total_revenue":5180,
         "preferred_room_type":"Waterview Suite","booking_sources":["direct","booking.com"],
         "last_stay_date":(today - timedelta(days=92)).isoformat(),
         "marketing_consent":True,"tags":[]},
        {"first_name":"Catherine","last_name":"DuBose","email":"cdubose@example.com",
         "home_city":"Washington","home_state":"DC",
         "total_stays":5,"total_nights":15,"total_revenue":6420,
         "preferred_room_type":"Cottage Room","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=180)).isoformat(),
         "marketing_consent":True,"tags":["anniversary"]},

        # 4 Local (SC/GA/NC)
        {"first_name":"Daniel","last_name":"Holloway","email":"daniel.holloway@example.com",
         "home_city":"Greenville","home_state":"SC",
         "total_stays":2,"total_nights":4,"total_revenue":1140,
         "preferred_room_type":"Garden View Room","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=60)).isoformat(),
         "marketing_consent":True,"tags":[]},
        {"first_name":"Olivia","last_name":"Rhett","email":"orhett@example.com",
         "home_city":"Savannah","home_state":"GA",
         "total_stays":1,"total_nights":2,"total_revenue":620,
         "preferred_room_type":"Waterview Suite","booking_sources":["airbnb"],
         "last_stay_date":(today - timedelta(days=210)).isoformat(),
         "marketing_consent":True,"tags":[]},
        {"first_name":"James","last_name":"Calhoun","email":"jcalhoun@example.com",
         "home_city":"Asheville","home_state":"NC",
         "total_stays":2,"total_nights":5,"total_revenue":1480,
         "preferred_room_type":"Cottage Room","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=120)).isoformat(),
         "marketing_consent":True,"tags":[]},
        {"first_name":"Mary","last_name":"Pinckney","email":"mpinckney@example.com",
         "home_city":"Mount Pleasant","home_state":"SC",
         "total_stays":2,"total_nights":4,"total_revenue":1180,
         "preferred_room_type":"Garden View Room","booking_sources":["direct","booking.com"],
         "last_stay_date":(today - timedelta(days=35)).isoformat(),
         "marketing_consent":False,"tags":[]},

        # 3 Lapsed (last stay 13+ months ago)
        {"first_name":"Henry","last_name":"Ashworth","email":"hashworth@example.com",
         "home_city":"Richmond","home_state":"VA",
         "total_stays":2,"total_nights":6,"total_revenue":1980,
         "preferred_room_type":"Waterview Suite","booking_sources":["booking.com"],
         "last_stay_date":(today - timedelta(days=420)).isoformat(),
         "marketing_consent":True,"tags":[]},
        {"first_name":"Eleanor","last_name":"Beaufain","email":"ebeaufain@example.com",
         "home_city":"Nashville","home_state":"TN",
         "total_stays":3,"total_nights":9,"total_revenue":3340,
         "preferred_room_type":"Waterfront Suite","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=480)).isoformat(),
         "marketing_consent":True,"tags":["anniversary"]},
        {"first_name":"Frederick","last_name":"Middleton","email":"fmiddleton@example.com",
         "home_city":"Philadelphia","home_state":"PA",
         "total_stays":1,"total_nights":3,"total_revenue":920,
         "preferred_room_type":"Garden View Room","booking_sources":["expedia"],
         "last_stay_date":(today - timedelta(days=540)).isoformat(),
         "marketing_consent":True,"tags":[]},

        # 3 New (first stay within 90 days)
        {"first_name":"Sarah","last_name":"Lockwood","email":"slockwood@example.com",
         "home_city":"Boston","home_state":"MA",
         "total_stays":1,"total_nights":2,"total_revenue":690,
         "preferred_room_type":"Waterview Suite","booking_sources":["booking.com"],
         "last_stay_date":(today - timedelta(days=14)).isoformat(),
         "marketing_consent":True,"tags":[],"source":"wifi"},
        {"first_name":"Marcus","last_name":"Bellamy","email":"mbellamy@example.com",
         "home_city":"New York","home_state":"NY",
         "total_stays":1,"total_nights":3,"total_revenue":1085,
         "preferred_room_type":"Cottage Room","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=42)).isoformat(),
         "marketing_consent":True,"tags":[],"source":"website"},
        {"first_name":"Isabella","last_name":"Trescott","email":"itrescott@example.com",
         "home_city":"Brooklyn","home_state":"NY",
         "total_stays":1,"total_nights":1,"total_revenue":295,
         "preferred_room_type":"Garden View Room","booking_sources":["airbnb"],
         "last_stay_date":(today - timedelta(days=78)).isoformat(),
         "marketing_consent":True,"tags":[]},

        # 2 Anniversary / Honeymoon tagged
        {"first_name":"Thomas","last_name":"Heyward","email":"theyward@example.com",
         "home_city":"Beaufort","home_state":"SC",
         "total_stays":3,"total_nights":9,"total_revenue":3520,
         "preferred_room_type":"Cottage Room","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=200)).isoformat(),
         "marketing_consent":True,"tags":["anniversary"]},
        {"first_name":"Amelia","last_name":"Drayton","email":"adrayton@example.com",
         "home_city":"Raleigh","home_state":"NC",
         "total_stays":2,"total_nights":6,"total_revenue":2370,
         "preferred_room_type":"Waterfront Suite","booking_sources":["direct"],
         "last_stay_date":(today - timedelta(days=120)).isoformat(),
         "marketing_consent":True,"tags":["honeymoon"]},
    ]

    print(f"\n  Seeding {len(guest_specs)} guests for Anchorage 1770 Demo…")
    ids: list[str] = []
    for spec in guest_specs:
        gid = upsert_guest(tid, pid, spec)
        ids.append(gid)
    print(f"  ✓ Upserted {len(ids)} guests")

    # Recompute segments
    counts = update_guest_segments(tid, pid)
    print(f"  ✓ Segments: {counts}")

    # 3 sample campaigns
    print("\n  Creating 3 sample campaigns…")
    # 1. Sent campaign with realistic engagement (mock send)
    body = (
        "<div style='font-family:Georgia,serif;max-width:540px;'>"
        "<h1>Welcome back, {{first_name}}</h1>"
        "<p>Our garden is at peak bloom and we saved you a porch breakfast.</p>"
        "<a href='https://anchorage1770inn.com/book'>Book your return</a>"
        "<p style='font-size:11px;color:#94A3B8;'><a href='{{unsubscribe_url}}'>Unsubscribe</a></p>"
        "</div>"
    )
    c1 = create_draft_campaign(
        tid, pid,
        name="Spring Bloom · VIP Welcome Back",
        target_segment="vip",
        subject="Your room is ready, {{first_name}} — spring in Beaufort",
        body_html=body,
    )
    if c1:
        send_campaign(c1)
        print(f"    · sent  : {c1}")

    # 2. Scheduled campaign next month
    next_month = datetime.now(timezone.utc) + timedelta(days=18)
    c2 = create_draft_campaign(
        tid, pid,
        name="June Sunsets · Local SC/GA",
        target_segment="local",
        subject="A weekend escape 90 minutes from home, {{first_name}}",
        body_html=body,
        scheduled_at=next_month,
    )
    print(f"    · sched : {c2}")

    # 3. Draft demand-triggered campaign for a soft November window
    nov_start = today.replace(month=11, day=4) if today.month <= 11 else today.replace(year=today.year+1, month=11, day=4)
    nov_end   = nov_start + timedelta(days=6)
    c3 = create_draft_campaign(
        tid, pid,
        name=f"Demand fill · {nov_start.strftime('%b %-d')}–{nov_end.strftime('%b %-d')}",
        target_segment="vip,lapsed",
        subject=f"A quiet week in Beaufort — {nov_start.strftime('%b %-d')}–{nov_end.strftime('%b %-d')} from $245/night",
        body_html=body,
        trigger_source="demand",
        trigger_metadata={
            "window_start": nov_start.isoformat(),
            "window_end":   nov_end.isoformat(),
            "avg_occupancy_proxy": 0.48,
            "from_rate":    245,
            "lead_days":    (nov_start - today).days,
        },
    )
    print(f"    · draft : {c3}")

    print("\n  ✓ Phase 6 seed complete.\n")


if __name__ == "__main__":
    main()
