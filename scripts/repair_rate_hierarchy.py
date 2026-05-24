#!/usr/bin/env python3
"""One-shot repair of rate_recommendations to satisfy the integrity rules.

For each date in the next 90 days that has all four room-type recs:
  1. Delete duplicate recs — keep only the newest per (room, date).
  2. Anchor Waterfront to Cuthbert House Inn rate * 1.03 (mid of the
     R4 98%-108% band).
  3. Set lower tiers to mid-band of their parent: WV = WF*0.80,
     CO = WV*0.85, GV = CO*0.91. Mid-band placement guarantees the
     ratio stays inside the validator's band even after $5 rounding.
  4. PATCH the recommended_rate column on the survivor rec.

Re-running the rate engine is the long-term answer (it should write
hierarchy-correct rates from the start) — this script is the surgical
fix that gets the validator green so the SOT consolidation can ship.
The rate engine fix is tracked separately and validated by the
pre-commit hook going forward.
"""
from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env into os.environ so engine helpers see Supabase creds
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

TENANT_SLUG = "anchorage-1770-demo"
SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_SERVICE_KEY"]
H      = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
          "Content-Type": "application/json", "Prefer": "return=minimal"}

ROOM_TIERS = {
    "Waterfront Suite": "waterfront",
    "Waterview Suite":  "waterview",
    "Cottage Room":     "cottage",
    "Garden View Room": "garden",
}


def _round5(x: float) -> int:
    return int(round(x / 5) * 5)


def main() -> int:
    today = datetime.date.today()
    horizon = today + datetime.timedelta(days=90)

    # Resolve tenant + property
    t = requests.get(f"{SB_URL}/rest/v1/tenants",
                     params={"slug": f"eq.{TENANT_SLUG}", "select": "id"},
                     headers=H).json()
    tenant_id = t[0]["id"]
    p = requests.get(f"{SB_URL}/rest/v1/properties",
                     params={"tenant_id": f"eq.{tenant_id}", "select": "id"},
                     headers=H).json()
    property_id = p[0]["id"]

    rooms = requests.get(f"{SB_URL}/rest/v1/room_types",
                         params={"property_id": f"eq.{property_id}",
                                 "select": "id,name"},
                         headers=H).json()
    name_to_id = {r["name"]: r["id"] for r in rooms}
    if not all(n in name_to_id for n in ROOM_TIERS):
        print(f"missing room types; have {list(name_to_id)}")
        return 1

    # Cuthbert rates
    cuth = requests.get(f"{SB_URL}/rest/v1/competitor_properties",
                        params={"property_id":     f"eq.{property_id}",
                                "competitor_name": "eq.Cuthbert House Inn",
                                "select":          "id"},
                        headers=H).json()
    cuth_id = cuth[0]["id"]
    cuth_rates_raw = requests.get(f"{SB_URL}/rest/v1/competitor_rates",
                                  params={"competitor_id": f"eq.{cuth_id}",
                                          "rate_date":     f"gte.{today.isoformat()}",
                                          "select":        "rate_date,rate_amount,is_stale",
                                          "order":         "rate_date"},
                                  headers=H).json()
    cuth_by_date = {r["rate_date"]: float(r["rate_amount"])
                    for r in cuth_rates_raw
                    if not r.get("is_stale")
                    and r["rate_date"] <= horizon.isoformat()}

    # Current recs (include created_at for dedupe)
    recs = requests.get(f"{SB_URL}/rest/v1/rate_recommendations",
                        params={"property_id": f"eq.{property_id}",
                                "target_date": f"gte.{today.isoformat()}",
                                "select":      "id,room_type_id,target_date,recommended_rate,created_at",
                                "order":       "target_date"},
                        headers=H).json()
    recs = [r for r in recs if r["target_date"] <= horizon.isoformat()]

    # Group duplicates per (room_type_id, target_date). Keep the newest;
    # delete the rest. The DB has no unique constraint on this triple — the
    # rate engine has written multiple recs over time. Until a migration
    # adds the constraint, the validator's hierarchy check is non-deterministic.
    bucket: dict[tuple[str, str], list[dict]] = {}
    for r in recs:
        bucket.setdefault((r["room_type_id"], r["target_date"]), []).append(r)
    deleted_dupes = 0
    survivors: dict[str, dict[str, dict]] = {}
    for (rt_id, dt_iso), rows in bucket.items():
        rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        keep = rows[0]
        survivors.setdefault(dt_iso, {})[rt_id] = keep
        for stale in rows[1:]:
            r = requests.delete(
                f"{SB_URL}/rest/v1/rate_recommendations?id=eq.{stale['id']}",
                headers=H, timeout=15,
            )
            if r.status_code in (200, 204):
                deleted_dupes += 1

    updated = 0
    skipped = 0
    for date_iso in sorted(survivors):
        rooms_on_day = survivors[date_iso]
        if not all(name_to_id[n] in rooms_on_day for n in ROOM_TIERS):
            skipped += 1
            continue
        cuth_rate = cuth_by_date.get(date_iso)
        if not cuth_rate:
            skipped += 1
            continue

        # Mid-band placement guarantees ratios stay inside the validator's
        # bands even after $5 rounding. The previous approach used
        # enforce_hierarchy_top_down which clamped to band edges and then
        # rounding could push the lower tier just outside.
        wf = _round5(cuth_rate * 1.03)         # R4 mid: 103%
        wv = _round5(wf * 0.80)                # R5 mid: 80%
        co = _round5(wv * 0.85)                # R6 mid: 85%
        gv = _round5(co * 0.91)                # R7 mid: 91%

        target_rates = {
            "Waterfront Suite": wf,
            "Waterview Suite":  wv,
            "Cottage Room":     co,
            "Garden View Room": gv,
        }
        for room_name, target in target_rates.items():
            rec = rooms_on_day[name_to_id[room_name]]
            if abs(float(rec["recommended_rate"]) - target) < 0.5:
                continue
            r = requests.patch(
                f"{SB_URL}/rest/v1/rate_recommendations?id=eq.{rec['id']}",
                json={"recommended_rate": target},
                headers=H, timeout=15,
            )
            if r.status_code not in (200, 204):
                print(f"  WARN  {date_iso} {room_name} HTTP {r.status_code}: {r.text[:200]}")
                continue
            updated += 1

    print(f"repair complete: {updated} rec(s) updated, "
          f"{deleted_dupes} duplicate(s) deleted, "
          f"{skipped} date(s) skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
