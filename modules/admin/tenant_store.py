"""JSON-backed tenant registry for admin-led onboarding.

Persists dynamically-provisioned tenants beyond the static DEMO_ACCOUNTS in
auth.py. Each tenant record carries the full onboarding payload so we can
re-render their dashboard, edit their plan, and re-send credentials later.
"""
from __future__ import annotations

import json
import os
import secrets
import string
from datetime import date, datetime, timezone
from typing import Any

STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "tenants.json")
PMS_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "pms_catalog.json")


def _load() -> dict[str, dict[str, Any]]:
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _slugify(name: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "property"


def _generate_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def list_tenants() -> list[dict[str, Any]]:
    data = _load()
    return sorted(data.values(), key=lambda t: t.get("created_at", ""), reverse=True)


def get_tenant(tenant_id: str) -> dict[str, Any] | None:
    return _load().get(tenant_id)


def get_tenant_by_email(email: str) -> dict[str, Any] | None:
    email = (email or "").lower().strip()
    for t in _load().values():
        if t.get("owner_email", "").lower() == email:
            return t
    return None


def update_tenant(tenant_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    data = _load()
    if tenant_id not in data:
        return None
    data[tenant_id].update(patch)
    data[tenant_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(data)
    return data[tenant_id]


def mark_logged_in(tenant_id: str) -> None:
    """Flip status from 'pending' to 'active' on first login."""
    data = _load()
    if tenant_id in data and data[tenant_id].get("status") == "pending":
        data[tenant_id]["status"] = "active"
        data[tenant_id]["first_login_at"] = datetime.now(timezone.utc).isoformat()
        _save(data)


def provision_tenant(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a tenant from the onboarding wizard payload.

    Returns the persisted record including a freshly-generated temp password.
    """
    inn_name      = payload.get("inn_name", "Untitled Inn").strip()
    owner_email   = payload.get("owner_email", "").lower().strip()
    plan_tier     = payload.get("plan_tier", "professional")
    founding      = bool(payload.get("founding_member"))
    tenant_id     = _slugify(inn_name) + "-" + secrets.token_hex(3)
    temp_password = _generate_password()
    now_iso       = datetime.now(timezone.utc).isoformat()

    record = {
        "tenant_id":         tenant_id,
        "inn_name":          inn_name,
        "address":           payload.get("address", ""),
        "city":              payload.get("city", ""),
        "state":             payload.get("state", ""),
        "postcode":          payload.get("postcode", ""),
        "country":           payload.get("country", "US"),
        "currency":          payload.get("currency", "USD"),
        "currency_symbol":   payload.get("currency_symbol", "$"),
        "timezone":          payload.get("timezone", "America/New_York"),
        "gdpr_in_scope":     bool(payload.get("gdpr_in_scope")),
        "total_rooms":       int(payload.get("total_rooms", 0)),
        "owner_first_name":  payload.get("owner_first_name", ""),
        "owner_last_name":   payload.get("owner_last_name", ""),
        "owner_email":       owner_email,
        "owner_phone":       payload.get("owner_phone", ""),
        "website_url":       payload.get("website_url", ""),
        "plan_tier":         plan_tier,
        "founding_member":   founding,
        "founding_converts_on": _founding_conversion_date() if founding else None,
        "room_types":        payload.get("room_types", []),
        "pms_id":            payload.get("pms_id"),
        "pms_connected":     bool(payload.get("pms_connected")),
        "pms_property_name": payload.get("pms_property_name"),
        "competitors":       payload.get("competitors", []),
        "temp_password":     temp_password,
        "status":            "pending",
        "created_at":        now_iso,
        "updated_at":        now_iso,
        "first_login_at":    None,
        "welcome_email_sent_at": None,
    }

    data = _load()
    data[tenant_id] = record
    _save(data)
    return record


def regenerate_password(tenant_id: str) -> str | None:
    data = _load()
    if tenant_id not in data:
        return None
    new_pw = _generate_password()
    data[tenant_id]["temp_password"] = new_pw
    data[tenant_id]["updated_at"]    = datetime.now(timezone.utc).isoformat()
    _save(data)
    return new_pw


def _founding_conversion_date() -> str:
    today = date.today()
    month = today.month + 6
    year  = today.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    try:
        return date(year, month, today.day).isoformat()
    except ValueError:
        return date(year, month, 28).isoformat()


def load_pms_catalog() -> list[dict[str, Any]]:
    if not os.path.exists(PMS_CATALOG_PATH):
        return _DEFAULT_PMS_CATALOG
    try:
        with open(PMS_CATALOG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _DEFAULT_PMS_CATALOG


_DEFAULT_PMS_CATALOG: list[dict[str, Any]] = [
    {"id": "cloudbeds",         "name": "Cloudbeds",         "tier": "tier_1", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password", "help": "Found in Cloudbeds → Settings → API."},
    ]},
    {"id": "resnexus",          "name": "ResNexus",          "tier": "tier_1", "auth_fields": [
        {"key": "username", "label": "Username", "type": "text"},
        {"key": "password", "label": "Password", "type": "password"},
    ]},
    {"id": "thinkreservations", "name": "ThinkReservations", "tier": "tier_1", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "littlehotelier",    "name": "Little Hotelier",   "tier": "tier_1", "auth_fields": [
        {"key": "api_key",     "label": "API Key",     "type": "password"},
        {"key": "property_id", "label": "Property ID", "type": "text"},
    ]},
    {"id": "mews",              "name": "Mews",              "tier": "tier_1", "auth_fields": [
        {"key": "access_token", "label": "Access Token", "type": "password"},
        {"key": "client_token", "label": "Client Token", "type": "password"},
    ]},
    {"id": "webrezpro",   "name": "WebRezPro",   "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "roomraccoon", "name": "RoomRaccoon", "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "innroad",     "name": "innRoad",     "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "hotelogix",   "name": "Hotelogix",   "tier": "tier_2", "auth_fields": [
        {"key": "username", "label": "Username", "type": "text"},
        {"key": "password", "label": "Password", "type": "password"},
    ]},
    {"id": "eviivo",      "name": "eviivo",      "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "amenitiz",    "name": "Amenitiz",    "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "beds24",      "name": "Beds24",      "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "guestline",   "name": "Guestline",   "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "sirvoy",      "name": "Sirvoy",      "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "rms_cloud",   "name": "RMS Cloud",   "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "protel",      "name": "Protel",      "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "lodgify",     "name": "Lodgify",     "tier": "tier_2", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "siteminder",  "name": "SiteMinder",  "tier": "channel_manager", "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password"},
    ]},
    {"id": "csv_import",  "name": "CSV Import (manual)", "tier": "csv_import", "auth_fields": []},
]
