"""
app.py — Anchorage 1770 Inn Pricing Dashboard
Flask web application — http://localhost:5001

Routes:
  GET  /                              — dashboard HTML
  GET  /api/dashboard?date=YYYY-MM-DD — all panel data for a selected date
  GET  /api/market-intelligence       — rate compression + pressure score
  GET  /api/packages                  — package definitions + status + revenue estimates
  POST /api/packages/<id>/toggle      — toggle active / coming_soon
  GET  /api/settings/competitors      — load competitor radius config
  POST /api/settings/competitors      — save competitor radius config
  GET  /export                        — 90-day CSV download
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, make_response, render_template, request

from modules.hospitality.anchorage_pricing import (
    ROOM_INVENTORY,
    AnchoragePricingEngine,
)
from modules.hospitality.competitor_scraper import CompetitorScraper
from modules.module5_optimization.optimizer import PricingOptimizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Config file paths
# ─────────────────────────────────────────────────────────────────────────────

_BASE_DIR              = os.path.dirname(os.path.abspath(__file__))
_PACKAGES_STATUS_PATH  = os.path.join(_BASE_DIR, "config", "packages_status.json")
_COMPETITORS_CFG_PATH  = os.path.join(_BASE_DIR, "config", "tenant_competitors.json")

# ─────────────────────────────────────────────────────────────────────────────
#  Package definitions (content) — status persisted in packages_status.json
# ─────────────────────────────────────────────────────────────────────────────

PACKAGES_CONFIG: Dict[str, Dict[str, Any]] = {
    "romance": {
        "name": "Romance Package",
        "emoji": "💑",
        "tagline": "Room · Dinner for Two at Ribaut Social Club · Bottle of Wine",
        "description": "An unforgettable evening: premium room, in-room dining at the legendary Ribaut Social Club, and a selected South Carolina wine awaiting on arrival.",
        "premium": 85,
        "eligible_rooms": "waterfront/cottage/water_view",
        "eligible_rooms_count": 10,
        "take_rate": 0.25,
        "available": "Year-round",
    },
    "anniversary": {
        "name": "Anniversary Package",
        "emoji": "🥂",
        "tagline": "Room · Fresh Flowers · Champagne on Arrival",
        "description": "In-room fresh floral arrangement from a local Beaufort florist and chilled champagne waiting when you arrive.",
        "premium": 65,
        "eligible_rooms": "all rooms",
        "eligible_rooms_count": 14,
        "take_rate": 0.20,
        "available": "Year-round",
    },
    "adventure": {
        "name": "Adventure Package",
        "emoji": "🚣",
        "tagline": "Room · Kayak Rental · Packed Lowcountry Lunch",
        "description": "Full-day kayak rental on the Beaufort River estuary with a packed Lowcountry lunch to enjoy on the water.",
        "premium": 75,
        "eligible_rooms": "all rooms",
        "eligible_rooms_count": 14,
        "take_rate": 0.15,
        "available": "May – October",
    },
    "spa": {
        "name": "Spa Enhancement",
        "emoji": "💆",
        "tagline": "In-Room Massage for Two (90 min)",
        "description": "A licensed therapist comes to you — 90-minute couples massage in the comfort of your room. Add to any booking.",
        "premium": 120,
        "eligible_rooms": "all rooms",
        "eligible_rooms_count": 14,
        "take_rate": 0.12,
        "available": "Year-round",
        "add_on": True,
    },
    "breakfast": {
        "name": "Breakfast Upgrade",
        "emoji": "☕",
        "tagline": "Private Porch Breakfast for Two",
        "description": "Skip the continental buffet — enjoy a private, fully-served breakfast for two delivered to your porch or balcony.",
        "premium": 35,
        "eligible_rooms": "all rooms",
        "eligible_rooms_count": 14,
        "take_rate": 0.35,
        "available": "Year-round",
    },
    "sunset_cruise": {
        "name": "Sunset Cruise",
        "emoji": "⛵",
        "tagline": "Chartered Boat Sunset Cruise for Two",
        "description": "A private 2-hour chartered sunset cruise on the Beaufort River — one of the most scenic waterways in the Lowcountry.",
        "premium": 95,
        "eligible_rooms": "all rooms",
        "eligible_rooms_count": 14,
        "take_rate": 0.18,
        "available": "April – October",
    },
    "pet": {
        "name": "Pet Package",
        "emoji": "🐾",
        "tagline": "Pet Welcome Kit · $50 Pet Fee Waived · Pet-Friendly Amenities",
        "description": "Rooms 101–103 only. Bring your four-legged family member — the welcome kit includes a bed, treats, and a local trail guide. Pet fee waived.",
        "premium": 45,
        "eligible_rooms": "rooms 101–103 only",
        "eligible_rooms_count": 3,
        "take_rate": 0.25,
        "available": "Year-round",
    },
}

GIFT_SHOP_CATEGORIES = [
    {
        "name": "Lowcountry Food & Pantry",
        "emoji": "🫙",
        "items": ["Sweetgrass Jams", "Lowcountry Hot Sauces", "Stone-Ground Grits", "Sea Island Pralines", "Local Honey", "Boiled Peanut Mix"],
        "item_count": 24,
        "monthly_revenue_est": 1200,
        "note": "Best sellers: jams, pralines",
    },
    {
        "name": "Anchorage 1770 Branded Items",
        "emoji": "🛍️",
        "items": ["Monogrammed Robes", "Canvas Tote Bags", "Soy Candles", "Coffee Mugs", "Embroidered Hats", "Guest Journal"],
        "item_count": 12,
        "monthly_revenue_est": 800,
        "note": "High-margin, strong gifting season",
    },
    {
        "name": "Local Artisan Goods",
        "emoji": "🎨",
        "items": ["Sweetgrass Baskets", "Lowcountry Watercolor Prints", "Sea Glass Jewelry", "Handmade Pottery", "Gullah Art"],
        "item_count": 18,
        "monthly_revenue_est": 650,
        "note": "Curated from Beaufort artists — consignment model",
    },
    {
        "name": "Wines & Spirits",
        "emoji": "🍷",
        "items": ["SC Muscadine Wine", "Firefly Sweet Tea Vodka", "Striped Pig Rum", "Palmetto Brewing Ales", "Local Craft Seltzers"],
        "item_count": 8,
        "monthly_revenue_est": 950,
        "note": "Requires SC liquor license compliance review",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
#  Singletons + TTL cache
# ─────────────────────────────────────────────────────────────────────────────

_engine    = AnchoragePricingEngine()
_scraper   = CompetitorScraper()
_optimizer = PricingOptimizer()

_cache: Dict[str, Any] = {}
_CACHE_TTL = 300


def _cached(key: str, fn) -> Any:
    now   = time.monotonic()
    entry = _cache.get(key)
    if entry and (now - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    data = fn()
    _cache[key] = {"data": data, "ts": now}
    return data


def _invalidate(prefix: str) -> None:
    for k in list(_cache.keys()):
        if k.startswith(prefix):
            del _cache[k]


# ─────────────────────────────────────────────────────────────────────────────
#  Config helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_packages_status() -> Dict[str, str]:
    try:
        with open(_PACKAGES_STATUS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {k: "active" for k in PACKAGES_CONFIG}


def _save_packages_status(status: Dict[str, str]) -> None:
    with open(_PACKAGES_STATUS_PATH, "w") as f:
        json.dump(status, f, indent=2)


def _load_competitor_settings() -> Dict[str, Any]:
    try:
        with open(_COMPETITORS_CFG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"property": {}, "search_radius_miles": 10, "competitors": []}


def _save_competitor_settings(data: Dict[str, Any]) -> None:
    with open(_COMPETITORS_CFG_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────────────────────────────────────

# v2 dashboard (The Gracious Collection — single-property Anchorage view)
# Lives at "/" and pulls from the new modules.hospitality.* engines.
# The legacy demo (templates/index.html + /api/dashboard) is preserved at /legacy.

from config.settings import (
    ACTIVE_PROPERTY as V2_PROPERTY,
    ROOM_TYPES as V2_ROOM_TYPES,
    COMPETITORS as V2_COMPETITORS,
    GUEST_PACKAGES as V2_GUEST_PACKAGES,
    GIFT_SHOP_CATEGORIES as V2_GIFT_SHOP,
    KNOWN_ANNUAL_EVENTS as V2_ANNUAL_EVENTS,
    EVENT_SOURCES as V2_EVENT_SOURCES,
    FEATURE_GATES as V2_FEATURE_GATES,
    FB_CONFIG as V2_FB_CONFIG,
)
from modules.hospitality.demand_engine        import DemandEngine
from modules.hospitality.rate_engine          import RateEngine
from modules.hospitality.optimization_engine  import OptimizationEngine
from modules.hospitality.competitor_scraper   import CompetitorScraper as V2Scraper
from modules.hospitality.packages_engine      import PackagesEngine
from modules.hospitality.gift_shop_engine     import GiftShopEngine
from modules.hospitality.fb_engine            import FBEngine

_v2_demand   = DemandEngine()
_v2_rate     = RateEngine()
_v2_opt      = OptimizationEngine()
_v2_scraper  = V2Scraper()
_v2_pkgs     = PackagesEngine()
_v2_shop     = GiftShopEngine()
_v2_fb       = FBEngine()


def _v2_plan_features():
    tier = V2_PROPERTY.get("plan_tier", "professional")
    return V2_FEATURE_GATES.get(tier, V2_FEATURE_GATES["professional"])


def _v2_daily_rates(check_in: date) -> list:
    comp_snap = _v2_scraper.get_current_snapshot()
    comp_rates = list(comp_snap.values())
    results = []
    fc = _v2_demand.forecast(check_in)
    for room in V2_ROOM_TYPES:
        rec = _v2_rate.recommend(
            room=room, demand_score=fc.score, demand_label=fc.label,
            demand_drivers=fc.drivers, confidence=fc.confidence,
            comp_rates=comp_rates, target_date=check_in,
        )
        rack_mid = room["base"]
        delta_pct = ((rec.recommended_rate - rack_mid) / rack_mid) * 100
        results.append({
            "id":          room["id"],
            "name":        room["name"],
            "icon":        room["icon"],
            "price":       int(rec.recommended_rate),
            "rack_low":    rec.rack_low,
            "rack_high":   rec.rack_high,
            "delta_pct":   f"{delta_pct:+.1f}%",
            "delta_sign":  "up" if delta_pct >= 0 else "down",
            "demand_score": fc.score,
            "demand_label": fc.label,
            "reasoning":   rec.reasoning,
            "minimum_stay": rec.minimum_stay,
            "competitive_position": rec.competitive_position,
        })
    return results


def _v2_calendar(check_in: date, days: int = 90) -> list:
    cal = []
    comp_snap = _v2_scraper.get_current_snapshot()
    comp_avg = sum(comp_snap.values()) / len(comp_snap) if comp_snap else 350
    waterfront_room = next((r for r in V2_ROOM_TYPES if "waterfront" in r["id"]), V2_ROOM_TYPES[0])
    garden_room     = next((r for r in V2_ROOM_TYPES if "garden"     in r["id"]), V2_ROOM_TYPES[-1])
    waterview_room  = next((r for r in V2_ROOM_TYPES if "waterview"  in r["id"]), V2_ROOM_TYPES[5])
    for i in range(min(days, 365)):
        d = check_in + timedelta(days=i)
        fc = _v2_demand.forecast(d)
        rec_wf = _v2_rate.recommend(waterfront_room, fc.score, fc.label, fc.drivers, fc.confidence, [comp_avg], d)
        rec_g  = _v2_rate.recommend(garden_room,     fc.score, fc.label, fc.drivers, fc.confidence, [comp_avg * 0.75], d)
        rec_wv = _v2_rate.recommend(waterview_room,  fc.score, fc.label, fc.drivers, fc.confidence, [comp_avg * 0.87], d)
        cal.append({
            "date":            d.isoformat(),
            "label":           d.strftime("%b %-d"),
            "dow":             d.strftime("%a"),
            "is_weekend":      d.weekday() in (4, 5, 6),
            "waterfront_rate": int(rec_wf.recommended_rate),
            "waterview_rate":  int(rec_wv.recommended_rate),
            "garden_rate":     int(rec_g.recommended_rate),
            "demand_score":    fc.score,
            "demand_label":    fc.label,
            "has_event":       fc.event_name is not None,
            "event_name":      fc.event_name,
        })
    return cal


def _v2_upcoming_events(days_ahead: int = 120) -> list:
    today = date.today()
    events = []
    for ev in V2_ANNUAL_EVENTS:
        for year in (today.year, today.year + 1):
            ev_date = date(year, ev["month"], ev["day"])
            days_away = (ev_date - today).days
            if 0 <= days_away <= days_ahead:
                events.append({
                    "date_str":   ev_date.strftime("%b %-d"),
                    "name":       ev["name"],
                    "days_away":  days_away,
                    "nudge_pct":  ev["pricing_nudge"],
                    "nudge_label": f"+{ev['pricing_nudge']}% pricing",
                    "source":     ev.get("source", "Tourist Board"),
                    "color":      "#c9a84c" if ev["pricing_nudge"] >= 15 else "#1d9e75",
                })
    events.sort(key=lambda x: x["days_away"])
    return events[:12]


def _v2_90day_forecast(check_in: date) -> dict:
    labels, projected = [], []
    total_rooms = V2_PROPERTY["total_rooms"]
    running_sum = 0
    for i in range(90):
        d = check_in + timedelta(days=i)
        fc = _v2_demand.forecast(d)
        base_rev = total_rooms * 0.75 * 388
        mult = 0.75 + (fc.score / 100) * 0.70
        daily_rev = int(base_rev * mult)
        running_sum += daily_rev
        labels.append(d.strftime("%b %-d"))
        projected.append(daily_rev)
    avg_val = int(running_sum / 90)
    return {"labels": labels, "projected": projected, "avg": [avg_val] * 90, "avg_val": avg_val}


def _v2_kpis(check_in: date, room_rates: list) -> dict:
    total_rooms = V2_PROPERTY["total_rooms"]
    avg_rate = sum(r["price"] for r in room_rates) / len(room_rates) if room_rates else 388
    revpar = int(avg_rate * 0.75)
    premium_count = sum(1 for r in room_rates if r["delta_sign"] == "up")
    events_today = _v2_demand.get_events_for_date(check_in)
    active_event = events_today[0]["name"] if events_today else "None"
    fc_today = _v2_demand.forecast(check_in)
    pressure = max(1, min(10, int(fc_today.score / 10)))
    pressure_label = "Low" if pressure <= 3 else "Normal" if pressure <= 6 else "High" if pressure <= 8 else "Critical"
    return {
        "avg_rate":       int(avg_rate),
        "revpar":         revpar,
        "total_rooms":    total_rooms,
        "premium_rooms":  premium_count,
        "active_event":   active_event,
        "check_in_date":  check_in.isoformat(),
        "pressure_score": pressure,
        "pressure_label": pressure_label,
    }


def _v2_market_intelligence() -> dict:
    snap  = _v2_scraper.get_current_snapshot()
    drops = _v2_scraper.detect_rate_drops()
    rows = []
    for comp in V2_COMPETITORS:
        rate_now = snap.get(comp["name"], 0)
        rows.append({
            "name":      comp["name"],
            "rate_now":  f"${rate_now}" if rate_now else "—",
            "rate_14d":  "—",
            "rate_30d":  "—",
            "trend":     "—",
        })
    return {"rows": rows, "drops": drops}


def _v2_competitor_7day(check_in: date) -> dict:
    snap7 = _v2_scraper.get_7day_snapshot(check_in)
    cal = _v2_calendar(check_in, 7)
    anch_rates = [c["waterfront_rate"] for c in cal]
    snap7["competitors"]["Anchorage 1770 Inn (avg)"] = anch_rates
    snap7["avail"] = {c["name"]: c["avail_color"] for c in V2_COMPETITORS}
    snap7["property_avg"] = anch_rates
    return snap7


# NOTE — v2_dashboard HTML route retired 2026-05-18.
# Flask is now a pure JSON API. React app at :5173 is the only UI.
# Helpers above (_v2_*) are kept because the new /api/* endpoints below
# call into them.

@app.route("/")
def root_redirect():
    """Root no longer serves HTML — point developers at the React app."""
    return jsonify({
        "service":   "TGC Pricing Engine API",
        "ui_url":    "http://localhost:5173",
        "endpoints": [r.rule for r in app.url_map.iter_rules() if r.rule.startswith("/api")],
    })


@app.route("/api/rates")
def v2_api_rates():
    check_in_str = request.args.get("date", date.today().isoformat())
    return jsonify(_v2_daily_rates(date.fromisoformat(check_in_str)))


@app.route("/api/calendar")
def v2_api_calendar():
    check_in_str = request.args.get("date", date.today().isoformat())
    days = int(request.args.get("days", 90))
    return jsonify(_v2_calendar(date.fromisoformat(check_in_str), days))


@app.route("/api/events")
def v2_api_events():
    return jsonify(_v2_upcoming_events())


# ── Section F — Events Intelligence ────────────────────────────────────

def _categorize_event(name: str) -> str:
    nl = name.lower()
    if any(w in nl for w in ["festival", "fair", "gullah", "music", "film", "shrimp"]):
        return "Festival"
    if any(w in nl for w in ["graduation", "military", "mcrd", "uscb", "parris"]):
        return "Military/Academic"
    if any(w in nl for w in ["market", "art walk", "parade", "first friday"]):
        return "Community"
    if any(w in nl for w in ["4th", "memorial", "labor", "thanksgiving", "holiday", "mlk", "martin luther"]):
        return "Holiday"
    return "Event"


def _event_action_plan(ev: dict, days_away: int, nudge_pct: int, proj_occ: float) -> str:
    name = ev["name"]
    if days_away <= 0:
        return f"{name} is happening now. Monitor walk-in demand and last-minute booking pace."
    if days_away <= 7:
        return (f"{name} is {days_away} days away. Apply {nudge_pct}% rate premium "
                f"immediately if not already set. Consider 2-night minimum stay.")
    if days_away <= 30:
        return (f"{name} in {days_away} days. Set {nudge_pct}% rate premium. "
                f"Target {proj_occ*100:.0f}% occupancy. Send email campaign to "
                f"lapsed guests this week.")
    if days_away <= 90:
        return (f"{name} in {days_away} days. Begin rate ramp — raise "
                f"{nudge_pct // 2}% now, full {nudge_pct}% by {days_away - 30} "
                f"days out. Set 2-night minimum for the weekend.")
    return (f"{name} in {days_away} days. Advance planning: set rate calendar "
            f"placeholders, activate promotional packages targeting this audience.")


def _event_rate_status(ev: dict, ev_date: date) -> str:
    """premium_applied | needs_attention | not_yet_set"""
    if "water festival" in ev["name"].lower():
        return "premium_applied"
    if (ev_date - date.today()).days <= 30:
        return "needs_attention"
    return "not_yet_set"


@app.route("/api/events/intelligence")
def v2_api_events_intelligence():
    """Full-year event intel with revenue impact + action plans + status."""
    from config.settings import KNOWN_ANNUAL_EVENTS
    today = date.today()
    total_rooms = V2_PROPERTY["total_rooms"]
    out: list = []
    for ev in KNOWN_ANNUAL_EVENTS:
        for year in (today.year, today.year + 1):
            try:
                ev_date = date(year, ev["month"], ev["day"])
            except ValueError:
                continue
            days_away = (ev_date - today).days
            if days_away < -7:
                continue
            duration  = ev.get("duration_days", 1)
            nudge_pct = ev["pricing_nudge"]

            avg_base_rate = 380
            boosted_rate  = avg_base_rate * (1 + nudge_pct / 100)
            projected_occ = min(0.97, 0.75 + (nudge_pct / 100) * 0.8)
            nightly_rev   = int(total_rooms * projected_occ * boosted_rate)
            event_total_rev = nightly_rev * duration

            urgency = ("immediate" if 0 < days_away <= 21
                       else "upcoming" if days_away <= 60
                       else "planning" if days_away <= 180
                       else "horizon")

            out.append({
                "id":                       f"{ev['name'].lower().replace(' ', '_').replace('/','_')}_{year}",
                "name":                     ev["name"],
                "date":                     ev_date.isoformat(),
                "end_date":                 (ev_date + timedelta(days=duration - 1)).isoformat(),
                "days_away":                days_away,
                "duration_days":            duration,
                "month":                    ev_date.strftime("%B"),
                "month_num":                ev_date.month,
                "pricing_nudge_pct":        nudge_pct,
                "projected_occupancy_pct":  round(projected_occ * 100, 1),
                "projected_nightly_rev":    nightly_rev,
                "projected_event_total_rev": event_total_rev,
                "source":                   ev.get("source", "Tourist Board"),
                "category":                 _categorize_event(ev["name"]),
                "action_plan":              _event_action_plan(ev, days_away, nudge_pct, projected_occ),
                "rate_status":              _event_rate_status(ev, ev_date),
                "urgency":                  urgency,
            })
    out.sort(key=lambda x: x["days_away"] if x["days_away"] >= 0 else 999)
    return jsonify(out)


@app.route("/api/forecast")
def v2_api_forecast():
    check_in_str = request.args.get("date", date.today().isoformat())
    return jsonify(_v2_90day_forecast(date.fromisoformat(check_in_str)))


# ── Section E — Dual confirmed vs projected revenue forecast ──────────

def _generate_demo_bookings(start: date, days: int = 90) -> list:
    """
    Synthetic advance bookings shaped like real PMS advance pace:
      - 7 days out:    85% booked
      - 8-30 days:     55%
      - 31-60 days:    30%
      - 61-90 days:    15%
      - Water Festival Jul 17-26: 70%
      - First week of July:        50%
      - Rest of July:              40%
    """
    import random as _r
    rng = _r.Random(20260519)
    total_rooms = V2_PROPERTY["total_rooms"]
    bookings: list = []
    for i in range(days):
        d = start + timedelta(days=i)
        days_out = (d - date.today()).days

        # Base pace by lead time
        if days_out <= 7:                pace = 0.85
        elif days_out <= 30:             pace = 0.55
        elif days_out <= 60:             pace = 0.30
        else:                            pace = 0.15

        # July overrides
        if d.month == 7:
            if 17 <= d.day <= 26:        pace = 0.70   # Water Festival
            elif d.day <= 7:             pace = 0.50
            else:                        pace = 0.40

        n_rooms_booked = max(0, min(total_rooms, round(total_rooms * pace + rng.gauss(0, 0.7))))
        # Representative rate at this date
        fc  = _v2_demand.forecast(d)
        rep = next((r for r in V2_ROOM_TYPES if "waterfront" in r["id"]), V2_ROOM_TYPES[0])
        rec = _v2_rate.recommend(rep, fc.score, fc.label, fc.drivers, fc.confidence, None, d)
        rate = float(rec.recommended_rate)

        for n in range(n_rooms_booked):
            los = rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
            bookings.append({
                "check_in":   d,
                "check_out":  d + timedelta(days=los),
                "rate":       rate,
                "los":        los,
            })
    return bookings


@app.route("/api/forecast/dual")
def v2_api_forecast_dual():
    """90-day dual revenue forecast: confirmed vs projected additional."""
    try:
        check_in = date.fromisoformat(request.args.get("date", date.today().isoformat()))
    except ValueError:
        check_in = date.today()

    total_rooms = V2_PROPERTY["total_rooms"]
    labels:    list = []
    confirmed: list = []
    projected: list = []
    conf_occ:  list = []
    proj_occ:  list = []

    bookings = _generate_demo_bookings(check_in, 90)

    for i in range(90):
        d = check_in + timedelta(days=i)
        labels.append(d.strftime("%b %-d"))

        # Confirmed: rooms already booked for this date
        day_b = [b for b in bookings if b["check_in"] <= d < b["check_out"]]
        confirmed_rooms = min(total_rooms, len(day_b))
        confirmed_rev   = sum(b["rate"] for b in day_b[:confirmed_rooms])
        confirmed.append(int(confirmed_rev))
        conf_occ.append(round(confirmed_rooms / total_rooms * 100, 1))

        # Projected additional fill
        fc = _v2_demand.forecast(d)
        days_out = (d - date.today()).days
        if days_out <= 7:                fill = 0.95
        elif days_out <= 30:             fill = 0.80 + (fc.score / 1000)
        elif days_out <= 60:             fill = 0.65 + (fc.score / 1000)
        else:                            fill = 0.50 + (fc.score / 1000)
        if fc.event_name:                fill = min(0.98, fill * 1.15)
        projected_total_occ = min(fill, 1.0)
        additional_rooms = max(0, int(projected_total_occ * total_rooms) - confirmed_rooms)

        rep = next((r for r in V2_ROOM_TYPES if "waterfront" in r["id"]), V2_ROOM_TYPES[0])
        rec = _v2_rate.recommend(rep, fc.score, fc.label, fc.drivers, fc.confidence, None, d)
        additional_rev = int(additional_rooms * rec.recommended_rate)
        projected.append(additional_rev)
        proj_occ.append(round(projected_total_occ * 100, 1))

    return jsonify({
        "labels":                   labels,
        "confirmed_revenue":        confirmed,
        "projected_additional":     projected,
        "total_projected":          [c + p for c, p in zip(confirmed, projected)],
        "confirmed_occupancy_pct":  conf_occ,
        "projected_occupancy_pct":  proj_occ,
        "avg_confirmed_daily":      int(sum(confirmed) / 90),
        "avg_total_daily":          int(sum(c + p for c, p in zip(confirmed, projected)) / 90),
        "summary": {
            "confirmed_90day_total":  sum(confirmed),
            "projected_90day_total":  sum(projected),
            "combined_90day_total":   sum(confirmed) + sum(projected),
        },
        "monthly": _v2_monthly_summary(check_in, confirmed, projected, conf_occ, proj_occ),
    })


def _v2_monthly_summary(check_in: date, confirmed: list, projected: list,
                        conf_occ: list, proj_occ: list) -> list:
    """Aggregate the 90-day series into monthly buckets for the table."""
    from collections import defaultdict
    by_month: dict = defaultdict(lambda: {"conf": 0, "proj": 0, "occ_sum": 0.0, "days": 0, "wf": False})
    for i in range(90):
        d = check_in + timedelta(days=i)
        key = d.strftime("%Y-%m")
        b = by_month[key]
        b["conf"]    += confirmed[i]
        b["proj"]    += projected[i]
        b["occ_sum"] += proj_occ[i]
        b["days"]    += 1
        if d.month == 7 and 17 <= d.day <= 26:
            b["wf"] = True

    out: list = []
    for key in sorted(by_month):
        b = by_month[key]
        year, mo = key.split("-")
        mo_name = date(int(year), int(mo), 1).strftime("%b")
        out.append({
            "month_key":      key,
            "month_label":    mo_name,
            "confirmed":      b["conf"],
            "projected":      b["proj"],
            "combined":       b["conf"] + b["proj"],
            "projected_occ":  round(b["occ_sum"] / max(1, b["days"]), 1),
            "is_water_fest":  b["wf"],
            "days":           b["days"],
        })
    return out


@app.route("/api/competitors")
def v2_api_competitors():
    check_in_str = request.args.get("date", date.today().isoformat())
    return jsonify(_v2_competitor_7day(date.fromisoformat(check_in_str)))


@app.route("/api/competitors/by-room-type")
def v2_api_competitors_by_room_type():
    """Room-type-aware competitive comparison (Section C)."""
    from config.settings import (
        COMPETITOR_ROOM_TYPES, OUR_ROOM_CATEGORIES,
        COMPETITORS as _C_LIST, ROOM_TYPES,
    )
    room_cat     = request.args.get("room_category", "waterfront")
    check_in_str = request.args.get("date", date.today().isoformat())
    days         = max(1, min(int(request.args.get("days", 14)), 30))
    try:
        check_in = date.fromisoformat(check_in_str)
    except ValueError:
        check_in = date.today()

    our_cat = next((c for c in OUR_ROOM_CATEGORIES if c["id"] == room_cat), None)
    if not our_cat:
        return jsonify({"error": "Invalid room category"}), 400

    dates   = [check_in + timedelta(days=i) for i in range(days)]
    labels  = [d.strftime("%a %b %-d") for d in dates]

    # Our rates for this room category (representative room = first in category)
    rep_room = next((r for r in ROOM_TYPES if r["id"] == our_cat["room_ids"][0]), ROOM_TYPES[0])
    our_rates = []
    for d in dates:
        fc  = _v2_demand.forecast(d)
        rec = _v2_rate.recommend(rep_room, fc.score, fc.label, fc.drivers,
                                  fc.confidence, None, d)
        our_rates.append(int(rec.recommended_rate))

    # Competitor rates for the equivalent room type
    competitors_out: list = []
    for comp in _C_LIST:
        name      = comp["name"]
        equiv     = (COMPETITOR_ROOM_TYPES.get(name) or {}).get(room_cat)
        snap7     = _v2_scraper.get_7day_snapshot(check_in)
        blended   = snap7["competitors"].get(name, [300] * 7)
        # Stretch the 7-day base rates across the requested window
        extended  = (blended * ((days // 7) + 2))[:days]
        entry = {
            "name":             name,
            "tier":             comp.get("tier", "Direct Boutique Competitor"),
            "distance":         comp.get("distance_miles"),
            "tripadvisor":      comp.get("tripadvisor_rating"),
            "avail_color":      comp.get("avail_color", "gray"),
            "has_equivalent":   equiv is not None,
            "comp_room_name":   equiv["comp_room_name"] if equiv else None,
            "comp_room_notes":  equiv["notes"] if equiv else None,
            "no_equivalent_msg": (None if equiv
                                   else f"{name} has no {our_cat['label']} equivalent"),
        }
        if equiv:
            premium = equiv.get("rate_premium_vs_base", 0) or 0
            entry["rates"] = [int(r * (1 + premium)) for r in extended]
        else:
            entry["rates"] = [None] * days
        competitors_out.append(entry)

    # Per-date position vs comp set average
    position_by_date: list = []
    for i, our_r in enumerate(our_rates):
        comp_rates = [c["rates"][i] for c in competitors_out if c["rates"][i] is not None]
        if comp_rates:
            avg = sum(comp_rates) / len(comp_rates)
            pct = (our_r - avg) / avg
            position_by_date.append({
                "date":       dates[i].isoformat(),
                "our_rate":   our_r,
                "comp_avg":   int(avg),
                "comp_min":   min(comp_rates),
                "comp_max":   max(comp_rates),
                "pct_vs_avg": round(pct * 100, 1),
                "position":   "Premium" if pct > 0.12
                              else "Below Market" if pct < -0.12
                              else "At Market",
            })
        else:
            position_by_date.append({
                "date":     dates[i].isoformat(),
                "our_rate": our_r, "comp_avg": None, "position": "No data",
            })

    return jsonify({
        "room_category":    room_cat,
        "our_room_label":   our_cat["label"],
        "our_description":  our_cat["description"],
        "our_base_rate":    our_cat["base_rate"],
        "icon":             our_cat.get("icon"),
        "dates":            [d.isoformat() for d in dates],
        "date_labels":      labels,
        "our_rates":        our_rates,
        "competitors":      competitors_out,
        "position_by_date": position_by_date,
    })


@app.route("/api/health")
def v2_api_health():
    return jsonify({"status": "ok", "property": V2_PROPERTY["name"]})


# ── New JSON-only endpoints (Section B4) ────────────────────────────

@app.route("/api/packages")
def v2_api_packages():
    """Returns GUEST_PACKAGES with est_monthly_rev computed for each."""
    return jsonify(_v2_pkgs.list_with_revenue())


@app.route("/api/packages/<pkg_id>/toggle", methods=["PATCH", "POST"])
def v2_api_package_toggle(pkg_id: str):
    body = request.get_json(force=True) or {}
    active = bool(body.get("active", True))
    status = _load_packages_status()
    status[pkg_id] = "active" if active else "coming_soon"
    _save_packages_status(status)
    return jsonify({"ok": True, "id": pkg_id, "active": active})


@app.route("/api/gift-shop")
def v2_api_gift_shop():
    """Returns GIFT_SHOP_CATEGORIES with margin_dollars computed for each."""
    return jsonify(_v2_shop.categories())


# ── Flexible Gift Shop store (2026-05-19) ─────────────────────────────
# Replaces the prior flat _gs_store. Categories now carry their own
# items list plus optional arrangement details (consignment_details,
# resell_details). One in-memory store; swap in a DB query layer in
# production. Items are reached via /api/gift-shop/categories/<id>/items.

from modules.data.gift_shop_seed import init_demo_gift_shop
from config.settings import (
    FULFILLMENT_TYPES as _FULFILL_TYPES,
    ARRANGEMENT_TYPES as _ARR_TYPES,
    SUGGESTED_CATEGORY_TEMPLATES as _CAT_TEMPLATES,
)

_gift_shop: dict = init_demo_gift_shop()


def _enriched_category(cat: dict) -> dict:
    """Add per-category aggregates (item count, monthly rev) for list view."""
    items        = cat.get("items", [])
    active_items = [i for i in items if i.get("active", True)]
    monthly_rev  = sum(i["price"] * i.get("monthly_units", 0) for i in active_items)
    out = {k: v for k, v in cat.items() if k != "items"}
    out.update({
        "item_count":         len(active_items),
        "total_item_count":   len(items),
        "est_monthly_rev":    int(monthly_rev),
        "est_monthly_label":  f"Est. ${int(monthly_rev):,}/mo",
    })
    return out


# ── Categories ─────────────────────────────────────────────────────

@app.route("/api/gift-shop/categories", methods=["GET"])
def api_gs_categories():
    out = [_enriched_category(c) for c in _gift_shop.values()]
    out.sort(key=lambda x: x.get("sort_order", 99))
    return jsonify(out)


@app.route("/api/gift-shop/categories", methods=["POST"])
def api_gs_create_category():
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    cat_id = (data.get("id") or
              data["name"].lower().replace(" ", "_").replace("&", "and").replace("/", "_"))
    if cat_id in _gift_shop:
        return jsonify({"error": "Category ID already exists"}), 409
    new_cat = {
        "id":                  cat_id,
        "icon":                data.get("icon", "📦"),
        "name":                data["name"],
        "description":         data.get("description", ""),
        "arrangement":         data.get("arrangement", "owned"),
        "fulfillment":         data.get("fulfillment", "in_person"),
        "margin":              float(data.get("margin", 0.50)),
        "active":              True,
        "sort_order":          len(_gift_shop) + 1,
        "notes":               data.get("notes", ""),
        "items":               [],
        "resell_details":      data.get("resell_details"),
        "consignment_details": data.get("consignment_details"),
    }
    _gift_shop[cat_id] = new_cat
    return jsonify({"success": True, "category": new_cat}), 201


@app.route("/api/gift-shop/categories/<cat_id>", methods=["PATCH"])
def api_gs_update_category(cat_id: str):
    if cat_id not in _gift_shop:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json(force=True) or {}
    for k, v in data.items():
        if k not in ("id", "items"):
            _gift_shop[cat_id][k] = v
    return jsonify({"success": True, "category": _gift_shop[cat_id]})


@app.route("/api/gift-shop/categories/<cat_id>", methods=["DELETE"])
def api_gs_delete_category(cat_id: str):
    if cat_id not in _gift_shop:
        return jsonify({"error": "Not found"}), 404
    items = _gift_shop[cat_id].get("items", [])
    force = request.args.get("force", "").lower() == "true"
    if items and not force:
        return jsonify({
            "error":      f"Cannot delete category with {len(items)} items. "
                          "Remove all items first or use force=true.",
            "item_count": len(items),
        }), 400
    del _gift_shop[cat_id]
    return jsonify({"success": True})


@app.route("/api/gift-shop/categories/templates", methods=["GET"])
def api_gs_category_templates():
    return jsonify(_CAT_TEMPLATES)


# ── Items ──────────────────────────────────────────────────────────

@app.route("/api/gift-shop/categories/<cat_id>/items", methods=["GET"])
def api_gs_get_items(cat_id: str):
    if cat_id not in _gift_shop:
        return jsonify({"error": "Not found"}), 404
    cat   = _gift_shop[cat_id]
    items = cat.get("items", [])
    enriched: list = []
    for item in items:
        rev    = item["price"] * item.get("monthly_units", 0)
        cost   = item.get("cost") if item.get("cost") is not None else item["price"] * (1 - cat.get("margin", 0.5))
        margin = (item["price"] - cost) / item["price"] if item["price"] > 0 else 0
        enriched.append({
            **item,
            "est_monthly_rev":  int(rev),
            "margin_pct":       round(margin * 100, 1),
            "category_id":      cat_id,
            "category_name":    cat["name"],
            "arrangement":      cat.get("arrangement"),
            "fulfillment":      item.get("fulfillment") or cat.get("fulfillment"),
        })
    return jsonify(enriched)


@app.route("/api/gift-shop/categories/<cat_id>/items", methods=["POST"])
def api_gs_add_item_v2(cat_id: str):
    if cat_id not in _gift_shop:
        return jsonify({"error": "Category not found"}), 404
    data = request.get_json(force=True) or {}
    for k in ("name", "price"):
        if not data.get(k):
            return jsonify({"error": f"{k} required"}), 400
    import time
    new_item = {
        "id":              f"{cat_id}_{int(time.time() * 1000)}",
        "name":            data["name"],
        "price":           float(data["price"]),
        "cost":            float(data.get("cost", 0)),
        "monthly_units":   int(data.get("monthly_units", 5)),
        "active":          bool(data.get("active", True)),
        "notes":           data.get("notes", ""),
        "vendor":          data.get("vendor", ""),
        "fulfillment":     data.get("fulfillment"),
        "is_consignment":  bool(data.get("is_consignment", False)),
        "seasonal":        bool(data.get("seasonal", False)),
        "seasonal_months": data.get("seasonal_months", []),
        "source":          "manual",
    }
    _gift_shop[cat_id]["items"].append(new_item)
    return jsonify({"success": True, "item": new_item}), 201


@app.route("/api/gift-shop/categories/<cat_id>/items/<item_id>", methods=["PATCH"])
def api_gs_update_item_v2(cat_id: str, item_id: str):
    if cat_id not in _gift_shop:
        return jsonify({"error": "Category not found"}), 404
    items = _gift_shop[cat_id]["items"]
    item  = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    data = request.get_json(force=True) or {}
    for k, v in data.items():
        if k != "id":
            if k == "price" or k == "cost":
                item[k] = float(v)
            elif k == "monthly_units":
                item[k] = int(v)
            elif k in ("active", "is_consignment", "seasonal"):
                item[k] = bool(v)
            else:
                item[k] = v
    return jsonify({"success": True, "item": item})


@app.route("/api/gift-shop/categories/<cat_id>/items/<item_id>", methods=["DELETE"])
def api_gs_delete_item_v2(cat_id: str, item_id: str):
    if cat_id not in _gift_shop:
        return jsonify({"error": "Category not found"}), 404
    items  = _gift_shop[cat_id]["items"]
    before = len(items)
    _gift_shop[cat_id]["items"] = [i for i in items if i["id"] != item_id]
    if len(_gift_shop[cat_id]["items"]) == before:
        return jsonify({"error": "Item not found"}), 404
    return jsonify({"success": True})


# ── Summary + config ───────────────────────────────────────────────

@app.route("/api/gift-shop/summary", methods=["GET"])
def api_gs_summary():
    total_rev   = 0
    total_items = 0
    cats_out: list = []
    for cat in _gift_shop.values():
        if not cat.get("active", True):
            continue
        items = [i for i in cat.get("items", []) if i.get("active", True)]
        rev   = sum(i["price"] * i.get("monthly_units", 0) for i in items)
        total_rev   += rev
        total_items += len(items)
        cats_out.append({
            "id":          cat["id"],
            "name":        cat["name"],
            "icon":        cat["icon"],
            "item_count":  len(items),
            "monthly_rev": int(rev),
        })
    return jsonify({
        "total_monthly_rev":  int(total_rev),
        "total_active_items": total_items,
        "category_count":     len(cats_out),
        "categories":         sorted(cats_out, key=lambda x: x["monthly_rev"], reverse=True),
    })


@app.route("/api/gift-shop/config", methods=["GET"])
def api_gs_config():
    return jsonify({
        "fulfillment_types":   _FULFILL_TYPES,
        "arrangement_types":   _ARR_TYPES,
        "suggested_templates": _CAT_TEMPLATES,
    })


@app.route("/api/fb-summary")
def v2_api_fb_summary():
    """Returns the monthly F&B revenue breakdown + raw FB_CONFIG."""
    return jsonify({**_v2_fb.monthly_revenue(), "config": V2_FB_CONFIG})


@app.route("/api/optimization-recommendations")
def v2_api_optimization_recs():
    """Returns midweek/rate-alert/package-opportunity recommendation cards."""
    check_in_str = request.args.get("date", date.today().isoformat())
    try:
        check_in = date.fromisoformat(check_in_str)
    except ValueError:
        check_in = date.today()
    room_rates = _v2_daily_rates(check_in)
    demand_range = _v2_demand.forecast_range(check_in, 90)
    events = _v2_upcoming_events()
    return jsonify(_v2_opt.generate_recommendations(
        rate_recs=[{"room_id": r["id"], "recommended_rate": r["price"],
                    "demand_score": r["demand_score"], "target_date": check_in_str}
                   for r in room_rates],
        demand_forecasts=demand_range,
        events=events,
        comp_snapshot=_v2_scraper.get_current_snapshot(),
    ))


@app.route("/api/property-config")
def v2_api_property_config():
    """Returns the current property + plan_tier + active feature gates."""
    tier = V2_PROPERTY.get("plan_tier", "professional")
    return jsonify({
        "property":  V2_PROPERTY,
        "plan_tier": tier,
        "features":  V2_FEATURE_GATES.get(tier, V2_FEATURE_GATES["professional"]),
        "all_tiers": V2_FEATURE_GATES,
    })


# ── Package Intelligence (Section B — national packages + recs) ──────

from modules.hospitality.package_intelligence import (
    PackageIntelligenceEngine, NATIONAL_PACKAGES as _NATIONAL_PACKAGES,
)


def _get_package_engine() -> PackageIntelligenceEngine:
    return PackageIntelligenceEngine(
        property_config=V2_PROPERTY,
        competitor_data=V2_COMPETITORS,
    )


@app.route("/api/packages/national")
def api_packages_national():
    """All 20 national packages with per-property fit_score + est revenue."""
    return jsonify(_get_package_engine().get_top_20_ranked())


@app.route("/api/packages/recommendations")
def api_packages_recommendations():
    """
    GET — Auto-recommend 5-10 packages (or use ?selected=id1,id2,... selections).
    """
    sel = request.args.get("selected", "").strip()
    selected_ids = [s for s in sel.split(",") if s] if sel else None
    return jsonify(_get_package_engine().recommend_packages(selected_ids))


@app.route("/api/packages/competitive-comparison")
def api_packages_competitive_comparison():
    """For every national package, show which local competitors offer it + gap analysis."""
    eng = _get_package_engine()
    out: list = []
    for pkg in eng.get_top_20_ranked():
        recommended_price = eng._recommend_price(pkg)
        # Inject for rationale function (it reads pkg["recommended_price"])
        pkg_with_price = {**pkg, "recommended_price": recommended_price}
        rationale = eng._pricing_rationale(pkg_with_price)
        cnt = len(pkg["competitors_offering"])
        gap = ("Differentiator"     if cnt == 0
               else "Low competition" if cnt <= 2
               else "Competitive"     if cnt <= 5
               else "Saturated")
        out.append({
            "package_id":           pkg["id"],
            "package_name":         pkg["name"],
            "icon":                 pkg["icon"],
            "category":             pkg["category"],
            "national_avg":         pkg["national_avg_upsell"],
            "recommended_price":    recommended_price,
            "competitors_offering": pkg["competitors_offering"],
            "competitor_count":     cnt,
            "competitor_avg_price": pkg["competitor_avg_price"],
            "competitive_gap":      gap,
            "your_opportunity":     rationale,
            "fit_score":            pkg["fit_score"],
            "fit_label":            pkg["fit_label"],
        })
    return jsonify(out)


@app.route("/api/packages/active", methods=["GET"])
def api_packages_active():
    """Innkeeper's currently active packages (driven from GUEST_PACKAGES in settings)."""
    from config.settings import GUEST_PACKAGES
    total_rooms = V2_PROPERTY["total_rooms"]
    out: list = []
    for pkg in GUEST_PACKAGES:
        eligible = len(pkg["room_restriction"]) if pkg.get("room_restriction") else total_rooms
        monthly  = int(eligible * 0.75 * 30 * pkg["take_rate"] * pkg["upsell_price"])
        out.append({
            **pkg,
            "est_monthly_rev":   monthly,
            "est_monthly_label": f"Est. ${monthly:,}/mo @ {int(pkg['take_rate']*100)}% take rate",
        })
    return jsonify(out)


