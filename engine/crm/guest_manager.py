"""
engine/crm/guest_manager.py — Phase 6
Guest profile upsert + automatic segmentation + unsubscribe tokens.

Functions:
    upsert_guest(tenant_id, property_id, guest_data) -> guest_id
        Idempotent merge on (tenant_id, property_id, email_hash). When the
        row exists, stay/revenue/nights counts are *added* to existing values
        if the caller marks the record as a new stay (`new_stay=True`),
        otherwise they replace.

    update_guest_segments(tenant_id, property_id) -> {segment: count, ...}
        Walks every guest for the property and re-derives the tags[] array
        according to VIP / Local / Lapsed / New / Anniversary / Corporate
        rules. Designed to be run nightly by the scheduler.

    unsubscribe_token_for(guest_id) -> str
    consume_unsubscribe(token) -> guest_id | None
        Stateless HMAC tokens for email unsubscribe links.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
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
#  Supabase REST helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sb_url() -> str: return os.getenv("SUPABASE_URL", "").rstrip("/")
def _sb_key() -> str: return os.getenv("SUPABASE_SERVICE_KEY", "")


def _sb_hdrs(extra: Optional[dict] = None) -> dict:
    h = {
        "apikey":        _sb_key(),
        "Authorization": f"Bearer {_sb_key()}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _sb_get(table: str, params: dict) -> list[dict]:
    r = requests.get(f"{_sb_url()}/rest/v1/{table}",
                     headers=_sb_hdrs({"Prefer": "count=none"}),
                     params=params, timeout=15)
    r.raise_for_status()
    return r.json() if r.text else []


def _sb_post(table: str, body: dict | list[dict], *,
             prefer: str = "return=representation") -> Optional[list[dict]]:
    r = requests.post(f"{_sb_url()}/rest/v1/{table}",
                      headers=_sb_hdrs({"Prefer": prefer}),
                      json=body, timeout=20)
    if not r.ok:
        logger.warning("Supabase POST %s failed: %s — %s",
                       table, r.status_code, r.text[:200])
        return None
    return r.json() if "representation" in prefer and r.text else None


def _sb_patch(table: str, params: dict, body: dict) -> bool:
    r = requests.patch(f"{_sb_url()}/rest/v1/{table}",
                       headers=_sb_hdrs({"Prefer": "return=minimal"}),
                       params=params, json=body, timeout=15)
    return r.ok


# ─────────────────────────────────────────────────────────────────────────────
#  PII helpers (consistent with engine.pms)
# ─────────────────────────────────────────────────────────────────────────────

def _hash_email(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _encrypt_pii(value: str) -> Optional[str]:
    if not value:
        return None
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"enc:placeholder:{h[:32]}"


# ─────────────────────────────────────────────────────────────────────────────
#  Unsubscribe tokens
# ─────────────────────────────────────────────────────────────────────────────

def _unsub_secret() -> bytes:
    """Stable per-deployment secret for HMAC-signed unsubscribe tokens."""
    s = os.getenv("UNSUBSCRIBE_SECRET") or _sb_key()[:32] or "default_unsub_secret"
    return s.encode("utf-8")


def unsubscribe_token_for(guest_id: str) -> str:
    """HMAC-SHA256 signed token: <guest_id>.<hex_sig> — opaque to the user."""
    mac = hmac.new(_unsub_secret(), guest_id.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{guest_id}.{mac[:32]}"


def consume_unsubscribe(token: str) -> Optional[str]:
    """Verify a token; if valid, set marketing_consent=False on the guest. Returns guest_id."""
    if not token or "." not in token:
        return None
    guest_id, _, sig = token.partition(".")
    expected = hmac.new(_unsub_secret(), guest_id.encode("ascii"),
                        hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig.strip().lower()):
        logger.warning("Unsubscribe token signature mismatch for %s", guest_id[:8])
        return None
    ok = _sb_patch("guests", {"id": f"eq.{guest_id}"}, {
        "marketing_consent": False,
        "consent_date":      datetime.now(timezone.utc).isoformat(),
    })
    return guest_id if ok else None


# ─────────────────────────────────────────────────────────────────────────────
#  upsert_guest
# ─────────────────────────────────────────────────────────────────────────────

def upsert_guest(
    tenant_id:   str,
    property_id: str,
    guest_data:  dict,
    *,
    new_stay:    bool = False,
) -> str:
    """
    Upsert a guest record keyed on (tenant_id, property_id, email_hash).

    Returns the guest's UUID.

    `guest_data` keys (all optional except email):
        first_name, last_name, email (required), phone,
        home_city, home_state, total_stays, total_nights, total_revenue,
        avg_rate_paid, preferred_room_type, booking_sources (list),
        last_stay_date (ISO date), marketing_consent (bool),
        next_stay_date (ISO date), tags (list[str]), source (str)

    When new_stay=True and an existing record is found, stay/night/revenue
    counters from guest_data are *added* to the existing values (rather than
    replacing). Use this when the call site represents a fresh reservation
    rather than a profile sync.
    """
    email = (guest_data.get("email") or "").strip().lower()
    if not email:
        raise ValueError("upsert_guest: email is required")

    email_hash = _hash_email(email)

    existing = _sb_get("guests", {
        "tenant_id":   f"eq.{tenant_id}",
        "property_id": f"eq.{property_id}",
        "email_hash":  f"eq.{email_hash}",
        "select":      "id,total_stays,total_nights,total_revenue,tags,"
                       "marketing_consent,first_name,last_name,home_city,"
                       "home_state,last_stay_date,booking_sources",
        "limit":       "1",
    })

    base_row = {
        "tenant_id":         tenant_id,
        "property_id":       property_id,
        "email_hash":        email_hash,
        "email_encrypted":   _encrypt_pii(email),
        "first_name":        guest_data.get("first_name"),
        "last_name":         guest_data.get("last_name"),
        "phone_encrypted":   _encrypt_pii(guest_data.get("phone", "")),
        "home_city":         guest_data.get("home_city"),
        "home_state":        guest_data.get("home_state"),
        "preferred_room_type": guest_data.get("preferred_room_type"),
        "booking_sources":   guest_data.get("booking_sources") or [],
        "last_stay_date":    guest_data.get("last_stay_date"),
        "next_stay_date":    guest_data.get("next_stay_date"),
        "marketing_consent": bool(guest_data.get("marketing_consent", False)),
        "source":            guest_data.get("source"),
    }

    incoming_stays   = int(guest_data.get("total_stays", 0) or 0)
    incoming_nights  = int(guest_data.get("total_nights", 0) or 0)
    incoming_revenue = float(guest_data.get("total_revenue", 0) or 0)
    incoming_tags    = list(guest_data.get("tags") or [])

    if existing:
        ex      = existing[0]
        gid     = ex["id"]
        ex_tags = list(ex.get("tags") or [])

        if new_stay:
            stays   = int(ex.get("total_stays")   or 0) + max(1, incoming_stays)
            nights  = int(ex.get("total_nights")  or 0) + incoming_nights
            revenue = float(ex.get("total_revenue") or 0) + incoming_revenue
        else:
            stays   = max(incoming_stays,   int(ex.get("total_stays")   or 0))
            nights  = max(incoming_nights,  int(ex.get("total_nights")  or 0))
            revenue = max(incoming_revenue, float(ex.get("total_revenue") or 0))

        merged = {
            **base_row,
            "total_stays":   stays,
            "total_nights":  nights,
            "total_revenue": round(revenue, 2),
            "avg_rate_paid": round(revenue / nights, 2) if nights else None,
            "tags":          sorted({*ex_tags, *incoming_tags}),
            # Don't blow away existing consent on a profile sync
            "marketing_consent": bool(ex.get("marketing_consent"))
                                 or bool(guest_data.get("marketing_consent", False)),
        }
        # Strip None-only fields so we don't blank out existing values.
        merged = {k: v for k, v in merged.items()
                  if v is not None or k in ("phone_encrypted",
                                            "preferred_room_type")}
        _sb_patch("guests", {"id": f"eq.{gid}"}, merged)
        return gid

    # Insert
    row = {
        **base_row,
        "total_stays":   incoming_stays,
        "total_nights":  incoming_nights,
        "total_revenue": round(incoming_revenue, 2),
        "avg_rate_paid": (round(incoming_revenue / incoming_nights, 2)
                          if incoming_nights else None),
        "tags":          sorted(set(incoming_tags)),
        "consent_date":  (datetime.now(timezone.utc).isoformat()
                          if base_row["marketing_consent"] else None),
        "unsubscribe_token": secrets.token_urlsafe(24),
    }
    out = _sb_post("guests", row)
    return out[0]["id"] if out else ""


# ─────────────────────────────────────────────────────────────────────────────
#  Segmentation
# ─────────────────────────────────────────────────────────────────────────────

_LOCAL_STATES = ("SC", "GA", "NC")

_CORPORATE_DOMAINS = (
    "boeing.com", "ibm.com", "lockheedmartin.com", "delta.com",
    "duke-energy.com", "bcbssc.com", "sfn.com",
    # Generic corp suffixes — extend per-tenant via settings later
)

_PRESERVE_TAGS = ("anniversary", "honeymoon", "corporate")


def update_guest_segments(
    tenant_id:   str,
    property_id: str,
    *,
    today:       Optional[date] = None,
) -> dict[str, int]:
    """
    Walk every guest for the property and recompute their `tags[]` array.
    Returns a counter of segment → count.

    Segments computed:
        vip          — total_stays >= 3 OR total_revenue >= 1500
        local        — home_state ∈ {SC, GA, NC}
        lapsed       — has stayed (total_stays > 0) AND last_stay_date is
                       older than 12 months
        new_guest    — total_stays == 1 AND last_stay_date within 90 days
        anniversary  — preserved from existing tags
        honeymoon    — preserved from existing tags
        corporate    — email domain matches (we can't read the raw email
                       because email_encrypted is placeholder, so we rely
                       on the existing tag — kept for compatibility)
    """
    today = today or date.today()
    twelve_mo_ago = today - timedelta(days=365)
    ninety_d_ago  = today - timedelta(days=90)

    guests = _sb_get("guests", {
        "tenant_id":   f"eq.{tenant_id}",
        "property_id": f"eq.{property_id}",
        "select":      "id,total_stays,total_revenue,home_state,"
                       "last_stay_date,tags",
    })

    counts: dict[str, int] = {
        "vip": 0, "local": 0, "lapsed": 0, "new_guest": 0,
        "anniversary": 0, "honeymoon": 0, "corporate": 0,
    }

    for g in guests:
        tags: set[str] = set()
        stays   = int(g.get("total_stays")   or 0)
        revenue = float(g.get("total_revenue") or 0)
        state   = (g.get("home_state") or "").upper().strip()
        last    = g.get("last_stay_date")
        last_d  = date.fromisoformat(last) if last else None
        prior   = set(g.get("tags") or [])

        # Preserve sticky tags set by humans / earlier flows
        for keep in _PRESERVE_TAGS:
            if keep in prior:
                tags.add(keep)

        if stays >= 3 or revenue >= 1500:
            tags.add("vip")
        if state in _LOCAL_STATES:
            tags.add("local")
        if stays > 0 and last_d and last_d < twelve_mo_ago:
            tags.add("lapsed")
        if stays == 1 and last_d and last_d >= ninety_d_ago:
            tags.add("new_guest")

        new_tags = sorted(tags)
        if set(new_tags) != prior:
            _sb_patch("guests", {"id": f"eq.{g['id']}"}, {"tags": new_tags})

        for t in new_tags:
            counts[t] = counts.get(t, 0) + 1

    counts["_total"] = len(guests)
    logger.info("update_guest_segments(%s) → %s", property_id, counts)
    return counts


__all__ = [
    "upsert_guest", "update_guest_segments",
    "unsubscribe_token_for", "consume_unsubscribe",
    "_hash_email", "_encrypt_pii",
    "_sb_get", "_sb_post", "_sb_patch", "_sb_url", "_sb_key", "_sb_hdrs",
]
