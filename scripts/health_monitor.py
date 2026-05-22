#!/usr/bin/env python3
"""INNtelligence health monitor — four checks against the running Flask
server. If anything fails AND ALERT_EMAIL + GMAIL_APP_PASSWORD are set,
sends a red-alert email so the operator hears about it before the
customer does.

Run manually:  python3 scripts/health_monitor.py
Cron:          */15 * * * * /usr/bin/python3 /path/to/scripts/health_monitor.py
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
import urllib.request
from email.mime.text import MIMEText
from urllib.parse import urlencode

API_BASE   = os.environ.get("API_BASE", "http://localhost:5001")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "jwilliams8559@gmail.com")
GMAIL_PASS  = os.environ.get("GMAIL_APP_PASSWORD")


def _get(path: str, params: dict | None = None, timeout: int = 15) -> dict:
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "inn-health/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return json.loads(resp.read().decode())


def check_api_health() -> str:
    d = _get("/api/health")
    if d.get("status") != "ok":
        raise RuntimeError(f"unexpected payload: {d}")
    return f"product={d.get('product')} property={d.get('property')}"


def check_rates_generate() -> str:
    d = _get("/api/calendar/per-room", {"days": 7})
    n = len(d.get("rates", {}))
    if n == 0:
        raise RuntimeError("no rate rooms returned")
    return f"{n} room keys, source={d.get('source')}"


def check_hierarchy() -> str:
    d = _get("/api/calendar/per-room", {"days": 14})
    rates = d.get("rates", {})
    wf_grid = rates.get("Waterfront Suite", {})
    failures: list[str] = []
    for date_iso in sorted(wf_grid.keys())[:14]:
        wf = wf_grid[date_iso]["recommended_rate"]
        wv = rates.get("Water View Suite", {}).get(date_iso, {}).get("recommended_rate")
        co = rates.get("Cottage Room",     {}).get(date_iso, {}).get("recommended_rate")
        gv = rates.get("Garden View Room", {}).get(date_iso, {}).get("recommended_rate")
        if None in (wf, wv, co, gv):
            continue
        if not (wf > wv > co >= gv):
            failures.append(f"{date_iso}: WF={wf} WV={wv} CO={co} GV={gv}")
    if failures:
        raise RuntimeError("hierarchy violations: " + " | ".join(failures[:3]))
    return "hierarchy holds across 14-day window"


def check_competitor_data() -> str:
    d = _get("/api/competitors/by-room-type", {"room_category": "waterfront", "days": 1})
    comps = d.get("competitors", [])
    if not comps:
        raise RuntimeError("no competitor rows returned")
    boutiques = [c for c in comps if c.get("property_type") == "boutique_inn"]
    return f"{len(comps)} comps, {len(boutiques)} boutique peers"


CHECKS = [
    ("API health",       check_api_health),
    ("Rates generating", check_rates_generate),
    ("Room hierarchy",   check_hierarchy),
    ("Competitor data",  check_competitor_data),
]


def _send_alert(failures: list[str]) -> None:
    if not (ALERT_EMAIL and GMAIL_PASS):
        print("(no GMAIL_APP_PASSWORD set — skipping alert email)")
        return
    body  = "INNtelligence health check FAILED. Investigate now.\n\n"
    body += "\n".join(failures) + f"\n\nAPI_BASE={API_BASE}\n"
    msg = MIMEText(body)
    msg["Subject"] = "🚨 INNtelligence: System Health Check Failed"
    msg["From"]    = ALERT_EMAIL
    msg["To"]      = ALERT_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(ALERT_EMAIL, GMAIL_PASS)
        s.send_message(msg)
    print("(alert email sent)")


def main() -> int:
    print(f"INNtelligence health monitor — {API_BASE}")
    failures: list[str] = []
    for name, fn in CHECKS:
        try:
            info = fn()
            print(f"  ✓ {name}: {info}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {name}: {exc}")
            failures.append(f"{name}: {exc}")
    if failures:
        print(f"\n❌ {len(failures)} check(s) FAILED")
        _send_alert(failures)
        return 1
    print("\n✅ All health checks PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