@app.route("/api/packages/active", methods=["PATCH"])
def api_packages_active_toggle():
    """Toggle a package active/inactive — persists via packages_status.json."""
    body = request.get_json(force=True) or {}
    pid = body.get("id")
    active = bool(body.get("active", False))
    if not pid:
        return jsonify({"error": "id required"}), 400
    status = _load_packages_status()
    status[pid] = "active" if active else "coming_soon"
    _save_packages_status(status)
    return jsonify({"success": True, "id": pid, "active": active})


@app.route("/api/package-toggle", methods=["POST"])
def v2_api_pkg_toggle():
    body = request.get_json(force=True) or {}
    pid = body.get("id"); active = bool(body.get("active", False))
    status = _load_packages_status()
    status[pid] = "active" if active else "coming_soon"
    _save_packages_status(status)
    return jsonify({"ok": True, "id": pid, "active": active})


# NOTE — /legacy demo dashboard retired 2026-05-18.
# Flask serves no HTML pages anymore (except wifi.html which is a
# captive-portal flow, not a dashboard).


@app.route("/api/dashboard")
def dashboard_data():
    date_str = request.args.get("date", "")
    try:
        report_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        report_date = date.today()

    occ      = 0.75
    date_key = report_date.isoformat()

    day_df = _cached(f"rates_{date_key}", lambda: _engine.generate_daily_report(
        target_date=report_date, occupancy_rate=occ
    ))
    day_rates = _format_room_rates(day_df, report_date)

    cal_df = _cached("calendar_90d", lambda: _engine.generate_pricing_calendar(
        days_ahead=90, base_occupancy=occ
    ))

    comp_7day = _cached(f"comp_{date_key}", lambda: _build_competitor_comparison(
        days=7, start_date=report_date
    ))

    events = _upcoming_events(days=60, start_date=report_date)

    forecast = _cached("forecast_90d", lambda: _build_revenue_forecast(cal_df))

    optimizations = _cached("optimizations", lambda: _optimizer.analyze(cal_df, occ))

    return jsonify({
        "today_rates":           day_rates,
        "competitor_comparison": comp_7day,
        "upcoming_events":       events,
        "revenue_forecast":      forecast,
        "optimizations":         _format_optimizations(optimizations),
        "summary": {
            "avg_rate":       round(sum(r["rate"] for r in day_rates) / len(day_rates), 2),
            "revpar":         round(sum(r["rate"] for r in day_rates) * occ / len(day_rates), 2),
            "active_events":  sum(1 for r in day_rates if r["active_events"]),
            "rooms_premium":  sum(1 for r in day_rates if r["status"] == "premium"),
            "rooms_hold":     sum(1 for r in day_rates if r["status"] == "hold"),
            "rooms_discount": sum(1 for r in day_rates if r["status"] == "discount"),
        },
        "report_date":  report_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })


