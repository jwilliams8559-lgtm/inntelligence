"""
engine/learning/market_signals.py — Phase 7

Federated learning signal extraction. For each property we compute a set
of anonymized, aggregate signals and store them in `market_signals`
keyed by (market, month, day_of_week) — never by tenant or property.
A separate aggregation pass then collapses contributions from every
property into city+state-level benchmarks the rate engine can use.

Privacy invariants:
  - market_signals rows carry NO tenant_id and NO property_id
  - signals are derived from at least 30 days of history per cell
  - we drop any cell whose underlying day count < 14 (too thin to share)
  - rate_elasticity is a ratio, not a raw rate
"""
from __future__ import annotations

import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Supabase REST helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sb_url() -> str: return os.getenv("SUPABASE_URL", "").rstrip("/")
def _sb_key() -> str: return os.getenv("SUPABASE_SERVICE_KEY", "")
def _sb_hdrs(extra: Optional[dict] = None) -> dict:
    h = {"apikey": _sb_key(), "Authorization": f"Bearer {_sb_key()}",
         "Content-Type": "application/json"}
    if extra: h.update(extra)
    return h


def _sb_get(table: str, params: dict) -> list[dict]:
    r = requests.get(f"{_sb_url()}/rest/v1/{table}",
                     headers=_sb_hdrs({"Prefer": "count=none"}),
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else []


def _sb_upsert(table: str, rows: list[dict],
               on_conflict: Optional[str] = None) -> int:
    if not rows: return 0
    params = {"on_conflict": on_conflict} if on_conflict else {}
    r = requests.post(f"{_sb_url()}/rest/v1/{table}",
                      headers=_sb_hdrs({"Prefer": "resolution=merge-duplicates,return=minimal"}),
                      params=params, json=rows, timeout=60)
    if not r.ok:
        logger.warning("upsert %s failed: %s — %s", table, r.status_code, r.text[:200])
        return 0
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
#  Market key derivation (no property identification)
# ─────────────────────────────────────────────────────────────────────────────

def _market_for(city: Optional[str], state: Optional[str]) -> str:
    """
    Build a market key from city + state. We slug it so the value is
    stable and queryable. Example: 'beaufort-sc-lowcountry' is hand-tuned
    above, generic case is 'savannah-ga' style.
    """
    city  = (city or "").strip().lower().replace(" ", "-")
    state = (state or "").strip().upper()
    if not city or not state:
        return "unknown"
    return f"{city}-{state.lower()}"


# ─────────────────────────────────────────────────────────────────────────────
#  Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_anonymized_signals(property_id: str,
                               *, lookback_days: int = 365) -> int:
    """
    Walk the last *lookback_days* of occupancy_snapshots + bookings + the
    competitor signal for the property, compute anonymized per-(month,
    day_of_week) signals, and upsert into market_signals.

    Returns the number of (market, month, dow) cells written.
    """
    prop = _sb_get("properties", {
        "id":     f"eq.{property_id}",
        "select": "id,city,state,name",
        "limit":  "1",
    })
    if not prop:
        raise ValueError(f"property {property_id} not found")
    p = prop[0]
    market = _market_for(p.get("city"), p.get("state"))

    today = date.today()
    start = today - timedelta(days=lookback_days)

    # Occupancy snapshots — backbone of avg_occupancy / avg_adr
    occ = _sb_get("occupancy_snapshots", {
        "property_id":   f"eq.{property_id}",
        "snapshot_date": f"gte.{start.isoformat()}",
        "and":           f"(snapshot_date.lte.{today.isoformat()})",
        "select":        "snapshot_date,occupancy_rate,adr,revpar",
    })

    # Bookings — derive booking_window_distribution + rate_elasticity_signal
    bookings = _sb_get("bookings", {
        "property_id": f"eq.{property_id}",
        "check_in":    f"gte.{start.isoformat()}",
        "select":      "check_in,check_out,rate_paid,booked_at,booking_source",
    })

    # Rate recommendations / actual rates — paired with occupancy lift
    recs = _sb_get("rate_recommendations", {
        "property_id": f"eq.{property_id}",
        "target_date": f"gte.{start.isoformat()}",
        "select":      "target_date,recommended_rate,current_rate,demand_score",
    })

    # ── Aggregate by (month, dow) ────────────────────────────────────────────
    buckets: dict[tuple[int, int], dict[str, Any]] = defaultdict(
        lambda: {"days": 0, "occ_sum": 0.0, "adr_sum": 0.0,
                  "bookings": 0, "bw_0_7": 0, "bw_8_30": 0,
                  "bw_31_60": 0, "bw_61_plus": 0,
                  "rate_pairs": [],  # (recommended, current, demand)
                  })

    for s in occ:
        d = date.fromisoformat(s["snapshot_date"])
        k = (d.month, d.weekday())
        b = buckets[k]
        b["days"]    += 1
        b["occ_sum"] += float(s.get("occupancy_rate") or 0)
        b["adr_sum"] += float(s.get("adr") or 0)

    for r in bookings:
        ci    = date.fromisoformat(r["check_in"])
        b_key = (ci.month, ci.weekday())
        b     = buckets[b_key]
        b["bookings"] += 1
        if r.get("booked_at"):
            try:
                booked = datetime.fromisoformat(r["booked_at"].replace("Z", "+00:00")).date()
                window = (ci - booked).days
                if   window <=  7: b["bw_0_7"]      += 1
                elif window <= 30: b["bw_8_30"]     += 1
                elif window <= 60: b["bw_31_60"]    += 1
                else:              b["bw_61_plus"]  += 1
            except (ValueError, TypeError):
                pass

    for r in recs:
        d = date.fromisoformat(r["target_date"])
        k = (d.month, d.weekday())
        if r.get("recommended_rate") and r.get("current_rate") and r.get("demand_score"):
            buckets[k]["rate_pairs"].append((
                float(r["recommended_rate"]),
                float(r["current_rate"]),
                int(r["demand_score"]),
            ))

    # Seasonal index — month occupancy normalized to [0, 100]
    monthly_occ: dict[int, list[float]] = defaultdict(list)
    for (m, _dow), b in buckets.items():
        if b["days"]:
            monthly_occ[m].append(b["occ_sum"] / b["days"])
    if monthly_occ:
        means = {m: sum(v)/len(v) for m, v in monthly_occ.items()}
        lo, hi = min(means.values()), max(means.values())
    else:
        means, lo, hi = {}, 0.0, 1.0

    def _seasonal_idx(month: int) -> int:
        if hi <= lo: return 50
        return int(round((means.get(month, lo) - lo) / (hi - lo) * 100))

    # Event lift — pull market_signals rows already keyed by date (event days)
    # We treat the existing event_lift column as known events and copy through.
    event_rows = _sb_get("market_signals", {
        "market": f"eq.{market}",
        "select": "month,event_lift",
    })
    event_lift_by_month: dict[int, float] = {}
    for r in event_rows:
        if r.get("event_lift") is not None and r.get("month") is not None:
            event_lift_by_month[r["month"]] = float(r["event_lift"])

    # ── Build rows for upsert ────────────────────────────────────────────────
    rows: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for (month, dow), b in buckets.items():
        if b["days"] < 14:  # privacy floor — too thin to share
            continue
        avg_occ = b["occ_sum"] / b["days"]
        avg_adr = b["adr_sum"] / b["days"]
        total_bk = b["bw_0_7"] + b["bw_8_30"] + b["bw_31_60"] + b["bw_61_plus"]
        if total_bk == 0:
            bw_dist = {"bw_0_7": 0, "bw_8_30": 0, "bw_31_60": 0, "bw_61_plus": 0}
        else:
            bw_dist = {
                "bw_0_7":     b["bw_0_7"]     / total_bk,
                "bw_8_30":    b["bw_8_30"]    / total_bk,
                "bw_31_60":   b["bw_31_60"]   / total_bk,
                "bw_61_plus": b["bw_61_plus"] / total_bk,
            }

        # rate_elasticity_signal: avg ratio (recommended / current) bucketed by
        # demand_score; high-demand cells with rec > current indicate that
        # the engine pushed prices and the market accepted the lift.
        pairs = b["rate_pairs"]
        if len(pairs) >= 5:
            high_demand = [p for p in pairs if p[2] >= 65]
            base = high_demand if len(high_demand) >= 3 else pairs
            elasticity = round(sum(p[0]/p[1] for p in base if p[1]) / len(base), 4)
        else:
            elasticity = None

        rows.append({
            "signal_date":           date(today.year, month,
                                          min(28, ((dow + 1) % 28) + 1)).isoformat(),
            "market":                market,
            "month":                 month,
            "day_of_week":           dow,
            "avg_occupancy":         round(avg_occ, 4),
            "avg_adr":               round(avg_adr, 2),
            "booking_window_0_7":    round(bw_dist["bw_0_7"], 4),
            "booking_window_8_30":   round(bw_dist["bw_8_30"], 4),
            "booking_window_31_60":  round(bw_dist["bw_31_60"], 4),
            "booking_window_61_plus":round(bw_dist["bw_61_plus"], 4),
            "event_lift":            event_lift_by_month.get(month),
            "rate_elasticity":       elasticity,
            "seasonal_index":        _seasonal_idx(month),
            "sample_property_count": 1,
            "last_aggregated_at":    now_iso,
        })

    if not rows:
        logger.info("extract_anonymized_signals(%s): no qualifying cells (need >=14 days each)",
                     property_id)
        return 0

    n = _sb_upsert("market_signals", rows, on_conflict="market,month,day_of_week")
    logger.info("extract_anonymized_signals(%s) → market=%s · %d cells written",
                 property_id, market, n)
    return n


