"""
Phase 7 + Phase 8 mock tests.

Test 1: run_autopilot — show which recs auto-publish (Waterfront only)
Test 2: run_alert_checks — show alerts generated
Test 3: generate_autopilot_report — weekly summary
Test 4: API endpoints — sanity dispatch via Flask test client

Run:  python -m tests.test_phase78
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


def migration_007_applied() -> bool:
    r = requests.get(f"{sb_url()}/rest/v1/autopilot_configs",
                     headers=sb_hdrs(), params={"select": "id", "limit": "1"},
                     timeout=10)
    if r.status_code == 404: return False
    r = requests.get(f"{sb_url()}/rest/v1/alerts",
                     headers=sb_hdrs(), params={"select": "id", "limit": "1"},
                     timeout=10)
    return r.status_code != 404


def get_property():
    t = requests.get(f"{sb_url()}/rest/v1/tenants", headers=sb_hdrs(),
                     params={"slug": "eq.anchorage-1770-demo", "select": "id"},
                     timeout=10).json()[0]
    p = requests.get(f"{sb_url()}/rest/v1/properties", headers=sb_hdrs(),
                     params={"tenant_id": f"eq.{t['id']}", "select": "id,name",
                             "limit": "1"}, timeout=10).json()[0]
    return p


# ──────────────────────────────────────────────────────────────────────────────
#  Test 1 — run_autopilot
# ──────────────────────────────────────────────────────────────────────────────

def test_1_autopilot() -> None:
    banner("TEST 1 — run_autopilot (Waterfront Suite only)")
    if not migration_007_applied():
        print("  ⊘ SKIPPED — migration 007 not applied")
        return

    from engine.autopilot import run_autopilot
    p = get_property()
    summary = run_autopilot(p["id"], mock=True)
    print(json.dumps({k: v for k, v in summary.items() if k != "skipped_reasons"},
                     indent=2))
    if summary.get("skipped_reasons"):
        print(f"  Skipped reasons: {summary['skipped_reasons']}")


# ──────────────────────────────────────────────────────────────────────────────
#  Test 2 — run_alert_checks
# ──────────────────────────────────────────────────────────────────────────────

def test_2_alert_checks() -> None:
    banner("TEST 2 — run_alert_checks")
    if not migration_007_applied():
        print("  ⊘ SKIPPED — migration 007 not applied")
        return

    from engine.autopilot import list_alerts, run_alert_checks
    p = get_property()
    new = run_alert_checks(p["id"])
    print(f"  New alerts emitted this run: {len(new)}")
    for a in new:
        print(f"    · {a['type']:18s} → id={a['id'][:8]}…")
    print("\n  All current unread alerts:")
    for a in list_alerts(p["id"], unread_only=True, limit=20):
        print(f"    [{a['severity']:8s}] {a['alert_type']:18s}  {a['message']}")


# ──────────────────────────────────────────────────────────────────────────────
#  Test 3 — Weekly autopilot report
# ──────────────────────────────────────────────────────────────────────────────

def test_3_report() -> None:
    banner("TEST 3 — generate_autopilot_report (last 1 week)")
    if not migration_007_applied():
        print("  ⊘ SKIPPED — migration 007 not applied")
        return

    from engine.autopilot import generate_autopilot_report
    p = get_property()
    rpt = generate_autopilot_report(p["id"], weeks=1)
    print(json.dumps(rpt, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
#  Test 4 — Flask API endpoints
# ──────────────────────────────────────────────────────────────────────────────

def test_4_api() -> None:
    banner("TEST 4 — Flask API endpoints (test client)")
    if not migration_007_applied():
        print("  ⊘ SKIPPED — migration 007 not applied")
        return

    from app import app as flask_app
    client = flask_app.test_client()
    p = get_property()

    res = client.post("/api/run-autopilot", json={"property_id": p["id"], "mock": True})
    print(f"  POST /api/run-autopilot                → HTTP {res.status_code}")
    j = res.get_json()
    print(f"        auto_published={j.get('auto_published')}  skipped={j.get('skipped')}")

    res = client.get(f"/api/alerts/{p['id']}?limit=5")
    print(f"  GET  /api/alerts/<property>            → HTTP {res.status_code}  alerts={len(res.get_json() or [])}")

    res = client.get(f"/api/autopilot-config/{p['id']}")
    print(f"  GET  /api/autopilot-config/<property>  → HTTP {res.status_code}  rows={len(res.get_json() or [])}")

    res = client.get(f"/api/autopilot-report/{p['id']}?weeks=1")
    print(f"  GET  /api/autopilot-report/<property>  → HTTP {res.status_code}")
    j = res.get_json() or {}
    print(f"        rates_auto_published={j.get('rates_auto_published')}  "
          f"avg_lift_pct={j.get('avg_lift_pct')}  "
          f"estimated_revenue_lift=${j.get('estimated_revenue_lift')}")

    # Phase 7 — federated benchmarks (no migration dep beyond existing market_signals)
    res = client.get("/api/market-benchmarks?market=beaufort-sc-lowcountry&month=7")
    print(f"  GET  /api/market-benchmarks (Beaufort) → HTTP {res.status_code}")
    j = res.get_json() or {}
    print(f"        avg_occupancy={j.get('avg_occupancy')}  avg_adr=${j.get('avg_adr')}  "
          f"cells_used={j.get('cells_used')}")


# ──────────────────────────────────────────────────────────────────────────────
#  Entry
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  Phase 7+8 Test Suite  ·  migration_007_applied={migration_007_applied()}")
    test_1_autopilot()
    test_2_alert_checks()
    test_3_report()
    test_4_api()
    print(f"\n{'='*72}\n  Phase 7+8 tests complete\n{'='*72}\n")
