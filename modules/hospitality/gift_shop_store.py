"""Gift Shop store for Bay Street Inn — categories, items, inventory, and sales.

Persists to config/gift_shop_store.json. Seeds a realistic boutique-inn retail
catalog on first load. Pure stdlib; safe to import from Flask routes.
"""
from __future__ import annotations

import json
import os
from typing import Any

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_STORE_PATH = os.path.join(_BASE, "config", "gift_shop_store.json")

FULFILLMENT = ["in-stock", "dropship", "consignment", "print-on-demand"]


def _seed() -> dict[str, Any]:
    def item(iid, name, desc, price, cost, ful, inv, reorder, supplier, sold, sold_last):
        return {"id": iid, "name": name, "description": desc, "price": price, "cost": cost,
                "fulfillment": ful, "inventory": inv, "reorder_point": reorder, "supplier": supplier,
                "units_sold_month": sold, "units_sold_last_month": sold_last}
    return {"categories": [
        {"id": "comphy", "name": "Comphy Bedding Collection", "emoji": "🛏️", "fulfillment": "dropship",
         "supplier": "Comphy Co.", "items": [
            item("comphy_sheets", "Signature Sheet Set", "Spa-soft microfiber sheet set, queen/king.", 189, 95, "dropship", 14, 6, "Comphy Co.", 9, 7),
            item("comphy_pillow", "Pillowcase Pair", "Matching luxe pillowcases.", 49, 22, "dropship", 30, 10, "Comphy Co.", 16, 12),
            item("comphy_duvet", "Duvet Cover", "Hotel-weight duvet cover.", 229, 118, "dropship", 8, 4, "Comphy Co.", 4, 5),
            item("comphy_robe", "Spa Robe", "The robe guests always ask about.", 119, 58, "dropship", 22, 8, "Comphy Co.", 13, 9),
        ]},
        {"id": "murano", "name": "Murano Glass by Gino Mazzuccato", "emoji": "🍷", "fulfillment": "consignment",
         "supplier": "Mazzuccato (Italy)", "items": [
            item("murano_vase", "Hand-Blown Vase", "Signed Murano art vase, imported from Venice.", 385, 231, "consignment", 5, 2, "Mazzuccato", 2, 1),
            item("murano_sculpture", "Glass Sculpture", "Limited-edition decorative sculpture.", 620, 372, "consignment", 3, 1, "Mazzuccato", 1, 2),
            item("murano_drinkset", "Drinking Glass Set", "Set of 6 Murano tumblers.", 295, 177, "dropship", 7, 3, "Mazzuccato", 3, 2),
            item("murano_piece", "Decorative Piece", "Assorted small decorative pieces.", 145, 87, "consignment", 12, 4, "Mazzuccato", 5, 4),
        ]},
        {"id": "local_artists", "name": "Local Beaufort Artists", "emoji": "🎨", "fulfillment": "consignment",
         "supplier": "Beaufort Artists Co-op", "items": [
            item("art_painting", "Lowcountry Painting", "Original marsh & waterfront paintings.", 450, 270, "consignment", 6, 2, "Local Co-op", 2, 3),
            item("art_photo", "Framed Photography", "Historic Beaufort photography prints.", 165, 99, "consignment", 10, 4, "Local Co-op", 6, 4),
            item("art_pottery", "Handmade Pottery", "Wheel-thrown coastal pottery.", 88, 53, "consignment", 15, 5, "Local Co-op", 8, 7),
            item("art_jewelry", "Sea Glass Jewelry", "Locally made sea-glass pieces.", 72, 43, "consignment", 20, 8, "Local Co-op", 11, 10),
        ]},
        {"id": "pantry", "name": "Lowcountry Pantry", "emoji": "🫙", "fulfillment": "in-stock",
         "supplier": "Regional purveyors", "items": [
            item("pantry_jam", "Sweetgrass Jam", "Small-batch local preserves.", 14, 6, "in-stock", 48, 20, "Lady's Island Preserves", 34, 28),
            item("pantry_hotsauce", "Lowcountry Hot Sauce", "Bottled local pepper sauce.", 11, 4, "in-stock", 60, 24, "Beaufort Pepper Co.", 29, 25),
            item("pantry_grits", "Stone-Ground Grits", "Sea Island heirloom grits.", 9, 4, "in-stock", 40, 16, "Geechie Boy Mill", 22, 24),
            item("pantry_pralines", "Sea Island Pralines", "Box of fresh pralines.", 16, 7, "in-stock", 35, 14, "Local Confectioner", 31, 26),
            item("pantry_soup", "She-Crab Soup Mix", "Lowcountry classic, dry mix.", 13, 6, "in-stock", 28, 12, "Charleston Specialty", 18, 15),
            item("pantry_honey", "Local Honey", "Raw Lowcountry wildflower honey.", 12, 5, "in-stock", 0, 12, "Beaufort Bee Co.", 0, 14),
        ]},
        {"id": "branded", "name": "Bay Street Inn Branded", "emoji": "🧢", "fulfillment": "print-on-demand",
         "supplier": "Printful / in-house", "items": [
            item("brand_cap", "Embroidered Cap", "Bay Street Inn logo cap.", 28, 11, "print-on-demand", 25, 10, "Printful", 12, 10),
            item("brand_mug", "Ceramic Mug", "River-view logo mug.", 18, 7, "in-stock", 40, 15, "In-house", 21, 18),
            item("brand_tote", "Canvas Tote", "Heavyweight branded tote bag.", 24, 9, "print-on-demand", 30, 12, "Printful", 15, 13),
            item("brand_robe", "Branded Robe", "Logo waffle robe.", 79, 38, "in-stock", 12, 5, "In-house", 6, 5),
            item("brand_candle", "Soy Candle", "Lowcountry-scented soy candle.", 26, 10, "in-stock", 35, 14, "Local Chandler", 19, 16),
        ]},
        {"id": "experience_kits", "name": "Inn Experience Kits", "emoji": "🎁", "fulfillment": "in-stock",
         "supplier": "Assembled in-house", "items": [
            item("kit_cocktail", "Cocktail Kit", "Lowcountry cocktail kit with recipes.", 65, 28, "in-stock", 18, 8, "In-house", 9, 6),
            item("kit_cooking", "Cooking Class Kit", "At-home Lowcountry cooking kit.", 95, 44, "in-stock", 10, 4, "In-house", 4, 5),
            item("kit_giftbox", "Curated Gift Box", "Mixed local-favorites gift box.", 120, 55, "in-stock", 14, 6, "In-house", 7, 8),
        ]},
    ]}