@app.route("/api/market-intelligence")
def market_intelligence():
    data = _cached("market_intel", lambda: _scraper.get_compression_data(forward_days=30))
    return jsonify(data)


@app.route("/api/packages")
def packages():
    status = _load_packages_status()
    result = []
    for pkg_id, cfg in PACKAGES_CONFIG.items():
        monthly_rev = round(
            cfg["eligible_rooms_count"] * 30 * 0.75 * cfg["take_rate"] * cfg["premium"], 0
        )
        result.append({
            "id":              pkg_id,
            "status":          status.get(pkg_id, "active"),
            "monthly_revenue": monthly_rev,
            **cfg,
        })
    return jsonify(result)


@app.route("/api/packages/<pkg_id>/toggle", methods=["POST"])
def toggle_package(pkg_id: str):
    if pkg_id not in PACKAGES_CONFIG:
        return jsonify({"error": "Unknown package"}), 404
    status = _load_packages_status()
    status[pkg_id] = "coming_soon" if status.get(pkg_id) == "active" else "active"
    _save_packages_status(status)
    return jsonify({"id": pkg_id, "status": status[pkg_id]})


@app.route("/api/settings/competitors", methods=["GET"])
def get_competitor_settings():
    return jsonify(_load_competitor_settings())


@app.route("/api/settings/competitors", methods=["POST"])
def save_competitor_settings():
    data = request.get_json(force=True) or {}
    existing = _load_competitor_settings()
    existing.update({k: v for k, v in data.items() if k in ("search_radius_miles", "property")})
    if "competitors" in data:
        existing["competitors"] = data["competitors"]
    _save_competitor_settings(existing)
    _invalidate("comp_")
    return jsonify({"ok": True})