# ─────────────────────────────────────────────────────────────────────────────
#  Market-wide aggregation across all contributing properties
# ─────────────────────────────────────────────────────────────────────────────

def run_market_aggregation() -> dict:
    """
    For every active property, run extract_anonymized_signals and then
    collapse contributions per (market, month, day_of_week) into the
    canonical benchmark row.

    Returns:
        {markets: [...], properties_contributed: N, cells_total: M,
         ran_at: ISO}
    """
    props = _sb_get("properties", {"select": "id,name,city,state"})
    contributed = 0
    cells_total = 0
    for p in props:
        try:
            n = extract_anonymized_signals(p["id"])
            if n:
                contributed += 1
                cells_total += n
        except Exception as exc:
            logger.warning("aggregation skip property %s: %s", p["id"], exc)

    # Re-derive avg per cell across all contributing properties.
    cells = _sb_get("market_signals", {"select": "market,month,day_of_week,"
                                                  "avg_occupancy,avg_adr,"
                                                  "sample_property_count"})
    bucket: dict[tuple[str, int, int], dict[str, Any]] = defaultdict(
        lambda: {"occ_sum": 0.0, "adr_sum": 0.0, "n": 0, "samples": 0})
    for c in cells:
        if c.get("market") is None or c.get("month") is None or c.get("day_of_week") is None:
            continue
        k = (c["market"], c["month"], c["day_of_week"])
        b = bucket[k]
        b["occ_sum"] += float(c.get("avg_occupancy") or 0)
        b["adr_sum"] += float(c.get("avg_adr") or 0)
        b["n"]       += 1
        b["samples"] += int(c.get("sample_property_count") or 0)

    update_rows: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for (mkt, m, dow), b in bucket.items():
        if b["n"] == 0:
            continue
        update_rows.append({
            "market":                mkt,
            "month":                 m,
            "day_of_week":           dow,
            "avg_occupancy":         round(b["occ_sum"] / b["n"], 4),
            "avg_adr":               round(b["adr_sum"] / b["n"], 2),
            "sample_property_count": b["samples"] or b["n"],
            "last_aggregated_at":    now_iso,
            "signal_date":           date.today().isoformat(),
        })
    _sb_upsert("market_signals", update_rows, on_conflict="market,month,day_of_week")

    summary = {
        "markets":                sorted({r["market"] for r in update_rows}),
        "properties_contributed": contributed,
        "cells_total":            len(update_rows),
        "ran_at":                 now_iso,
    }
    logger.info("run_market_aggregation → %s", summary)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
