"""
Packages Engine — Estimates revenue from guest add-on packages.
Drives the GUEST PACKAGES section of the dashboard.
"""
from config.settings import ACTIVE_PROPERTY, GUEST_PACKAGES


class PackagesEngine:

    def list_with_revenue(self, occ: float | None = None,
                          nights_per_month: int = 30) -> list:
        occ = occ if occ is not None else ACTIVE_PROPERTY["target_occupancy_min"]
        total_rooms = ACTIVE_PROPERTY["total_rooms"]
        out = []
        for pkg in GUEST_PACKAGES:
            eligible = len(pkg["room_restriction"]) if pkg.get("room_restriction") else total_rooms
            est = int(eligible * occ * nights_per_month * pkg["take_rate"] * pkg["upsell_price"])
            out.append({
                **pkg,
                "est_monthly_rev":     est,
                "est_monthly_label":   f"Est. ${est:,}/mo @ {int(pkg['take_rate'] * 100)}% take rate",
                "eligible_rooms":      eligible,
                "room_restriction_label": (
                    f"⚠ {', '.join(pkg['room_restriction'][:2])}"
                    f"{'...' if pkg['room_restriction'] and len(pkg['room_restriction']) > 2 else ''}"
                    if pkg.get("room_restriction") else ""
                ),
            })
        return out

    def total_active_monthly_revenue(self, **kwargs) -> int:
        return sum(p["est_monthly_rev"] for p in self.list_with_revenue(**kwargs) if p["active"])
