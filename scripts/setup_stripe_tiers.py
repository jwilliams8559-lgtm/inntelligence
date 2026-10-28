#!/usr/bin/env python3
"""
Idempotently create the 4 INNtelligence tier products + monthly recurring
prices in Stripe, and print their product/price IDs. Works against TEST
(sk_test_) or LIVE (sk_live_) depending on the STRIPE_SECRET_KEY in the
environment. The key is read from the env and never written to disk.

Live run (key passed inline, NOT persisted to .env):
    STRIPE_SECRET_KEY=sk_live_xxx ./venv/bin/python scripts/setup_stripe_tiers.py

Idempotency model (mirrors engine/billing.py):
  - Each price carries a stable, unique `lookup_key`.
  - On each run we look up the price via Price.list(lookup_keys=[...]), which
    is STRONGLY consistent (read-after-write safe).
      * If the price exists, we reuse it AND derive the product from
        price.product — so the product is never recreated.
      * If the amount/shape drifted, we create a new price on the SAME product
        and move the lookup_key over with transfer_lookup_key=True (Stripe
        prices are immutable; the old price is just unlinked from the key).
      * If no price exists, we create product + price together.

NOTE: we deliberately do NOT use Product.search / Price.search for the
lookup — the Search API is eventually consistent (indexing lags up to ~1 min),
which caused duplicate products on fast re-runs. lookup_keys is the anchor.

Re-running this script must NOT create duplicates.

Usage:
    ./venv/bin/python scripts/setup_stripe_tiers.py          # create/sync
    ./venv/bin/python scripts/setup_stripe_tiers.py --json   # machine output
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import stripe
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# tier_key -> definition. lookup_key is the idempotency anchor for the price.
TIERS: list[dict] = [
    {"tier_key": "inn",        "env": "STRIPE_PRICE_INN",
     "name": "INNtelligence Inn",        "amount_cents": 14900,
     "lookup_key": "inntelligence_inn_monthly"},
    {"tier_key": "boutique",   "env": "STRIPE_PRICE_BOUTIQUE",
     "name": "INNtelligence Boutique",   "amount_cents": 39900,
     "lookup_key": "inntelligence_boutique_monthly"},
    {"tier_key": "signature",  "env": "STRIPE_PRICE_SIGNATURE",
     "name": "INNtelligence Signature",  "amount_cents": 79900,
     "lookup_key": "inntelligence_signature_monthly"},
    {"tier_key": "collection", "env": "STRIPE_PRICE_COLLECTION",
     "name": "INNtelligence Collection", "amount_cents": 149900,
     "lookup_key": "inntelligence_collection_monthly"},
]
CURRENCY = "usd"
INTERVAL = "month"


def _fail(msg: str) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _ensure_tier(tier: dict):
    """
    Returns (product, product_created, price, price_created).

    Anchored on the price lookup_key (strongly consistent). The product is
    derived from an existing price, so it is only ever created alongside a
    brand-new price — re-runs never spawn duplicate products.
    """
    existing = stripe.Price.list(lookup_keys=[tier["lookup_key"]], limit=1)
    if existing.data:
        price = existing.data[0]
        product = stripe.Product.retrieve(price.product)
        shape_ok = (
            price.unit_amount == tier["amount_cents"]
            and price.currency == CURRENCY
            and price.recurring
            and price.recurring.interval == INTERVAL
            and price.active
        )
        if shape_ok:
            return product, False, price, False
        # Amount/shape drifted: new price on the SAME product, move the key.
        price = stripe.Price.create(
            product=product.id,
            unit_amount=tier["amount_cents"],
            currency=CURRENCY,
            recurring={"interval": INTERVAL},
            lookup_key=tier["lookup_key"],
            transfer_lookup_key=True,
        )
        return product, False, price, True

    # Nothing exists yet: create product + price together.
    product = stripe.Product.create(
        name=tier["name"],
        metadata={"tier_key": tier["tier_key"]},
    )
    price = stripe.Price.create(
        product=product.id,
        unit_amount=tier["amount_cents"],
        currency=CURRENCY,
        recurring={"interval": INTERVAL},
        lookup_key=tier["lookup_key"],
    )
    return product, True, price, True


def main() -> None:
    as_json = "--json" in sys.argv

    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        _fail("STRIPE_SECRET_KEY not set in environment/.env")
    # Accept TEST (sk_test_) or LIVE (sk_live_) secret keys only — never a
    # publishable/placeholder key. The key is read from the environment and is
    # never written to disk by this script.
    if key.startswith("sk_test_"):
        mode = "TEST"
    elif key.startswith("sk_live_"):
        mode = "LIVE"
    else:
        _fail(f"Refusing to run: STRIPE_SECRET_KEY is not a secret key "
              f"(starts with {key[:8]!r}, expected 'sk_test_' or 'sk_live_').")
    stripe.api_key = key

    out: dict[str, dict] = {}
    for tier in TIERS:
        prod, prod_created, price, price_created = _ensure_tier(tier)
        out[tier["env"]] = {
            "tier_key":    tier["tier_key"],
            "name":        tier["name"],
            "amount_usd":  tier["amount_cents"] / 100,
            "product_id":  prod.id,
            "price_id":    price.id,
            "lookup_key":  tier["lookup_key"],
            "product_created": prod_created,
            "price_created":   price_created,
        }

    if as_json:
        print(json.dumps({"mode": mode, "tiers": out}, indent=2))
        return

    print(f"Stripe {mode} mode — INNtelligence tiers\n" + "=" * 64)
    for env, v in out.items():
        pflag = "created" if v["product_created"] else "reused "
        rflag = "created" if v["price_created"] else "reused "
        print(f"{v['name']:<26} ${v['amount_usd']:>8,.2f}/mo")
        print(f"  product  [{pflag}] {v['product_id']}")
        print(f"  price    [{rflag}] {v['price_id']}   (lookup: {v['lookup_key']})")
        print(f"  -> {env}={v['price_id']}")
    print("=" * 64)


if __name__ == "__main__":
    main()
