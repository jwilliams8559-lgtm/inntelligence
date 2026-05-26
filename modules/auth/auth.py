"""
Authentication and tenant resolution for The Gracious Collection.
Demo system uses base64-encoded JSON tokens against an in-memory account
table — adequate for the demo, replaced by Supabase Auth in production.
"""
from __future__ import annotations

import base64
import json
from functools import wraps
from typing import Optional

from flask import jsonify, request


# Demo accounts — in production these come from Supabase Auth
DEMO_ACCOUNTS = {
    "demo@graciouscollection.com": {
        "tenant_id":     "bay-street-inn-demo",
        "plan_tier":     "professional",
        "property_name": "Bay Street Inn",
        "role":          "inn_owner",
        "password_hash": "demo2026",
    },
    "starter@graciouscollection.com": {
        "tenant_id":     "starter-demo",
        "plan_tier":     "starter",
        "property_name": "Starter Demo Inn",
        "role":          "inn_owner",
        "password_hash": "demo2026",
    },
    "premium@graciouscollection.com": {
        "tenant_id":     "premium-demo",
        "plan_tier":     "premium",
        "property_name": "Premium Demo Properties",
        "role":          "inn_owner",
        "password_hash": "demo2026",
    },
    "founding@graciouscollection.com": {
        "tenant_id":     "founding-demo",
        "plan_tier":     "founding_member",
        "property_name": "Founding Member Inn",
        "role":          "inn_owner",
        "password_hash": "demo2026",
    },
    "admin@graciouscollection.com": {
        "tenant_id":     "tgc-admin",
        "plan_tier":     "premium",
        "property_name": "INNtelligence Admin",
        "role":          "tgc_admin",
        "password_hash": "admin2026",
    },
}

# Valid subscription tiers (matches engine/billing.py plan catalog).
PLAN_TIERS = ["starter", "professional", "enterprise", "premium", "founding_member"]


def get_current_user() -> Optional[dict]:
    """
    Resolve the current user from a Bearer token in the Authorization header,
    falling back to the demo professional account if no token is present.
    The fallback keeps existing fetch calls working during development.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user  = _decode_token(token)
        if user:
            return user
    # Dev fallback — drop this when Supabase Auth lands.
    return _account_to_user("demo@graciouscollection.com",
                            DEMO_ACCOUNTS["demo@graciouscollection.com"])


def _decode_token(token: str) -> Optional[dict]:
    try:
        return json.loads(base64.b64decode(token.encode()).decode())
    except Exception:
        return None


def _account_to_user(email: str, account: dict) -> dict:
    return {
        "email":         email,
        "tenant_id":     account["tenant_id"],
        "plan_tier":     account["plan_tier"],
        "role":          account["role"],
        "property_name": account["property_name"],
    }


def _lookup_account(email: str) -> Optional[dict]:
    """Resolve an email to either a static DEMO_ACCOUNTS entry or a dynamic
    tenant_store record. Dynamic accounts authenticate with the temp_password
    set at provisioning time."""
    email = (email or "").lower().strip()
    if email in DEMO_ACCOUNTS:
        return DEMO_ACCOUNTS[email]
    try:
        from modules.admin.tenant_store import get_tenant_by_email
        t = get_tenant_by_email(email)
        if t:
            return {
                "tenant_id":     t["tenant_id"],
                "plan_tier":     t["plan_tier"],
                "property_name": t["inn_name"],
                "role":          "inn_owner",
                "password_hash": t["temp_password"],
            }
    except ImportError:
        pass
    return None


def authenticate(email: str, password: str) -> Optional[dict]:
    """Verify credentials and return the account dict if valid."""
    account = _lookup_account(email)
    if not account:
        return None
    if account.get("password_hash") != password:
        return None
    return account


def create_token(email: str) -> Optional[str]:
    account = _lookup_account(email)
    if not account:
        return None
    return base64.b64encode(json.dumps(_account_to_user(email, account)).encode()).decode()


def get_plan_features(plan_tier: str) -> dict:
    from config.settings import FEATURE_GATES
    return FEATURE_GATES.get(plan_tier, FEATURE_GATES.get("starter", {}))


def check_feature(feature_name: str) -> bool:
    user = get_current_user()
    if not user:
        return False
    return bool(get_plan_features(user.get("plan_tier", "starter")).get(feature_name, False))


def _upgrade_tier_for(current_tier: str, feature: str) -> str:
    from config.settings import FEATURE_GATES
    order = ["starter", "professional", "enterprise", "premium"]
    for tier in order:
        if tier == current_tier:
            continue
        if FEATURE_GATES.get(tier, {}).get(feature):
            return tier
    return "premium"


def require_feature(feature_name: str):
    """Flask route decorator — returns 403 with upgrade hint when locked."""
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not check_feature(feature_name):
                user = get_current_user() or {}
                tier = user.get("plan_tier", "starter")
                return jsonify({
                    "error":        "feature_not_available",
                    "feature":      feature_name,
                    "current_tier": tier,
                    "upgrade_to":   _upgrade_tier_for(tier, feature_name),
                    "message":      f"'{feature_name}' is not available on the {tier} plan.",
                    "locked":       True,
                }), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator


__all__ = [
    "DEMO_ACCOUNTS", "get_current_user", "create_token", "authenticate",
    "get_plan_features", "check_feature", "require_feature",
]
