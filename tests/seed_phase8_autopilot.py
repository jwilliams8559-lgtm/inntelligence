"""
Seed autopilot config for Phase 8 demo:
  - Waterfront Suite enabled
  - max_rate_change_pct = 0.10 (10%)
  - min_confidence_score = 80
  - hours 6am to 10pm

Run:  python -m tests.seed_phase8_autopilot
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from engine.autopilot import upsert_autopilot_config


def main() -> None:
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=none"}
    t = requests.get(f"{sb}/rest/v1/tenants", headers=h,
                     params={"slug": "eq.anchorage-1770-demo", "select": "id"},
                     timeout=10).json()[0]
    p = requests.get(f"{sb}/rest/v1/properties", headers=h,
                     params={"tenant_id": f"eq.{t['id']}", "select": "id,name",
                             "limit": "1"}, timeout=10).json()[0]
    waterfront = requests.get(f"{sb}/rest/v1/room_types", headers=h,
                              params={"property_id": f"eq.{p['id']}",
                                      "name": "eq.Waterfront Suite",
                                      "select": "id,name"}, timeout=10).json()[0]

    cfg = upsert_autopilot_config(
        t["id"], p["id"], waterfront["id"],
        enabled=True,
        max_rate_change_pct=0.10,
        min_confidence_score=80,
        autopilot_start_hour=6,
        autopilot_end_hour=22,
        notify_on_publish=True,
        max_daily_changes=3,
    )
    print(f"\n  ✓ Autopilot config seeded for Waterfront Suite")
    print(f"    enabled               = {cfg.get('enabled')}")
    print(f"    max_rate_change_pct   = {cfg.get('max_rate_change_pct')}")
    print(f"    min_confidence_score  = {cfg.get('min_confidence_score')}")
    print(f"    hours                 = {cfg.get('autopilot_start_hour')}–{cfg.get('autopilot_end_hour')}")
    print(f"    max_daily_changes     = {cfg.get('max_daily_changes')}\n")


if __name__ == "__main__":
    main()