@app.route("/api/settings/competitors/add", methods=["POST"])
def add_competitor():
    body    = request.get_json(force=True) or {}
    cfg     = _load_competitor_settings()
    new_key = body.get("key") or body["name"].lower().replace(" ", "_")
    cfg["competitors"].append({
        "key":               new_key,
        "name":              body.get("name", ""),
        "address":           body.get("address", ""),
        "distance_miles":    body.get("distance_miles"),
        "estimated_rooms":   body.get("estimated_rooms"),
        "rate_range_low":    body.get("rate_range_low"),
        "rate_range_high":   body.get("rate_range_high"),
        "url_hint":          body.get("url_hint", ""),
        "active":            True,
    })
    _save_competitor_settings(cfg)
    return jsonify({"ok": True, "key": new_key})


@app.route("/api/settings/competitors/<key>", methods=["DELETE"])
def remove_competitor(key: str):
    cfg = _load_competitor_settings()
    cfg["competitors"] = [c for c in cfg["competitors"] if c["key"] != key]
    _save_competitor_settings(cfg)
    return jsonify({"ok": True})


@app.route("/export")
def export_csv():
    cal_df = _engine.generate_pricing_calendar(days_ahead=90, base_occupancy=0.75)
    buf    = io.StringIO()
    cal_df.to_csv(buf, index=False)
    buf.seek(0)
    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="anchorage_1770_pricing_{date.today().isoformat()}.csv"'
    )
    return resp


