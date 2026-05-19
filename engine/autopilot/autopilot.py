"""
engine/autopilot/autopilot.py — Phase 8
Autopilot rate publishing + demand alert system.

Public API:
    run_autopilot(property_id, mock=False) -> dict
        Walks every pending recommendation; for each room_type with autopilot
        enabled, checks confidence + change-percentage + business hours +
        daily-change cap, and if all gates pass, publishes the rate via
        engine.channel.publisher.publish_approved_rate. Emits an
        'autopilot_published' alert per successful publish.

    run_alert_checks(property_id) -> list[dict]
        Five checks:
          SURGE           — booking pace >= 40% above LY for any 7-day forward window
          COMPETITOR_DROP — any competitor dropped > 20% overnight, target_date within 60d
          LOW_OCCUPANCY   — forecasted occupancy < 40% for dates within 21d
          FESTIVAL        — known event within 90d with no rate premium yet
          GAP_NIGHT       — 1-2 night gaps between bookings
        Inserts alerts with dedup_key so repeat checks don't spam.

    generate_autopilot_report(property_id, weeks=1) -> dict
        Counts autopilot publishes this week, average rate delta, estimated
        revenue lift, forecast accuracy, and the top win.

    upsert_autopilot_config(tenant_id, property_id, room_type_id, **fields) -> dict
        Insert or update an autopilot_configs row.
"""
from __future__ import annotations

import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Supabase helpers (shared shape with engine.crm)
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
                     params=params, timeout=20)
    r.raise_for_status()
    return r.json() if r.text else []

def _sb_post(table: str, body: dict | list[dict], *,
             prefer: str = "return=representation") -> Optional[list[dict]]:
    r = requests.post(f"{_sb_url()}/rest/v1/{table}",
                      headers=_sb_hdrs({"Prefer": prefer}),
                      json=body, timeout=20)
    if not r.ok:
        logger.warning("POST %s failed: %s — %s", table, r.status_code, r.text[:200])
        return None
    return r.json() if "representation" in prefer and r.text else None

def _sb_patch(table: str, params: dict, body: dict) -> bool:
    r = requests.patch(f"{_sb_url()}/rest/v1/{table}",
                       headers=_sb_hdrs({"Prefer": "return=minimal"}),
                       params=params, json=body, timeout=15)
    return r.ok


# ─────────────────────────────────────────────────────────────────────────────
#  Autopilot config
# ─────────────────────────────────────────────────────────────────────────────

def upsert_autopilot_config(
    tenant_id:               str,
    property_id:             str,
    room_type_id:            str,
    *,
    enabled:                 Optional[bool]  = None,
    max_rate_change_pct:     Optional[float] = None,
    min_confidence_score:    Optional[int]   = None,
    autopilot_start_hour:    Optional[int]   = None,
    autopilot_end_hour:      Optional[int]   = None,
    notify_on_publish:       Optional[bool]  = None,
    max_daily_changes:       Optional[int]   = None,
) -> dict:
    """Insert-or-update one autopilot_configs row by (property_id, room_type_id)."""
    existing = _sb_get("autopilot_configs", {
        "property_id":  f"eq.{property_id}",
        "room_type_id": f"eq.{room_type_id}",
        "select":       "*", "limit": "1",
    })
    body = {k: v for k, v in {
        "tenant_id":             tenant_id,
        "property_id":           property_id,
        "room_type_id":          room_type_id,
        "enabled":               enabled,
        "max_rate_change_pct":   max_rate_change_pct,
        "min_confidence_score":  min_confidence_score,
        "autopilot_start_hour":  autopilot_start_hour,
        "autopilot_end_hour":    autopilot_end_hour,
        "notify_on_publish":     notify_on_publish,
        "max_daily_changes":     max_daily_changes,
        "updated_at":            datetime.now(timezone.utc).isoformat(),
    }.items() if v is not None}
    if existing:
        _sb_patch("autopilot_configs", {"id": f"eq.{existing[0]['id']}"}, body)
        return {**existing[0], **body}
    out = _sb_post("autopilot_configs", body)
    return out[0] if out else body


# ─────────────────────────────────────────────────────────────────────────────
#  Alerts
# ─────────────────────────────────────────────────────────────────────────────

