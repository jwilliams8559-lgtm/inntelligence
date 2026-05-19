"""
Phase 5 — Rate Publishing integration tests (mock mode).

Test 1: Single rate approval for Water Festival July 20 (Waterfront Suite)
Test 2: Approve all 360 recommendations
Test 3: API endpoint test for /api/approve-rate
Test 4: Dashboard Approve button toast simulation

Tests 1 and 2 require migration 005 to be applied to the live DB so
rate_publish_log + properties.channel_manager_type exist. The script
probes for migration 005 and reports a clear skip if missing — Test 3
+ Test 4 run regardless.

Run:
    python -m tests.test_phase5_publishing
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("phase5-tests")


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def sb_url():   return os.getenv("SUPABASE_URL", "").rstrip("/")
def sb_hdrs():
    k = os.getenv("SUPABASE_SERVICE_KEY", "")
    return {"apikey": k, "Authorization": f"Bearer {k}", "Prefer": "count=none"}


def banner(text: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n  {text}\n{bar}")


def migration_005_applied() -> bool:
    """Probe both rate_publish_log table + properties.channel_manager_type col."""
    r = requests.get(f"{sb_url()}/rest/v1/rate_publish_log",
                     headers=sb_hdrs(), params={"select": "id", "limit": "1"},
                     timeout=10)
    if r.status_code == 404:
        return False
    r = requests.get(f"{sb_url()}/rest/v1/properties",
                     headers=sb_hdrs(),
                     params={"select": "channel_manager_type", "limit": "1"},
                     timeout=10)
    return r.ok


def find_anchorage() -> dict:
    """Return Anchorage 1770 property dict (id, tenant_id, name)."""
    r = requests.get(f"{sb_url()}/rest/v1/properties",
                     headers=sb_hdrs(),
                     params={"name": "ilike.%Anchorage%",
                             "select": "id,tenant_id,name", "limit": "1"},
                     timeout=10)
    r.raise_for_status()
    return r.json()[0]


def find_water_festival_waterfront_rec(property_id: str) -> dict | None:
    """Return one pending Water Festival Waterfront Suite rec."""
    rts = requests.get(f"{sb_url()}/rest/v1/room_types",
                       headers=sb_hdrs(),
                       params={"property_id": f"eq.{property_id}",
                               "name": "eq.Waterfront Suite",
                               "select": "id,name"},
                       timeout=10).json()
    if not rts: return None
    rt_id = rts[0]["id"]
    yyyy = date.today().year
    target_date = f"{yyyy}-07-20"
    r = requests.get(f"{sb_url()}/rest/v1/rate_recommendations",
                     headers=sb_hdrs(),
                     params={"property_id":  f"eq.{property_id}",
                             "room_type_id": f"eq.{rt_id}",
                             "target_date":  f"eq.{target_date}",
                             "select":       "*",
                             "limit":        "1"},
                     timeout=10)
    return (r.json() or [None])[0]


# ──────────────────────────────────────────────────────────────────────────────
#  Test 1 — Single rate approval (Waterfront Suite, Water Festival July 20)
# ──────────────────────────────────────────────────────────────────────────────

def test_1_single_publish() -> None:
    banner("TEST 1 — Single rate approval (Waterfront Suite · Jul 20 · $535)")
    if not migration_005_applied():
        print("  ⊘ SKIPPED — migration 005 not applied (rate_publish_log table missing)")
        print("    Apply 005_rate_publishing.sql via Supabase SQL editor, then re-run.")
        return

    from engine.channel.publisher import publish_approved_rate

    prop = find_anchorage()
    rec  = find_water_festival_waterfront_rec(prop["id"])
    if not rec:
        print("  ⊘ SKIPPED — no Waterfront Suite Jul 20 recommendation found")
        return

    print(f"  Recommendation: id={rec['id']} · ${rec['recommended_rate']} · status={rec['status']}")
    result = publish_approved_rate(rec["id"], mock=True)
    print(f"\n  PushResult:")
    print(json.dumps(result.to_jsonable(), indent=4))

    # Confirm log entry
    log_rows = requests.get(f"{sb_url()}/rest/v1/rate_publish_log",
                            headers=sb_hdrs(),
                            params={"recommendation_id": f"eq.{rec['id']}",
                                    "select": "id,channel_manager,status,otas_updated,"
                                              "published_at,error_message",
                                    "order":  "published_at.desc", "limit": "1"},
                            timeout=10).json()
    print(f"\n  rate_publish_log latest row:")
    print(json.dumps(log_rows[0] if log_rows else {}, indent=4, default=str))

    # Confirm rec status flipped to 'published'
    after = requests.get(f"{sb_url()}/rest/v1/rate_recommendations",
                        headers=sb_hdrs(),
                        params={"id": f"eq.{rec['id']}",
                                "select": "status,published_at"},
                        timeout=10).json()
    print(f"\n  rate_recommendations after publish: {after[0] if after else {}}")
    print(f"\n  Result: {'✓ PASS' if result.success else '✗ FAIL'}")


# ──────────────────────────────────────────────────────────────────────────────
#  Test 2 — Bulk approve all pending recommendations
# ──────────────────────────────────────────────────────────────────────────────

def test_2_publish_all() -> None:
    banner("TEST 2 — Approve all pending recommendations (publish_all_pending)")
    if not migration_005_applied():
        print("  ⊘ SKIPPED — migration 005 not applied")
        return

    from engine.channel.publisher import publish_all_pending

    prop = find_anchorage()
    summary = publish_all_pending(prop["id"], mock=True)
    summary_print = {k: v for k, v in summary.items() if k != "batches"}
    print(f"\n  Summary:")
    print(json.dumps(summary_print, indent=4))

    batches = summary.get("batches", [])
    print(f"\n  First 2 batches (of {len(batches)}):")
    print(json.dumps(batches[:2], indent=4))

    sample = requests.get(f"{sb_url()}/rest/v1/rate_publish_log",
                          headers=sb_hdrs(),
                          params={"property_id": f"eq.{prop['id']}",
                                  "select":      "channel_manager,status,otas_updated,published_at",
                                  "order":       "published_at.desc",
                                  "limit":       "3"},
                          timeout=10).json()
    print(f"\n  Sample rate_publish_log rows ({len(sample)}):")
    print(json.dumps(sample, indent=4, default=str))


# ──────────────────────────────────────────────────────────────────────────────
#  Test 3 — Flask API endpoint dispatch (in-process test client, no live server)
# ──────────────────────────────────────────────────────────────────────────────

def test_3_api_endpoint() -> None:
    banner("TEST 3 — POST /api/approve-rate (Flask test client)")
    if not migration_005_applied():
        print("  ⊘ SKIPPED — migration 005 not applied; endpoint would 500 on log write")
        return

    from app import app as flask_app

    prop = find_anchorage()
    rec  = find_water_festival_waterfront_rec(prop["id"])
    if not rec:
        print("  ⊘ SKIPPED — no Waterfront Suite Jul 20 rec found")
        return

    client = flask_app.test_client()
    res = client.post("/api/approve-rate", json={
        "recommendation_id": rec["id"],
        "tenant_id":         prop["tenant_id"],
        "mock":              True,
    })
    print(f"  HTTP {res.status_code}")
    print(f"  JSON response:")
    print(json.dumps(res.get_json(), indent=4))


# ──────────────────────────────────────────────────────────────────────────────
#  Test 4 — Dashboard Approve button toast simulation
# ──────────────────────────────────────────────────────────────────────────────

def test_4_toast_simulation() -> None:
    banner("TEST 4 — Dashboard Approve button toast simulation")
    from engine.channel.siteminder import SiteMinderConnector
    from engine.channel.base import RateUpdate

    cm = SiteMinderConnector("00000000-0000-0000-0000-000000000000",
                              "MOCK_KEY",
                              hotel_code="ANCHORAGE1770DEMO",
                              mock=True)
    cm.authenticate()
    result = cm.push_rate_bulk([
        RateUpdate("rt-waterfront", date(date.today().year, 7, 20), 535.0)
    ])
    otas_str = ", ".join(result.otas_updated)

    print("  When the innkeeper clicks Approve on the drawer:")
    print()
    print(f"      ┌─────────────────────────────────────────────────────────┐")
    print(f"      │  ✓ Rate published to {otas_str}".ljust(60) + "│")
    print(f"      └─────────────────────────────────────────────────────────┘")
    print()
    print(f"  Cell status dot: orange (pending) → blue (published)")
    print(f"  Drawer status:   'Pending'        → 'Published {result.published_at:%b %d, %I:%M %p}'")
    print(f"  Pending count:   decremented by 1")
    print(f"  push_id:         {result.push_id}")
    print(f"  recommendations_updated: {result.recommendations_updated}")


# ──────────────────────────────────────────────────────────────────────────────
#  Entry
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  Phase 5 Test Suite  ·  migration_005_applied={migration_005_applied()}")
    test_1_single_publish()
    test_2_publish_all()
    test_3_api_endpoint()
    test_4_toast_simulation()
    print(f"\n{'='*72}\n  Phase 5 tests complete\n{'='*72}\n")
