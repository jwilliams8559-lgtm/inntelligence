"""
Phase 6 — Guest CRM mock tests.

Test 1: Guest segmentation (VIP / Local / Lapsed / New / Anniversary)
Test 2: Demand-triggered campaign drafting from rate forecasts
Test 3: WiFi capture form submission (Flask test client)
Test 4: Unsubscribe link handling (HMAC token round-trip)

All tests run in mock mode — no live SendGrid traffic. Migration 006
must be applied for the DB writes to succeed; the script probes for
it and skips with a clear message if missing.

Run:
    python -m tests.test_phase6_crm
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")


def sb_url(): return os.getenv("SUPABASE_URL", "").rstrip("/")
def sb_hdrs():
    k = os.getenv("SUPABASE_SERVICE_KEY", "")
    return {"apikey": k, "Authorization": f"Bearer {k}", "Prefer": "count=none"}


def banner(text: str) -> None:
    print(f"\n{'='*72}\n  {text}\n{'='*72}")


def migration_006_applied() -> bool:
    r = requests.get(f"{sb_url()}/rest/v1/campaigns",
                     headers=sb_hdrs(), params={"select": "id", "limit": "1"},
                     timeout=10)
    if r.status_code == 404: return False
    r = requests.get(f"{sb_url()}/rest/v1/wifi_sessions",
                     headers=sb_hdrs(), params={"select": "id", "limit": "1"},
                     timeout=10)
    return r.status_code != 404


def get_tenant_property():
    t = requests.get(f"{sb_url()}/rest/v1/tenants", headers=sb_hdrs(),
                     params={"slug": "eq.anchorage-1770-demo", "select": "id,slug"},
                     timeout=10).json()[0]
    p = requests.get(f"{sb_url()}/rest/v1/properties", headers=sb_hdrs(),
                     params={"tenant_id": f"eq.{t['id']}", "select": "id,name",
                             "limit": "1"}, timeout=10).json()[0]
    return t, p


# ──────────────────────────────────────────────────────────────────────────────
#  Test 1 — Guest segmentation
# ──────────────────────────────────────────────────────────────────────────────

def test_1_segmentation() -> None:
    banner("TEST 1 — Guest segmentation (VIP / Local / Lapsed / New / Anniversary)")
    if not migration_006_applied():
        print("  ⊘ SKIPPED — migration 006 not applied")
        return

    from engine.crm import update_guest_segments

    t, p = get_tenant_property()
    counts = update_guest_segments(t["id"], p["id"])
    print(f"  Segment counts: {counts}")
    expectations = {
        "vip":         (3, 7),
        "local":       (4, 9),
        "lapsed":      (3, 6),
        "new_guest":   (3, 5),
        "anniversary": (2, 4),
    }
    for seg, (lo, hi) in expectations.items():
        n = counts.get(seg, 0)
        ok = lo <= n <= hi
        print(f"    · {seg:12s} = {n:>3d}   {'✓' if ok else '✗ expected ' + f'{lo}-{hi}'}")
    print(f"  Total guests: {counts.get('_total', 0)}")


# ──────────────────────────────────────────────────────────────────────────────
#  Test 2 — Demand-triggered campaign drafting
# ──────────────────────────────────────────────────────────────────────────────

def test_2_demand_campaign() -> None:
    banner("TEST 2 — Demand-triggered campaign drafting")
    if not migration_006_applied():
        print("  ⊘ SKIPPED — migration 006 not applied")
        return

    from engine.crm import check_and_create_campaigns

    _, p = get_tenant_property()
    # Loosen thresholds so the demo data triggers at least one draft.
    created = check_and_create_campaigns(
        p["id"], lookahead_days=90, window_days=7,
        occupancy_floor=0.75, min_lead_days=14,
    )
    print(f"  Drafts created this run: {len(created)}")
    if created:
        rows = requests.get(f"{sb_url()}/rest/v1/campaigns",
                            headers=sb_hdrs(),
                            params={"id": f"in.({','.join(created)})",
                                    "select": "name,target_segment,subject,"
                                              "trigger_source,trigger_metadata"},
                            timeout=10).json()
        for r in rows[:3]:
            print(f"    · {r['name']}")
            print(f"        segment : {r['target_segment']}")
            print(f"        subject : {r['subject']}")
            md = r.get("trigger_metadata") or {}
            print(f"        window  : {md.get('window_start')} → {md.get('window_end')}  "
                  f"occ={md.get('avg_occupancy_proxy')}  from ${md.get('from_rate')}")
    else:
        print("  (no soft windows under the threshold — try lowering occupancy_floor)")


# ──────────────────────────────────────────────────────────────────────────────
#  Test 3 — WiFi capture form submission
# ──────────────────────────────────────────────────────────────────────────────

def test_3_wifi_capture() -> None:
    banner("TEST 3 — WiFi capture form submission")
    if not migration_006_applied():
        print("  ⊘ SKIPPED — migration 006 not applied")
        return

    from app import app as flask_app
    client = flask_app.test_client()

    # GET landing
    r = client.get("/wifi/anchorage-1770-demo")
    print(f"  GET  /wifi/anchorage-1770-demo  → HTTP {r.status_code}")
    print(f"        title appears in HTML: {'Anchorage' in (r.data.decode() or '')}")

    # POST submit
    r = client.post("/wifi/anchorage-1770-demo/submit", data={
        "first_name":         "WifiTest",
        "last_name":          "Walker",
        "email":              "wifi.walker.test@example.com",
        "home_city":          "Beaufort",
        "home_state":         "sc",
        "marketing_consent":  "on",
    })
    print(f"  POST /wifi/anchorage-1770-demo/submit → HTTP {r.status_code}")
    body = r.data.decode()
    print(f"        success page rendered: {'Connected' in body}")

    # Confirm the row landed
    rows = requests.get(f"{sb_url()}/rest/v1/guests", headers=sb_hdrs(),
                        params={"first_name": "eq.WifiTest",
                                "select":     "id,first_name,home_city,home_state,"
                                              "source,marketing_consent,tags",
                                "limit":      "1"}, timeout=10).json()
    print(f"        guest row: {rows[0] if rows else 'NOT FOUND'}")


# ──────────────────────────────────────────────────────────────────────────────
#  Test 4 — Unsubscribe handling
# ──────────────────────────────────────────────────────────────────────────────

def test_4_unsubscribe() -> None:
    banner("TEST 4 — Unsubscribe handling")
    if not migration_006_applied():
        print("  ⊘ SKIPPED — migration 006 not applied")
        return

    from engine.crm import consume_unsubscribe, unsubscribe_token_for

    _, p = get_tenant_property()
    # Pick any consenting guest
    rows = requests.get(f"{sb_url()}/rest/v1/guests", headers=sb_hdrs(),
                        params={"property_id": f"eq.{p['id']}",
                                "marketing_consent": "eq.true",
                                "select":     "id,first_name,last_name,marketing_consent",
                                "limit":      "1"}, timeout=10).json()
    if not rows:
        print("  ⊘ SKIPPED — no consenting guests in DB")
        return
    g = rows[0]
    print(f"  Subject guest: {g['first_name']} {g['last_name']}  (consent before: {g['marketing_consent']})")

    token = unsubscribe_token_for(g["id"])
    print(f"  Token: {token[:24]}…")

    # Tampered token must be rejected
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    rejected = consume_unsubscribe(tampered)
    print(f"  Tampered token rejected: {rejected is None}")

    # Real token must succeed and flip consent off
    gid = consume_unsubscribe(token)
    after = requests.get(f"{sb_url()}/rest/v1/guests", headers=sb_hdrs(),
                         params={"id": f"eq.{g['id']}",
                                 "select": "marketing_consent"}, timeout=10).json()
    print(f"  Real token accepted: guest_id={gid[:8] if gid else None}…  "
          f"consent_after={after[0]['marketing_consent'] if after else None}")

    # Restore consent so subsequent demo runs still target this guest
    requests.patch(f"{sb_url()}/rest/v1/guests",
                   headers={**sb_hdrs(), "Content-Type": "application/json",
                            "Prefer": "return=minimal"},
                   params={"id": f"eq.{g['id']}"},
                   json={"marketing_consent": True}, timeout=10)
    print(f"  Consent restored (demo cleanup)")


# ──────────────────────────────────────────────────────────────────────────────
#  Entry
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  Phase 6 Test Suite  ·  migration_006_applied={migration_006_applied()}")
    test_1_segmentation()
    test_2_demand_campaign()
    test_3_wifi_capture()
    test_4_unsubscribe()
    print(f"\n{'='*72}\n  Phase 6 tests complete\n{'='*72}\n")