_ALERT_DEFAULT_SEVERITY = {
    "surge":               "warning",
    "competitor_drop":     "warning",
    "low_occupancy":       "warning",
    "festival":            "info",
    "gap_night":           "info",
    "autopilot_published": "info",
}


def _emit_alert(
    tenant_id:   Optional[str],
    property_id: str,
    alert_type:  str,
    message:     str,
    *,
    severity:    Optional[str]  = None,
    metadata:    Optional[dict] = None,
    dedup_key:   Optional[str]  = None,
) -> Optional[str]:
    """Insert an alert, deduplicating on (property_id, dedup_key) for unread rows."""
    if dedup_key:
        existing = _sb_get("alerts", {
            "property_id": f"eq.{property_id}",
            "dedup_key":   f"eq.{dedup_key}",
            "dismissed_at": "is.null",
            "select":      "id", "limit": "1",
        })
        if existing:
            return existing[0]["id"]

    sev = severity or _ALERT_DEFAULT_SEVERITY.get(alert_type, "info")
    out = _sb_post("alerts", {
        "tenant_id":   tenant_id,
        "property_id": property_id,
        "alert_type":  alert_type,
        "severity":    sev,
        "message":     message,
        "metadata":    metadata or {},
        "dedup_key":   dedup_key,
    })
    return out[0]["id"] if out else None


def list_alerts(property_id: str, *, unread_only: bool = True,
                limit: int = 50) -> list[dict]:
    params = {
        "property_id": f"eq.{property_id}",
        "order":       "created_at.desc",
        "limit":       str(max(1, min(limit, 500))),
        "select":      "id,alert_type,severity,message,metadata,"
                       "created_at,read_at,dismissed_at",
    }
    if unread_only:
        params["dismissed_at"] = "is.null"
    return _sb_get("alerts", params)


def dismiss_alert(alert_id: str) -> bool:
    return _sb_patch("alerts", {"id": f"eq.{alert_id}"},
                     {"dismissed_at": datetime.now(timezone.utc).isoformat()})


# ─────────────────────────────────────────────────────────────────────────────
#  run_autopilot
# ─────────────────────────────────────────────────────────────────────────────

def _tenant_id_for(property_id: str) -> Optional[str]:
    rows = _sb_get("properties", {"id": f"eq.{property_id}",
                                   "select": "tenant_id"})
    return rows[0]["tenant_id"] if rows else None