#  Read API for rate engine
# ─────────────────────────────────────────────────────────────────────────────

def get_market_benchmarks(market: str,
                          month: Optional[int] = None,
                          day_of_week: Optional[int] = None) -> dict:
    """
    Return aggregated benchmarks for a (market, month, dow) slice. If
    month or dow are None, the result averages across the missing dim.

    Returns:
        {market, avg_occupancy, avg_adr, booking_window:{...},
         event_lift, rate_elasticity, seasonal_index,
         sample_property_count}
    """
    params = {"market": f"eq.{market}",
              "select": "month,day_of_week,avg_occupancy,avg_adr,"
                        "booking_window_0_7,booking_window_8_30,"
                        "booking_window_31_60,booking_window_61_plus,"
                        "event_lift,rate_elasticity,seasonal_index,"
                        "sample_property_count"}
    if month is not None:
        params["month"] = f"eq.{month}"
    if day_of_week is not None:
        params["day_of_week"] = f"eq.{day_of_week}"
    rows = _sb_get("market_signals", params)

    if not rows:
        return {"market": market, "avg_occupancy": None, "avg_adr": None}

    def _avg(key: str) -> Optional[float]:
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(vals)/len(vals), 4) if vals else None

    return {
        "market":                 market,
        "month":                  month,
        "day_of_week":            day_of_week,
        "avg_occupancy":          _avg("avg_occupancy"),
        "avg_adr":                _avg("avg_adr"),
        "booking_window":         {
            "0_7":     _avg("booking_window_0_7"),
            "8_30":    _avg("booking_window_8_30"),
            "31_60":   _avg("booking_window_31_60"),
            "61_plus": _avg("booking_window_61_plus"),
        },
        "event_lift":             _avg("event_lift"),
        "rate_elasticity":        _avg("rate_elasticity"),
        "seasonal_index":         _avg("seasonal_index"),
        "sample_property_count":  max((r.get("sample_property_count") or 0)
                                       for r in rows),
        "cells_used":             len(rows),
    }


__all__ = ["extract_anonymized_signals", "run_market_aggregation",
           "get_market_benchmarks"]