def _load() -> dict[str, Any]:
    try:
        with open(_STORE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = _seed()
        _save(data)
        return data


def _save(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
    with open(_STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _margin_pct(price, cost):
    return round((price - cost) / price * 100) if price else 0


def get_store() -> dict[str, Any]:
    """Full store with computed margins, sales, best-sellers, and slow-movers."""
    data = _load()
    all_items = []
    total_rev = total_margin = total_units = 0
    for cat in data["categories"]:
        cat_rev = cat_units = 0
        for it in cat["items"]:
            it["margin_pct"] = _margin_pct(it["price"], it["cost"])
            it["revenue_month"] = it["price"] * it["units_sold_month"]
            it["margin_month"] = (it["price"] - it["cost"]) * it["units_sold_month"]
            prev = it["units_sold_last_month"]
            it["trend_pct"] = round((it["units_sold_month"] - prev) / prev * 100) if prev else 0
            it["low_stock"] = it["inventory"] <= it["reorder_point"]
            it["category_id"] = cat["id"]
            it["category_name"] = cat["name"]
            cat_rev += it["revenue_month"]
            cat_units += it["units_sold_month"]
            total_margin += it["margin_month"]
            all_items.append(it)
        cat["revenue_month"] = cat_rev
        cat["units_month"] = cat_units
        cat["item_count"] = len(cat["items"])
        total_rev += cat_rev
        total_units += cat_units

    best_sellers = sorted(all_items, key=lambda i: i["revenue_month"], reverse=True)[:5]
    slow_movers = [i for i in all_items if i["units_sold_month"] == 0]
    low_stock = [i for i in all_items if i["low_stock"]]
    return {
        "categories": data["categories"],
        "summary": {
            "total_monthly_revenue": total_rev,
            "total_monthly_margin": total_margin,
            "total_units": total_units,
            "category_count": len(data["categories"]),
            "item_count": len(all_items),
        },
        "best_sellers": best_sellers,
        "slow_movers": slow_movers,
        "low_stock": low_stock,
        "fulfillment_types": FULFILLMENT,
    }


# ── CRUD ─────────────────────────────────────────────────────────────────────

def _slug(s):
    return "".join(c for c in s.lower().replace(" ", "_") if c.isalnum() or c == "_")[:32]


def add_category(name, emoji="🛍️", fulfillment="in-stock", supplier=""):
    data = _load()
    cid = _slug(name) or f"cat{len(data['categories'])}"
    if any(c["id"] == cid for c in data["categories"]):
        cid = f"{cid}_{len(data['categories'])}"
    data["categories"].append({"id": cid, "name": name, "emoji": emoji,
                               "fulfillment": fulfillment, "supplier": supplier, "items": []})
    _save(data)
    return cid


def update_category(cid, fields):
    data = _load()
    for c in data["categories"]:
        if c["id"] == cid:
            for k in ("name", "emoji", "fulfillment", "supplier"):
                if k in fields:
                    c[k] = fields[k]
            _save(data)
            return True
    return False


def delete_category(cid):
    data = _load()
    n = len(data["categories"])
    data["categories"] = [c for c in data["categories"] if c["id"] != cid]
    _save(data)
    return len(data["categories"]) < n


def add_item(cid, fields):
    data = _load()
    for c in data["categories"]:
        if c["id"] == cid:
            iid = _slug(fields.get("name", "item")) or f"item{len(c['items'])}"
            if any(i["id"] == iid for i in c["items"]):
                iid = f"{iid}_{len(c['items'])}"
            c["items"].append({
                "id": iid,
                "name": fields.get("name", "New Item"),
                "description": fields.get("description", ""),
                "price": float(fields.get("price", 0)),
                "cost": float(fields.get("cost", 0)),
                "fulfillment": fields.get("fulfillment", c.get("fulfillment", "in-stock")),
                "inventory": int(fields.get("inventory", 0)),
                "reorder_point": int(fields.get("reorder_point", 0)),
                "supplier": fields.get("supplier", c.get("supplier", "")),
                "units_sold_month": int(fields.get("units_sold_month", 0)),
                "units_sold_last_month": int(fields.get("units_sold_last_month", 0)),
            })
            _save(data)
            return iid
    return None


def update_item(iid, fields):
    data = _load()
    for c in data["categories"]:
        for it in c["items"]:
            if it["id"] == iid:
                for k in ("name", "description", "fulfillment", "supplier"):
                    if k in fields:
                        it[k] = fields[k]
                for k in ("price", "cost"):
                    if k in fields:
                        it[k] = float(fields[k])
                for k in ("inventory", "reorder_point", "units_sold_month", "units_sold_last_month"):
                    if k in fields:
                        it[k] = int(fields[k])
                _save(data)
                return True
    return False


def delete_item(iid):
    data = _load()
    removed = False
    for c in data["categories"]:
        before = len(c["items"])
        c["items"] = [i for i in c["items"] if i["id"] != iid]
        removed = removed or len(c["items"]) < before
    _save(data)
    return removed