def run_autopilot(property_id: str, *, mock: bool = False,
                  now: Optional[datetime] = None) -> dict:
    """
    Walk every enabled autopilot config for *property_id*; publish pending
    recommendations that pass all gates. Returns a summary dict.

    Gates per recommendation:
        confidence_score   >=  config.min_confidence_score
        rate_change_pct    <=  config.max_rate_change_pct  (vs current_rate)
        current hour       within [start_hour, end_hour]
        published-today    <   max_daily_changes
    """
    now = now or datetime.now(timezone.utc)
    hour = now.hour
    today = now.date()
    tenant_id = _tenant_id_for(property_id)

    configs = _sb_get("autopilot_configs", {
        "property_id": f"eq.{property_id}",
        "enabled":     "eq.true",
        "select":      "*",
    })
    if not configs:
        return {"property_id": property_id, "auto_published": 0, "skipped": 0,
                "skipped_reasons": {}, "configs_enabled": 0,
                "ran_at": now.isoformat()}

    cfg_by_rt: dict[str, dict] = {c["room_type_id"]: c for c in configs}
    rt_ids = list(cfg_by_rt.keys())
    if not rt_ids:
        return {"property_id": property_id, "auto_published": 0, "skipped": 0,
                "configs_enabled": 0, "ran_at": now.isoformat()}

    # Pending recommendations for the enabled room types
    rec_filter = ",".join(rt_ids)
    pending = _sb_get("rate_recommendations", {
        "property_id":  f"eq.{property_id}",
        "room_type_id": f"in.({rec_filter})",
        "status":       "in.(pending,approved)",
        "select":       "id,room_type_id,target_date,recommended_rate,"
                        "current_rate,confidence_score,demand_score",
        "order":        "target_date.asc",
        "limit":        "1000",
    })

    # How many auto-publishes already today per room_type?
    today_published = _sb_get("rate_recommendations", {
        "property_id":  f"eq.{property_id}",
        "status":       "eq.auto_published",
        "published_at": f"gte.{today.isoformat()}T00:00:00Z",
        "select":       "room_type_id", "limit": "1000",
    })
    daily_count: Counter[str] = Counter(r["room_type_id"] for r in today_published)

    auto_published = 0
    skipped_reasons: Counter[str] = Counter()
    win_examples: list[dict] = []

    # Lazy import — keeps test imports light
    from engine.channel.publisher import publish_approved_rate

    for rec in pending:
        cfg = cfg_by_rt.get(rec["room_type_id"])
        if not cfg: continue

        # Gate 1 — business hours
        sh, eh = int(cfg["autopilot_start_hour"]), int(cfg["autopilot_end_hour"])
        if not (sh <= hour < eh):
            skipped_reasons["outside_hours"] += 1
            continue

        # Gate 2 — daily change cap
        if daily_count[rec["room_type_id"]] >= int(cfg["max_daily_changes"]):
            skipped_reasons["daily_cap"] += 1
            continue

        # Gate 3 — confidence
        cs = int(rec.get("confidence_score") or 0)
        if cs < int(cfg["min_confidence_score"]):
            skipped_reasons["low_confidence"] += 1
            continue

        # Gate 4 — rate change percentage
        new_rate     = float(rec.get("recommended_rate") or 0)
        current_rate = float(rec.get("current_rate") or 0)
        if new_rate <= 0 or current_rate <= 0:
            skipped_reasons["missing_rate"] += 1
            continue
        change_pct = abs((new_rate - current_rate) / current_rate)
        if change_pct > float(cfg["max_rate_change_pct"]):
            skipped_reasons["change_too_large"] += 1
            continue

        # ── Publish ─────────────────────────────────────────────────────────
        try:
            result = publish_approved_rate(rec["id"], mock=mock)
        except Exception as exc:
            logger.exception("autopilot publish failed for %s: %s", rec["id"], exc)
            skipped_reasons["publish_error"] += 1
            continue

        if not result.success:
            skipped_reasons["publish_failed"] += 1
            continue

        # Overwrite status to auto_published (publisher set it to published)
        _sb_patch("rate_recommendations", {"id": f"eq.{rec['id']}"},
                  {"status": "auto_published"})

        if bool(cfg.get("notify_on_publish")):
            _emit_alert(
                tenant_id, property_id, "autopilot_published",
                f"Auto-published ${new_rate:.0f} for {rec['target_date']} (Δ ${new_rate-current_rate:+.0f})",
                severity="info",
                metadata={
                    "recommendation_id": rec["id"],
                    "room_type_id":      rec["room_type_id"],
                    "target_date":       rec["target_date"],
                    "previous_rate":     current_rate,
                    "new_rate":          new_rate,
                    "change_pct":        round(change_pct, 4),
                    "confidence_score":  cs,
                    "otas_updated":      result.otas_updated,
                },
                dedup_key=f"autopilot_published:{rec['id']}",
            )

        auto_published += 1
        daily_count[rec["room_type_id"]] += 1
        if abs(new_rate - current_rate) >= 25 and len(win_examples) < 1:
            win_examples.append({
                "recommendation_id": rec["id"],
                "target_date":       rec["target_date"],
                "previous_rate":     current_rate,
                "new_rate":          new_rate,
                "delta":             round(new_rate - current_rate, 2),
                "confidence":        cs,
            })

    summary = {
        "property_id":     property_id,
        "configs_enabled": len(configs),
        "auto_published":  auto_published,
        "skipped":         sum(skipped_reasons.values()),
        "skipped_reasons": dict(skipped_reasons),
        "top_win":         win_examples[0] if win_examples else None,
        "ran_at":          now.isoformat(),
    }
    logger.info("run_autopilot → %s", summary)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
#  Alert checks
# ─────────────────────────────────────────────────────────────────────────────

