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

@app.route("/")
def index():
    return render_template("index.html")


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
            "id":           meta["id"],
            "name":         meta["name"],
            "city":         meta["city"],
            "show_address": meta.get("show_address", True),
            "address":      meta.get("address", ""),
            "restaurant":   meta.get("restaurant", ""),
            "rooftop_bar":  meta.get("rooftop_bar", ""),
            "room_count":   meta.get("room_count", len(day_rates)),
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
    return jsonify({
        "labels": {
            "restaurant": meta.get("restaurant", "Restaurant"),
            "rooftop_bar": meta.get("rooftop_bar", "Rooftop Bar"),
        },
        "summary":         eng.summary_flat(tenant),
        "restaurant_dow":  eng.dow_daily(tenant, "restaurant"),
        "rooftop_dow":     eng.dow_daily(tenant, "rooftop_bar"),
        "recommendations": [dict(c) for c in RECOMMENDATIONS_SPEC],
    })


@app.route("/api/packages")
def packages():
    prop   = _resolve_property()
    status = _load_packages_status(prop)
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
    prop   = _resolve_property()
    status = _load_packages_status(prop)
    status[pkg_id] = "coming_soon" if status.get(pkg_id) == "active" else "active"
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
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting Anchorage 1770 Pricing Dashboard on http://localhost:5001")
    app.run(debug=False, host="0.0.0.0", port=5001, threaded=True)
