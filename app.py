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

import io
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, make_response, render_template, request, send_file, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()  # read .env so ELEVENLABS_API_KEY (etc.) are available
except ImportError:
    pass

from modules.hospitality.anchorage_pricing import (
    ROOM_INVENTORY,
    AnchoragePricingEngine,
    YOY_GROWTH,
    SEASONAL_INDEX,
)
from modules.hospitality.competitor_scraper import CompetitorScraper
from modules.module5_optimization.optimizer import PricingOptimizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/health")
@app.route("/healthz")
def health():
    """Dependency-free liveness probe for Railway. Returns 200 even if optional
    services (Supabase, Redis, SendGrid) aren't configured — point Railway's
    Healthcheck Path here."""
    return {"status": "ok"}, 200


logger.info("INNtelligence starting · PORT=%s", os.environ.get("PORT", "(unset)"))

# ─────────────────────────────────────────────────────────────────────────────
#  Config file paths
# ─────────────────────────────────────────────────────────────────────────────

_BASE_DIR              = os.path.dirname(os.path.abspath(__file__))
_DIST_DIR              = os.path.join(_BASE_DIR, "dashboard", "dist")  # Vite production build
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

# Industry package catalog — the top packages boutique inns commonly offer.
# Default to the "available" (not-yet-active) tab; activating one moves it to
# the Active tab. `pct_inns` = % of comparable inns that offer it (benchmark).
# `premium` = recommended price premium (the source of truth for pricing).
INDUSTRY_PACKAGES: Dict[str, Dict[str, Any]] = {
    "romantic_escape":      {"name": "Romantic Escape",        "emoji": "🌹", "premium": 89,  "pct_inns": 82, "description": "Champagne, rose petal turndown, and a couples' dinner reservation."},
    "anniversary_celebration": {"name": "Anniversary Celebration", "emoji": "🥂", "premium": 79, "pct_inns": 74, "description": "Commemorate the milestone with flowers, cake, and a keepsake photo."},
    "honeymoon_suite":      {"name": "Honeymoon Suite",        "emoji": "💍", "premium": 149, "pct_inns": 61, "description": "Top-tier suite, sparkling wine, late checkout, and breakfast in bed."},
    "girls_getaway":        {"name": "Girls Getaway",          "emoji": "👯", "premium": 119, "pct_inns": 48, "description": "Multi-room block, welcome cocktails, and a spa add-on for the group."},
    "corporate_retreat":    {"name": "Corporate Retreat",      "emoji": "💼", "premium": 199, "pct_inns": 39, "description": "Meeting space, catered working lunch, and AV for small teams."},
    "writers_retreat":      {"name": "Writers Retreat",        "emoji": "✍️", "premium": 95,  "pct_inns": 22, "description": "Quiet garden room, unlimited coffee, and a late 2pm checkout."},
    "photography_package":  {"name": "Photography Package",    "emoji": "📷", "premium": 129, "pct_inns": 28, "description": "Golden-hour session with a local photographer on the waterfront."},
    "culinary_experience":  {"name": "Culinary Experience",    "emoji": "🍽️", "premium": 159, "pct_inns": 44, "description": "Chef's tasting menu plus a Lowcountry cooking demonstration."},
    "history_heritage_tour":{"name": "History & Heritage Tour","emoji": "🏛️", "premium": 75,  "pct_inns": 57, "description": "Guided walking tour of historic Beaufort's antebellum district."},
    "ghost_tour":           {"name": "Ghost Tour",             "emoji": "👻", "premium": 59,  "pct_inns": 51, "description": "Evening lantern-lit ghost tour of the old district for two."},
    "kayak_adventure":      {"name": "Kayak Adventure",        "emoji": "🛶", "premium": 85,  "pct_inns": 46, "description": "Guided estuary paddle with gear and a packed Lowcountry lunch."},
    "fishing_charter":      {"name": "Fishing Charter",        "emoji": "🎣", "premium": 245, "pct_inns": 33, "description": "Half-day inshore charter with a licensed local captain."},
    "wine_cheese_welcome":  {"name": "Wine & Cheese Welcome",  "emoji": "🧀", "premium": 49,  "pct_inns": 78, "description": "Local cheese board and a bottle of SC wine on arrival."},
    "birthday_celebration": {"name": "Birthday Celebration",   "emoji": "🎂", "premium": 55,  "pct_inns": 69, "description": "Cake, balloons, and a celebratory turndown for the guest of honor."},
    "proposal_package":     {"name": "Proposal Package",       "emoji": "💎", "premium": 175, "pct_inns": 41, "description": "Private setup, photographer on standby, and champagne to toast."},
    "pet_friendly_getaway": {"name": "Pet Friendly Getaway",   "emoji": "🐶", "premium": 45,  "pct_inns": 63, "description": "Pet bed, bowls, treats, and a trail map — fee waived."},
    "wellness_spa":         {"name": "Wellness & Spa",         "emoji": "💆", "premium": 139, "pct_inns": 58, "description": "In-room couples massage and a wellness amenity kit."},
    "golf_package":         {"name": "Golf Package",           "emoji": "⛳", "premium": 165, "pct_inns": 36, "description": "Tee times at a nearby coastal course plus cart and transport."},
    "military_appreciation":{"name": "Military Appreciation",  "emoji": "🎖️", "premium": -40, "pct_inns": 71, "description": "Discounted rate honoring active and veteran service members."},
    "first_responder":      {"name": "First Responder Package","emoji": "🚒", "premium": -35, "pct_inns": 64, "description": "Thank-you discount for police, fire, and EMS personnel."},
    "aaa_member":           {"name": "AAA Member Special",     "emoji": "🚗", "premium": -25, "pct_inns": 88, "description": "Standard AAA member discount with flexible cancellation."},
    "aarp_senior":          {"name": "AARP Senior Discount",   "emoji": "🧓", "premium": -25, "pct_inns": 84, "description": "AARP / 55+ discount available year-round."},
    "extended_stay":        {"name": "Extended Stay Discount", "emoji": "📅", "premium": -60, "pct_inns": 76, "description": "Reduced nightly rate for stays of 5 nights or more."},
    "last_minute_deal":     {"name": "Last Minute Deal",       "emoji": "⏰", "premium": -45, "pct_inns": 79, "description": "Discount on bookings made within 48 hours of arrival."},
    "early_bird":           {"name": "Early Bird Special",     "emoji": "🐦", "premium": -30, "pct_inns": 81, "description": "Save when booking 60+ days ahead with prepayment."},
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

try:
    _engine    = AnchoragePricingEngine()
    _scraper   = CompetitorScraper()
    _optimizer = PricingOptimizer()
    logger.info("Pricing engines initialized")
except Exception:  # noqa: BLE001
    # Never let engine init crash the whole app — /health and the SPA must stay
    # up so Railway's probe passes and we can read the error in the logs.
    logger.exception("Pricing engine initialization failed — engines disabled")
    _engine = _scraper = _optimizer = None

# ── Multi-property support ────────────────────────────────────────────────────
# Anchorage keeps the original singleton (built from the untouched globals).
# Other properties get their own engine built from config.settings.PROPERTIES.
from config.settings import PROPERTIES, DEFAULT_PROPERTY  # noqa: E402

# Start empty and let _engine_for build each correctly: a property flagged
# use_engine_defaults reuses the Anchorage globals singleton; everyone else gets
# an engine built from its own config. (Seeding by DEFAULT_PROPERTY would be
# wrong now that the default is Bay Street, which is NOT the globals engine.)
_engines: Dict[str, AnchoragePricingEngine] = {}


def _engine_for(property_id: str) -> AnchoragePricingEngine:
    if property_id not in _engines:
        cfg = PROPERTIES.get(property_id)
        if not cfg or cfg.get("use_engine_defaults"):
            _engines[property_id] = _engine
        else:
            _engines[property_id] = AnchoragePricingEngine(property_config=cfg)
    return _engines[property_id]


def _resolve_property() -> str:
    pid = request.args.get("property", DEFAULT_PROPERTY)
    return pid if pid in PROPERTIES else DEFAULT_PROPERTY


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

def _packages_status_path(property_id: str = DEFAULT_PROPERTY) -> str:
    """Per-property status file so package toggles are isolated between
    properties. Anchorage keeps the original path (unchanged behavior)."""
    if property_id == DEFAULT_PROPERTY:
        return _PACKAGES_STATUS_PATH
    return os.path.join(_BASE_DIR, "config", f"packages_status_{property_id}.json")


def _load_packages_status(property_id: str = DEFAULT_PROPERTY) -> Dict[str, str]:
    try:
        with open(_packages_status_path(property_id)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {k: "active" for k in PACKAGES_CONFIG}


def _save_packages_status(status: Dict[str, str], property_id: str = DEFAULT_PROPERTY) -> None:
    with open(_packages_status_path(property_id), "w") as f:
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

def _serve_spa():
    """Serve the built React app's index.html. Falls back to the legacy Jinja
    template in dev when dashboard/dist hasn't been built yet."""
    if os.path.isfile(os.path.join(_DIST_DIR, "index.html")):
        return send_from_directory(_DIST_DIR, "index.html")
    try:
        return render_template("index.html")
    except Exception:  # noqa: BLE001
        return ("React build not found. Run: cd dashboard && npm run build", 200)


@app.route("/")
def index():
    return _serve_spa()


@app.route("/api/dashboard")
def dashboard_data():
    prop = _resolve_property()
    eng  = _engine_for(prop)
    meta = PROPERTIES[prop]

    date_str = request.args.get("date", "")
    try:
        report_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        report_date = date.today()

    occ      = 0.75
    date_key = report_date.isoformat()

    day_df = _cached(f"{prop}:rates_{date_key}", lambda: eng.generate_daily_report(
        target_date=report_date, occupancy_rate=occ
    ))
    day_rates = _format_room_rates(day_df, report_date)

    cal_df = _cached(f"{prop}:calendar_90d", lambda: eng.generate_pricing_calendar(
        days_ahead=90, base_occupancy=occ
    ))

    comp_7day = _cached(f"{prop}:comp_{date_key}", lambda: _build_competitor_comparison(
        days=7, start_date=report_date, engine=eng
    ))

    events = _upcoming_events(days=60, start_date=report_date, engine=eng)

    forecast = _cached(f"{prop}:forecast_90d", lambda: _build_revenue_forecast(cal_df))

    optimizations = _cached(f"{prop}:optimizations", lambda: _optimizer.analyze(cal_df, occ))

    return jsonify({
        "property": {
            "id":               meta["id"],
            "name":             meta["name"],
            "city":             meta["city"],
            "show_address":     meta.get("show_address", True),
            "address":          meta.get("address", ""),
            "restaurant":       meta.get("restaurant", ""),
            "rooftop_bar":      meta.get("rooftop_bar", ""),
            "room_count":       meta.get("room_count", len(day_rates)),
            "occ_target_low":   meta.get("occ_target_low", 0.70),
            "occ_target_high":  meta.get("occ_target_high", 0.85),
            "occupancy_assumed": occ,
        },
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


@app.route("/api/room-rate")
def api_room_rate():
    """Full pricing detail for one room on one date (Rate Calendar detail panel)."""
    prop = _resolve_property()
    eng  = _engine_for(prop)
    room_id = request.args.get("room_id", "")
    try:
        d = date.fromisoformat(request.args.get("date", ""))
    except ValueError:
        d = date.today()
    if room_id not in eng.rooms:
        return jsonify({"error": f"Unknown room_id {room_id!r}"}), 404
    detail = eng.calculate_room_rate(room_id, d, 0.75)
    # Tier-comparable competitor rates: label each competitor with its rate.
    detail["competitor_rates"] = [
        {"name": n, "rate": r} for n, r in detail["competitor_rates"].items()
    ]
    return jsonify(detail)


@app.route("/api/rate-calendar")
def api_rate_calendar():
    """Per-room rate series across a date range (Rate Calendar grid)."""
    prop = _resolve_property()
    eng  = _engine_for(prop)
    try:
        days = max(1, min(int(request.args.get("days", 30)), 90))
    except ValueError:
        days = 30
    meta = PROPERTIES[prop]

    cal_df = _cached(f"{prop}:calendar_90d", lambda: eng.generate_pricing_calendar(
        days_ahead=90, base_occupancy=0.75
    ))
    df = cal_df[cal_df["days_out"] < days]

    tier_icons = {"cottage": "🏡", "waterfront": "🌊", "water_view": "🔭", "garden": "🌿",
                  "carriage_house": "🏛️", "signature_suite": "✨", "grand_parlor": "👑"}
    rooms = {}
    for _, row in df.iterrows():
        rid = row["room_id"]
        if rid not in rooms:
            rooms[rid] = {
                "room_id":   rid,
                "room_name": row["room_name"],
                "tier":      row["tier"],
                "tier_icon": tier_icons.get(row["tier"], "🏨"),
                "rack_low":  float(row["rack_low"]),
                "rack_high": float(row["rack_high"]),
                "days":      [],
            }
        rate, rack_mid = float(row["recommended_rate"]), float(row["rack_mid"])
        if rate > rack_mid * 1.05:
            status = "premium"
        elif rate >= float(row["rack_low"]) * 0.99:
            status = "hold"
        else:
            status = "discount"
        evts = [e.strip() for e in str(row["active_events"]).split(";") if e.strip()]
        rooms[rid]["days"].append({
            "date":           row["date"],
            "day_of_week":    row["day_of_week"],
            "rate":           rate,
            "last_year_rate": float(row["last_year_rate"]),
            "status":         status,
            "is_weekend":     bool(row["is_weekend"]),
            "confidence":     row["confidence"],
            "active_events":  evts,
        })
    return jsonify({
        "property_name": meta["name"],
        "days":          days,
        "rooms":         list(rooms.values()),
    })


_SUITE_TIERS = {"carriage_house", "signature_suite", "grand_parlor"}

# Verified competitor room-type availability matrix (real-world research).
# Per competitor key → per room category → status:
#   "yes"  → offers a directly comparable room type (rate shown normally)
#   "na"   → does not offer this type (row grayed, shows N/A, excluded from avg)
#   <str>  → partial availability; the string is the display label
#            ("Limited", "Varies", "Junior suites only") — rate shown italic,
#            included in the comp-set average.
# "average" is always "yes" (every property has standard rooms).
_COMP_MATRIX = {
    "rhett_house": {"waterfront": "na", "water_view": "Limited", "garden": "yes",
                    "carriage_house": "yes", "signature_suite": "yes", "grand_parlor": "na"},
    "cuthbert_house": {"waterfront": "yes", "water_view": "yes", "garden": "yes",
                       "carriage_house": "yes", "signature_suite": "yes", "grand_parlor": "yes"},
    "anchorage_1770": {"waterfront": "yes", "water_view": "yes", "garden": "yes",
                       "carriage_house": "na", "signature_suite": "yes", "grand_parlor": "na"},
    "bay_inn_607": {"waterfront": "na", "water_view": "na", "garden": "yes",
                    "carriage_house": "na", "signature_suite": "na", "grand_parlor": "na"},
    "beaufort_inn": {"waterfront": "na", "water_view": "na", "garden": "yes",
                     "carriage_house": "na", "signature_suite": "yes", "grand_parlor": "na"},
    "city_loft": {"waterfront": "na", "water_view": "na", "garden": "yes",
                  "carriage_house": "na", "signature_suite": "Junior suites only", "grand_parlor": "na"},
    "airbnb_avg": {"waterfront": "Varies", "water_view": "Varies", "garden": "yes",
                   "carriage_house": "Varies", "signature_suite": "na", "grand_parlor": "na"},
    "hampton_inn": {"waterfront": "na", "water_view": "na", "garden": "yes",
                    "carriage_house": "na", "signature_suite": "na", "grand_parlor": "na"},
    "montage": {"waterfront": "yes", "water_view": "yes", "garden": "yes",
                "carriage_house": "yes", "signature_suite": "yes", "grand_parlor": "yes"},
}

# Accurate 2026 tier-specific rate ranges (low, high) per competitor. Used to
# anchor the competitive comparison to each property's real positioning.
_COMP_RATES = {
    "rhett_house":    {"garden": (189, 249), "water_view": (189, 249),
                       "carriage_house": (289, 389), "signature_suite": (289, 389), "average": (189, 389)},
    "cuthbert_house": {"garden": (249, 299), "water_view": (319, 389), "waterfront": (389, 469),
                       "carriage_house": (449, 549), "signature_suite": (449, 549),
                       "grand_parlor": (449, 549), "average": (249, 549)},
    "anchorage_1770": {"garden": (269, 299), "water_view": (319, 369), "waterfront": (389, 469),
                       "signature_suite": (389, 469), "average": (269, 469)},
    "bay_inn_607":    {"garden": (149, 219), "average": (149, 219)},
    "beaufort_inn":   {"garden": (179, 249), "signature_suite": (279, 349), "average": (179, 349)},
    "city_loft":      {"garden": (169, 229), "signature_suite": (229, 289), "average": (169, 289)},
    "hampton_inn":    {"garden": (129, 189), "average": (129, 189)},
    "montage":        {"garden": (650, 1800), "water_view": (650, 1800), "waterfront": (650, 1800),
                       "carriage_house": (650, 1800), "signature_suite": (650, 1800),
                       "grand_parlor": (650, 1800), "average": (650, 1800)},
    "airbnb_avg":     {"garden": (149, 299), "water_view": (149, 299), "waterfront": (149, 299),
                       "carriage_house": (149, 299), "average": (149, 299)},
}


# Reference-only competitors: shown in the table but EXCLUDED from the
# comp-set average (they anchor the high/low ends of the market, not the
# directly comparable set).
_COMP_REFERENCE = {
    "montage":     {"kind": "luxury", "label": "Luxury Reference",
                    "tooltip": "Excluded from comp average — luxury resort benchmark only"},
    "hampton_inn": {"kind": "budget", "label": "Budget Reference",
                    "tooltip": "Excluded from comp average — budget anchor benchmark only"},
}


def _comp_status(key, tier):
    """Return availability status for a competitor in a room category."""
    if tier == "average":
        return "yes"
    return _COMP_MATRIX.get(key, {}).get(tier, "na")


def _comp_rate_for(key, tier, d, eng):
    """Anchor a competitor's rate to its tier-specific range, varied by date
    (weekend/event/season push toward the high end)."""
    rates = _COMP_RATES.get(key, {})
    rng = rates.get(tier) or rates.get("average")
    if not rng:
        return None
    low, high = rng
    seasonal = SEASONAL_INDEX.get(d.month, 1.0)
    is_weekend = d.weekday() in (4, 5)
    mult, _ = eng.get_event_multiplier(d)
    pos = 0.30 + (0.30 if is_weekend else 0.0) + min(0.30, mult - 1.0) + (seasonal - 1.0) * 0.5
    pos = max(0.0, min(1.0, pos))
    noise = ((d.toordinal() * 7 + hash(key)) % 7 - 3) * 0.01
    rate = (low + (high - low) * pos) * (1 + noise)
    return round(rate / 5) * 5


@app.route("/api/competitive")
def api_competitive():
    """Tier-aware, date-ranged competitive comparison with YoY (Competitive Intel).
    Competitors without a comparable room type for the selected category are
    flagged available=False so the UI can gray them out and show N/A."""
    prop = _resolve_property()
    eng  = _engine_for(prop)
    meta = PROPERTIES[prop]
    try:
        days = max(1, min(int(request.args.get("days", 14)), 90))
    except ValueError:
        days = 14
    tier = request.args.get("tier", "average")

    cal_df = _cached(f"{prop}:calendar_90d", lambda: eng.generate_pricing_calendar(
        days_ahead=90, base_occupancy=0.75
    ))
    df = cal_df[cal_df["days_out"] < days]

    def _room_ids_for(t):
        if t == "average":
            return list(eng.rooms.keys())
        if t == "suites":
            return [rid for rid, r in eng.rooms.items() if r.tier in _SUITE_TIERS]
        return [rid for rid, r in eng.rooms.items() if r.tier == t]

    # Per-competitor availability status + tier-anchored rate series.
    comp_meta = {}   # key → {name, tier, status, available, partial, label, reference…}
    for key, comp in eng.competitors.items():
        status = _comp_status(key, tier)
        partial = status not in ("yes", "na")
        ref = _COMP_REFERENCE.get(key)
        comp_meta[key] = {
            "key": key, "name": comp.name, "tier": getattr(comp, "tier", 1),
            "status": status, "available": status != "na", "partial": partial,
            "label": status if partial else "",
            "reference": ref["kind"] if ref else None,
            "reference_label": ref["label"] if ref else "",
            "reference_tooltip": ref["tooltip"] if ref else "",
            "rates": [],
        }

    sel_ids = set(_room_ids_for(tier))
    dates, you, you_ly, comp_avg = [], [], [], []

    for d, grp in df.groupby("date", sort=True):
        dates.append(d)
        overall_avg = grp["recommended_rate"].mean()
        sel = grp[grp["room_id"].isin(sel_ids)]
        you_rate = sel["recommended_rate"].mean() if len(sel) else overall_avg
        you.append(round(you_rate))
        you_ly.append(round(sel["last_year_rate"].mean() if len(sel) else grp["last_year_rate"].mean()))
        dd = date.fromisoformat(d)
        day_avail_rates = []
        for key, m in comp_meta.items():
            rate = _comp_rate_for(key, tier, dd, eng) if m["available"] else None
            m["rates"].append(rate)
            # Comp-set average: comparable properties only — exclude N/A AND
            # reference-only benchmarks (Montage luxury, Hampton budget).
            if m["available"] and rate is not None and m["reference"] is None:
                day_avail_rates.append(rate)
        comp_avg.append(round(sum(day_avail_rates) / len(day_avail_rates)) if day_avail_rates else 0)

    comparable_count = sum(
        1 for m in comp_meta.values() if m["available"] and m["reference"] is None
    )
    competitors = [
        {"name": m["name"], "tier": m["tier"], "rates": m["rates"],
         "available": m["available"], "partial": m["partial"], "label": m["label"],
         "reference": m["reference"], "reference_label": m["reference_label"],
         "reference_tooltip": m["reference_tooltip"]}
        for m in sorted(comp_meta.values(), key=lambda x: x["tier"])
    ]
    return jsonify({
        "property_name": meta["name"],
        "tier":          tier,
        "days":          days,
        "dates":         dates,
        "you":           you,
        "you_last_year": you_ly,
        "comp_avg":      comp_avg,
        "comparable_count": comparable_count,
        "competitors":   competitors,
        "tier_labels":   _TIER_LABELS,
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Product Tour — ElevenLabs (Will) narration, generated server-side & cached
# ─────────────────────────────────────────────────────────────────────────────
_TOUR_VOICE_ID  = "kIfcKu9kr8RZrbz7H3ox"           # ElevenLabs "Will"
_TOUR_AUDIO_DIR = os.path.join(_BASE_DIR, "dashboard", "public", "audio", "tour")
# 14 numbered steps plus an opening + closing narration. "Inn-telligence" is
# spelled hyphenated on purpose so the TTS pronounces it "Inn-telligence".
_TOUR_STEP_IDS  = ["opening"] + [f"step_{i:02d}" for i in range(1, 15)] + ["closing"]

# Source of truth for narration text (used by both POST generate + GET serve).
_TOUR_NARRATION = {
    "opening": "Inn-telligence was built by a pricing professional with eleven years of experience building revenue optimization systems for one of America's largest telecommunications companies. Systems that are now enterprise standard. Systems that generate hundreds of millions of dollars in optimized revenue. He looked at the boutique inn industry and saw the same problem he had solved in telecom: owners making pricing decisions based on gut feel, leaving significant revenue on the table every single night. So he built Inn-telligence. The same institutional-grade pricing intelligence that Fortune 500 companies pay millions for — built specifically for boutique inns, starting at three hundred and ninety-nine dollars a month. This is The Bay Street Inn in Beaufort, South Carolina. Nineteen rooms. Let's show you what Inn-telligence does for an inn like this every single morning.",
    "step_01": "It's seven oh two on a Friday morning in Beaufort, South Carolina. The owner of Bay Street Inn opens Inn-telligence. Before the first cup of coffee is finished, she knows everything she needs to know about today. Average rate across all nineteen rooms: four hundred and eighty-seven dollars. RevPAR: three hundred and sixty-five dollars. Market pressure score seven out of ten — demand is building. Four active events in the next thirty days. And one alert at the top of the screen: a competitor dropped rates overnight. This is what running an inn looks like with Inn-telligence. Every morning starts with clarity instead of guesswork. Let's walk through exactly what she does next.",
    "step_02": "The first screen every morning is Competitive Intelligence. Here is something most inn owners do not know: your competitors are adjusting their rates constantly — sometimes daily, sometimes overnight while you sleep. Without a system monitoring them around the clock, you are always reacting instead of leading. Inn-telligence monitors nine properties in the Beaufort market twenty-four hours a day, updating rates every morning at six AM. The AI identifies patterns in how each competitor prices — when they discount, how aggressively, and what triggers it. Over time it learns their behavior and predicts their next move before they make it. Your competitors are organized into three tiers based on how directly they compete for your guests. Direct competitors — Rhett House Inn, Cuthbert House Inn, Anchorage 1770, and 607 Bay Inn — these four properties drive your rate recommendations with the highest weight. Now filter to Waterfront rooms specifically. Rhett House and City Loft Hotel immediately gray out. They do not have true waterfront rooms. Inn-telligence never compares you to a property that is not actually competing for the same guest on the same product. This is the kind of nuance that comes from real hospitality expertise baked into the system — not just an algorithm pulling rates off a website. Your direct comp set average for waterfront rooms tonight is four hundred and twelve dollars. Inn-telligence recommends holding at four hundred and forty-five dollars — an eight percent premium. Why is that premium justified? Your TripAdvisor score is higher. Your waterfront views are rated better by guests who have stayed at both properties. And the market pressure score of seven out of ten means demand is strong enough to support it. The rate drop alert: Rhett House dropped forty dollars overnight. They have availability for Water Festival weekend — they are nervous. Cuthbert House has not moved. Inn-telligence recommendation: hold your rates. Your strongest competitor is confident. You should be too. That recommendation comes from eleven years of pricing experience encoded into every decision the AI makes. It does not just show you data — it tells you what to do with it.",
    "step_03": "The Rate Calendar is where Inn-telligence's pricing expertise becomes real money. Every inn owner knows they should be charging more during peak season and less during slow periods. But knowing that and actually doing it — room by room, night by night, accounting for events, competitor moves, lead time, and demand signals — is a full-time job. It is what a professional revenue manager does. Inn-telligence does it automatically, for every room, every night. Select Waterfront rooms and look at Water Festival weekend — Friday July seventeenth through Sunday July nineteenth. Waterfront Room 1 on Friday: five hundred and two dollars. Twenty-nine percent above rack rate. Here is the exact reasoning. Seasonal index: one point three for peak July. Water Festival demand multiplier: one point three five — thirteen consecutive days of the biggest event in Beaufort. Lead time urgency: nine days out, demand is building. Competitor average for comparable waterfront rooms: four hundred and twelve dollars. Reputation premium: eight percent above comp set, justified. Confidence level: HIGH. Every number in that calculation comes from a methodology developed over eleven years of professional pricing practice. The same approach used to optimize hundreds of millions of dollars in revenue — now running automatically for your nineteen rooms. Click accept. Rate is set. One click. Done. Saturday: five hundred and forty-seven. Grand Parlor Suite: seven hundred and twenty-one. All nineteen rooms, Water Festival weekend, individually priced in under sixty seconds. Now look at Tuesday July twenty-first — mid-week after the festival peak. Garden Room 3: two hundred and forty-nine dollars. Below rack rate. The engine knows demand drops sharply mid-week after the festival and recommends a strategic discount to fill the room rather than hold a rate you will not achieve. That balance — charging premium when you can, being strategic when you should — is exactly what separates professional revenue management from guesswork. And now every inn owner has access to it.",
    "step_04": "This is one of the screens I am most proud of, because it solves a problem I saw inn owners struggling with long before Inn-telligence existed. The orphan gap problem. You have a Saturday booking for Waterfront Room 1. Friday before it: empty. Sunday after it: empty. Those nights are almost impossible to fill at full price because most guests want a minimum two-night stay. Without a system watching your calendar, those nights just go empty. You never even think about them until checkout day when it is too late. Inn-telligence finds every orphan gap automatically and gives you specific actions to take right now — not generic suggestions, but calculated recommendations based on your actual guest data and current market conditions. For this Friday gap: contact the Saturday guest and offer Friday at a fifteen percent discount. They are already coming — the incremental cost to you is almost nothing and the revenue is pure upside. If that does not work by Wednesday: send a targeted email to past guests within a hundred and fifty miles who have stayed in waterfront rooms before. Frame it as an exclusive offer for past guests. This week alone: three orphan gaps, eight hundred and forty dollars in recoverable revenue that would have gone empty without this screen. The ten AI recommendations below are generated fresh every morning from your booking data, competitor rates, and the local events calendar. Human pricing expertise, encoded into an algorithm, running while you sleep. That is Inn-telligence.",
    "step_05": "The best revenue you will ever generate comes from guests who already love you. Win-back marketing — reaching out to past guests who have not returned — consistently outperforms acquiring new guests by three to five times in both conversion rate and lifetime value. Every major hotel chain has known this for decades and built entire CRM systems around it. Boutique inn owners have had no equivalent tool. Until now. Inn-telligence builds a complete intelligence profile on every guest who has ever stayed with you. Look at Catherine Beaumont from Charlotte, North Carolina. Four stays. Lifetime spend: three thousand eight hundred and forty dollars. Always books waterfront. Last visit: seven months ago. Catherine is a Lapsed VIP. She loved Bay Street Inn enough to come back three times. Something got in the way. Maybe she just needed someone to reach out. Campaign Manager. Lapsed VIP segment. Win-Back template. The email personalizes itself — her name, her preferred room, a ten percent loyalty rate for her next waterfront stay. Twelve guests match this profile right now. If three of them book a two-night waterfront stay — conservative estimate based on industry win-back conversion rates — that is five thousand four hundred dollars in recovered revenue. From fifteen minutes of a Friday morning. From guests who already chose you once.",
    "step_06": "I built Inn-telligence to be accountable — so let's do the honest math for a typical boutique inn. Twelve rooms, an average nightly rate of three hundred and fifty dollars, sixty-five percent occupancy. That's about ninety-nine thousand five hundred dollars in annual room revenue. Inn-telligence typically lifts revenue fifteen to twenty percent — through smarter pricing, gap-night recovery, and win-back campaigns. Take the conservative end, fifteen percent. That's fourteen thousand nine hundred and thirty-one dollars in additional revenue every year — about one thousand two hundred and forty-four dollars a month. The Professional subscription is six hundred and ninety-nine dollars a month. So you spend six hundred and ninety-nine to earn an extra twelve hundred and forty-four — a net benefit of five hundred and forty-five dollars every month, and a one point eight times return on your Inn-telligence subscription. And that's the conservative case. At twenty percent, the return climbs past two times. This screen shows you the real numbers for your property every month — including the misses — because honest math is the only math worth trusting.",
    "step_07": "For inns with a restaurant or bar, food and beverage is a revenue center that most owners dramatically underanalyze. I know this from experience. The same yield management principles that work for room pricing work for restaurant seats and bar tops. Day of week. Time of day. Event influence. Guest mix. All of it matters. Inn-telligence applies those principles to The Parlor and The Rooftop at Bay Street Inn automatically. Thursday Rooftop: eight hundred and ninety dollars. Friday: two thousand one hundred. That gap tells a story. Guests arriving Thursday have dinner plans elsewhere. The Rooftop has empty seats on the most beautiful sunset evening of the week. Recommendation: Thursday Lowcountry Sunset Supper. Fixed price, three courses, sixty-five dollars per person, rooftop cocktail hour included. Inns that introduce a Thursday evening special see twenty to twenty-five percent revenue lift. At Bay Street Inn's cover count: fourteen hundred additional dollars per month. Sixteen thousand eight hundred dollars per year. One menu decision.",
    "step_08": "This is the screen that surprises people most when they first see Inn-telligence. Because nobody else has built it. Every revenue management system in hospitality is built around transactional nightly bookings. None of them help you price a wedding. None of them tell you whether to accept a corporate buyout on a festival weekend. None of them calculate the exact premium you should charge for exclusivity. I built this screen because I know from personal experience that group events are where boutique inns leave the most money on the table. Elizabeth and William Hartley. Wedding inquiry. August twenty-third. Forty-five guests. Full buyout. The calculator runs in seconds. Room block: fifteen thousand nine hundred and sixty. Event space: fifteen hundred. Food and beverage: five thousand six hundred and twenty-five. Setup: eight hundred. Exclusivity premium: four thousand seven hundred and seventy-seven. Total: twenty-eight thousand six hundred and sixty-two dollars. Compare to individual bookings that weekend: fifteen thousand nine hundred and sixty. Wedding premium: twelve thousand seven hundred and two dollars. Accept. Now change the date to July nineteenth — Water Festival opening weekend. The conflict alert fires immediately. Festival individual pricing: nineteen thousand two hundred. The wedding offer is below that threshold. Recommendation: Decline or negotiate above festival pricing. That one calculation, on that one date change, protects thousands of dollars that most inn owners would never have thought to calculate.",
    "step_09": "The Weddings screen is designed to be shared directly with couples who are considering Bay Street Inn for their celebration. Four packages, from intimate elopements at twenty-five hundred to forty-five hundred dollars, all the way to Grand Celebrations for seventy-five guests at twenty-eight to forty-five thousand. Every package includes the full inclusions list, deposit schedule, and cancellation terms — everything a couple needs to make a confident decision. The inquiry form captures everything you need to qualify a wedding lead and routes it to your event coordinator immediately. Your wedding business runs through Inn-telligence from first contact to confirmed booking. No spreadsheets. No pricing uncertainty. Every date checked against your revenue calendar before you say yes.",
    "step_10": "Inn-telligence tracks every event in the Beaufort market — from the Original Gullah Festival on Memorial Day weekend to Parris Island Marine Corps graduations that fill rooms eight times a year. Understanding your local events calendar is not optional for a boutique inn in an event-driven market like Beaufort. It is the foundation of everything else. Switch to Next Six Months and every revenue opportunity is laid out in front of you, with pricing impact and recommended action for each. The Beaufort Water Festival: thirty to forty percent premium, rooms selling out sixty days in advance. Inn-telligence started adjusting your rates ninety days ago. Penn Center Heritage Days in November: historically underpriced by most Bay Street properties. Twenty percent premium opportunity. You are planning months ahead now, not reacting the week of.",
    "step_11": "The Romance Package generates four thousand seven hundred and eighty-one dollars per month at Bay Street Inn. Nearly fifty-eight thousand dollars a year. From one package offering at eighty-five dollars above rack rate. The Available Packages tab shows what comparable inns offer that Bay Street Inn does not — yet. The Proposal Package is offered by only twelve percent of comparable boutique inns. Low competition. High perceived value. One hundred and ninety-five dollar premium. Estimated monthly revenue: three thousand two hundred dollars. Thirty-eight thousand four hundred dollars a year from one toggle switch. Inn-telligence monitors what packages the market offers and identifies the gaps specific to your property and guest profile. The opportunities are always there. Now you can see them.",
    "step_12": "Twenty-four months of performance data so you always know where you have been and where you are going. Best month ever: July twenty twenty-five, sixty-eight thousand four hundred dollars. This May running twenty-three percent ahead of last year. The seasonal pattern becomes visible over time — July and October your peaks, January and February your valleys. Inn-telligence uses this history to build smarter forward recommendations. It knows your property. It learns your patterns. Every month the model gets more accurate.",
    "step_13": "Pricing power comes from reputation. You cannot charge a premium if guests do not believe you are worth it. And you cannot know what guests think if you are not systematically listening. Pricing Power Score: eighty-four out of one hundred. That number means Bay Street Inn has earned the right to price above the market average. Top guest keywords: location, breakfast, staff, views. One trend to watch: value mentions dropping slightly. Recommendation: add a Lowcountry welcome amenity to all check-ins. Local jam, pralines, handwritten note. Under eight dollars per room. The kind of gesture that turns a four-star review into a five-star review and a five-star review into a repeat guest.",
    "step_14": "The final revenue stream — and one of the most satisfying to build into Inn-telligence, because it turns a guest's love for their experience into ongoing revenue long after checkout. Comphy bedding — the exact sheets on every bed at Bay Street Inn. Eight sets sold this month. Nineteen hundred and twenty dollars. Pure margin. Murano glass by Gino Mazzuccato — authentic hand-blown glass from the island of Murano in Venice, Italy, displayed throughout the inn, available to purchase and ship anywhere in the United States. Three pieces this month. Twelve hundred and forty dollars. Three thousand one hundred and sixty dollars in gift shop revenue. Zero additional staff. Guests take home a piece of Bay Street Inn and a reason to come back.",
    "closing": "Eleven years building pricing systems for Fortune 500 companies. The same methodology. The same rigor. Now available to every boutique inn owner who has ever wondered if they are charging the right rate. Inn-telligence combines artificial intelligence with real-world pricing expertise built by someone who has spent over a decade doing this professionally — and who now owns a boutique inn himself. Every recommendation is AI-generated and expert-validated. Not just an algorithm. Not just data. Pricing intelligence with the judgment to know what the data means. Bay Street Inn. Nineteen rooms. Maximum revenue. Every single day. Your inn deserves the same. Start your free thirty-day trial today. No credit card required.",
}


def _tour_path(step_id: str) -> str:
    return os.path.join(_TOUR_AUDIO_DIR, f"{step_id}.mp3")


def _tour_generate(step_id: str, text: str | None) -> tuple[str, bool]:
    """Return (path, cached). Generates the MP3 via ElevenLabs if missing."""
    path = _tour_path(step_id)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path, True
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not configured")
    narration = text or _TOUR_NARRATION.get(step_id)
    if not narration:
        raise RuntimeError(f"No narration text for {step_id}")
    import requests
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{_TOUR_VOICE_ID}",
        headers={"xi-api-key": api_key, "accept": "audio/mpeg", "content-type": "application/json"},
        json={
            "text": narration,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.45, "similarity_boost": 0.85,
                "style": 0.35, "use_speaker_boost": True,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    os.makedirs(_TOUR_AUDIO_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(resp.content)
    return path, False


@app.route("/api/tour/audio-status")
def api_tour_audio_status():
    """Which step audio files exist + whether ElevenLabs is configured."""
    generated = [
        sid for sid in _TOUR_STEP_IDS
        if os.path.exists(_tour_path(sid)) and os.path.getsize(_tour_path(sid)) > 0
    ]
    return jsonify({
        "generated": generated,
        "total": len(_TOUR_STEP_IDS),
        "all_ready": len(generated) == len(_TOUR_STEP_IDS),
        "configured": bool(os.getenv("ELEVENLABS_API_KEY")),
    })


@app.route("/api/tour/generate-audio", methods=["POST"])
def api_tour_generate_audio():
    """Generate (or return cached) MP3 for one step."""
    data = request.get_json(force=True) or {}
    step_id = data.get("step_id", "")
    if step_id not in _TOUR_STEP_IDS:
        return jsonify({"ok": False, "error": "Invalid step_id"}), 400
    try:
        _path, cached = _tour_generate(step_id, data.get("narration_text"))
        return jsonify({"ok": True, "step_id": step_id, "cached": cached,
                        "path": f"/audio/tour/{step_id}.mp3"})
    except Exception as e:  # noqa: BLE001 — surface to frontend for Web Speech fallback
        logger.warning("Tour audio generation failed for %s: %s", step_id, e)
        return jsonify({"ok": False, "step_id": step_id, "error": str(e)}), 502


@app.route("/api/tour/audio/<step_id>")
def api_tour_audio(step_id: str):
    """Serve a step's MP3, generating on demand if missing."""
    if step_id not in _TOUR_STEP_IDS:
        return jsonify({"error": "Invalid step_id"}), 404
    path = _tour_path(step_id)
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        try:
            _tour_generate(step_id, None)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 502
    return send_file(path, mimetype="audio/mpeg", conditional=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Authentication, tenant provisioning, onboarding (Supabase Auth + SendGrid)
#  All Supabase access is server-side via REST. Frontend talks only to /api/auth/*.
# ─────────────────────────────────────────────────────────────────────────────
_SUPABASE_URL     = os.getenv("SUPABASE_URL", "").rstrip("/")
_SUPABASE_ANON    = os.getenv("SUPABASE_ANON_KEY", "")
_SUPABASE_SERVICE = os.getenv("SUPABASE_SERVICE_KEY", "")
_SENDGRID_KEY     = os.getenv("SENDGRID_API_KEY", "")
_APP_PUBLIC_URL   = os.getenv("APP_PUBLIC_URL", "https://app.inntelligence.app")
_CALENDLY_URL     = os.getenv("CALENDLY_URL", "https://calendly.com/inntelligence/onboarding")
_FROM_EMAIL       = os.getenv("WELCOME_FROM_EMAIL", "jim@graciouscollection.com")
# These accounts are always treated as platform admins regardless of JWT claims.
_ADMIN_EMAILS     = {"jwilliams8559@gmail.com", "jim@graciouscollection.com"}


def _auth_configured() -> bool:
    return bool(_SUPABASE_URL and _SUPABASE_ANON)


def _bearer_token() -> str:
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        return h[7:]
    return request.cookies.get("inn_token", "")


def _sb_user(token: str) -> Optional[dict]:
    """Validate a token by asking Supabase for the user it belongs to."""
    if not (token and _auth_configured()):
        return None
    try:
        import requests
        r = requests.get(f"{_SUPABASE_URL}/auth/v1/user",
                         headers={"apikey": _SUPABASE_ANON, "Authorization": f"Bearer {token}"},
                         timeout=15)
        return r.json() if r.ok else None
    except Exception:  # noqa: BLE001
        return None


def _role_and_tenant(user: Optional[dict]) -> tuple[str, Optional[str]]:
    """Extract role + tenant_id from the custom_access_token_hook claims.
    The hook injects app_metadata.app_role and app_metadata.tenant_id.
    Admin email allowlist always wins."""
    user = user or {}
    app_md = user.get("app_metadata") or {}
    usr_md = user.get("user_metadata") or {}
    email = (user.get("email") or "").lower()
    # app_role is the canonical claim; fall back to legacy 'role' just in case.
    role = app_md.get("app_role") or app_md.get("role") or usr_md.get("app_role") or "inn_owner"
    tenant_id = app_md.get("tenant_id") or usr_md.get("tenant_id")
    if email in _ADMIN_EMAILS:
        role = "tgc_admin"
    return role, tenant_id


def _sb_rest_get(path: str, params: dict) -> list:
    """Service-key REST GET against Supabase PostgREST. Returns [] on any error."""
    if not (_SUPABASE_URL and _SUPABASE_SERVICE):
        return []
    try:
        import requests
        r = requests.get(f"{_SUPABASE_URL}/rest/v1/{path}",
                         headers={"apikey": _SUPABASE_SERVICE, "Authorization": f"Bearer {_SUPABASE_SERVICE}"},
                         params=params, timeout=15)
        return r.json() if (r.ok and r.text) else []
    except Exception:  # noqa: BLE001
        return []


def _tenant_context(tenant_id: Optional[str], user: Optional[dict]) -> dict:
    """Resolve display context from the real schema:
      - tenants:        plan_tier, name, onboarding_complete
      - properties:     first property.name (by tenant_id) → property_name
      - user_profiles / auth metadata: owner_name
    onboarding_complete=false → pending_onboarding=true (forces /onboarding).
    Never raises — falls back to auth metadata + sensible defaults."""
    usr_md = (user or {}).get("user_metadata") or {}
    app_md = (user or {}).get("app_metadata") or {}
    ctx = {
        "property_name": usr_md.get("property_name") or "",
        "plan_tier": app_md.get("plan_tier") or usr_md.get("plan_tier") or "professional",
        "owner_name": usr_md.get("owner_name") or usr_md.get("full_name") or "",
        "pending_onboarding": False,
    }
    if not tenant_id:
        return ctx

    # tenants → plan_tier, name, onboarding_complete
    rows = _sb_rest_get("tenants", {"id": f"eq.{tenant_id}",
                                    "select": "name,plan_tier,onboarding_complete,active"})
    if rows:
        t = rows[0]
        ctx["plan_tier"] = t.get("plan_tier") or ctx["plan_tier"]
        if not ctx["property_name"]:
            ctx["property_name"] = t.get("name") or ""
        # Force onboarding only when the column explicitly says it's incomplete.
        if t.get("onboarding_complete") is False:
            ctx["pending_onboarding"] = True

    # properties → first property's name (preferred display name)
    props = _sb_rest_get("properties", {"tenant_id": f"eq.{tenant_id}",
                                        "select": "name", "order": "created_at.asc", "limit": "1"})
    if props and props[0].get("name"):
        ctx["property_name"] = props[0]["name"]

    # user_profiles → owner_name (if present), keyed by auth user id
    uid = (user or {}).get("id")
    if uid and not ctx["owner_name"]:
        prof = _sb_rest_get("user_profiles", {"user_id": f"eq.{uid}",
                                              "select": "full_name,name,owner_name", "limit": "1"})
        if prof:
            p = prof[0]
            ctx["owner_name"] = p.get("full_name") or p.get("name") or p.get("owner_name") or ""
    return ctx


def _require_admin() -> tuple[Optional[dict], Optional[tuple]]:
    """Returns (user, None) if caller is tgc_admin, else (None, error_response)."""
    if not _auth_configured():
        return None, (jsonify({"error": "Auth not configured"}), 503)
    user = _sb_user(_bearer_token())
    if not user:
        return None, (jsonify({"error": "Unauthorized"}), 401)
    role, _ = _role_and_tenant(user)
    if role != "tgc_admin":
        return None, (jsonify({"error": "Admin access required"}), 403)
    return user, None


def _send_welcome_email(to_email: str, owner_name: str, temp_password: str, property_name: str) -> bool:
    """Send the founding-member/welcome email via SendGrid REST. No-op (logged)
    when SENDGRID_API_KEY isn't set."""
    if not _SENDGRID_KEY:
        logger.info("Welcome email skipped (no SENDGRID_API_KEY) for %s", to_email)
        return False
    login_url = f"{_APP_PUBLIC_URL}/login"
    first = (owner_name or "there").split()[0]
    text = (
        f"Dear {first},\n\n"
        f"Welcome to INNtelligence — your account for {property_name} is ready.\n\n"
        f"Sign in:  {login_url}\n"
        f"Email:    {to_email}\n"
        f"Temporary password:  {temp_password}\n\n"
        f"Please change your password after your first sign-in.\n\n"
        f"Schedule your onboarding call: {_CALENDLY_URL}\n\n"
        f"Before the call, please have ready:\n"
        f"  - Your PMS login (ResNexus or Cloudbeds)\n"
        f"  - A list of your main competitors\n"
        f"  - Your base rate for each room type\n\n"
        f"Looking forward to getting you live.\n\n"
        f"Jim Williams\nINNtelligence by The Gracious Collection\n{_FROM_EMAIL}"
    )
    try:
        import requests
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {_SENDGRID_KEY}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": _FROM_EMAIL, "name": "Jim Williams · INNtelligence"},
                "subject": "Welcome to INNtelligence — Your account is ready",
                "content": [{"type": "text/plain", "value": text}],
            },
            timeout=20,
        )
        if not r.ok:
            logger.warning("SendGrid failed %s: %s", r.status_code, r.text[:200])
        return r.ok
    except Exception as e:  # noqa: BLE001
        logger.warning("SendGrid error: %s", e)
        return False


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    if not _auth_configured():
        return jsonify({"error": "Authentication is not configured on this server."}), 503
    d = request.get_json(force=True) or {}
    email, password = d.get("email", ""), d.get("password", "")
    try:
        import requests
        r = requests.post(f"{_SUPABASE_URL}/auth/v1/token?grant_type=password",
                          headers={"apikey": _SUPABASE_ANON, "Content-Type": "application/json"},
                          json={"email": email, "password": password}, timeout=15)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Auth service unavailable: {e}"}), 502
    if not r.ok:
        return jsonify({"error": "Invalid email or password."}), 401
    j = r.json()
    user = j.get("user") or {}
    role, tenant_id = _role_and_tenant(user)
    ctx = _tenant_context(tenant_id, user)
    return jsonify({
        "access_token": j.get("access_token"),
        "refresh_token": j.get("refresh_token"),
        "user": {"id": user.get("id"), "email": user.get("email")},
        "tenant_id": tenant_id, "role": role, **ctx,
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    token = _bearer_token()
    if token and _auth_configured():
        try:
            import requests
            requests.post(f"{_SUPABASE_URL}/auth/v1/logout",
                          headers={"apikey": _SUPABASE_ANON, "Authorization": f"Bearer {token}"}, timeout=10)
        except Exception:  # noqa: BLE001
            pass
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("inn_token")
    return resp


@app.route("/api/auth/me")
def api_auth_me():
    if not _auth_configured():
        # Open mode — no Supabase configured (local/demo). Frontend stays usable.
        return jsonify({"authenticated": False, "auth_configured": False})
    user = _sb_user(_bearer_token())
    if not user:
        return jsonify({"authenticated": False, "auth_configured": True})
    role, tenant_id = _role_and_tenant(user)
    ctx = _tenant_context(tenant_id, user)
    return jsonify({
        "authenticated": True, "auth_configured": True,
        "user_id": user.get("id"), "email": user.get("email"),
        "tenant_id": tenant_id, "role": role, **ctx,
    })


@app.route("/api/auth/reset-password", methods=["POST"])
def api_auth_reset_password():
    d = request.get_json(force=True) or {}
    email = d.get("email", "")
    if email and _auth_configured():
        try:
            import requests
            requests.post(f"{_SUPABASE_URL}/auth/v1/recover",
                          headers={"apikey": _SUPABASE_ANON, "Content-Type": "application/json"},
                          json={"email": email}, timeout=15)
        except Exception:  # noqa: BLE001
            pass
    # Always 200 — never reveal whether the email exists.
    return jsonify({"ok": True})


def _slugify(s: str) -> str:
    return "".join(c if (c.isalnum() or c == "-") else "-" for c in (s or "").lower()).strip("-")[:48] or "inn"


@app.route("/api/admin/provision-tenant", methods=["POST"])
def api_admin_provision_tenant():
    _user, err = _require_admin()
    if err:
        return err
    if not _SUPABASE_SERVICE:
        return jsonify({"error": "SUPABASE_SERVICE_KEY not configured"}), 503
    import requests
    d = request.get_json(force=True) or {}
    email = d.get("owner_email", "")
    if not email:
        return jsonify({"error": "owner_email required"}), 400
    plan = d.get("plan_tier", "professional")
    name = d.get("property_name", "")
    svc_hdr = {"apikey": _SUPABASE_SERVICE, "Authorization": f"Bearer {_SUPABASE_SERVICE}",
               "Content-Type": "application/json"}
    rep_hdr = {**svc_hdr, "Prefer": "return=representation"}
    warnings = []

    # 1) Invite the user — Supabase sends the secure invite link automatically.
    try:
        inv = requests.post(f"{_SUPABASE_URL}/auth/v1/invite", headers=svc_hdr,
                            json={"email": email,
                                  "data": {"property_name": name, "owner_name": d.get("owner_name", "")}},
                            timeout=20)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Invite failed: {e}"}), 502
    if not inv.ok:
        return jsonify({"error": f"Invite failed: {inv.text[:200]}"}), 502
    user_id = (inv.json() or {}).get("id")

    # 2) Insert tenant (onboarding_complete=false → forces /onboarding on first login).
    tenant_id = None
    try:
        tr = requests.post(f"{_SUPABASE_URL}/rest/v1/tenants", headers=rep_hdr, json={
            "name": name, "slug": _slugify(name), "plan_tier": plan,
            "active": True, "onboarding_complete": False,
        }, timeout=20)
        if tr.ok and tr.text:
            row = tr.json()
            tenant_id = (row[0] if isinstance(row, list) else row).get("id")
        else:
            warnings.append(f"tenant insert: {tr.text[:120]}")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"tenant insert: {e}")

    # 3) Insert property.
    property_id = None
    if tenant_id:
        try:
            pr = requests.post(f"{_SUPABASE_URL}/rest/v1/properties", headers=rep_hdr, json={
                "tenant_id": tenant_id, "name": name, "city": d.get("city", ""), "state": d.get("state", ""),
            }, timeout=20)
            if pr.ok and pr.text:
                row = pr.json()
                property_id = (row[0] if isinstance(row, list) else row).get("id")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"property insert: {e}")

    # 4) Insert user_profile (feeds the JWT hook: role + tenant_id).
    if user_id and tenant_id:
        try:
            requests.post(f"{_SUPABASE_URL}/rest/v1/user_profiles", headers=svc_hdr, json={
                "user_id": user_id, "tenant_id": tenant_id, "role": "inn_owner",
            }, timeout=20)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"user_profile insert: {e}")

    # 5) Mirror claims onto auth app_metadata so the hook always has them.
    if user_id:
        try:
            requests.put(f"{_SUPABASE_URL}/auth/v1/admin/users/{user_id}", headers=svc_hdr, json={
                "app_metadata": {"app_role": "inn_owner", "tenant_id": tenant_id, "plan_tier": plan},
            }, timeout=20)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"app_metadata set: {e}")

    return jsonify({
        "tenant_id": tenant_id, "property_id": property_id, "user_id": user_id,
        "invited": True, "note": "Supabase invite email sent. Follow up with the personal welcome email.",
        "warnings": warnings or None,
    })


@app.route("/api/admin/tenants")
def api_admin_tenants():
    _user, err = _require_admin()
    if err:
        return err
    if _SUPABASE_SERVICE:
        try:
            import requests
            # Join the first property per tenant for a friendly location label.
            r = requests.get(f"{_SUPABASE_URL}/rest/v1/tenants",
                             headers={"apikey": _SUPABASE_SERVICE, "Authorization": f"Bearer {_SUPABASE_SERVICE}"},
                             params={"select": "id,name,plan_tier,active,onboarding_complete,created_at,"
                                               "properties(name,city,state)"}, timeout=15)
            if r.ok and r.json():
                out = []
                for t in r.json():
                    props = t.get("properties") or []
                    p0 = props[0] if props else {}
                    out.append({
                        "name": p0.get("name") or t.get("name"),
                        "location": ", ".join([x for x in [p0.get("city"), p0.get("state")] if x]) or "—",
                        "plan_tier": t.get("plan_tier"),
                        "last_login": "—",
                        "sync_status": "synced" if t.get("onboarding_complete") else "pending_onboarding",
                        "pending_count": 0,
                    })
                return jsonify({"tenants": out, "source": "supabase"})
        except Exception as e:  # noqa: BLE001
            logger.warning("admin/tenants query failed: %s", e)
    # Demo fallback so the console renders before the tenants table is populated.
    return jsonify({"source": "demo", "tenants": [
        {"name": "Bay Street Inn", "location": "Beaufort, SC", "plan_tier": "professional",
         "last_login": "2026-05-25", "sync_status": "synced", "pending_count": 6},
        {"name": "Cuthbert House Inn", "location": "Beaufort, SC", "plan_tier": "starter",
         "last_login": "2026-05-24", "sync_status": "synced", "pending_count": 3},
        {"name": "Palmetto Bluff Cottages", "location": "Bluffton, SC", "plan_tier": "premium",
         "last_login": "2026-05-26", "sync_status": "syncing", "pending_count": 2},
    ]})


@app.route("/api/onboarding/complete", methods=["POST"])
def api_onboarding_complete():
    if not _auth_configured():
        return jsonify({"success": True, "sync_status": "demo", "note": "auth not configured"})
    token = _bearer_token()
    user = _sb_user(token)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json(force=True) or {}
    user_id = user.get("id")
    # 1) Save PMS credentials (per-tenant JSON; flagged for real KMS encryption).
    if d.get("pms_api_key"):
        try:
            os.makedirs(os.path.join(_BASE_DIR, "config", "pms_creds"), exist_ok=True)
            with open(os.path.join(_BASE_DIR, "config", "pms_creds", f"{user_id}.json"), "w") as f:
                json.dump({"pms_type": d.get("pms_type"), "api_key": d.get("pms_api_key"),
                           "saved_at": datetime.now(timezone.utc).isoformat()}, f)
        except Exception as e:  # noqa: BLE001
            logger.warning("PMS cred save failed: %s", e)
    # 2) Trigger initial PMS sync — stub until PMS connectors are live.
    sync_status = "queued" if d.get("pms_api_key") else "demo_data"
    # 3) Mark onboarding complete on the tenant (clears the /onboarding gate).
    _role, tenant_id = _role_and_tenant(user)
    if _SUPABASE_SERVICE:
        try:
            import requests
            svc_hdr = {"apikey": _SUPABASE_SERVICE, "Authorization": f"Bearer {_SUPABASE_SERVICE}",
                       "Content-Type": "application/json"}
            if tenant_id:
                requests.patch(f"{_SUPABASE_URL}/rest/v1/tenants",
                               headers={**svc_hdr, "Prefer": "return=minimal"},
                               params={"id": f"eq.{tenant_id}"},
                               json={"onboarding_complete": True}, timeout=15)
            # Also clear the legacy app_metadata flag if present.
            requests.put(f"{_SUPABASE_URL}/auth/v1/admin/users/{user_id}", headers=svc_hdr,
                         json={"app_metadata": {"pending_onboarding": False}}, timeout=15)
        except Exception as e:  # noqa: BLE001
            logger.warning("mark onboarding complete failed: %s", e)
    return jsonify({"success": True, "sync_status": sync_status})


@app.route("/api/private-events")
def api_private_events():
    """Private-events inquiries + revenue metrics (Private Events screen).
    Seed data is realistic and static so the screen works independently."""
    prop = _resolve_property()
    meta = PROPERTIES[prop]
    return jsonify({
        "property_name": meta["name"],
        "inquiries": [
            {"id": "pe1", "name": "Sarah & James Thompson", "type": "Wedding",
             "date": "2026-08-23", "guests": 45, "status": "Negotiating",
             "quoted_value": 22500, "days_out": 90, "conflict": None,
             "notes": "Wants rooftop cocktail hour; comparing with one other venue."},
            {"id": "pe2", "name": "Beaufort Medical Group", "type": "Corporate Retreat",
             "date": "2026-06-15", "guests": 12, "status": "Confirmed",
             "quoted_value": 6800, "days_out": 21, "conflict": None,
             "notes": "Annual leadership offsite. AV confirmed."},
            {"id": "pe3", "name": "Emily & Robert Chen", "type": "Wedding",
             "date": "2026-10-10", "guests": 30, "status": "New",
             "quoted_value": None, "days_out": 138, "conflict": None,
             "notes": "Inquiry via website. Not yet quoted."},
            {"id": "pe4", "name": "Marcus & Diana Williams", "type": "Anniversary Buyout",
             "date": "2026-07-19", "guests": 8, "status": "Quoted",
             "quoted_value": 4200, "days_out": 55, "conflict": "Beaufort Water Festival",
             "notes": "July 19 falls during Water Festival — individual bookings may exceed buyout value."},
            {"id": "pe5", "name": "Lowcountry Realty Group", "type": "Executive Meeting",
             "date": "2026-06-05", "guests": 8, "status": "Confirmed",
             "quoted_value": 1200, "days_out": 11, "conflict": None,
             "notes": "Half-day meeting + working lunch."},
        ],
        "metrics": {
            "this_year_revenue": 47200,
            "last_year_revenue": 31500,
            "yoy_growth_pct": 49.8,
            "avg_package_value": 15733,
            "conversion_rate_pct": 62,
            "avg_lead_time_days": 94,
        },
        "event_type_breakdown": [
            {"type": "Weddings", "revenue": 31200, "pct": 66},
            {"type": "Corporate Retreats", "revenue": 10200, "pct": 22},
            {"type": "Anniversary Buyouts", "revenue": 5800, "pct": 12},
        ],
        "blackout_dates": [
            {"window": "Jul 17–27", "event": "Beaufort Water Festival", "individual_revenue": 19800},
            {"window": "May 23–26", "event": "Original Gullah Festival", "individual_revenue": 14200},
            {"window": "Sep 19–21", "event": "Beaufort Shrimp Festival", "individual_revenue": 11400},
        ],
        "projections": [
            {"label": "2 weddings/month @ $18,000 avg", "annual": 432000},
            {"label": "4 corporate retreats/month @ $4,500 avg", "annual": 216000},
        ],
    })


@app.route("/api/events")
def api_events():
    """Demand events within a horizon, each with revenue lift, recommended
    action, and last-year performance (Events Intelligence screen)."""
    prop = _resolve_property()
    eng  = _engine_for(prop)
    try:
        days = max(1, min(int(request.args.get("days", 90)), 180))
    except ValueError:
        days = 90
    base = date.today()

    # Use a calendar that covers the full horizon so far-out events still get a
    # real revenue-lift estimate (90-day cache for short views, 180-day for 6mo).
    horizon = 180 if days > 90 else 90
    cal_df = _cached(f"{prop}:calendar_{horizon}d", lambda: eng.generate_pricing_calendar(
        days_ahead=horizon, base_occupancy=0.75
    ))
    df = cal_df[cal_df["days_out"] < days].copy()

    events = []
    seen = {}
    for offset in range(days):
        d = base + timedelta(days=offset)
        mult, active = eng.get_event_multiplier(d)
        for name in active:
            if name not in seen:
                seen[name] = {"first": d, "mult": mult, "dates": set()}
            seen[name]["dates"].add(d.isoformat())

    for name, info in seen.items():
        rows = df[df["active_events"].str.contains(name, regex=False, na=False)]
        lift = round(((rows["recommended_rate"] - rows["rack_mid"]) * 0.75).sum()) if len(rows) else 0
        impacted_days = len(info["dates"])
        impact_pct = round((info["mult"] - 1.0) * 100, 1)
        days_away = (info["first"] - base).days
        if days_away <= 7:
            action = "Lock premium rates now — demand is imminent. Push 2-night minimums."
        elif impact_pct >= 30:
            action = "High-impact event: raise rates and set minimum-stay; promote packages."
        elif impact_pct >= 15:
            action = "Apply event premium and monitor pickup pace daily."
        else:
            action = "Modest lift — hold rack and watch competitor moves."
        events.append({
            "event":          name,
            "first_date":     info["first"].isoformat(),
            "display":        info["first"].strftime("%b %d"),
            "month":          info["first"].strftime("%B %Y"),
            "days_away":      days_away,
            "impacted_days":  impacted_days,
            "multiplier":     info["mult"],
            "impact_pct":     impact_pct,
            "est_revenue_lift": lift,
            "recommended_action": action,
            "last_year": {
                "revenue_lift": round(lift / YOY_GROWTH),
                "note": f"Drove ~{round(impact_pct / YOY_GROWTH, 1)}% rate lift last year",
            },
        })
    events.sort(key=lambda e: e["first_date"])
    return jsonify({
        "days": days,
        "events": events,
        "total_lift": sum(e["est_revenue_lift"] for e in events),
        "event_count": len(events),
    })


@app.route("/api/market-intelligence")
def market_intelligence():
    data = _cached("market_intel", lambda: _scraper.get_compression_data(forward_days=30))
    return jsonify(data)


@app.route("/api/fnb/summary")
def fnb_summary():
    """F&B revenue summary. The selected property supplies the display labels
    (restaurant + bar names); the underlying demo dataset is shared.
    RECOMMENDATIONS_SPEC is imported directly because generate_recommendations()
    pulls a config helper not present in this build."""
    from modules.hospitality.fnb_engine import (
        FNBEngine, RECOMMENDATIONS_SPEC, DEMO_FNB_TENANT,
    )
    prop = _resolve_property()
    meta = PROPERTIES[prop]
    tenant = meta.get("fnb_tenant") or DEMO_FNB_TENANT
    eng = FNBEngine()

    WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def _with_yoy(rows):
        """Normalize both outlets to covers/avg_check, pad to a full 7-day week
        (closed days shown as zero), and add last-year YoY figures."""
        by_day = {}
        for r in rows:
            covers = r.get("covers", r.get("guests", 0))
            check  = r.get("avg_check", r.get("avg_spend", 0))
            by_day[r["day"]] = {
                "day":          r["day"],
                "covers":       covers,
                "avg_check":    check,
                "revenue":      r["revenue"],
                "occ_pct":      r["occ_pct"],
                "closed":       False,
                "ly_covers":    round(covers / YOY_GROWTH),
                "ly_avg_check": round(check / YOY_GROWTH, 1),
                "ly_revenue":   round(r["revenue"] / YOY_GROWTH),
            }
        out = []
        for day in WEEK:
            out.append(by_day.get(day, {
                "day": day, "covers": 0, "avg_check": 0, "revenue": 0, "occ_pct": 0,
                "closed": True, "ly_covers": 0, "ly_avg_check": 0, "ly_revenue": 0,
            }))
        return out

    return jsonify({
        "labels": {
            "restaurant": meta.get("restaurant", "Restaurant"),
            "rooftop_bar": meta.get("rooftop_bar", "Rooftop Bar"),
        },
        "summary":         eng.summary_flat(tenant),
        "restaurant_dow":  _with_yoy(eng.dow_daily(tenant, "restaurant")),
        "rooftop_dow":     _with_yoy(eng.dow_daily(tenant, "rooftop_bar")),
        "recommendations": [dict(c) for c in RECOMMENDATIONS_SPEC],
    })


@app.route("/api/roi")
def api_roi():
    """Monthly ROI performance report from the existing performance_engine,
    augmented with comp-set indices, YTD, projected annual, and expanded
    top-5 wins / missed opportunities mined from the live pricing calendar."""
    from modules.hospitality.performance_engine import get_report
    from modules.analytics.historical_engine import HistoricalEngine, SEASONAL_OCC
    prop = _resolve_property()
    eng  = _engine_for(prop)
    report = get_report(PROPERTIES.get(prop), "professional")
    m = report["metrics"]
    today = date.today()

    # ── Comp-set indices (100 = parity; >100 = outperforming) ──────────────
    your_occ   = m["occupancy_this_month"]
    your_revpar = m["revpar_this_month"]
    your_adr   = round(your_revpar / (your_occ / 100)) if your_occ else your_revpar
    comp_rates = eng.get_competitor_rates(today)
    comp_adr   = round(sum(comp_rates.values()) / len(comp_rates)) if comp_rates else your_adr
    comp_occ   = round(SEASONAL_OCC[today.month - 1] * 100, 1)
    comp_revpar = round(comp_adr * comp_occ / 100)
    idx = lambda you, comp: round(you / comp * 100, 1) if comp else 100.0
    comp_index = {
        "revpar": {"you": your_revpar, "comp": comp_revpar, "index": idx(your_revpar, comp_revpar)},
        "occupancy": {"you": your_occ, "comp": comp_occ, "index": idx(your_occ, comp_occ)},
        "adr": {"you": your_adr, "comp": comp_adr, "index": idx(your_adr, comp_adr)},
    }

    # ── YTD + projected annual (from 24-month historical trend) ────────────
    trend = HistoricalEngine().monthly_kpi_trend(prop, months=24)
    cy = trend["current_year"]
    months_elapsed = today.month
    ytd_current = sum(r["revenue"] for r in cy[:months_elapsed])
    # prior-year same period
    py = trend["prior_year"]
    ytd_prior = sum(r["revenue"] for r in py[:months_elapsed])
    projected_annual = round(ytd_current / months_elapsed * 12) if months_elapsed else 0

    # ── Expand wins / missed from the live 90-day calendar ─────────────────
    cal_df = _cached(f"{prop}:calendar_90d", lambda: eng.generate_pricing_calendar(
        days_ahead=90, base_occupancy=0.75
    ))
    evt = cal_df[cal_df["active_events"].astype(bool) & (cal_df["active_events"] != "")]
    evt = evt.sort_values("recommended_rate", ascending=False)
    wins = []
    seen = set()
    for _, row in evt.iterrows():
        key = (row["date"], row["tier"])
        if key in seen:
            continue
        seen.add(key)
        lift = round(row["recommended_rate"] - row["last_year_rate"])
        wins.append({
            "date":             row["date"],
            "event":            str(row["active_events"]).split(";")[0].strip(),
            "room":             row["room_name"],
            "rate_recommended": round(row["recommended_rate"]),
            "rate_prior_year":  round(row["last_year_rate"]),
            "lift_per_night":   lift,
        })
        if len(wins) >= 5:
            break

    # Missed: cells priced below the comp-set average (money left on the table)
    under = cal_df[cal_df["rate_vs_comp_pct"] < 0].sort_values("rate_vs_comp_pct").head(5)
    missed = [{
        "date":   row["date"],
        "room":   row["room_name"],
        "reason": f"Priced {abs(round(row['rate_vs_comp_pct'],1))}% below comp avg (${round(row['competitor_avg']):,}) — room to raise",
        "estimated_missed_revenue": round(row["competitor_avg"] - row["recommended_rate"]),
    } for _, row in under.iterrows()]

    report["comp_index"] = comp_index
    report["ytd"] = {
        "current": ytd_current, "prior": ytd_prior,
        "change": ytd_current - ytd_prior,
        "change_pct": round((ytd_current - ytd_prior) / ytd_prior * 100, 1) if ytd_prior else 0.0,
        "months_elapsed": months_elapsed,
    }
    report["projected_annual_revenue"] = projected_annual
    report["monthly_impact_vs_nothing"] = report["engine_contribution"]["estimated_revenue_lift"]
    if len(wins) >= len(report.get("top_wins", [])):
        report["top_wins"] = wins
    if missed:
        report["missed_opportunities"] = missed
    return jsonify(report)


@app.route("/api/weather")
def api_weather():
    """7-day NWS forecast + demand hints from weather_engine."""
    from modules.hospitality import weather_engine
    prop = _resolve_property()
    cfg  = PROPERTIES.get(prop, {})
    return jsonify(_cached(f"{prop}:weather", lambda: weather_engine.get_summary(cfg)))


@app.route("/api/historical")
def api_historical():
    """24-month KPI trend + positioning + best/worst months, seasonal analysis,
    and a rolling 12-month RevPAR trend (Historical screen)."""
    from modules.analytics.historical_engine import HistoricalEngine
    import calendar as _cal
    prop = _resolve_property()
    eng  = HistoricalEngine()

    def _build():
        trend = eng.monthly_kpi_trend(prop, months=24)
        positioning = eng.competitive_positioning_history(prop, days=90)
        monthly = trend["monthly_data"]

        best = max(monthly, key=lambda r: r["revpar"])
        worst = min(monthly, key=lambda r: r["revpar"])

        # Seasonal pattern: average RevPAR by calendar month across all data
        by_month = {}
        for r in monthly:
            mnum = int(r["month_iso"].split("-")[1])
            by_month.setdefault(mnum, []).append(r["revpar"])
        seasonal = [{
            "month": _cal.month_abbr[mn],
            "avg_revpar": round(sum(v) / len(v)),
        } for mn, v in sorted(by_month.items())]
        peak = max(seasonal, key=lambda s: s["avg_revpar"])
        low  = min(seasonal, key=lambda s: s["avg_revpar"])
        seasonal_reco = (
            f"Peak season centers on {peak['month']} — protect rate and require minimum stays. "
            f"{low['month']} is softest; deploy packages, midweek offers, and local-market campaigns to fill."
        )

        # Rolling 12-month RevPAR (trailing average)
        rolling = []
        for i in range(len(monthly)):
            window = monthly[max(0, i - 11):i + 1]
            rolling.append({
                "month": monthly[i]["month"],
                "rolling_revpar": round(sum(w["revpar"] for w in window) / len(window)),
            })

        return {
            "kpi_trend":   trend,
            "positioning": positioning,
            "best_month":  best,
            "worst_month": worst,
            "seasonal":    seasonal,
            "seasonal_recommendation": seasonal_reco,
            "rolling_12mo": rolling,
        }

    return jsonify(_cached(f"{prop}:historical", _build))


@app.route("/api/reputation")
def api_reputation():
    """Per-platform review scores, competitor comparison, pricing power."""
    from modules.hospitality.reputation_engine import ReputationEngine
    prop = _resolve_property()
    cfg  = PROPERTIES.get(prop, {})
    eng  = _engine_for(prop)
    competitors = [{"name": c.name} for c in eng.competitors.values()]
    return jsonify(_cached(
        f"{prop}:reputation",
        lambda: ReputationEngine().get_reputation_summary(cfg, competitors),
    ))


@app.route("/api/guests")
def api_guests():
    """Searchable guest list (summary fields)."""
    from modules.analytics import guest_crm_engine as crm
    return jsonify({"guests": crm.guest_summaries(), "total": len(crm.GUESTS)})


@app.route("/api/guests/<gid>")
def api_guest_profile(gid: str):
    """Full guest profile."""
    from modules.analytics import guest_crm_engine as crm
    g = crm.guest_profile(gid)
    if not g:
        return jsonify({"error": "Guest not found"}), 404
    return jsonify(g)


@app.route("/api/crm/meta")
def api_crm_meta():
    """Campaign segments, templates, and campaign history."""
    from modules.analytics import guest_crm_engine as crm
    return jsonify({
        "segments": crm.segments(),
        "templates": crm.templates(),
        "campaign_history": crm.campaign_history(),
    })


@app.route("/api/crm/analytics")
def api_crm_analytics():
    """Guest analytics: sources, lead time, geography, price sensitivity."""
    from modules.analytics import guest_crm_engine as crm
    return jsonify(crm.analytics())


@app.route("/api/crm/campaign", methods=["POST"])
def api_crm_send_campaign():
    """Create/send a campaign (demo — echoes a campaign record)."""
    from modules.analytics import guest_crm_engine as crm
    data = request.get_json(force=True) or {}
    seg = next((s for s in crm.segments() if s["id"] == data.get("segment")), None)
    tpl = next((t for t in crm.templates() if t["id"] == data.get("template")), None)
    recipients = seg["count"] if seg else 0
    return jsonify({
        "ok": True,
        "campaign": {
            "name": data.get("name", "Untitled Campaign"),
            "segment": seg["name"] if seg else "—",
            "template": tpl["name"] if tpl else "—",
            "recipients": recipients,
            "sent_date": date.today().isoformat(),
            "status": "queued",
        },
    })


@app.route("/api/gift-shop")


@app.route("/api/gift-shop")
def api_gift_shop():
    """Full gift-shop store: categories, items, inventory, sales, best/slow movers."""
    from modules.hospitality import gift_shop_store
    return jsonify(gift_shop_store.get_store())


@app.route("/api/gift-shop/category", methods=["POST"])
def api_gift_shop_add_category():
    from modules.hospitality import gift_shop_store
    d = request.get_json(force=True) or {}
    cid = gift_shop_store.add_category(d.get("name", "New Category"), d.get("emoji", "🛍️"),
                                       d.get("fulfillment", "in-stock"), d.get("supplier", ""))
    return jsonify({"ok": True, "id": cid})


@app.route("/api/gift-shop/category/<cid>", methods=["PUT", "DELETE"])
def api_gift_shop_category(cid):
    from modules.hospitality import gift_shop_store
    if request.method == "DELETE":
        return jsonify({"ok": gift_shop_store.delete_category(cid)})
    ok = gift_shop_store.update_category(cid, request.get_json(force=True) or {})
    return jsonify({"ok": ok})


@app.route("/api/gift-shop/item", methods=["POST"])
def api_gift_shop_add_item():
    from modules.hospitality import gift_shop_store
    d = request.get_json(force=True) or {}
    iid = gift_shop_store.add_item(d.get("category_id", ""), d)
    if iid is None:
        return jsonify({"ok": False, "error": "Unknown category"}), 404
    return jsonify({"ok": True, "id": iid})


@app.route("/api/gift-shop/item/<iid>", methods=["PUT", "DELETE"])
def api_gift_shop_item(iid):
    from modules.hospitality import gift_shop_store
    if request.method == "DELETE":
        return jsonify({"ok": gift_shop_store.delete_item(iid)})
    ok = gift_shop_store.update_item(iid, request.get_json(force=True) or {})
    return jsonify({"ok": ok})


@app.route("/api/revenue-intelligence")
def api_revenue_intelligence():
    """Revenue Intelligence: gap nights, Fri/Sat solver, min-stay optimizer,
    AI revenue recommendations, and customer-experience recommendations."""
    from modules.hospitality import los_engine, weather_engine
    prop = _resolve_property()
    eng  = _engine_for(prop)
    meta = PROPERTIES.get(prop, {})
    base = date.today()
    rooms = [{"id": r["room_id"], "name": r["name"], "base": r.get("rack_low", 300)}
             for r in meta.get("rooms", [])] or None

    cal_df = _cached(f"{prop}:calendar_90d", lambda: eng.generate_pricing_calendar(
        days_ahead=90, base_occupancy=0.75
    ))

    def _build():
        gaps = los_engine.find_gap_nights(days=60, rooms=rooms)
        recovery = sum(g["recommended_price"] for g in gaps)

        # ── Friday/Saturday solver: high-demand Saturdays needing Friday fill ──
        sat = cal_df[(cal_df["day_of_week"] == "Saturday")].copy()
        sat = sat.sort_values("recommended_rate", ascending=False)
        fri_sat, seen_dates = [], set()
        for _, row in sat.iterrows():
            d = row["date"]
            if d in seen_dates:
                continue
            seen_dates.add(d)
            fri = (date.fromisoformat(d) - timedelta(days=1))
            evt = str(row["active_events"]).split(";")[0].strip()
            fri_sat.append({
                "saturday": d,
                "friday": fri.isoformat(),
                "room": row["room_name"],
                "context": evt or "high weekend demand",
                "recommendations": [
                    f"Add a Friday-night requirement to new Saturday {row['day_of_week']} bookings",
                    f"Offer a Friday-only rate of {('$' + str(round(row['recommended_rate'] * 0.9)))} to bridge the gap",
                    "Send a targeted 'extend your weekend' email to the Saturday guest",
                ],
            })
            if len(fri_sat) >= 4:
                break

        # ── Min-stay optimizer: events / strong weekends ──────────────────────
        min_stay = []
        evt_rows = cal_df[cal_df["active_events"].str.len() > 0].sort_values("event_multiplier", ascending=False)
        seen_ms = set()
        for _, row in evt_rows.iterrows():
            d = row["date"]
            if d in seen_ms:
                continue
            seen_ms.add(d)
            nights = 3 if row["event_multiplier"] >= 1.3 else 2
            min_stay.append({
                "date": d, "recommended_min_stay": nights,
                "reason": f"{str(row['active_events']).split(';')[0].strip()} — demand ×{row['event_multiplier']}; {nights}-night minimum protects revenue",
            })
            if len(min_stay) >= 6:
                break

        # ── AI revenue recommendations (top 10) ───────────────────────────────
        recs = []
        under = cal_df[cal_df["rate_vs_comp_pct"] < -5].sort_values("rate_vs_comp_pct").head(4)
        for _, r in under.iterrows():
            gain = round(r["competitor_avg"] - r["recommended_rate"])
            recs.append({"priority": "high", "category": "Pricing",
                         "action": f"Raise {r['room_name']} for {r['date']} — priced {abs(round(r['rate_vs_comp_pct'],1))}% below comp avg",
                         "impact": gain})
        for g in gaps[:3]:
            recs.append({"priority": "medium", "category": "Gap Fill",
                         "action": f"Fill {g['gap_length_nights']}-night gap on {g['date']} ({g['room_name']}) at {('$' + str(g['recommended_price']))}",
                         "impact": g["recommended_price"]})
        for ms in min_stay[:2]:
            recs.append({"priority": "high", "category": "Min Stay",
                         "action": f"Set {ms['recommended_min_stay']}-night minimum on {ms['date']} — {ms['reason'].split('—')[0].strip()}",
                         "impact": 0})
        recs.append({"priority": "medium", "category": "Win-back",
                     "action": "Send win-back email to guests who haven't visited in 6+ months",
                     "impact": 0})
        recs = recs[:10]

        # ── Customer-experience recommendations ───────────────────────────────
        cx = []
        wx = weather_engine.get_summary(meta)
        rainy = next((f for f in wx.get("forecast", []) if "rain" in f.get("short", "").lower()), None)
        if rainy:
            cx.append({"icon": "🌧️", "text": f"{rainy['name']} forecast: {rainy['short']} — promote indoor F&B specials and spa add-ons."})
        cx.append({"icon": "🎉", "text": "3 guests checking in this week are celebrating anniversaries — consider a complimentary upgrade or amenity."})
        cx.append({"icon": "⭐", "text": "2 VIP repeat guests arrive this weekend — flag for personalized welcome notes."})
        cx.append({"icon": "🐶", "text": "1 arriving guest booked the pet-friendly room — pre-stage the pet welcome kit."})

        return {
            "gap_nights": gaps,
            "gap_count": len(gaps),
            "potential_recovery": recovery,
            "fri_sat": fri_sat,
            "min_stay": min_stay,
            "ai_recommendations": recs,
            "cx_recommendations": cx,
        }

    return jsonify(_cached(f"{prop}:revintel", _build))


@app.route("/api/gap-night")
def api_gap_night():
    """Orphan gap-night fills + min-stay recommendations from los_engine."""
    from modules.hospitality import los_engine
    prop = _resolve_property()
    cfg  = PROPERTIES.get(prop, {})
    rooms = [
        {"id": r["room_id"], "name": r["name"], "base": r.get("rack_low", 300)}
        for r in cfg.get("rooms", [])
    ] or None
    def _build():
        gaps = los_engine.find_gap_nights(days=60, rooms=rooms)
        try:
            mins = los_engine.min_stay_recommendations(days=60, rooms=rooms)
        except ImportError:
            mins = []
        recovery = sum(g["recommended_price"] for g in gaps)
        return {
            "gap_nights":           gaps,
            "min_stay":             mins,
            "gap_count":            len(gaps),
            "potential_recovery":   recovery,
            "min_stay_count":       len(mins),
        }
    return jsonify(_cached(f"{prop}:gapnight", _build))


def _all_packages():
    """Combined catalog: rich existing packages (default active) + the broader
    industry catalog (default available). Existing entries win on id collision."""
    catalog = {}
    for pid, cfg in INDUSTRY_PACKAGES.items():
        catalog[pid] = {
            "name": cfg["name"], "emoji": cfg["emoji"], "description": cfg["description"],
            "premium": cfg["premium"], "pct_inns": cfg["pct_inns"],
            "eligible_rooms_count": 14, "take_rate": 0.20, "default": "available",
            "tagline": cfg["description"], "eligible_rooms": "all rooms", "available": "Year-round",
        }
    for pid, cfg in PACKAGES_CONFIG.items():
        catalog[pid] = {**cfg, "pct_inns": cfg.get("pct_inns", 55), "default": "active"}
    return catalog


def _pkg_revenue(rooms_count, take_rate, premium):
    return round(rooms_count * 30 * 0.75 * take_rate * abs(premium))


@app.route("/api/packages")
def packages():
    prop    = _resolve_property()
    status  = _load_packages_status(prop)
    catalog = _all_packages()
    active, available = [], []
    for pid, cfg in catalog.items():
        st = status.get(pid, cfg["default"])
        if st == "coming_soon":
            st = "available"
        rooms_count = cfg["eligible_rooms_count"]
        entry = {
            "id":                       pid,
            "status":                   st,
            "name":                     cfg["name"],
            "emoji":                    cfg["emoji"],
            "tagline":                  cfg.get("tagline", cfg["description"]),
            "description":              cfg["description"],
            "premium":                  cfg["premium"],
            "is_discount":              cfg["premium"] < 0,
            "pct_inns":                 cfg["pct_inns"],
            "eligible_rooms":           cfg.get("eligible_rooms", "all rooms"),
            "eligible_rooms_count":     rooms_count,
            "take_rate":                cfg["take_rate"],
            "available":                cfg.get("available", "Year-round"),
            "monthly_revenue":          _pkg_revenue(rooms_count, cfg["take_rate"], cfg["premium"]),
            "monthly_revenue_potential": _pkg_revenue(rooms_count, 0.20, cfg["premium"]),
        }
        (active if st == "active" else available).append(entry)
    available.sort(key=lambda p: p["pct_inns"], reverse=True)
    return jsonify({"active": active, "available": available})


@app.route("/api/packages/<pkg_id>/toggle", methods=["POST"])
def toggle_package(pkg_id: str):
    catalog = _all_packages()
    if pkg_id not in catalog:
        return jsonify({"error": "Unknown package"}), 404
    prop   = _resolve_property()
    status = _load_packages_status(prop)
    current = status.get(pkg_id, catalog[pkg_id]["default"])
    if current == "coming_soon":
        current = "available"
    status[pkg_id] = "available" if current == "active" else "active"
    _save_packages_status(status, prop)
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
    prop   = _resolve_property()
    eng    = _engine_for(prop)
    prefix = PROPERTIES[prop].get("export_prefix", "anchorage_1770")
    cal_df = eng.generate_pricing_calendar(days_ahead=90, base_occupancy=0.75)
    buf    = io.StringIO()
    cal_df.to_csv(buf, index=False)
    buf.seek(0)
    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="{prefix}_pricing_{date.today().isoformat()}.csv"'
    )
    return resp


# ─────────────────────────────────────────────────────────────────────────────
#  Data formatters
# ─────────────────────────────────────────────────────────────────────────────

def _format_room_rates(df, report_date: date) -> List[Dict[str, Any]]:
    tier_icons = {"cottage": "🏡", "waterfront": "🌊", "water_view": "🔭", "garden": "🌿",
                  "carriage_house": "🏛️", "signature_suite": "✨", "grand_parlor": "👑"}
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
            "last_year_rate": float(row["last_year_rate"]) if "last_year_rate" in row else None,
            "rack_low":      rack_low,
            "rack_high":     float(row["rack_high"]),
            "rack_mid":      rack_mid,
            "status":        status,
            "status_label":  status_label,
            "vs_rack_pct":   float(row["rate_vs_rack_pct"]),
            "vs_comp_pct":   float(row.get("rate_vs_comp_pct", 0)),
            "confidence":    str(row.get("confidence", "")),
            "active_events": events,
            "reasoning":     str(row.get("reasoning", "")),
        })
    return rooms


_TIER_LABELS = {1: "Your Direct Competitors", 2: "Market Reference", 3: "Market Anchors"}


def _synth_availability(comp, rate: float) -> Dict[str, Any]:
    """Deterministic availability for a competitor the scraper doesn't cover
    (e.g. Anchorage 1770, Hampton, Montage). Uses the competitor's own rate
    relative to its rack midpoint as a demand proxy — same seasonal/event/
    weekend signal already baked into get_competitor_rates()."""
    mid = (comp.base_low + comp.base_high) / 2.0 or 1.0
    ratio = rate / mid
    est_occ = max(0.45, min(0.99, 0.55 + (ratio - 1.0) * 1.4))
    if   est_occ >= 0.90: status, ind = "sold_out", "🔴"
    elif est_occ >= 0.75: status, ind = "limited",  "🟡"
    else:                 status, ind = "available", "🟢"
    return {"indicator": ind, "est_occ": round(est_occ, 2), "status": status}


def _build_competitor_comparison(days: int = 7, start_date: Optional[date] = None,
                                 engine: Optional[AnchoragePricingEngine] = None) -> Dict[str, Any]:
    eng          = engine or _engine
    base         = start_date or date.today()
    dates: List[str]              = []
    property_avg: List[float]     = []
    competitors: Dict[str, List]  = {}
    availability: Dict[str, List] = {}

    # name → Competitor object, for tier metadata + availability synthesis
    comp_by_name = {c.name: c for c in eng.competitors.values()}

    for offset in range(days):
        check_in = base + timedelta(days=offset)
        dates.append(check_in.strftime("%a %b %-d"))

        room_rates = [eng.calculate_room_rate(rid, check_in, 0.75)["rate"] for rid in eng.rooms]
        property_avg.append(round(sum(room_rates) / len(room_rates), 2))

        comp_rates = eng.get_competitor_rates(check_in)
        avail_snap = _scraper.get_availability_snapshot(check_in)
        for name, rate in comp_rates.items():
            competitors.setdefault(name, []).append(rate)
            if name in avail_snap:
                info = avail_snap[name]
                availability.setdefault(name, []).append({
                    "indicator": info["indicator"],
                    "est_occ":   info["est_occupancy"],
                    "status":    info["availability_status"],
                })
            else:
                # Synthesize for competitors the scraper doesn't track.
                availability.setdefault(name, []).append(
                    _synth_availability(comp_by_name[name], rate)
                )

    # Group competitor names by tier (tier 1 first) for the tiered panel.
    tier_groups: Dict[int, List[str]] = {1: [], 2: [], 3: []}
    for name in competitors:
        t = getattr(comp_by_name.get(name), "tier", 1)
        tier_groups.setdefault(t, []).append(name)
    comp_tiers = [
        {"tier": t, "label": _TIER_LABELS.get(t, f"Tier {t}"), "names": tier_groups[t]}
        for t in sorted(tier_groups) if tier_groups[t]
    ]

    return {
        "dates":         dates,
        "property_avg":  property_avg,
        "competitors":   competitors,
        "availability":  availability,
        "comp_tiers":    comp_tiers,
    }


def _upcoming_events(days: int = 60, start_date: Optional[date] = None,
                     engine: Optional[AnchoragePricingEngine] = None) -> List[Dict[str, Any]]:
    eng  = engine or _engine
    base = start_date or date.today()
    seen: Dict[str, Dict] = {}
    for offset in range(days):
        check_date = base + timedelta(days=offset)
        mult, active = eng.get_event_multiplier(check_date)
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
#  SPA catch-all — MUST be the last route. Serves built static assets from
#  dashboard/dist, and falls back to index.html so client-side routing works.
#  Any unmatched /api/* path returns JSON 404 instead of the SPA shell.
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/<path:path>")
def spa_catch_all(path):
    if path == "api" or path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    candidate = os.path.join(_DIST_DIR, path)
    if os.path.isfile(candidate):
        return send_from_directory(_DIST_DIR, path)
    return _serve_spa()


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Local dev only — in production gunicorn binds $PORT (see nixpacks.toml).
    port = int(os.environ.get("PORT", 5001))
    logger.info("Starting INNtelligence on http://0.0.0.0:%s", port)
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