def run_alert_checks(property_id: str, *, today: Optional[date] = None) -> list[dict]:
    """
    Run the five alert checks and persist any new findings. Returns the
    list of newly-inserted alerts (excluding ones suppressed by dedup_key).
    """
    today = today or date.today()
    tenant_id = _tenant_id_for(property_id)
    new_alerts: list[dict] = []

    # ── SURGE — booking pace +40% vs LY (proxy: avg demand_score next 7d) ──
    today_iso = today.isoformat()
    in_7      = (today + timedelta(days=7)).isoformat()
    recs7 = _sb_get("rate_recommendations", {
        "property_id": f"eq.{property_id}",
        "target_date": f"gte.{today_iso}",
        "and":         f"(target_date.lte.{in_7})",
        "select":      "demand_score,recommended_rate,target_date",
    })
    if recs7:
        scores = [r["demand_score"] for r in recs7 if r.get("demand_score") is not None]
        if scores:
            avg = sum(scores) / len(scores)
            if avg >= 80:  # proxy for >40% above baseline
                aid = _emit_alert(
                    tenant_id, property_id, "surge",
                    f"Booking surge: avg demand {avg:.0f}/100 over next 7 days",
                    severity="warning",
                    metadata={"avg_demand": round(avg, 1), "window": "7d_forward"},
                    dedup_key=f"surge:{today_iso}",
                )
                if aid: new_alerts.append({"id": aid, "type": "surge"})

    # ── COMPETITOR_DROP — > 20% drop overnight, target_date within 60d ──
    in_60 = (today + timedelta(days=60)).isoformat()
    drops = _sb_get("competitor_rates", {
        "property_id": f"eq.{property_id}",
        "rate_date":   f"gte.{today_iso}",
        "and":         f"(rate_date.lte.{in_60})",
        "select":      "competitor_id,rate_date,rate_amount,is_sold_out,is_stale,"
                       "competitor_properties(competitor_name,name)",
        "is_stale":    "eq.false",
        "limit":       "500",
    })
    by_comp: dict[str, list[dict]] = defaultdict(list)
    for d in drops:
        by_comp[d["competitor_id"]].append(d)
    for cid, rows in by_comp.items():
        rows.sort(key=lambda r: r["rate_date"])
        for prev, cur in zip(rows, rows[1:]):
            p_rate = prev.get("rate_amount"); c_rate = cur.get("rate_amount")
            if (p_rate and c_rate and not prev.get("is_sold_out")
                and not cur.get("is_sold_out")):
                drop = (p_rate - c_rate) / p_rate
                if drop >= 0.20:
                    name = ((cur.get("competitor_properties") or {}).get("competitor_name")
                            or (cur.get("competitor_properties") or {}).get("name")
                            or "competitor")
                    aid = _emit_alert(
                        tenant_id, property_id, "competitor_drop",
                        f"{name} dropped {drop*100:.0f}% to ${c_rate:.0f} for {cur['rate_date']}",
                        severity="warning",
                        metadata={"competitor_id": cid,
                                  "previous_rate": p_rate, "new_rate": c_rate,
                                  "drop_pct":      round(drop, 4),
                                  "target_date":   cur["rate_date"]},
                        dedup_key=f"competitor_drop:{cid}:{cur['rate_date']}",
                    )
                    if aid: new_alerts.append({"id": aid, "type": "competitor_drop"})
                    break  # one alert per competitor per run

    # ── LOW_OCCUPANCY — forecast < 40% within 21 days ─────────────────────
    in_21 = (today + timedelta(days=21)).isoformat()
    recs21 = _sb_get("rate_recommendations", {
        "property_id": f"eq.{property_id}",
        "target_date": f"gte.{today_iso}",
        "and":         f"(target_date.lte.{in_21})",
        "select":      "target_date,demand_score",
    })
    by_date: dict[str, list[int]] = defaultdict(list)
    for r in recs21:
        if r.get("demand_score") is not None:
            by_date[r["target_date"]].append(int(r["demand_score"]))
    low_dates = [d for d, s in by_date.items() if (sum(s)/len(s)) < 40]
    if low_dates:
        aid = _emit_alert(
            tenant_id, property_id, "low_occupancy",
            f"Low occupancy forecast on {len(low_dates)} day(s) within 21d",
            severity="warning",
            metadata={"dates": sorted(low_dates)[:14]},
            dedup_key=f"low_occupancy:{today_iso}",
        )
        if aid: new_alerts.append({"id": aid, "type": "low_occupancy"})

    # ── FESTIVAL — Water Festival or other within 90d, no premium yet ──
    in_90 = today + timedelta(days=90)
    yyyy  = today.year
    festival_windows = [
        ("Beaufort Water Festival",
         date(yyyy, 7, 17), date(yyyy, 7, 26), 1.45),
    ]
    if today.month >= 8:
        festival_windows.append(
            ("Beaufort Water Festival",
             date(yyyy + 1, 7, 17), date(yyyy + 1, 7, 26), 1.45),
        )

    base_rates = _sb_get("room_types", {
        "property_id": f"eq.{property_id}",
        "select": "id,name,base_rate",
    })
    bases = {rt["id"]: float(rt.get("base_rate") or 0) for rt in base_rates}

    for name, w_start, w_end, multiplier in festival_windows:
        if w_start > in_90 or w_end < today:
            continue
        in_window = _sb_get("rate_recommendations", {
            "property_id": f"eq.{property_id}",
            "target_date": f"gte.{w_start.isoformat()}",
            "and":         f"(target_date.lte.{w_end.isoformat()})",
            "select":      "room_type_id,recommended_rate",
            "limit":       "500",
        })
        applied = False
        for rec in in_window:
            base = bases.get(rec["room_type_id"], 0)
            if base and rec.get("recommended_rate") and rec["recommended_rate"] >= base * (multiplier - 0.05):
                applied = True; break
        if not applied:
            aid = _emit_alert(
                tenant_id, property_id, "festival",
                f"{name} ({w_start.strftime('%b %-d')}–{w_end.strftime('%b %-d')}) "
                "approaching — no premium applied yet",
                severity="info",
                metadata={"event": name, "start": w_start.isoformat(),
                          "end":   w_end.isoformat(),
                          "expected_multiplier": multiplier},
                dedup_key=f"festival:{name}:{w_start.isoformat()}",
            )
            if aid: new_alerts.append({"id": aid, "type": "festival"})

    # ── GAP_NIGHT — 1-2 night gaps between bookings (next 60 days) ──
    bookings = _sb_get("bookings", {
        "property_id": f"eq.{property_id}",
        "check_in":    f"gte.{today_iso}",
        "and":         f"(check_in.lte.{(today+timedelta(days=60)).isoformat()})",
        "select":      "check_in,check_out,room_type_id",
        "order":       "check_in.asc",
    })
    by_room: dict[str, list[dict]] = defaultdict(list)
    for b in bookings:
        if b.get("room_type_id"):
            by_room[b["room_type_id"]].append(b)
    gap_dates: list[str] = []
    for rt_id, rows in by_room.items():
        rows.sort(key=lambda r: r["check_in"])
        for a, b in zip(rows, rows[1:]):
            out_d  = date.fromisoformat(a["check_out"])
            next_d = date.fromisoformat(b["check_in"])
            gap = (next_d - out_d).days
            if 1 <= gap <= 2:
                gap_dates.append(out_d.isoformat())
    if gap_dates:
        aid = _emit_alert(
            tenant_id, property_id, "gap_night",
            f"{len(gap_dates)} short gap(s) between bookings — discount opportunity",
            severity="info",
            metadata={"gap_starts": sorted(set(gap_dates))[:10]},
            dedup_key=f"gap_night:{today_iso}",
        )
        if aid: new_alerts.append({"id": aid, "type": "gap_night"})

    logger.info("run_alert_checks(%s) → %d new alert(s)",
                 property_id, len(new_alerts))
    return new_alerts


