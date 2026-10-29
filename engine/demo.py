"""
engine/demo.py — Public read-only demo for INNtelligence.

A visitor at /demo gets a server-minted, signed, time-limited token that binds
them to the single demo tenant as a `demo_viewer`. The token is opaque and
carries no tenant id (the tenant is fixed server-side), so it cannot be tampered
to reach another tenant. The browser never receives service_role.

Enforcement (authoritative) lives in app.py:
  - a before_request gate returns 403 for the demo principal on every
    POST/PUT/PATCH/DELETE and on any /api/billing/* path.
Reads are served from the shared static demo dataset (config + modules).

Public API:
    DEMO_TENANT_ID, DEMO_ROLE, DEMO_EMAIL
    mint_demo_token() -> str
    verify_demo_token(token) -> bool
    demo_principal() -> dict           # synthetic user for _role_and_tenant/_tenant_context
    reset_demo() -> dict               # nightly backstop: restore pristine state
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, BadData

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_ROOT / ".env")
logger = logging.getLogger(__name__)

# The one, isolated demo tenant (Bay Street Inn Demo). Fixed server-side.
DEMO_TENANT_ID = "357afb97-1c29-427d-b58e-63d2fcc90f97"
DEMO_ROLE = "demo_viewer"
DEMO_EMAIL = "demo@getinntelligence.com"

_SALT = "inntelligence-demo-session-v1"
_TOKEN_MAX_AGE_S = 8 * 60 * 60  # 8 hours


def _secret() -> str:
    # Server-only secret. Never sent to the browser. Falls back to the service
    # key (also server-only) so the token is unforgeable even if the dedicated
    # var isn't set; a dev default keeps local runs working.
    return (os.getenv("DEMO_SESSION_SECRET")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or "dev-insecure-demo-secret")


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt=_SALT)


def mint_demo_token() -> str:
    """Issue a signed, time-limited demo session token."""
    return _serializer().dumps({"demo": True, "v": 1})


def verify_demo_token(token: str | None) -> bool:
    """True iff *token* is a valid, unexpired demo token signed by this server.
    A Supabase JWT or any other string fails the signature check → False."""
    if not token or not isinstance(token, str):
        return False
    try:
        data = _serializer().loads(token, max_age=_TOKEN_MAX_AGE_S)
    except BadData:
        return False
    except Exception:  # noqa: BLE001 — never raise into the request path
        return False
    return isinstance(data, dict) and bool(data.get("demo"))


def demo_principal() -> dict:
    """Synthetic user dict shaped like a Supabase user so the existing
    _role_and_tenant / _tenant_context helpers resolve it to the demo tenant.
    plan_tier='collection' is for display only; full feature access is granted
    server-side via the demo_viewer role."""
    return {
        "id": None,
        "email": DEMO_EMAIL,
        "demo": True,
        "app_metadata": {"app_role": DEMO_ROLE, "tenant_id": DEMO_TENANT_ID,
                         "plan_tier": "collection"},
        "user_metadata": {"property_name": "The Bay Street Inn",
                          "owner_name": "Live Demo"},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Nightly reset — backstop that restores the demo to pristine state.
# ─────────────────────────────────────────────────────────────────────────────
_MUTABLE_FILES = ["packages_status.json", "gift_shop_store.json",
                  "tenant_competitors.json"]


def reset_demo() -> dict:
    """Restore the demo tenant row + shared mutable files to pristine state.
    Idempotent. Safe to run nightly (or on demand)."""
    U = os.getenv("SUPABASE_URL", "").rstrip("/")
    S = os.getenv("SUPABASE_SERVICE_KEY", "")
    h = {"apikey": S, "Authorization": f"Bearer {S}", "Content-Type": "application/json"}
    actions: list = []

    if U and S:
        try:
            r = requests.patch(f"{U}/rest/v1/tenants",
                               headers={**h, "Prefer": "return=minimal"},
                               params={"id": f"eq.{DEMO_TENANT_ID}"},
                               json={"plan_tier": "boutique", "active": True,
                                     "onboarding_complete": True,
                                     "stripe_customer_id": None,
                                     "stripe_subscription_id": None,
                                     "subscription_status": None,
                                     "trial_ends_at": None},
                               timeout=20)
            actions.append({"tenant_reset": r.status_code})
        except Exception as e:  # noqa: BLE001
            actions.append({"tenant_reset_error": str(e)[:120]})
        try:
            r = requests.delete(f"{U}/rest/v1/feature_trials",
                                headers={**h, "Prefer": "return=representation"},
                                params={"tenant_id": f"eq.{DEMO_TENANT_ID}"},
                                timeout=20)
            actions.append({"trials_deleted": len(r.json()) if (r.ok and r.text) else 0})
        except Exception as e:  # noqa: BLE001
            actions.append({"trials_delete_error": str(e)[:120]})

    # Restore shared mutable files from the committed pristine baselines.
    base = _ROOT / "config" / "demo_pristine"
    live = _ROOT / "config"
    for name in _MUTABLE_FILES:
        src, dst = base / name, live / name
        try:
            if src.exists():
                dst.write_bytes(src.read_bytes())
                actions.append({"restored_file": name})
        except Exception as e:  # noqa: BLE001
            actions.append({"file_error": f"{name}: {str(e)[:80]}"})
    # Remove any per-property package status files the app may have written.
    try:
        for p in live.glob("packages_status_*.json"):
            p.unlink()
            actions.append({"removed_file": p.name})
    except Exception as e:  # noqa: BLE001
        actions.append({"glob_error": str(e)[:80]})

    return {"ok": True, "at": datetime.now(timezone.utc).isoformat(), "actions": actions}


__all__ = ["DEMO_TENANT_ID", "DEMO_ROLE", "DEMO_EMAIL",
           "mint_demo_token", "verify_demo_token", "demo_principal", "reset_demo"]
