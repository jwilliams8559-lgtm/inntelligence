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
        "tenant_id":     "anchorage-1770-demo",
        "plan_tier":     "professional",
        "property_name": "Anchorage 1770 Inn",
        "role":          "inn_owner",
        "password_hash": "demo2026",
    },
    "essentials@graciouscollection.com": {
        "tenant_id":     "essentials-demo",
        "plan_tier":     "essentials",
        "property_name": "Essentials Demo Inn",
        "role":          "inn_owner",
        "password_hash": "demo2026",
    },
    "portfolio@graciouscollection.com": {
        "tenant_id":     "portfolio-demo",
        "plan_tier":     "portfolio",
        "property_name": "Portfolio Demo Properties",
        "role":          "inn_owner",
        "password_hash": "demo2026",
    },
    "admin@graciouscollection.com": {
        "tenant_id":     "tgc-admin",
        "plan_tier":     "portfolio",
        "property_name": "The Gracious Collection",
        "role":          "tgc_admin",
        "password_hash": "admin2026",
    },
}


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


def create_token(email: str) -> Optional[str]:
    account = DEMO_ACCOUNTS.get(email)
    if not account:
        return None
    return base64.b64encode(json.dumps(_account_to_user(email, account)).encode()).decode()


def get_plan_features(plan_tier: str) -> dict:
    from config.settings import FEATURE_GATES
    return FEATURE_GATES.get(plan_tier, FEATURE_GATES.get("essentials", {}))


def check_feature(feature_name: str) -> bool:
    user = get_current_user()
    if not user:
        return False
    return bool(get_plan_features(user.get("plan_tier", "essentials")).get(feature_name, False))


def _upgrade_tier_for(current_tier: str, feature: str) -> str:
    from config.settings import FEATURE_GATES
    order = ["essentials", "professional", "portfolio", "enterprise"]
    for tier in order:
        if tier == current_tier:
            continue
        if FEATURE_GATES.get(tier, {}).get(feature):
            return tier
    return "portfolio"


def require_feature(feature_name: str):
    """Flask route decorator — returns 403 with upgrade hint when locked."""
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not check_feature(feature_name):
                user = get_current_user() or {}
                tier = user.get("plan_tier", "essentials")
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
    "DEMO_ACCOUNTS", "get_current_user", "create_token",
    "get_plan_features", "check_feature", "require_feature",
]