# ─────────────────────────────────────────────────────────────────────────────
#  Weekly autopilot performance report
# ─────────────────────────────────────────────────────────────────────────────

def generate_autopilot_report(property_id: str, *, weeks: int = 1) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(weeks=weeks)
    since_iso = since.isoformat()

    publishes = _sb_get("rate_publish_log", {
        "property_id": f"eq.{property_id}",
        "published_at": f"gte.{since_iso}",
        "select":      "id,status,response_body,published_at,recommendation_id",
        "order":       "published_at.desc",
        "limit":       "500",
    })
    auto_publishes = []
    for p in publishes:
        rb = p.get("response_body") or {}
        if (rb.get("recommendations_updated") or 0) >= 1 and p.get("recommendation_id"):
            auto_publishes.append(p)

    auto_count = len(auto_publishes)
    # Pair publishes to recommendations for rate-delta calc
    rec_ids = [p["recommendation_id"] for p in auto_publishes if p.get("recommendation_id")]
    rate_pairs: list[tuple[float, float]] = []
    forecast_pairs: list[tuple[int, float]] = []
    if rec_ids:
        for chunk in [rec_ids[i:i+50] for i in range(0, len(rec_ids), 50)]:
            recs = _sb_get("rate_recommendations", {
                "id":     f"in.({','.join(chunk)})",
                "select": "recommended_rate,current_rate,demand_score,target_date",
            })
            for r in recs:
                if r.get("recommended_rate") and r.get("current_rate"):
                    rate_pairs.append((float(r["recommended_rate"]),
                                       float(r["current_rate"])))
                if r.get("demand_score") and r.get("recommended_rate"):
                    forecast_pairs.append((int(r["demand_score"]),
                                            float(r["recommended_rate"])))

    avg_rate_change = (round(sum((n - c) for n, c in rate_pairs) / len(rate_pairs), 2)
                       if rate_pairs else 0.0)
    avg_lift_pct    = (round(sum((n - c) / c for n, c in rate_pairs if c > 0)
                              / len(rate_pairs) * 100, 2) if rate_pairs else 0.0)
    estimated_revenue_lift = round(sum((n - c) for n, c in rate_pairs) * 0.75, 2)

    # Forecast accuracy proxy — corr between demand_score and recommended_rate
    forecast_accuracy = None
    if len(forecast_pairs) >= 5:
        xs, ys = zip(*forecast_pairs)
        mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
        num = sum((x-mx)*(y-my) for x, y in forecast_pairs)
        denx = (sum((x-mx)**2 for x in xs))**0.5
        deny = (sum((y-my)**2 for y in ys))**0.5
        if denx and deny:
            forecast_accuracy = round((num / (denx*deny) + 1) / 2 * 100, 1)  # 0–100 from corr

    top_win = None
    if rate_pairs:
        peak = max(((n, c, abs(n-c)) for n, c in rate_pairs), key=lambda t: t[2])
        top_win = {"new_rate": peak[0], "previous_rate": peak[1],
                   "delta": round(peak[2], 2)}

    return {
        "property_id":            property_id,
        "weeks":                  weeks,
        "rates_auto_published":   auto_count,
        "avg_rate_change":        avg_rate_change,
        "avg_lift_pct":           avg_lift_pct,
        "estimated_revenue_lift": estimated_revenue_lift,
        "forecast_accuracy":      forecast_accuracy,
        "top_win":                top_win,
        "ran_at":                 now.isoformat(),
        "window_start":           since_iso,
    }