# ─────────────────────────────────────────────────────────────────────────────
#  Data formatters
# ─────────────────────────────────────────────────────────────────────────────

def _format_room_rates(df, report_date: date) -> List[Dict[str, Any]]:
    tier_icons = {"cottage": "🏡", "waterfront": "🌊", "water_view": "🔭", "garden": "🌿"}
    rooms = []
    for _, row in df.iterrows():
        rate, rack_mid, rack_low = float(row["rate"]), float(row["rack_mid"]), float(row["rack_low"])
        if rate > rack_mid * 1.05:
            status, status_label = "premium", f"+{row['rate_vs_rack_pct']}% vs rack"
        elif rate >= rack_low * 0.99:
            status, status_label = "hold", "At rack rate"
        else:
            status, status_label = "discount", f"{row['rate_vs_rack_pct']}% vs rack"

        events = row.get("active_events", [])
        if isinstance(events, str):
            events = [e.strip() for e in events.split(";") if e.strip()]

        rooms.append({
            "room_id":       row["room_id"],
            "room_name":     row["room_name"],
            "tier":          row["tier"],
            "tier_icon":     tier_icons.get(row["tier"], "🏨"),
            "rate":          rate,
            "rack_low":      rack_low,
            "rack_high":     float(row["rack_high"]),
            "rack_mid":      rack_mid,
            "status":        status,
            "status_label":  status_label,
            "vs_rack_pct":   float(row["rate_vs_rack_pct"]),
            "vs_comp_pct":   float(row.get("rate_vs_comp_pct", 0)),
            "active_events": events,
            "reasoning":     str(row.get("reasoning", "")),
        })
    return rooms


def _build_competitor_comparison(days: int = 7, start_date: Optional[date] = None) -> Dict[str, Any]:
    base         = start_date or date.today()
    dates: List[str]              = []
    anchorage_avg: List[float]    = []
    competitors: Dict[str, List]  = {}
    availability: Dict[str, List] = {}

    for offset in range(days):
        check_in = base + timedelta(days=offset)
        dates.append(check_in.strftime("%a %b %-d"))

        room_rates = [_engine.calculate_room_rate(rid, check_in, 0.75)["rate"] for rid in ROOM_INVENTORY]
        anchorage_avg.append(round(sum(room_rates) / len(room_rates), 2))

        comp_rates = _engine.get_competitor_rates(check_in)
        for name, rate in comp_rates.items():
            competitors.setdefault(name, []).append(rate)

        avail_snap = _scraper.get_availability_snapshot(check_in)
        for name, info in avail_snap.items():
            availability.setdefault(name, []).append({
                "indicator":   info["indicator"],
                "est_occ":     info["est_occupancy"],
                "status":      info["availability_status"],
            })

    return {
        "dates":         dates,
        "anchorage_avg": anchorage_avg,
        "competitors":   competitors,
        "availability":  availability,
    }


def _upcoming_events(days: int = 60, start_date: Optional[date] = None) -> List[Dict[str, Any]]:
    base = start_date or date.today()
    seen: Dict[str, Dict] = {}
    for offset in range(days):
        check_date = base + timedelta(days=offset)
        mult, active = _engine.get_event_multiplier(check_date)
        for evt_name in active:
            if evt_name not in seen:
                seen[evt_name] = {
                    "event":      evt_name,
                    "first_date": check_date.isoformat(),
                    "display":    check_date.strftime("%b %-d"),
                    "multiplier": mult,
                    "impact_pct": round((mult - 1.0) * 100, 1),
                    "days_away":  offset,
                }
    return sorted(seen.values(), key=lambda x: x["first_date"])[:25]


def _build_revenue_forecast(cal_df) -> Dict[str, Any]:
    cal_df = cal_df.copy()
    cal_df["projected_rev"] = cal_df["recommended_rate"] * 0.75
    daily = (
        cal_df.groupby("date")
        .agg(total_rev=("projected_rev", "sum"), avg_rate=("recommended_rate", "mean"))
        .reset_index()
        .sort_values("date")
    )
    labels = []
    for i, row in enumerate(daily.itertuples()):
        d = date.fromisoformat(row.date)
        labels.append(d.strftime("%b %-d") if d.weekday() == 0 or i == 0 else "")
    return {
        "dates":     daily["date"].tolist(),
        "labels":    labels,
        "revenues":  daily["total_rev"].round(2).tolist(),
        "avg_rates": daily["avg_rate"].round(2).tolist(),
    }


