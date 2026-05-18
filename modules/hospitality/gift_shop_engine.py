"""
Gift Shop Engine — Estimates gift shop revenue + gross margin.
"""
from config.settings import GIFT_SHOP_CATEGORIES


class GiftShopEngine:

    def categories(self) -> list:
        out = []
        for c in GIFT_SHOP_CATEGORIES:
            margin_dollars = int(c["est_monthly_rev"] * c.get("margin", 0.5))
            out.append({**c, "est_margin_dollars": margin_dollars})
        return out

    def total_monthly_revenue(self) -> int:
        return sum(c["est_monthly_rev"] for c in GIFT_SHOP_CATEGORIES)

    def total_monthly_margin(self) -> int:
        return sum(int(c["est_monthly_rev"] * c.get("margin", 0.5))
                   for c in GIFT_SHOP_CATEGORIES)