__all__ = ["run_autopilot", "run_alert_checks", "generate_autopilot_report",
           "list_alerts", "dismiss_alert", "upsert_autopilot_config"]


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def _cli_main() -> None:
    import argparse, json as _json
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s | %(name)s | %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--slug", default="anchorage-1770-demo")
    p.add_argument("--property-id", default=None,
                   help="If set, used directly (skips slug lookup)")
    p.add_argument("--alerts-only", action="store_true",
                   help="Only run alert checks, skip autopilot publish loop")
    p.add_argument("--mock", action="store_true", default=True,
                   help="Use mock channel-manager publish (default true)")
    args = p.parse_args()

    pid = args.property_id
    if not pid:
        sb = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        h = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=none"}
        t = requests.get(f"{sb}/rest/v1/tenants", headers=h,
                          params={"slug": f"eq.{args.slug}", "select": "id"},
                          timeout=10).json()[0]
        pr = requests.get(f"{sb}/rest/v1/properties", headers=h,
                           params={"tenant_id": f"eq.{t['id']}",
                                   "select": "id,name", "limit": "1"},
                           timeout=10).json()
        pid = pr[0]["id"]
        print(f"  Property: {pr[0]['name']}  ({pid})")

    if not args.alerts_only:
        print("\n── run_autopilot ──")
        print(_json.dumps(run_autopilot(pid, mock=args.mock), indent=2))
    print("\n── run_alert_checks ──")
    new_alerts = run_alert_checks(pid)
    print(f"  {len(new_alerts)} new alert(s)")
    print("\n── generate_autopilot_report ──")
    print(_json.dumps(generate_autopilot_report(pid, weeks=1), indent=2))


if __name__ == "__main__":
    _cli_main()
