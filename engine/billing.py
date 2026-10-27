"""
engine/billing.py — Phase 10
Stripe billing integration for The Gracious Collection.

Public API:
    setup_stripe_products() -> dict
        Idempotently creates the INNtelligence plan products in Stripe.
        Re-running is safe — fetches by lookup_key and only creates missing ones.

    price_id_for_tier(tier) -> str | None
        Resolve the live Stripe price id for a tier (STRIPE_PRICE_* env var,
        falling back to a lookup_key search).

    create_checkout_session(tenant_id, tier, success_url, cancel_url, email) -> dict
        Creates a Stripe Checkout Session (subscription mode) for a tier.

    create_portal_session(tenant_id, return_url) -> dict
        Creates a Stripe Billing Portal session for managing/canceling a sub.

    create_subscription(tenant_id, plan_tier, billing_email, trial_days=0) -> dict
        Creates a Stripe customer + subscription for a tenant (server-side).

    cancel_subscription(tenant_id, *, immediate=False) -> dict
        Cancels the tenant's active subscription.

    list_invoices(tenant_id, limit=20) -> list[dict]
        Returns the most recent invoices for a tenant's customer.

    process_webhook(payload: bytes, signature: str) -> dict
        Verifies signature, dispatches to handlers, writes billing_events row.
        On 'customer.subscription.updated' updates tenant.plan_tier.
        On 'invoice.payment_failed' emits a critical alert.

Mock fallback:
    When STRIPE_SECRET_KEY is not set (or contains 'placeholder'/'demo'),
    every function returns a deterministic mock dict — useful for testing
    the dashboard wiring before Stripe credentials are issued.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

try:
    import stripe as _stripe
except ImportError:
    _stripe = None


# ─────────────────────────────────────────────────────────────────────────────
#  Plan catalog
# ─────────────────────────────────────────────────────────────────────────────

# The four INNtelligence subscription tiers — single source of truth.
# `env` names the STRIPE_PRICE_* variable holding the live price id (created by
# scripts/setup_stripe_tiers.py); `lookup_key` is the Stripe-side idempotency
# anchor used as a fallback when the env var is unset.
_PLAN_CATALOG = {
    "inn": {
        "name":        "Inn",
        "env":         "STRIPE_PRICE_INN",
        "lookup_key":  "inntelligence_inn_monthly",
        "amount_cents": 149_00,
        "currency":    "usd",
        "interval":    "month",
        "description": "Rate recommendations, dashboard, 1 PMS, email support.",
        "features": [
            "90-day rate calendar with daily recommendations",
            "Single PMS integration (ResNexus or Cloudbeds)",
            "Competitor intelligence (up to 5 competitors)",
            "Email support · 48-hour response SLA",
        ],
    },
    "boutique": {
        "name":        "Boutique",
        "env":         "STRIPE_PRICE_BOUTIQUE",
        "lookup_key":  "inntelligence_boutique_monthly",
        "amount_cents": 399_00,
        "currency":    "usd",
        "interval":    "month",
        "description": "All Inn plus autopilot, guest CRM, channel publishing, "
                       "packages & gift shop, demand alerts.",
        "features": [
            "Everything in Inn",
            "Autopilot rate publishing to 7 OTAs via SiteMinder",
            "Guest CRM with demand-triggered campaigns",
            "Packages, gift shop, weddings & private events",
            "Demand alerts (surge / competitor / festival / gap)",
        ],
    },
    "signature": {
        "name":        "Signature",
        "env":         "STRIPE_PRICE_SIGNATURE",
        "lookup_key":  "inntelligence_signature_monthly",
        "amount_cents": 799_00,
        "currency":    "usd",
        "interval":    "month",
        "description": "All Boutique plus multi-property console, revenue "
                       "intelligence, advanced analytics, advisory hours.",
        "features": [
            "Everything in Boutique",
            "Multi-property management console",
            "Revenue intelligence (gap-night recovery)",
            "Advanced analytics",
            "2 advisory hours / month with Jim Williams",
        ],
    },
    "collection": {
        "name":        "Collection",
        "env":         "STRIPE_PRICE_COLLECTION",
        "lookup_key":  "inntelligence_collection_monthly",
        "amount_cents": 1499_00,
        "currency":    "usd",
        "interval":    "month",
        "description": "All Signature plus white-label, priority support, a "
                       "dedicated account manager, and API access.",
        "features": [
            "Everything in Signature",
            "White-label option",
            "Priority support · same-day response",
            "Dedicated account manager",
            "API access",
        ],
    },
    "founding_member": {
        "name":        "Founding Member",
        "lookup_key":  "inntelligence_founding_member",
        "amount_cents": 0,
        # After the 6-month free period the subscription rolls to Boutique.
        "rollover_tier":         "boutique",
        "rollover_amount_cents": 399_00,
        "currency":    "usd",
        "interval":    "month",
        "description": "Boutique tier free for 6 months, then $399/month — "
                       "in exchange for data access and a testimonial.",
        "features": [
            "Everything in Boutique",
            "6 months free, then $399/month",
            "Direct line to founding team",
            "First in line for advisory hours",
        ],
    },
}

# Tiers a customer can self-serve checkout into (founding_member is admin-provisioned).
CHECKOUT_TIERS = ["inn", "boutique", "signature", "collection"]


# ─────────────────────────────────────────────────────────────────────────────
#  INNsight — hospitality consulting advisory practice (sister business line to
#  the INNtelligence SaaS, under The Gracious Collection, LLC). Engagements are
#  scoped and invoiced per-project, NOT billed as a recurring Stripe subscription.
# ─────────────────────────────────────────────────────────────────────────────
INNSIGHT_ADVISORY = {
    "name":           "INNsight Advisory",
    "tagline":        "Expert Guidance for Boutique Hospitality",
    "billing":        "per_engagement",       # invoiced manually, not a subscription
    "price_low_usd":  25_000,
    "price_high_usd": 80_000,
    "description":    "Revenue transformation consulting engagements for boutique "
                      "inns — pricing strategy, market positioning, and operations.",
}


def _is_mock() -> bool:
    """Mock when SDK missing OR key missing/placeholder."""
    if _stripe is None:
        return True
    k = os.getenv("STRIPE_SECRET_KEY", "")
    return (not k) or "placeholder" in k.lower() or "demo" in k.lower() or "your_key" in k.lower()


def _stripe_init() -> None:
    if _stripe is not None:
        _stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def price_id_for_tier(tier: str) -> Optional[str]:
    """Resolve the live Stripe price id for *tier*.

    Order of resolution:
      1. founding_member → its rollover tier's price (free period runs via a
         Checkout trial; the billed price is Boutique).
      2. the STRIPE_PRICE_* env var named in the catalog.
      3. a Stripe lookup_keys search (strongly consistent) as a fallback.
    """
    plan = _PLAN_CATALOG.get(tier)
    if not plan:
        return None
    if plan.get("rollover_tier"):
        return price_id_for_tier(plan["rollover_tier"])
    env = plan.get("env")
    if env and os.getenv(env):
        return os.getenv(env)
    if _stripe is not None and not _is_mock():
        _stripe_init()
        res = _stripe.Price.list(lookup_keys=[plan["lookup_key"]], limit=1)
        if res.data:
            return res.data[0].id
    return None


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
                     params=params, timeout=15)
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
#  Product setup
# ─────────────────────────────────────────────────────────────────────────────

def setup_stripe_products() -> dict:
    """
    Idempotently create / update the plan products in Stripe.
    Returns {plan_key: {product_id, price_id}, ...}.
    """
    if _is_mock():
        logger.info("setup_stripe_products: MOCK mode (no Stripe key configured)")
        return {k: {"product_id": f"prod_mock_{k}",
                    "price_id":   f"price_mock_{k}",
                    "lookup_key": v["lookup_key"],
                    "amount":     v["amount_cents"]/100,
                    "name":       v["name"],
                    "mock":       True}
                for k, v in _PLAN_CATALOG.items()}

    _stripe_init()
    result: dict[str, dict] = {}
    for key, plan in _PLAN_CATALOG.items():
        # Find existing price by lookup_key
        existing = _stripe.Price.list(lookup_keys=[plan["lookup_key"]], limit=1)
        if existing.data:
            price = existing.data[0]
            product_id = price.product
            result[key] = {"product_id": product_id, "price_id": price.id,
                           "lookup_key": plan["lookup_key"],
                           "amount":     plan["amount_cents"]/100,
                           "name":       plan["name"]}
            continue

        # Create product + price
        product = _stripe.Product.create(
            name=f"INNtelligence {plan['name']}",
            description=plan["description"],
            metadata={"plan_key": key, "features": json.dumps(plan["features"])},
        )
        price = _stripe.Price.create(
            product=product.id,
            unit_amount=plan["amount_cents"],
            currency=plan["currency"],
            recurring={"interval": plan["interval"]},
            lookup_key=plan["lookup_key"],
            transfer_lookup_key=True,
        )
        result[key] = {"product_id": product.id, "price_id": price.id,
                       "lookup_key": plan["lookup_key"],
                       "amount":     plan["amount_cents"]/100,
                       "name":       plan["name"]}
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Checkout + Billing Portal (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

def create_checkout_session(
    tenant_id:     str,
    tier:          str,
    *,
    success_url:   str,
    cancel_url:    str,
    billing_email: Optional[str] = None,
    trial_days:    int = 0,
) -> dict:
    """Create a Stripe Checkout Session (subscription mode) for *tier*.

    The session carries client_reference_id=tenant_id and metadata so the
    checkout.session.completed webhook can attach the resulting customer +
    subscription to the tenant. Returns {url, session_id, ...}.
    """
    if tier not in CHECKOUT_TIERS:
        raise ValueError(f"tier {tier!r} is not a self-serve checkout tier")
    tenant = _get_tenant(tenant_id)
    price_id = price_id_for_tier(tier)

    if _is_mock() or not price_id:
        # No Stripe (or price) configured → return a deterministic stub so the
        # frontend wiring is testable; redirect lands back on success_url.
        return {"mock": True, "tenant_id": tenant_id, "tier": tier,
                "session_id": f"cs_mock_{tenant_id[:8]}",
                "url": success_url, "price_id": price_id}

    _stripe_init()
    params: dict[str, Any] = {
        "mode":                 "subscription",
        "line_items":           [{"price": price_id, "quantity": 1}],
        "success_url":          success_url,
        "cancel_url":           cancel_url,
        "client_reference_id":  tenant_id,
        "metadata":             {"tenant_id": tenant_id, "plan_tier": tier},
        "subscription_data":    {"metadata": {"tenant_id": tenant_id, "plan_tier": tier}},
        "allow_promotion_codes": True,
    }
    # Reuse an existing customer if we have one, else let Checkout create one
    # (prefilled with the billing email when available).
    customer_id = tenant.get("stripe_customer_id")
    if customer_id:
        params["customer"] = customer_id
    else:
        email = billing_email or tenant.get("billing_email")
        if email:
            params["customer_email"] = email
    if trial_days > 0:
        params["subscription_data"]["trial_period_days"] = trial_days

    session = _stripe.checkout.Session.create(**params)
    return {"mock": False, "tenant_id": tenant_id, "tier": tier,
            "session_id": session.id, "url": session.url, "price_id": price_id}


def create_portal_session(tenant_id: str, *, return_url: str) -> dict:
    """Create a Stripe Billing Portal session so a tenant can manage/cancel."""
    tenant = _get_tenant(tenant_id)
    customer_id = tenant.get("stripe_customer_id")

    if _is_mock():
        # No Stripe configured — stub url so frontend wiring is testable.
        return {"mock": True, "tenant_id": tenant_id,
                "url": return_url, "customer_id": customer_id}
    if not customer_id:
        # Live mode but the tenant has never checked out — nothing to manage.
        return {"mock": False, "tenant_id": tenant_id,
                "url": None, "customer_id": None, "error": "no_customer"}

    _stripe_init()
    session = _stripe.billing_portal.Session.create(
        customer=customer_id, return_url=return_url)
    return {"mock": False, "tenant_id": tenant_id,
            "url": session.url, "customer_id": customer_id}


# ─────────────────────────────────────────────────────────────────────────────
#  Subscriptions
# ─────────────────────────────────────────────────────────────────────────────

def _get_tenant(tenant_id: str) -> dict:
    rows = _sb_get("tenants", {"id": f"eq.{tenant_id}",
                                "select": "id,name,slug,plan_tier,"
                                          "stripe_customer_id,stripe_subscription_id,"
                                          "billing_email,trial_ends_at,"
                                          "subscription_status,current_period_end"})
    if not rows:
        raise ValueError(f"tenant {tenant_id} not found")
    return rows[0]


def create_subscription(
    tenant_id:      str,
    plan_tier:      str,
    billing_email:  str,
    *,
    trial_days:     int = 0,
) -> dict:
    """Create a Stripe customer (if needed) + subscription for *tenant_id*."""
    if plan_tier not in _PLAN_CATALOG:
        raise ValueError(f"unknown plan_tier {plan_tier!r}")
    tenant = _get_tenant(tenant_id)

    if _is_mock():
        sub_id = f"sub_mock_{tenant_id[:8]}"
        cust_id = tenant.get("stripe_customer_id") or f"cus_mock_{tenant_id[:8]}"
        period_end = datetime.now(timezone.utc) + timedelta(days=30)
        _sb_patch("tenants", {"id": f"eq.{tenant_id}"}, {
            "stripe_customer_id":     cust_id,
            "stripe_subscription_id": sub_id,
            "plan_tier":              plan_tier,
            "billing_email":          billing_email,
            "subscription_status":    "active",
            "current_period_end":     period_end.isoformat(),
            "trial_ends_at":          ((datetime.now(timezone.utc) + timedelta(days=trial_days))
                                        .isoformat() if trial_days else None),
        })
        return {
            "tenant_id":            tenant_id,
            "plan_tier":            plan_tier,
            "customer_id":          cust_id,
            "subscription_id":      sub_id,
            "status":               "active",
            "current_period_end":   period_end.isoformat(),
            "mock":                 True,
        }

    _stripe_init()
    price_id = price_id_for_tier(plan_tier)
    if not price_id:
        raise ValueError(f"no Stripe price configured for tier {plan_tier!r}")

    # Customer
    customer_id = tenant.get("stripe_customer_id")
    if not customer_id:
        cust = _stripe.Customer.create(
            email=billing_email,
            name=tenant.get("name"),
            metadata={"tenant_id": tenant_id, "slug": tenant.get("slug")},
        )
        customer_id = cust.id

    # Subscription
    sub_kwargs: dict[str, Any] = {
        "customer": customer_id,
        "items":    [{"price": price_id}],
        "metadata": {"tenant_id": tenant_id, "plan_tier": plan_tier},
    }
    if trial_days > 0:
        sub_kwargs["trial_period_days"] = trial_days
    sub = _stripe.Subscription.create(**sub_kwargs)

    period_end = datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc)
    _sb_patch("tenants", {"id": f"eq.{tenant_id}"}, {
        "stripe_customer_id":     customer_id,
        "stripe_subscription_id": sub.id,
        "plan_tier":              plan_tier,
        "billing_email":          billing_email,
        "subscription_status":    sub.status,
        "current_period_end":     period_end.isoformat(),
        "trial_ends_at":          (datetime.fromtimestamp(sub.trial_end, tz=timezone.utc).isoformat()
                                    if sub.trial_end else None),
    })
    return {
        "tenant_id":            tenant_id,
        "plan_tier":            plan_tier,
        "customer_id":          customer_id,
        "subscription_id":      sub.id,
        "status":               sub.status,
        "current_period_end":   period_end.isoformat(),
        "mock":                 False,
    }


def cancel_subscription(tenant_id: str, *, immediate: bool = False) -> dict:
    tenant = _get_tenant(tenant_id)
    sub_id = tenant.get("stripe_subscription_id")
    if not sub_id:
        return {"tenant_id": tenant_id, "status": "no_subscription"}

    if _is_mock():
        _sb_patch("tenants", {"id": f"eq.{tenant_id}"}, {
            "plan_tier":           "cancelled",
            "subscription_status": "canceled",
        })
        return {"tenant_id": tenant_id, "subscription_id": sub_id,
                "status": "canceled", "immediate": immediate, "mock": True}

    _stripe_init()
    if immediate:
        sub = _stripe.Subscription.delete(sub_id)
    else:
        sub = _stripe.Subscription.modify(sub_id, cancel_at_period_end=True)
    _sb_patch("tenants", {"id": f"eq.{tenant_id}"}, {
        "subscription_status": sub.status,
        "plan_tier":           "cancelled" if immediate else tenant.get("plan_tier"),
    })
    return {"tenant_id": tenant_id, "subscription_id": sub.id,
            "status": sub.status, "immediate": immediate}


def list_invoices(tenant_id: str, *, limit: int = 20) -> list[dict]:
    tenant = _get_tenant(tenant_id)
    cust_id = tenant.get("stripe_customer_id")
    if not cust_id:
        return []

    if _is_mock():
        # Return one synthetic invoice for the demo
        return [{
            "id":            f"in_mock_{tenant_id[:6]}",
            "amount_paid":   _PLAN_CATALOG.get(tenant.get("plan_tier") or "founding_member",
                                               {}).get("amount_cents", 0) / 100,
            "currency":      "usd",
            "status":        "paid",
            "created":       datetime.now(timezone.utc).isoformat(),
            "hosted_invoice_url": "https://example.com/invoices/mock",
            "mock":          True,
        }]

    _stripe_init()
    inv = _stripe.Invoice.list(customer=cust_id, limit=limit)
    return [{
        "id":                 i.id,
        "amount_paid":        i.amount_paid / 100,
        "currency":           i.currency,
        "status":             i.status,
        "created":            datetime.fromtimestamp(i.created, tz=timezone.utc).isoformat(),
        "hosted_invoice_url": i.hosted_invoice_url,
        "invoice_pdf":        i.invoice_pdf,
    } for i in inv.data]


# ─────────────────────────────────────────────────────────────────────────────
#  Webhook
# ─────────────────────────────────────────────────────────────────────────────

def process_webhook(payload: bytes, signature: str) -> dict:
    """
    Verify and dispatch a Stripe webhook event.
    Side effects:
        - billing_events row inserted (idempotent on stripe_event_id)
        - On customer.subscription.updated → tenants.plan_tier updated
        - On invoice.payment_failed → emit a critical alert
    """
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if _is_mock() or not secret:
        # Mock mode — just decode JSON, no signature check
        try:
            event = json.loads(payload or b"{}")
        except json.JSONDecodeError:
            return {"error": "invalid JSON", "status": 400}
        event_id   = event.get("id", f"evt_mock_{datetime.now().timestamp()}")
        event_type = event.get("type", "mock.event")
    else:
        _stripe_init()
        try:
            # construct_event verifies the signature; we then operate on the raw
            # JSON as a plain dict so all handling below is uniform (the Stripe
            # object returned here is not dict-compatible in stripe-python v15).
            _stripe.Webhook.construct_event(payload, signature, secret)
        except Exception as exc:
            return {"error": f"signature verification failed: {exc}", "status": 400}
        event = json.loads(payload)
        event_id   = event["id"]
        event_type = event["type"]

    # Resolve tenant — every event we care about has a customer
    customer_id = event.get("data", {}).get("object", {}).get("customer")
    tenant_id: Optional[str] = None
    if customer_id:
        rows = _sb_get("tenants", {"stripe_customer_id": f"eq.{customer_id}",
                                    "select": "id"})
        if rows:
            tenant_id = rows[0]["id"]

    # Idempotency — store the event
    _sb_post("billing_events", {
        "tenant_id":       tenant_id,
        "stripe_event_id": event_id,
        "event_type":      event_type,
        "payload":         event,
    }, prefer="return=minimal")

    # Dispatch
    handled = False
    if event_type == "checkout.session.completed":
        # A hosted Checkout finished. The customer may be brand-new (not yet on
        # any tenant row), so resolve the tenant from client_reference_id /
        # metadata rather than the customer lookup above, and persist the
        # Stripe customer + subscription ids onto the tenant.
        obj = event.get("data", {}).get("object", {})
        md = obj.get("metadata") or {}
        t_id = obj.get("client_reference_id") or md.get("tenant_id") or tenant_id
        cust = obj.get("customer")
        sub  = obj.get("subscription")
        plan = md.get("plan_tier")
        if t_id and (cust or sub):
            patch: dict[str, Any] = {"subscription_status": "active"}
            if cust: patch["stripe_customer_id"]     = cust
            if sub:  patch["stripe_subscription_id"] = sub
            if plan in _PLAN_CATALOG: patch["plan_tier"] = plan
            _sb_patch("tenants", {"id": f"eq.{t_id}"}, patch)
            tenant_id = t_id
            handled = True

    elif event_type == "customer.subscription.updated" and tenant_id:
        obj = event.get("data", {}).get("object", {})
        items = obj.get("items", {}).get("data", [])
        new_plan = None
        for it in items:
            md = (it.get("price", {}).get("metadata", {}) or {})
            lk = (it.get("price", {}).get("lookup_key") or "")
            for key, p in _PLAN_CATALOG.items():
                if p["lookup_key"] == lk or md.get("plan_key") == key:
                    new_plan = key; break
        if new_plan:
            _sb_patch("tenants", {"id": f"eq.{tenant_id}"}, {
                "plan_tier":           new_plan,
                "subscription_status": obj.get("status"),
            })
            handled = True

    elif event_type == "invoice.payment_failed" and tenant_id:
        try:
            from engine.autopilot.autopilot import _emit_alert
            # Find a property to attach the alert to
            props = _sb_get("properties", {"tenant_id": f"eq.{tenant_id}",
                                            "select": "id", "limit": "1"})
            if props:
                _emit_alert(
                    tenant_id, props[0]["id"], "competitor_drop",   # repurpose existing severity-warning bucket
                    "Stripe payment failed — please update payment method",
                    severity="critical",
                    metadata={"stripe_event_id": event_id},
                    dedup_key=f"stripe_payment_failed:{event_id}",
                )
                handled = True
        except Exception as exc:
            logger.warning("could not emit payment_failed alert: %s", exc)

    return {"status": "ok", "event_type": event_type, "event_id": event_id,
            "tenant_id": tenant_id, "handled": handled}


__all__ = ["setup_stripe_products", "price_id_for_tier",
           "create_checkout_session", "create_portal_session",
           "create_subscription", "cancel_subscription", "list_invoices",
           "process_webhook", "_PLAN_CATALOG", "CHECKOUT_TIERS"]
