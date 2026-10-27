"""
engine/features.py — INNtelligence feature gating + per-feature trials.

Single source of truth for which plan_tier unlocks which feature, plus the
per-feature 14-day trial mechanic. The server is authoritative — the client
may render locks optimistically, but every gated action must call
has_feature_access() (never trust the client).

Public API:
    FEATURE_CATALOG                       -> dict[feature_key, meta]
    TIER_ORDER, TIER_PRICE_USD
    tier_includes(plan_tier, feature_key) -> bool
    has_feature_access(tenant, feature_key) -> bool   # tier OR active trial
    start_trial(tenant_id, feature_key, plan_tier)    -> dict (trial or error)
    feature_access_snapshot(tenant_id, plan_tier)     -> dict for the UI
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Tiers
# ─────────────────────────────────────────────────────────────────────────────
TIER_ORDER = ["inn", "boutique", "signature", "collection"]
TIER_LABEL = {"inn": "Inn", "boutique": "Boutique",
              "signature": "Signature", "collection": "Collection"}
TIER_PRICE_USD = {"inn": 149, "boutique": 399, "signature": 799, "collection": 1499}
# founding_member gets Boutique-level feature access.
_FOUNDING_EQUIV = "boutique"

TRIAL_DAYS = 14
MAX_ACTIVE_TRIALS = 2

# ─────────────────────────────────────────────────────────────────────────────
#  Feature catalog — min_tier is the lowest tier that includes the feature.
#  `limits` carries per-tier caps surfaced in the UI (not enforced here).
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_CATALOG: dict[str, dict] = {
    # ── inn ($149) ──
    "rate_calendar":      {"min_tier": "inn",        "label": "Rate Calendar",
                           "value": "90-day AI rate recommendations for every room, every night."},
    "dynamic_pricing":    {"min_tier": "inn",        "label": "Dynamic Pricing",
                           "value": "Demand-based pricing with up to 4 rate updates a day.",
                           "limits": {"inn": "up to 4 updates/day"}},
    "competitive_intel":  {"min_tier": "inn",        "label": "Competitive Intelligence",
                           "value": "Track competitor rates and position against your comp set.",
                           "limits": {"inn": "up to 10 competitors",
                                      "boutique": "unlimited + smart comp-set tools"}},
    "ota_publishing":     {"min_tier": "inn",        "label": "OTA Publishing",
                           "value": "Push approved rates to 7 booking channels at once."},
    "guest_crm_basic":    {"min_tier": "inn",        "label": "Guest CRM",
                           "value": "Guest profiles, stay history, and segments."},
    "reputation":         {"min_tier": "inn",        "label": "Reputation",
                           "value": "Monitor reviews and ratings across booking sites."},

    # ── boutique ($399) ──
    "realtime_repricing": {"min_tier": "boutique",   "label": "Real-time Repricing",
                           "value": "Reprice instantly on every booking and cancellation."},
    "demand_forecast":    {"min_tier": "boutique",   "label": "Demand Forecast",
                           "value": "Forward-looking occupancy and demand signals."},
    "weather":            {"min_tier": "boutique",   "label": "Weather Intelligence",
                           "value": "Fold weather-driven demand swings into your rates."},
    "revenue_intel":      {"min_tier": "boutique",   "label": "Revenue Intelligence",
                           "value": "Find and fill orphan gap nights automatically."},
    "roi_performance":    {"min_tier": "boutique",   "label": "ROI Performance",
                           "value": "See the revenue lift INNtelligence drives for you."},
    "historical":         {"min_tier": "boutique",   "label": "Historical Performance",
                           "value": "Benchmark against your own booking history."},
    "events":             {"min_tier": "boutique",   "label": "Events Intelligence",
                           "value": "Local events that move demand, scored and priced in."},
    "packages":           {"min_tier": "boutique",   "label": "Packages",
                           "value": "Build and price revenue-boosting guest packages."},
    "guest_crm_full":     {"min_tier": "boutique",   "label": "Guest CRM + Campaigns",
                           "value": "Demand-triggered email campaigns to past guests."},

    # ── signature ($799) ──
    "fb_yield":           {"min_tier": "signature",  "label": "F&B Yield",
                           "value": "Yield-manage restaurant covers and F&B revenue."},
    "weddings":           {"min_tier": "signature",  "label": "Weddings",
                           "value": "Run your wedding inquiry-to-booking pipeline and pricing."},
    "private_events":     {"min_tier": "signature",  "label": "Private Events",
                           "value": "Price and manage private event bookings."},
    "gift_shop":          {"min_tier": "signature",  "label": "Gift Shop",
                           "value": "Sell branded goods and track margin per item."},
    "autopilot":          {"min_tier": "signature",  "label": "Autopilot",
                           "value": "Hands-off rate publishing while you sleep."},
    "demand_alerts":      {"min_tier": "signature",  "label": "Demand Alerts",
                           "value": "Surge / competitor / festival / gap alerts in real time."},

    # ── collection ($1499+) ──
    "management_console": {"min_tier": "collection", "label": "Management Console",
                           "value": "Operate every property from a single console."},
    "portfolio_analytics":{"min_tier": "collection", "label": "Portfolio Analytics",
                           "value": "Cross-property revenue analytics and benchmarking."},
}


# ─────────────────────────────────────────────────────────────────────────────
#  Supabase REST helpers (service key)
# ─────────────────────────────────────────────────────────────────────────────
def _sb_url() -> str: return os.getenv("SUPABASE_URL", "").rstrip("/")
def _sb_key() -> str: return os.getenv("SUPABASE_SERVICE_KEY", "")
def _sb_hdrs(extra: Optional[dict] = None) -> dict:
    h = {"apikey": _sb_key(), "Authorization": f"Bearer {_sb_key()}",
         "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h

def _sb_get(table: str, params: dict) -> list[dict]:
    try:
        r = requests.get(f"{_sb_url()}/rest/v1/{table}", headers=_sb_hdrs(),
                         params=params, timeout=15)
        return r.json() if (r.ok and r.text) else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("features _sb_get %s failed: %s", table, exc)
        return []

def _sb_post(table: str, body: dict, *, prefer: str = "return=representation") -> Optional[list[dict]]:
    try:
        r = requests.post(f"{_sb_url()}/rest/v1/{table}",
                          headers=_sb_hdrs({"Prefer": prefer}), json=body, timeout=20)
        if not r.ok:
            logger.warning("features _sb_post %s failed: %s — %s", table, r.status_code, r.text[:200])
            return None
        return r.json() if ("representation" in prefer and r.text) else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("features _sb_post %s error: %s", table, exc)
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)

def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ─────────────────────────────────────────────────────────────────────────────
#  Tier logic
# ─────────────────────────────────────────────────────────────────────────────
def _tier_rank(plan_tier: Optional[str]) -> int:
    pt = _FOUNDING_EQUIV if plan_tier == "founding_member" else (plan_tier or "")
    try:
        return TIER_ORDER.index(pt)
    except ValueError:
        return 0  # unknown → treat as entry (inn) level


def tier_includes(plan_tier: Optional[str], feature_key: str) -> bool:
    """True if *plan_tier* includes *feature_key* by plan (ignoring trials)."""
    meta = FEATURE_CATALOG.get(feature_key)
    if not meta:
        return False
    return _tier_rank(plan_tier) >= _tier_rank(meta["min_tier"])


def required_tier(feature_key: str) -> Optional[str]:
    meta = FEATURE_CATALOG.get(feature_key)
    return meta["min_tier"] if meta else None


# ─────────────────────────────────────────────────────────────────────────────
#  Trials
# ─────────────────────────────────────────────────────────────────────────────
def _trials_for(tenant_id: str) -> list[dict]:
    if not tenant_id:
        return []
    return _sb_get("feature_trials", {
        "tenant_id": f"eq.{tenant_id}",
        "select": "feature_key,started_at,ends_at,converted",
    })

def _is_active(trial: dict, now: Optional[datetime] = None) -> bool:
    now = now or _now()
    try:
        ends = datetime.fromisoformat(str(trial["ends_at"]).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return False
    return ends > now


def _active_trial_keys(trials: list[dict], now: Optional[datetime] = None) -> set[str]:
    return {t["feature_key"] for t in trials if _is_active(t, now)}


def _has_active_trial(tenant_id: str, feature_key: str) -> bool:
    now = _now()
    rows = _sb_get("feature_trials", {
        "tenant_id":   f"eq.{tenant_id}",
        "feature_key": f"eq.{feature_key}",
        "ends_at":     f"gt.{_iso(now)}",
        "select":      "id",
    })
    return bool(rows)


def has_feature_access(tenant, feature_key: str) -> bool:
    """Authoritative gate: True if *feature_key* is in the tenant's tier OR an
    active (non-expired) trial exists. `tenant` may be a dict with id/plan_tier
    or a tenant_id string."""
    if feature_key not in FEATURE_CATALOG:
        return False
    if isinstance(tenant, str):
        rows = _sb_get("tenants", {"id": f"eq.{tenant}", "select": "id,plan_tier"})
        t = rows[0] if rows else {}
    else:
        t = tenant or {}
    if tier_includes(t.get("plan_tier"), feature_key):
        return True
    tid = t.get("id")
    return bool(tid) and _has_active_trial(tid, feature_key)


def start_trial(tenant_id: str, feature_key: str, plan_tier: Optional[str]) -> dict:
    """Start a 14-day trial for *feature_key*. Enforces: feature must be lockable
    (not already in tier), not previously trialed (once per tenant per feature),
    and at most MAX_ACTIVE_TRIALS active trials. Returns the created trial, or
    {"error": <code>, "message": ...} on refusal."""
    if feature_key not in FEATURE_CATALOG:
        return {"error": "unknown_feature", "message": f"Unknown feature {feature_key!r}."}
    if tier_includes(plan_tier, feature_key):
        return {"error": "already_included",
                "message": "This feature is already part of your plan."}

    trials = _trials_for(tenant_id)
    if any(t["feature_key"] == feature_key for t in trials):
        return {"error": "already_trialed",
                "message": "You've already used your free trial for this feature."}

    if len(_active_trial_keys(trials)) >= MAX_ACTIVE_TRIALS:
        return {"error": "limit_reached",
                "message": f"You can trial {MAX_ACTIVE_TRIALS} features at a time — "
                           "upgrade or let one finish first."}

    now = _now()
    ends = now + timedelta(days=TRIAL_DAYS)
    created = _sb_post("feature_trials", {
        "tenant_id":   tenant_id,
        "feature_key": feature_key,
        "started_at":  _iso(now),
        "ends_at":     _iso(ends),
        "converted":   False,
    })
    if created is None:
        return {"error": "write_failed", "message": "Could not start trial. Please try again."}
    return {
        "ok": True,
        "feature_key": feature_key,
        "started_at": _iso(now),
        "ends_at": _iso(ends),
        "days_left": TRIAL_DAYS,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Snapshot for the UI (one round-trip)
# ─────────────────────────────────────────────────────────────────────────────
def _days_left(ends_iso: str, now: datetime) -> int:
    try:
        ends = datetime.fromisoformat(str(ends_iso).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return 0
    return max(0, (ends - now).days + (1 if (ends - now).seconds else 0))


def feature_access_snapshot(tenant_id: Optional[str], plan_tier: Optional[str],
                            *, is_admin: bool = False) -> dict:
    """Everything the frontend needs to render gating + trials for one tenant."""
    now = _now()
    trials = _trials_for(tenant_id) if tenant_id else []
    by_key = {t["feature_key"]: t for t in trials}
    active_keys = _active_trial_keys(trials, now)
    active_count = len(active_keys)

    features: dict[str, dict] = {}
    for key, meta in FEATURE_CATALOG.items():
        mt = meta["min_tier"]
        in_tier = is_admin or tier_includes(plan_tier, key)
        tr = by_key.get(key)
        trial_active = (not in_tier) and key in active_keys
        used = tr is not None
        access = in_tier or trial_active
        can_trial = (not in_tier) and (not used) and (active_count < MAX_ACTIVE_TRIALS)
        reason = None
        if not in_tier and not trial_active:
            if used:
                reason = "trial_used"
            elif active_count >= MAX_ACTIVE_TRIALS:
                reason = "limit_reached"
        features[key] = {
            "key": key,
            "label": meta["label"],
            "value": meta["value"],
            "limits": meta.get("limits", {}),
            "min_tier": mt,
            "required_tier": mt,
            "required_tier_label": TIER_LABEL.get(mt, mt),
            "price": TIER_PRICE_USD.get(mt),
            "in_tier": in_tier,
            "access": access,
            "source": "tier" if in_tier else ("trial" if trial_active else "locked"),
            "trial": {
                "active": trial_active,
                "used": used,
                "ends_at": tr["ends_at"] if tr else None,
                "days_left": _days_left(tr["ends_at"], now) if (tr and trial_active) else None,
            },
            "can_trial": can_trial,
            "trial_reason": reason,
        }

    return {
        "plan_tier": plan_tier,
        "is_admin": is_admin,
        "trial_limit": MAX_ACTIVE_TRIALS,
        "trial_days": TRIAL_DAYS,
        "active_trial_count": active_count,
        "tier_prices": TIER_PRICE_USD,
        "tier_labels": TIER_LABEL,
        "features": features,
    }


__all__ = [
    "FEATURE_CATALOG", "TIER_ORDER", "TIER_LABEL", "TIER_PRICE_USD",
    "TRIAL_DAYS", "MAX_ACTIVE_TRIALS",
    "tier_includes", "required_tier", "has_feature_access",
    "start_trial", "feature_access_snapshot",
]
