"""
app.py — Anchorage 1770 Inn Pricing Dashboard
Flask web application — http://localhost:5000

Routes:
  GET  /              — full dashboard (HTML)
  GET  /api/dashboard — all dashboard data as JSON (used by frontend JS)
  GET  /export        — 90-day pricing calendar as CSV download
"""

from __future__ import annotations

import io
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, make_response, render_template

from modules.hospitality.anchorage_pricing import (
    ANNUAL_EVENTS,
    ROOM_INVENTORY,
    AnchoragePricingEngine,
)
from modules.hospitality.competitor_scraper import CompetitorScraper
from modules.module5_optimization.optimizer import PricingOptimizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Singletons + simple TTL cache (no Redis needed for local use)
# ─────────────────────────────────────────────────────────────────────────────

_engine   = AnchoragePricingEngine()
_scraper  = CompetitorScraper()
_optimizer = PricingOptimizer()

_cache: Dict[str, Any] = {}
_CACHE_TTL = 300  # 5 minutes


def _cached(key: str, fn) -> Any:
    now = time.monotonic()
    entry = _cache.get(key)
    if entry and (now - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    data = fn()
    _cache[key] = {"data": data, "ts": now}
    return data


# ─────────────────────────────────────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def dashboard_data():
    today   = date.today()
    occ     = 0.75

    # ── Today's rates ────────────────────────────────────────────────────
    today_df = _cached("today_rates", lambda: _engine.generate_daily_report(
        target_date=today, occupancy_rate=occ
    ))
    today_rates = _format_room_rates(today_df, today)

    # ── 90-day calendar (source for forecast + optimizer) ─────────────────
    cal_df = _cached("calendar_90d", lambda: _engine.generate_pricing_calendar(
        days_ahead=90, base_occupancy=occ
    ))

    # ── 7-day competitor comparison ───────────────────────────────────────
    comp_7day = _cached("comp_7day", lambda: _build_competitor_comparison(7))

    # ── Upcoming events (next 60 days) ────────────────────────────────────
    events = _upcoming_events(days=60)

    # ── 90-day revenue forecast ───────────────────────────────────────────
    forecast = _build_revenue_forecast(cal_df)

    # ── Optimization recommendations ──────────────────────────────────────
    optimizations = _cached("optimizations", lambda: _optimizer.analyze(cal_df, occ))

    return jsonify({
        "today_rates":           today_rates,
        "competitor_comparison": comp_7day,
        "upcoming_events":       events,
        "revenue_forecast":      forecast,
        "optimizations":         _format_optimizations(optimizations),
        "summary": {
            "avg_rate":       round(sum(r["rate"] for r in today_rates) / len(today_rates), 2),
            "revpar":         round(sum(r["rate"] for r in today_rates) * occ / len(today_rates), 2),
            "occ_target":     f"{int(occ * 100)}%",
            "active_events":  sum(1 for r in today_rates if r["active_events"]),
            "rooms_premium":  sum(1 for r in today_rates if r["status"] == "premium"),
            "rooms_hold":     sum(1 for r in today_rates if r["status"] == "hold"),
            "rooms_discount": sum(1 for r in today_rates if r["status"] == "discount"),
        },
        "report_date":   today.isoformat(),
        "generated_at":  datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })


@app.route("/export")
def export_csv():
    cal_df = _engine.generate_pricing_calendar(days_ahead=90, base_occupancy=0.75)
    buf = io.StringIO()
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
    tier_icons = {
        "cottage":    "🏡",
        "waterfront": "🌊",
        "water_view": "🔭",
        "garden":     "🌿",
    }
    rooms = []
    for _, row in df.iterrows():
        rate     = float(row["rate"])
        rack_mid = float(row["rack_mid"])
        rack_low = float(row["rack_low"])

        if rate > rack_mid * 1.05:
            status, status_label = "premium", f"+{row['rate_vs_rack_pct']}% vs rack"
        elif rate >= rack_low * 0.99:
            status, status_label = "hold", "At rack rate"
        else:
            status, status_label = "discount", f"{row['rate_vs_rack_pct']}% vs rack"

        events = row.get("active_events", [])
        if isinstance(events, str):
            events = [e.strip() for e in events.split(";") if e.strip()] if events else []

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


def _build_competitor_comparison(days: int = 7) -> Dict[str, Any]:
    today = date.today()
    dates:         List[str]             = []
    anchorage_avg: List[float]           = []
    competitors:   Dict[str, List[float]] = {}

    for offset in range(days):
        check_in = today + timedelta(days=offset)
        dates.append(check_in.strftime("%a %b %-d"))

        room_rates = [
            _engine.calculate_room_rate(rid, check_in, 0.75)["rate"]
            for rid in ROOM_INVENTORY
        ]
        anchorage_avg.append(round(sum(room_rates) / len(room_rates), 2))

        comp_rates = _scraper.get_rates_for_date(check_in)
        for name, rate in comp_rates.items():
            competitors.setdefault(name, []).append(rate)

    return {
        "dates":         dates,
        "anchorage_avg": anchorage_avg,
        "competitors":   competitors,
    }


def _upcoming_events(days: int = 60) -> List[Dict[str, Any]]:
    today  = date.today()
    seen: Dict[str, Dict] = {}

    for offset in range(days):
        check_date = today + timedelta(days=offset)
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
    import pandas as _pd
    cal_df = cal_df.copy()
    cal_df["projected_rev"] = cal_df["recommended_rate"] * 0.75
    daily = (
        cal_df.groupby("date")
        .agg(total_rev=("projected_rev", "sum"), avg_rate=("recommended_rate", "mean"))
        .reset_index()
        .sort_values("date")
    )
    # Format date labels: show day-of-week + date for first of each week
    labels = []
    for i, row in enumerate(daily.itertuples()):
        d = date.fromisoformat(row.date)
        labels.append(d.strftime("%b %-d") if d.weekday() == 0 or i == 0 else "")

    return {
        "dates":    daily["date"].tolist(),
        "labels":   labels,
        "revenues": daily["total_rev"].round(2).tolist(),
        "avg_rates":daily["avg_rate"].round(2).tolist(),
    }


def _format_optimizations(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "midweek_specials":            raw.get("midweek_specials", [])[:6],
        "packages":                    raw.get("packages", [])[:8],
        "ranked_actions":              raw.get("ranked_actions", [])[:10],
        "total_midweek_windows":       raw.get("total_midweek_windows", 0),
        "total_package_opportunities": raw.get("total_package_opportunities", 0),
        "estimated_total_uplift":      raw.get("estimated_total_uplift", 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting Anchorage 1770 Pricing Dashboard on http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