def _format_optimizations(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "midweek_specials":            raw.get("midweek_specials", [])[:6],
        "packages":                    raw.get("packages", [])[:8],
        "total_midweek_windows":       raw.get("total_midweek_windows", 0),
        "total_package_opportunities": raw.get("total_package_opportunities", 0),
        "estimated_total_uplift":      raw.get("estimated_total_uplift", 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Competitor Discovery API (serves the React dashboard)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/discover-competitors")
def api_discover_competitors():
    """
    GET /api/discover-competitors?slug=anchorage-1770-demo&radius=25&address=...

    Runs live Google Places competitor discovery and returns grouped results.
    Upserts to competitor_properties and seeds rates for new discoveries.
    """
    from flask import Response
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        from engine.competitor_discovery import (
            discover_competitors_google,
            _BEAUFORT_TEXT_SEARCHES,
        )
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError as exc:
        return jsonify({"error": f"Engine import failed: {exc}"}), 500

    slug         = request.args.get("slug",    "anchorage-1770-demo")
    radius       = float(request.args.get("radius",  "25"))
    address_arg  = request.args.get("address", "")

    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key  = os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {"apikey": service_key, "Authorization": f"Bearer {service_key}",
            "Prefer": "count=none"}

    # Look up property_id from slug
    tenants = requests.get(
        f"{supabase_url}/rest/v1/tenants",
        headers=hdrs,
        params={"slug": f"eq.{slug}", "select": "id"},
        timeout=10,
    ).json()
    if not tenants:
        return jsonify({"error": f"Tenant {slug!r} not found"}), 404

    tid   = tenants[0]["id"]
    props = requests.get(
        f"{supabase_url}/rest/v1/properties",
        headers=hdrs,
        params={"tenant_id": f"eq.{tid}", "select": "id,name,address,city,state"},
        timeout=10,
    ).json()
    if not props:
        return jsonify({"error": "No property found for tenant"}), 404

    prop     = props[0]
    pid      = prop["id"]
    address  = address_arg or f"{prop.get('address','')}, {prop.get('city','')}, {prop.get('state','')}"

    # Use Beaufort text searches when this is the Beaufort property
    text_searches = _BEAUFORT_TEXT_SEARCHES if "beaufort" in address.lower() else None

    try:
        result = discover_competitors_google(
            property_id=pid,
            property_address=address,
            radius_miles=radius,
            text_searches=text_searches,
        )
    except Exception as exc:
        logger.exception("Discovery failed")
        return jsonify({"error": str(exc)}), 500

    # Make serialisable (convert None ratings etc)
    def _clean(obj):
        if isinstance(obj, list):
            return [_clean(i) for i in obj]
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        return obj

    return jsonify(_clean(result))


# ─────────────────────────────────────────────────────────────────────────────
#  Stripe Billing (Phase 10)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/billing/plans", methods=["GET"])
def api_billing_plans():
    """Return the plan catalog (used by the onboarding wizard)."""
    from engine.billing import _PLAN_CATALOG
    return jsonify({
        k: {**v, "amount": v["amount_cents"] / 100}
        for k, v in _PLAN_CATALOG.items()
    })


@app.route("/api/billing/create-subscription", methods=["POST"])
def api_billing_create_subscription():
    body = request.get_json(force=True) or {}
    for k in ("tenant_id", "plan_tier", "billing_email"):
        if not body.get(k):
            return jsonify({"error": f"{k} required"}), 400
    from engine.billing import create_subscription
    try:
        return jsonify(create_subscription(
            body["tenant_id"], body["plan_tier"], body["billing_email"],
            trial_days=int(body.get("trial_days", 0)),
        ))
    except Exception as exc:
        logger.exception("create-subscription failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/billing/cancel-subscription", methods=["POST"])
def api_billing_cancel_subscription():
    body = request.get_json(force=True) or {}
    tid = body.get("tenant_id")
    if not tid:
        return jsonify({"error": "tenant_id required"}), 400
    from engine.billing import cancel_subscription
    return jsonify(cancel_subscription(tid, immediate=bool(body.get("immediate", False))))


@app.route("/api/billing/invoices/<tenant_id>", methods=["GET"])
def api_billing_invoices(tenant_id: str):
    from engine.billing import list_invoices
    return jsonify(list_invoices(tenant_id,
                                  limit=int(request.args.get("limit", "20"))))


@app.route("/api/billing/webhook", methods=["POST"])
def api_billing_webhook():
    from engine.billing import process_webhook
    raw = request.get_data(cache=False)
    sig = request.headers.get("Stripe-Signature", "")
    result = process_webhook(raw, sig)
    return jsonify(result), (200 if not result.get("error") else 400)


@app.route("/api/billing/setup-products", methods=["POST"])
def api_billing_setup_products():
    from engine.billing import setup_stripe_products
    return jsonify(setup_stripe_products())


# ─────────────────────────────────────────────────────────────────────────────
#  SHG Management Console (Phase 9)
# ─────────────────────────────────────────────────────────────────────────────
#
# Strategic dashboard for The Gracious Collection across all client
# properties. All endpoints are intentionally read-only — they aggregate
# state from tables already populated by Phases 1–8.

def _mgmt_sb():
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    return sb, {"apikey": key, "Authorization": f"Bearer {key}",
                 "Prefer": "count=none"}


@app.route("/api/management/portfolio", methods=["GET"])
def api_management_portfolio():
    """One row per active TGC property — occupancy, RevPAR, pending count,
    autopilot status, last_sync, plan tier, MRR."""
    sb, h = _mgmt_sb()

    props = requests.get(f"{sb}/rest/v1/properties", headers=h,
                         params={"select": "id,tenant_id,name,city,state,timezone,"
                                           "pms_type,pms_last_sync_at,channel_manager_type",
                                 "order": "name.asc"}, timeout=15).json()
    if not isinstance(props, list):
        props = []

    today = date.today()
    month_start = today.replace(day=1)
    ly_start    = month_start.replace(year=month_start.year - 1)
    ly_end      = today.replace(year=today.year - 1)

    rows: List[Dict[str, Any]] = []
    for p in props:
        pid = p["id"]; tid = p.get("tenant_id")

        # YTD + this-month occupancy + RevPAR (this year vs last year)
        ty = requests.get(f"{sb}/rest/v1/occupancy_snapshots", headers=h,
                          params={"property_id": f"eq.{pid}",
                                  "snapshot_date": f"gte.{month_start.isoformat()}",
                                  "and": f"(snapshot_date.lte.{today.isoformat()})",
                                  "select": "occupancy_rate,adr,revpar"},
                          timeout=15).json() or []
        ly = requests.get(f"{sb}/rest/v1/occupancy_snapshots", headers=h,
                          params={"property_id": f"eq.{pid}",
                                  "snapshot_date": f"gte.{ly_start.isoformat()}",
                                  "and": f"(snapshot_date.lte.{ly_end.isoformat()})",
                                  "select": "occupancy_rate,adr,revpar"},
                          timeout=15).json() or []

        def _avg(rows_: list, key: str):
            xs = [float(r[key]) for r in rows_ if r.get(key) is not None]
            return round(sum(xs)/len(xs), 4) if xs else None

        ty_occ, ly_occ = _avg(ty, "occupancy_rate"), _avg(ly, "occupancy_rate")
        ty_rp,  ly_rp  = _avg(ty, "revpar"),         _avg(ly, "revpar")

        # YTD figure independent of month filter (year-to-date)
        ytd_start = date(today.year, 1, 1)
        ytd = requests.get(f"{sb}/rest/v1/occupancy_snapshots", headers=h,
                           params={"property_id": f"eq.{pid}",
                                   "snapshot_date": f"gte.{ytd_start.isoformat()}",
                                   "and": f"(snapshot_date.lte.{today.isoformat()})",
                                   "select": "occupancy_rate,adr,revpar"},
                           timeout=15).json() or []
        ytd_occ = _avg(ytd, "occupancy_rate")
        ytd_adr = _avg(ytd, "adr")

        # Pending rate recommendations (forward-looking)
        pending = requests.get(f"{sb}/rest/v1/rate_recommendations",
                               headers={**h, "Prefer": "count=exact"},
                               params={"property_id": f"eq.{pid}",
                                       "status":      "eq.pending",
                                       "target_date": f"gte.{today.isoformat()}",
                                       "select":      "id", "limit": "1"},
                               timeout=10)
        pending_count = int((pending.headers.get("content-range", "/0").split("/")[-1]) or 0)

        # Autopilot status — any enabled config?
        ac = requests.get(f"{sb}/rest/v1/autopilot_configs", headers=h,
                          params={"property_id": f"eq.{pid}",
                                  "enabled":     "eq.true",
                                  "select":      "room_type_id"},
                          timeout=10).json() or []
        autopilot_enabled_count = len(ac)

        # Plan tier — placeholder; Anchorage = Founding Member, others = Unknown
        is_anchorage = "Anchorage" in (p.get("name") or "")
        plan_tier = "Founding Member" if is_anchorage else "Unassigned"
        mrr       = 0  # all Founding Members are free for the demo

        delta_occ_pct = None
        if ty_occ is not None and ly_occ:
            delta_occ_pct = round((ty_occ - ly_occ) / ly_occ * 100, 1)
        delta_rp_pct = None
        if ty_rp is not None and ly_rp:
            delta_rp_pct = round((ty_rp - ly_rp) / ly_rp * 100, 1)

        rows.append({
            "property_id":         pid,
            "tenant_id":           tid,
            "name":                p.get("name"),
            "location":            f"{p.get('city') or '—'}, {p.get('state') or ''}".strip(", "),
            "ytd_occupancy":       ytd_occ,
            "ytd_adr":             ytd_adr,
            "month_occupancy":     ty_occ,
            "month_occupancy_ly":  ly_occ,
            "delta_occ_pct":       delta_occ_pct,
            "month_revpar":        ty_rp,
            "month_revpar_ly":     ly_rp,
            "delta_revpar_pct":    delta_rp_pct,
            "pending_count":       pending_count,
            "autopilot_enabled_rooms": autopilot_enabled_count,
            "pms_type":            p.get("pms_type"),
            "pms_last_sync_at":    p.get("pms_last_sync_at"),
            "channel_manager_type":p.get("channel_manager_type"),
            "plan_tier":           plan_tier,
            "mrr":                 mrr,
        })

    return jsonify({
        "as_of":      datetime.now(timezone.utc).isoformat(),
        "total_mrr":  sum(r["mrr"] for r in rows),
        "properties": rows,
    })


@app.route("/api/management/revenue", methods=["GET"])
def api_management_revenue():
    """MRR / ARR / pipeline. All zero — pre-revenue, honest framing."""
    # Compute totals from the portfolio (single source of truth)
    sb, h = _mgmt_sb()
    props = requests.get(f"{sb}/rest/v1/properties", headers=h,
                         params={"select": "name"}, timeout=10).json() or []
    founding_members = sum(1 for p in props if "Anchorage" in (p.get("name") or ""))

    # 6-month trend — all zeros pre-revenue
    today = date.today()
    months = []
    for i in range(6, -1, -1):
        m = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        months.append({"label": m.strftime("%b %y"),
                        "starter": 0, "professional": 0, "enterprise": 0})

    return jsonify({
        "mrr_total":             0,
        "arr_total":             0,
        "mom_growth_pct":        0,
        "paying_clients":        0,
        "founding_members":      founding_members,
        "founding_member_target":"3–5 by Q3 2026",
        "advisory_pipeline_value":0,
        "trend":                 months,
        "by_plan_current": {
            "starter":      {"mrr": 0, "clients": 0, "price": 199},
            "professional": {"mrr": 0, "clients": 0, "price": 499},
            "enterprise":   {"mrr": 0, "clients": 0, "price": 1499},
        },
    })


@app.route("/api/management/market-intel", methods=["GET"])
def api_management_market_intel():
    """Market-wide signals from market_signals — occupancy, ADR, booking window mix."""
    sb, h = _mgmt_sb()
    market = request.args.get("market", "beaufort-sc-lowcountry")

    rows = requests.get(f"{sb}/rest/v1/market_signals", headers=h,
                         params={"market": f"eq.{market}",
                                 "select": "month,day_of_week,avg_occupancy,avg_adr,"
                                           "booking_window_0_7,booking_window_8_30,"
                                           "booking_window_31_60,booking_window_61_plus,"
                                           "event_lift,seasonal_index"},
                         timeout=15).json() or []

    by_month: Dict[int, Dict[str, list]] = {}
    for r in rows:
        m = r.get("month")
        if m is None: continue
        b = by_month.setdefault(m, {"occ": [], "adr": [], "evt": [], "bw07": [],
                                     "bw830": [], "bw3160": [], "bw61": []})
        if r.get("avg_occupancy") is not None: b["occ"].append(float(r["avg_occupancy"]))
        if r.get("avg_adr") is not None:        b["adr"].append(float(r["avg_adr"]))
        if r.get("event_lift") is not None:     b["evt"].append(float(r["event_lift"]))
        if r.get("booking_window_0_7") is not None:    b["bw07"].append(float(r["booking_window_0_7"]))
        if r.get("booking_window_8_30") is not None:   b["bw830"].append(float(r["booking_window_8_30"]))
        if r.get("booking_window_31_60") is not None:  b["bw3160"].append(float(r["booking_window_31_60"]))
        if r.get("booking_window_61_plus") is not None:b["bw61"].append(float(r["booking_window_61_plus"]))

    def _avg(xs): return round(sum(xs)/len(xs), 4) if xs else None
    monthly = []
    for m in range(1, 13):
        b = by_month.get(m, {})
        monthly.append({
            "month":         m,
            "avg_occupancy": _avg(b.get("occ", [])),
            "avg_adr":       _avg(b.get("adr", [])),
            "event_lift":    _avg(b.get("evt", [])),
            "bw_0_7":        _avg(b.get("bw07", [])),
            "bw_8_30":       _avg(b.get("bw830", [])),
            "bw_31_60":      _avg(b.get("bw3160", [])),
            "bw_61_plus":    _avg(b.get("bw61", [])),
        })

    return jsonify({"market": market, "monthly": monthly,
                     "cells_used": len(rows)})


@app.route("/api/management/acquisition-signals", methods=["GET"])
def api_management_acquisition():
    """Markets where demand exceeds supply — TGC expansion opportunity scoring."""
    sb, h = _mgmt_sb()

    # All distinct markets in market_signals
    cells = requests.get(f"{sb}/rest/v1/market_signals", headers=h,
                          params={"select": "market,avg_occupancy,avg_adr"},
                          timeout=15).json() or []
    by_market: Dict[str, Dict[str, list]] = {}
    for c in cells:
        m = c.get("market");
        if not m: continue
        d = by_market.setdefault(m, {"occ": [], "adr": []})
        if c.get("avg_occupancy") is not None: d["occ"].append(float(c["avg_occupancy"]))
        if c.get("avg_adr") is not None:        d["adr"].append(float(c["avg_adr"]))

    # Active TGC properties per market (city-state matched)
    props = requests.get(f"{sb}/rest/v1/properties", headers=h,
                          params={"select": "city,state,name"}, timeout=10).json() or []
    tgc_by_market: Dict[str, int] = {}
    for p in props:
        c = (p.get("city") or "").lower().replace(" ", "-")
        s = (p.get("state") or "").lower()
        if c and s:
            tgc_by_market[f"{c}-{s}"] = tgc_by_market.get(f"{c}-{s}", 0) + 1

    # Add Savannah GA as a watched market even if it has no signals yet
    watched = {"savannah-ga", "beaufort-sc-lowcountry"}
    all_markets = set(by_market.keys()) | watched

    rows = []
    for m in sorted(all_markets):
        occs = by_market.get(m, {}).get("occ", [])
        adrs = by_market.get(m, {}).get("adr", [])
        avg_occ = round(sum(occs)/len(occs), 4) if occs else None
        avg_adr = round(sum(adrs)/len(adrs), 2) if adrs else None
        # Prefix match — TGC's 'beaufort-sc' should count for 'beaufort-sc-lowcountry'
        tgc_n = sum(c for k, c in tgc_by_market.items()
                    if m == k or m.startswith(f"{k}-") or k.startswith(f"{m}-"))
        # Opportunity score: high occ × high ADR × inverse presence
        score = 0
        if avg_occ and avg_adr:
            score = round((avg_occ * 100) * (avg_adr / 300) * (1.0 if tgc_n == 0 else 0.5), 1)
        status = ("Active Market" if tgc_n > 0 else
                  "High Opportunity — No presence yet" if (avg_occ or 0) > 0 else
                  "Watched — Awaiting data")
        # Pretty market name
        pretty = m.replace("-sc-lowcountry", " SC").replace("-ga", " GA").replace("-sc", " SC")
        pretty = pretty.replace("-", " ").title().replace(" Sc", " SC").replace(" Ga", " GA")
        rows.append({
            "market":            m,
            "market_name":       pretty,
            "avg_occupancy":     avg_occ,
            "avg_adr":           avg_adr,
            "tgc_properties":    tgc_n,
            "tgc_clients":       tgc_n,  # one-tenant-per-property for now
            "opportunity_score": score,
            "status":            status,
        })

    rows.sort(key=lambda r: -(r["opportunity_score"] or 0))
    return jsonify({"as_of": datetime.now(timezone.utc).isoformat(),
                     "markets": rows})


@app.route("/api/management/founding-members", methods=["GET"])
def api_management_founding_members():
    """List founding-member slots — populated as members join."""
    sb, h = _mgmt_sb()
    today = date.today()
    props = requests.get(f"{sb}/rest/v1/properties", headers=h,
                          params={"select": "id,name,city,state,created_at"}, timeout=10).json() or []
    # Treat Anchorage as the founding member 1 with a synthetic start date
    members: list[dict] = []
    for p in props:
        if "Anchorage" in (p.get("name") or ""):
            try:
                created = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
                months_elapsed = max(1, ((today.year - created.year) * 12
                                         + (today.month - created.month)))
            except Exception:
                months_elapsed = 1
            members.append({
                "name":           p["name"],
                "city":           p.get("city"),
                "state":          p.get("state"),
                "start_date":     (created.date().isoformat() if created else None),
                "months_elapsed": months_elapsed,
                "data_quality_score": 92,
                "engagement_score":   88,
                "testimonial_status": "Pending request",
                "converted_to_paid":  False,
            })
            break

    # Empty slots — show 3 by default
    while len(members) < 3:
        members.append({
            "name": f"Founding Member Slot {len(members) + 1} — Available",
            "city": None, "state": None, "start_date": None,
            "months_elapsed": None, "data_quality_score": None,
            "engagement_score": None, "testimonial_status": None,
            "converted_to_paid": None, "is_slot": True,
        })

    return jsonify({"target": "3–5 founding members by Q3 2026",
                     "members": members})


@app.route("/api/management/advisory", methods=["GET"])
def api_management_advisory():
    """Advisory client tracker — empty until first engagement."""
    return jsonify({
        "engagements": [],
        "prompt": "Start your first advisory conversation",
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Autopilot + Alerts (Phase 8)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/run-autopilot", methods=["POST"])
def api_run_autopilot():
    body = request.get_json(force=True) or {}
    pid = body.get("property_id")
    if not pid:
        return jsonify({"error": "property_id required"}), 400
    from engine.autopilot import run_autopilot
    return jsonify(run_autopilot(pid, mock=bool(body.get("mock", True))))


@app.route("/api/alerts/<property_id>", methods=["GET"])
def api_alerts(property_id: str):
    from engine.autopilot import list_alerts
    unread = request.args.get("unread", "true").lower() != "false"
    limit  = int(request.args.get("limit", "50"))
    return jsonify(list_alerts(property_id, unread_only=unread, limit=limit))


@app.route("/api/dismiss-alert", methods=["POST"])
def api_dismiss_alert():
    body = request.get_json(force=True) or {}
    aid = body.get("alert_id")
    if not aid:
        return jsonify({"error": "alert_id required"}), 400
    from engine.autopilot import dismiss_alert
    return jsonify({"ok": dismiss_alert(aid)})


@app.route("/api/autopilot-config", methods=["POST"])
def api_autopilot_config():
    """Body: { tenant_id, property_id, room_type_id, enabled?, max_rate_change_pct?, ... }"""
    body = request.get_json(force=True) or {}
    for k in ("tenant_id", "property_id", "room_type_id"):
        if not body.get(k):
            return jsonify({"error": f"{k} required"}), 400
    from engine.autopilot import upsert_autopilot_config
    cfg = upsert_autopilot_config(
        body["tenant_id"], body["property_id"], body["room_type_id"],
        enabled=body.get("enabled"),
        max_rate_change_pct=body.get("max_rate_change_pct"),
        min_confidence_score=body.get("min_confidence_score"),
        autopilot_start_hour=body.get("autopilot_start_hour"),
        autopilot_end_hour=body.get("autopilot_end_hour"),
        notify_on_publish=body.get("notify_on_publish"),
        max_daily_changes=body.get("max_daily_changes"),
    )
    return jsonify(cfg)


@app.route("/api/autopilot-config/<property_id>", methods=["GET"])
def api_get_autopilot_config(property_id: str):
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    r = requests.get(f"{sb}/rest/v1/autopilot_configs",
                     headers={"apikey": key, "Authorization": f"Bearer {key}",
                              "Prefer": "count=none"},
                     params={"property_id": f"eq.{property_id}",
                             "select": "*", "order": "room_type_id.asc"},
                     timeout=15)
    if not r.ok:
        return jsonify({"error": r.text}), r.status_code
    return jsonify(r.json())


@app.route("/api/autopilot-report/<property_id>", methods=["GET"])
def api_autopilot_report(property_id: str):
    from engine.autopilot import generate_autopilot_report
    weeks = int(request.args.get("weeks", "1"))
    return jsonify(generate_autopilot_report(property_id, weeks=weeks))


@app.route("/api/run-alert-checks", methods=["POST"])
def api_run_alert_checks():
    body = request.get_json(force=True) or {}
    pid = body.get("property_id")
    if not pid:
        return jsonify({"error": "property_id required"}), 400
    from engine.autopilot import run_alert_checks
    return jsonify({"new_alerts": run_alert_checks(pid)})


# ─────────────────────────────────────────────────────────────────────────────
#  Federated Market Signals (Phase 7)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/market-aggregation", methods=["POST"])
def api_market_aggregation():
    from engine.learning import run_market_aggregation
    return jsonify(run_market_aggregation())


@app.route("/api/market-benchmarks", methods=["GET"])
def api_market_benchmarks():
    from engine.learning import get_market_benchmarks
    market = request.args.get("market", "").strip()
    if not market:
        return jsonify({"error": "market required"}), 400
    month = request.args.get("month")
    dow   = request.args.get("day_of_week")
    return jsonify(get_market_benchmarks(
        market,
        month=int(month) if month else None,
        day_of_week=int(dow) if dow else None,
    ))


# ─────────────────────────────────────────────────────────────────────────────
#  Guest CRM + Email Marketing (Phase 6)
# ─────────────────────────────────────────────────────────────────────────────
#
# Routes:
#   GET  /wifi/<slug>                — branded WiFi capture landing page
#   POST /wifi/<slug>/submit         — process WiFi capture submission
#   GET  /unsubscribe?token=...      — process unsubscribe link
#   GET  /api/campaigns/<property>   — list campaigns
#   POST /api/create-campaign        — create draft campaign
#   POST /api/send-campaign          — dispatch a campaign
#   POST /api/check-campaigns        — run demand-trigger check
#   GET  /api/guests/<property>      — list guests with segments
#   POST /api/update-segments        — recompute all guest tags
#
# WiFi routes use TENANT slug (one-property-per-tenant for now); see
# memory note — properties.slug doesn't exist.

def _tenant_property_by_slug(slug: str) -> Optional[dict]:
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}",
            "Prefer": "count=none"}
    t = requests.get(f"{sb}/rest/v1/tenants", headers=hdrs,
                      params={"slug": f"eq.{slug}",
                              "select": "id,name,slug"},
                      timeout=10).json()
    if not t:
        return None
    tid = t[0]["id"]
    p = requests.get(f"{sb}/rest/v1/properties", headers=hdrs,
                      params={"tenant_id": f"eq.{tid}",
                              "select":    "id,name,city,state,address",
                              "limit":     "1"},
                      timeout=10).json()
    if not p:
        return None
    return {"tenant": t[0], "property": p[0]}


@app.route("/wifi/<slug>")
def wifi_landing(slug: str):
    """Branded WiFi capture landing page."""
    ctx = _tenant_property_by_slug(slug)
    if not ctx:
        return render_template("wifi.html", error="Property not found", slug=slug), 404
    return render_template(
        "wifi.html",
        slug=slug,
        property_name=ctx["property"]["name"],
        property_city=ctx["property"].get("city"),
        property_state=ctx["property"].get("state"),
        error=None,
    )


@app.route("/wifi/<slug>/submit", methods=["POST"])
def wifi_submit(slug: str):
    """Process WiFi capture; upsert guest + create wifi_session."""
    ctx = _tenant_property_by_slug(slug)
    if not ctx:
        return jsonify({"error": "property not found"}), 404

    form = request.form or request.get_json(silent=True) or {}
    email = (form.get("email") or "").strip().lower()
    if not email:
        return render_template(
            "wifi.html", slug=slug,
            property_name=ctx["property"]["name"],
            property_city=ctx["property"].get("city"),
            property_state=ctx["property"].get("state"),
            error="Email is required.",
        ), 400

    from engine.crm import upsert_guest

    consent = bool(form.get("marketing_consent")) or form.get("marketing_consent") == "on"
    try:
        gid = upsert_guest(
            tenant_id=ctx["tenant"]["id"],
            property_id=ctx["property"]["id"],
            guest_data={
                "first_name":        (form.get("first_name") or "").strip(),
                "last_name":         (form.get("last_name") or "").strip(),
                "email":             email,
                "home_city":         (form.get("home_city") or "").strip(),
                "home_state":        (form.get("home_state") or "").strip().upper(),
                "marketing_consent": consent,
                "source":            "wifi",
                "tags":              ["wifi_capture"],
            },
        )
    except Exception as exc:
        logger.exception("wifi submit upsert failed")
        return jsonify({"error": str(exc)}), 500

    # Best-effort log the session
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    try:
        import hashlib as _hash
        ip_hash = _hash.sha256((request.remote_addr or "").encode()).hexdigest()[:16]
        requests.post(f"{sb}/rest/v1/wifi_sessions",
                       headers={"apikey": key, "Authorization": f"Bearer {key}",
                                "Content-Type": "application/json",
                                "Prefer": "return=minimal"},
                       json={
                           "tenant_id":   ctx["tenant"]["id"],
                           "property_id": ctx["property"]["id"],
                           "guest_id":    gid,
                           "ip_hash":     ip_hash,
                           "user_agent":  request.headers.get("User-Agent", "")[:200],
                       }, timeout=8)
    except Exception:
        pass

    return render_template(
        "wifi.html", slug=slug,
        property_name=ctx["property"]["name"],
        success_message=f"You are connected! Welcome to {ctx['property']['name']}.",
        error=None,
    )


@app.route("/unsubscribe")
def unsubscribe_handler():
    token = request.args.get("token", "")
    from engine.crm import consume_unsubscribe
    gid = consume_unsubscribe(token)
    return render_template(
        "wifi.html",
        slug="",
        unsubscribed=bool(gid),
        error=None if gid else "This unsubscribe link is invalid or expired.",
    )


@app.route("/api/campaigns/<property_id>", methods=["GET"])
def api_campaigns(property_id: str):
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    r = requests.get(f"{sb}/rest/v1/campaigns",
                     headers={"apikey": key, "Authorization": f"Bearer {key}",
                              "Prefer": "count=none"},
                     params={"property_id": f"eq.{property_id}",
                             "order":       "created_at.desc",
                             "select":      "id,name,target_segment,subject,status,"
                                            "scheduled_at,sent_at,recipient_count,"
                                            "delivered_count,opened_count,clicked_count,"
                                            "bookings_attributed,revenue_attributed,"
                                            "trigger_source,trigger_metadata,created_at"},
                     timeout=15)
    if not r.ok:
        return jsonify({"error": r.text}), r.status_code
    return jsonify(r.json())


@app.route("/api/create-campaign", methods=["POST"])
def api_create_campaign():
    from engine.crm import create_draft_campaign
    body = request.get_json(force=True) or {}
    required = ("tenant_id", "property_id", "name", "target_segment",
                "subject", "body_html")
    missing = [k for k in required if not body.get(k)]
    if missing:
        return jsonify({"error": f"missing fields: {missing}"}), 400
    cid = create_draft_campaign(
        tenant_id=body["tenant_id"], property_id=body["property_id"],
        name=body["name"], target_segment=body["target_segment"],
        subject=body["subject"], body_html=body["body_html"],
        scheduled_at=(datetime.fromisoformat(body["scheduled_at"])
                      if body.get("scheduled_at") else None),
        trigger_source=body.get("trigger_source"),
        trigger_metadata=body.get("trigger_metadata"),
    )
    if not cid:
        return jsonify({"error": "create failed"}), 500
    return jsonify({"campaign_id": cid, "status": "draft"})


@app.route("/api/send-campaign", methods=["POST"])
def api_send_campaign():
    from engine.crm import send_campaign
    body = request.get_json(force=True) or {}
    cid = body.get("campaign_id")
    if not cid:
        return jsonify({"error": "campaign_id required"}), 400
    summary = send_campaign(cid)
    if summary.get("error"):
        return jsonify(summary), 400
    return jsonify(summary)


@app.route("/api/check-campaigns", methods=["POST"])
def api_check_campaigns():
    from engine.crm import check_and_create_campaigns
    body = request.get_json(force=True) or {}
    pid = body.get("property_id")
    if not pid:
        return jsonify({"error": "property_id required"}), 400
    created = check_and_create_campaigns(pid)
    return jsonify({"created": created, "count": len(created)})


@app.route("/api/guests/<property_id>", methods=["GET"])
def api_guests(property_id: str):
    sb  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    seg    = request.args.get("segment", "").strip().lower()
    search = request.args.get("q", "").strip()
    limit  = max(1, min(int(request.args.get("limit", "200")), 1000))
    params: Dict[str, str] = {
        "property_id": f"eq.{property_id}",
        "select":      "id,first_name,last_name,home_city,home_state,"
                       "total_stays,total_nights,total_revenue,avg_rate_paid,"
                       "preferred_room_type,booking_sources,last_stay_date,"
                       "next_stay_date,tags,marketing_consent,source,created_at",
        "order":       "total_revenue.desc.nullslast",
        "limit":       str(limit),
    }
    if seg:
        params["tags"] = f"cs.{{\"{seg}\"}}"
    if search:
        s = search.replace(",", "")
        params["or"] = (f"(first_name.ilike.*{s}*,last_name.ilike.*{s}*,"
                        f"home_city.ilike.*{s}*)")
    r = requests.get(f"{sb}/rest/v1/guests",
                     headers={"apikey": key, "Authorization": f"Bearer {key}",
                              "Prefer": "count=none"},
                     params=params, timeout=15)
    if not r.ok:
        return jsonify({"error": r.text}), r.status_code
    return jsonify(r.json())


@app.route("/api/update-segments", methods=["POST"])
def api_update_segments():
    from engine.crm import update_guest_segments
    body = request.get_json(force=True) or {}
    pid = body.get("property_id"); tid = body.get("tenant_id")
    if not (pid and tid):
        return jsonify({"error": "tenant_id and property_id required"}), 400
    counts = update_guest_segments(tid, pid)
    return jsonify(counts)


# ─────────────────────────────────────────────────────────────────────────────
#  Rate Publishing API (Phase 5)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/approve-rate", methods=["POST"])
def api_approve_rate():
    """
    POST /api/approve-rate
    Body: {recommendation_id, tenant_id?, mock?}
    Publishes a single approved rate to the property's channel manager.
    """
    body = request.get_json(force=True) or {}
    rec_id = body.get("recommendation_id")
    if not rec_id:
        return jsonify({"error": "recommendation_id required"}), 400
    use_mock = bool(body.get("mock", False))
    try:
        from engine.channel.publisher import publish_approved_rate
        result = publish_approved_rate(rec_id, mock=use_mock)
        return jsonify(result.to_jsonable()), (200 if result.success else 502)
    except Exception as exc:
        logger.exception("approve-rate failed")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/approve-all-rates", methods=["POST"])
def api_approve_all_rates():
    """
    POST /api/approve-all-rates
    Body: {property_id, tenant_id?, date_from?, date_to?, mock?}
    Bulk-publishes every pending/approved recommendation for the property.
    """
    body = request.get_json(force=True) or {}
    pid = body.get("property_id")
    if not pid:
        return jsonify({"error": "property_id required"}), 400

    df = body.get("date_from"); dt = body.get("date_to")
    date_from = date.fromisoformat(df) if df else None
    date_to   = date.fromisoformat(dt) if dt else None
    use_mock = bool(body.get("mock", False))

    try:
        from engine.channel.publisher import publish_all_pending
        summary = publish_all_pending(
            pid, date_from=date_from, date_to=date_to, mock=use_mock,
        )
        status_code = 200 if summary.get("failed", 0) == 0 else 207
        return jsonify(summary), status_code
    except Exception as exc:
        logger.exception("approve-all-rates failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/publish-log/<property_id>", methods=["GET"])
def api_publish_log(property_id: str):
    """
    GET /api/publish-log/<property_id>?limit=50&recommendation_id=<uuid>
    Returns the most recent rate_publish_log records for the property.
    Optional ?recommendation_id filter scopes to one date/room (for the
    Rate Calendar drawer's Publish History tab).
    """
    sb = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}",
            "Prefer": "count=none"}
    limit = max(1, min(int(request.args.get("limit", "50")), 500))
    params: Dict[str, str] = {
        "property_id": f"eq.{property_id}",
        "select":      "id,recommendation_id,channel_manager,status,"
                       "otas_updated,response_body,published_at,error_message",
        "order":       "published_at.desc",
        "limit":       str(limit),
    }
    rec_id = request.args.get("recommendation_id", "").strip()
    if rec_id:
        params["recommendation_id"] = f"eq.{rec_id}"
    try:
        r = requests.get(f"{sb}/rest/v1/rate_publish_log",
                         headers=hdrs, params=params, timeout=15)
        if not r.ok:
            return jsonify({"error": r.text}), r.status_code
        return jsonify(r.json())
    except Exception as exc:
        logger.exception("publish-log fetch failed")
        return jsonify({"error": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  PMS Webhooks (Phase 4B)
# ─────────────────────────────────────────────────────────────────────────────
#
# Each PMS posts reservation lifecycle events here. We verify the signature
# against a per-vendor shared secret, dispatch the payload to the connector's
# handle_webhook, and return 200 if processing succeeded — 401 on bad sig,
# 500 if processing raised. The connector handler is itself idempotent: it
# computes affected dates, marks demand for refresh, but never writes raw
# webhook data to a queue (the caller already retries on non-2xx).

def _resnexus_webhook_secret() -> str:
    return os.getenv("RESNEXUS_WEBHOOK_SECRET", "")


def _verify_resnexus_signature(raw_body: bytes, header_signature: str) -> bool:
    """HMAC-SHA256(hex) of raw body using shared webhook secret."""
    secret = _resnexus_webhook_secret()
    if not secret or not header_signature:
        return False
    mac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    sig = header_signature.strip().lower()
    if sig.startswith("sha256="):
        sig = sig[7:]
    return hmac.compare_digest(mac, sig)


def _resolve_pms_property_id(pms_type: str, payload: dict) -> Optional[str]:
    """Map a PMS webhook payload back to our internal properties.id."""
    sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    sb_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not sb_url or not sb_key:
        return None
    hdrs = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
            "Prefer": "count=none"}

    ext_id: Optional[str] = None
    if pms_type == "resnexus":
        ext_id = (payload.get("propertyId")
                  or payload.get("data", {}).get("propertyId"))
    elif pms_type == "cloudbeds":
        ext_id = (payload.get("propertyID")
                  or payload.get("data", {}).get("propertyID"))

    if ext_id:
        r = requests.get(f"{sb_url}/rest/v1/properties",
                         headers=hdrs,
                         params={"pms_type":        f"eq.{pms_type}",
                                 "pms_external_id": f"eq.{ext_id}",
                                 "select":          "id"},
                         timeout=10)
        if r.ok and r.json():
            return r.json()[0]["id"]

    # Fallback: single-tenant deployments — return any property using this PMS.
    r = requests.get(f"{sb_url}/rest/v1/properties",
                     headers=hdrs,
                     params={"pms_type": f"eq.{pms_type}", "select": "id",
                             "limit":    "1"},
                     timeout=10)
    if r.ok and r.json():
        return r.json()[0]["id"]
    return None


@app.route("/webhooks/resnexus", methods=["POST"])
def webhook_resnexus():
    """ResNexus reservation lifecycle webhook (HMAC-SHA256 signed)."""
    raw  = request.get_data(cache=False)
    sig  = request.headers.get("X-Resnexus-Signature", "")
    if not _verify_resnexus_signature(raw, sig):
        logger.warning("ResNexus webhook: invalid signature (len=%d)", len(raw))
        return jsonify({"error": "invalid signature"}), 401

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return jsonify({"error": "invalid JSON"}), 400

    try:
        from engine.pms.factory import get_connector as _factory_get_connector
        pid = _resolve_pms_property_id("resnexus", payload)
        if not pid:
            logger.error("ResNexus webhook: could not resolve property")
            return jsonify({"error": "property not found"}), 404
        pms = _factory_get_connector(pid)
        report = pms.handle_webhook(payload)
    except Exception as exc:
        logger.exception("ResNexus webhook processing failed")
        return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True, **report})


@app.route("/webhooks/cloudbeds", methods=["POST"])
def webhook_cloudbeds():
    """Cloudbeds reservation lifecycle webhook (HMAC-SHA256 signed)."""
    raw = request.get_data(cache=False)
    sig = request.headers.get("X-Cloudbeds-Signature", "")
    from engine.pms.cloudbeds import CloudbedsConnector
    if not CloudbedsConnector.verify_webhook_signature(raw, sig):
        logger.warning("Cloudbeds webhook: invalid signature (len=%d)", len(raw))
        return jsonify({"error": "invalid signature"}), 401

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return jsonify({"error": "invalid JSON"}), 400

    try:
        from engine.pms.factory import get_connector as _factory_get_connector
        pid = _resolve_pms_property_id("cloudbeds", payload)
        if not pid:
            logger.error("Cloudbeds webhook: could not resolve property")
            return jsonify({"error": "property not found"}), 404
        pms = _factory_get_connector(pid)
        report = pms.handle_webhook(payload)
    except Exception as exc:
        logger.exception("Cloudbeds webhook processing failed")
        return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True, **report})


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting Anchorage 1770 Pricing Dashboard on http://localhost:5001")
    app.run(debug=False, host="0.0.0.0", port=5001, threaded=True)
