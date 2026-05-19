"""
Package Intelligence Engine — The Gracious Collection
National package database + competitive benchmarking +
AI-powered package recommendation for any boutique inn.
"""
from __future__ import annotations

import hashlib
from typing import Optional


# ── National Package Master List ──────────────────────────────────────
# Top 20 packages offered by boutique inns nationally.
# Ranked by: prevalence (how many inns offer it), avg revenue lift,
# guest satisfaction impact, and operational complexity.
# Sources: TripAdvisor package analysis, Booking.com add-ons,
# direct inn websites, PAII (Professional Association of Innkeepers).

NATIONAL_PACKAGES = [
    {
        "id": "romance_package", "rank": 1,
        "name": "Romance / Couples Package",
        "prevalence_pct": 78,
        "category": "Romance & Celebration",
        "icon": "💑",
        "typical_components": [
            "Fresh flower arrangement on arrival",
            "Bottle of sparkling wine or champagne",
            "Chocolates or strawberries",
            "Rose petal turndown service",
            "Late checkout (when available)",
        ],
        "national_avg_upsell": 85, "national_range": (55, 145),
        "national_take_rate": 0.22,
        "operational_complexity": "low",
        "lead_time_days": 1, "seasonality": "year_round",
        "best_room_types": ["premium", "waterfront", "suite"],
        "competitive_notes": "Offered by 78% of direct boutique competitors. "
                             "Pricing variance is high — differentiate on quality "
                             "of flowers and wine tier, not just price.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "anniversary_celebration", "rank": 2,
        "name": "Anniversary Celebration Package",
        "prevalence_pct": 71,
        "category": "Romance & Celebration",
        "icon": "🥂",
        "typical_components": [
            "Custom anniversary card from innkeeper",
            "Champagne or prosecco on arrival",
            "Fresh floral arrangement",
            "Special anniversary dessert",
            "Keepsake photo frame",
        ],
        "national_avg_upsell": 75, "national_range": (50, 125),
        "national_take_rate": 0.18,
        "operational_complexity": "low",
        "lead_time_days": 2, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Often bundled with romance package — consider "
                             "offering as separate add-on OR as romance package upgrade.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "private_dining", "rank": 3,
        "name": "Private In-Room Dining Experience",
        "prevalence_pct": 52,
        "category": "Food & Beverage",
        "icon": "🍽️",
        "typical_components": [
            "Multi-course dinner served in room or on private balcony",
            "Local/regional menu curated by innkeeper",
            "Wine pairing included",
            "Personal server for the evening",
        ],
        "national_avg_upsell": 145, "national_range": (95, 280),
        "national_take_rate": 0.12,
        "operational_complexity": "high",
        "lead_time_days": 3, "seasonality": "year_round",
        "best_room_types": ["premium", "waterfront", "suite", "balcony"],
        "competitive_notes": "High revenue, lower take rate. Requires kitchen "
                             "partnership or caterer. Massive differentiator where "
                             "local restaurant scene is strong.",
        "revenue_model": "per_person",
    },
    {
        "id": "spa_massage", "rank": 4,
        "name": "In-Room Spa / Massage Experience",
        "prevalence_pct": 48,
        "category": "Wellness",
        "icon": "💆",
        "typical_components": [
            "60 or 90-minute couples massage in room",
            "Licensed massage therapist comes to property",
            "Aromatherapy oils and supplies included",
            "Optional: facial add-on for additional fee",
        ],
        "national_avg_upsell": 185, "national_range": (120, 320),
        "national_take_rate": 0.16,
        "operational_complexity": "medium",
        "lead_time_days": 2, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Highest per-booking revenue of any package nationally. "
                             "Requires reliable licensed therapist partnership. "
                             "90-min couples format generates 2x revenue vs 60-min solo.",
        "revenue_model": "per_person",
    },
    {
        "id": "adventure_outdoor", "rank": 5,
        "name": "Local Adventure / Outdoor Experience",
        "prevalence_pct": 45,
        "category": "Experience & Activities",
        "icon": "🚣",
        "typical_components": [
            "Guided or self-guided outdoor activity (kayak/canoe/bike/hike)",
            "Packed picnic lunch with local provisions",
            "Trail map or water route guide",
            "Equipment rental included",
        ],
        "national_avg_upsell": 95, "national_range": (45, 185),
        "national_take_rate": 0.20,
        "operational_complexity": "medium",
        "lead_time_days": 1, "seasonality": "seasonal",
        "seasonality_months": [4, 5, 6, 7, 8, 9, 10],
        "best_room_types": ["all"],
        "competitive_notes": "Extremely location-dependent. Properties near water, "
                             "mountains, or trails see 2-3x national avg take rate. "
                             "Beaufort/Lowcountry kayak/shrimping/birding packages "
                             "test very well in coastal markets.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "private_breakfast", "rank": 6,
        "name": "Private Breakfast in Bed or on Porch",
        "prevalence_pct": 44,
        "category": "Food & Beverage",
        "icon": "☕",
        "typical_components": [
            "Full breakfast delivered to room or private porch",
            "Freshly squeezed juice and coffee/tea",
            "Local pastries and fruit",
            "Choice of hot entree",
        ],
        "national_avg_upsell": 42, "national_range": (25, 75),
        "national_take_rate": 0.28,
        "operational_complexity": "low",
        "lead_time_days": 0, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Highest take rate of any package — nearly 1 in 3 guests. "
                             "Low price point means revenue adds up through volume. "
                             "Easy to operationalize if inn already serves breakfast.",
        "revenue_model": "per_person",
    },
    {
        "id": "wine_charcuterie", "rank": 7,
        "name": "Welcome Wine & Charcuterie Board",
        "prevalence_pct": 41,
        "category": "Food & Beverage",
        "icon": "🍷",
        "typical_components": [
            "Curated regional wine selection (1 bottle)",
            "Artisan charcuterie board with local cheeses and meats",
            "Fresh bread and accompaniments",
            "Tasting notes card",
        ],
        "national_avg_upsell": 68, "national_range": (45, 115),
        "national_take_rate": 0.24,
        "operational_complexity": "low",
        "lead_time_days": 1, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Trending strongly post-pandemic. Instagrammable "
                             "presentation drives organic social media for the inn. "
                             "Local sourcing story elevates perceived value significantly.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "sunset_boat_tour", "rank": 8,
        "name": "Private Sunset Boat / Water Tour",
        "prevalence_pct": 22,
        "category": "Experience & Activities",
        "icon": "⛵",
        "typical_components": [
            "2-hour private chartered boat tour at sunset",
            "Captain guide with local knowledge",
            "Champagne or beer on board",
            "Wildlife viewing (dolphins, birds) in coastal markets",
        ],
        "national_avg_upsell": 195, "national_range": (125, 395),
        "national_take_rate": 0.14,
        "operational_complexity": "high",
        "lead_time_days": 3, "seasonality": "seasonal",
        "seasonality_months": [4, 5, 6, 7, 8, 9, 10],
        "best_room_types": ["all"],
        "competitive_notes": "Only relevant for waterfront/coastal/lake properties. "
                             "Highest dollar-per-booking value in experience category. "
                             "Requires reliable boat charter partnership.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "historic_cultural_tour", "rank": 9,
        "name": "Historic / Cultural Guided Tour",
        "prevalence_pct": 31,
        "category": "Experience & Activities",
        "icon": "🏛️",
        "typical_components": [
            "1-2 hour guided walking or driving tour of historic area",
            "Certified local guide with expert knowledge",
            "Historical notes/map keepsake",
            "Optional: cocktail or refreshment stop included",
        ],
        "national_avg_upsell": 78, "national_range": (45, 145),
        "national_take_rate": 0.17,
        "operational_complexity": "medium",
        "lead_time_days": 2, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Extremely strong in historic districts — Beaufort SC, "
                             "Savannah GA, Charleston SC, etc. Gullah-Geechee cultural "
                             "tours in Beaufort market are highly differentiated "
                             "and generate significant press.",
        "revenue_model": "per_person",
    },
    {
        "id": "honeymoon_package", "rank": 10,
        "name": "Honeymoon / Newlywed Package",
        "prevalence_pct": 63,
        "category": "Romance & Celebration",
        "icon": "💍",
        "typical_components": [
            "Champagne and chocolate-covered strawberries",
            "Rose petal bed turndown",
            "Complimentary room upgrade (when available)",
            "Late checkout",
            "Wedding night card from innkeeper",
            "Optional: couples spa add-on",
        ],
        "national_avg_upsell": 110, "national_range": (65, 195),
        "national_take_rate": 0.08,
        "operational_complexity": "low",
        "lead_time_days": 3, "seasonality": "year_round",
        "best_room_types": ["premium", "suite", "cottage"],
        "competitive_notes": "Lower take rate by definition (only newlyweds qualify) "
                             "but very high guest satisfaction. Often generates "
                             "the best reviews the inn receives.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "cooking_class", "rank": 11,
        "name": "Local Cooking Class / Food Experience",
        "prevalence_pct": 19,
        "category": "Food & Beverage",
        "icon": "👨‍🍳",
        "typical_components": [
            "2-hour hands-on cooking class with local chef",
            "Regional cuisine focus (Lowcountry, Cajun, etc.)",
            "Ingredients provided, recipes to take home",
            "Dinner from what you cooked",
        ],
        "national_avg_upsell": 145, "national_range": (85, 245),
        "national_take_rate": 0.09,
        "operational_complexity": "high",
        "lead_time_days": 5, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Low prevalence = strong differentiator where offered. "
                             "Strong fit for Lowcountry/Southern cuisine markets. "
                             "Requires consistent chef partner.",
        "revenue_model": "per_person",
    },
    {
        "id": "pet_friendly", "rank": 12,
        "name": "Pet Welcome / Pet-Friendly Package",
        "prevalence_pct": 38,
        "category": "Lifestyle",
        "icon": "🐾",
        "typical_components": [
            "Pet welcome kit (bed, food/water bowls, treats, toy)",
            "Local trail map with pet-friendly routes",
            "Pet fee waived or reduced",
            "Cleanup supplies provided",
        ],
        "national_avg_upsell": 45, "national_range": (25, 85),
        "national_take_rate": 0.22,
        "operational_complexity": "low",
        "lead_time_days": 0, "seasonality": "year_round",
        "best_room_types": ["garden", "cottage", "ground_floor"],
        "competitive_notes": "Pet travel is growing 12% annually. Properties that "
                             "market pet-friendliness see higher weekday occupancy. "
                             "Must designate specific rooms to manage wear.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "wellness_retreat", "rank": 13,
        "name": "Wellness / Self-Care Retreat Package",
        "prevalence_pct": 28,
        "category": "Wellness",
        "icon": "🧘",
        "typical_components": [
            "Morning yoga session (private or group)",
            "Healthy breakfast with superfood options",
            "Guided meditation or sound bath",
            "Aromatherapy bath salts and candles in room",
        ],
        "national_avg_upsell": 125, "national_range": (75, 225),
        "national_take_rate": 0.13,
        "operational_complexity": "medium",
        "lead_time_days": 2, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Fastest growing package category nationally. "
                             "Especially strong for Thursday-Sunday bookings. "
                             "Yoga/wellness instructor partnership required.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "photography_session", "rank": 14,
        "name": "Professional Photography Session",
        "prevalence_pct": 17,
        "category": "Experience & Activities",
        "icon": "📸",
        "typical_components": [
            "1-hour session with local professional photographer",
            "Property grounds + surrounding area shoot",
            "25-50 edited digital images delivered",
            "Perfect for couples/honeymoon/anniversary",
        ],
        "national_avg_upsell": 275, "national_range": (195, 450),
        "national_take_rate": 0.07,
        "operational_complexity": "medium",
        "lead_time_days": 5, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Low prevalence = strong differentiator. Instagrammable "
                             "properties see stronger results. Couples and honeymoon "
                             "guests are primary buyers.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "early_checkin_late_checkout", "rank": 15,
        "name": "Flexible Check-In / Check-Out",
        "prevalence_pct": 67,
        "category": "Convenience",
        "icon": "⏰",
        "typical_components": [
            "Early check-in from 11am (vs standard 3pm)",
            "Late check-out until 1pm or 2pm (vs standard 11am)",
            "Luggage storage if room not ready",
        ],
        "national_avg_upsell": 38, "national_range": (20, 65),
        "national_take_rate": 0.31,
        "operational_complexity": "low",
        "lead_time_days": 0, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Highest take rate of any add-on — nearly 1 in 3 guests. "
                             "Very low cost to deliver. Can be offered free as upgrade "
                             "for VIP/returning guests to drive loyalty.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "local_wine_trail", "rank": 16,
        "name": "Local Winery / Distillery Tour Package",
        "prevalence_pct": 24,
        "category": "Experience & Activities",
        "icon": "🍇",
        "typical_components": [
            "Curated itinerary for 2-3 local wineries or distilleries",
            "Transportation arranged or map provided",
            "Tasting credits included",
            "Bottle of local wine in room on return",
        ],
        "national_avg_upsell": 88, "national_range": (55, 165),
        "national_take_rate": 0.16,
        "operational_complexity": "low",
        "lead_time_days": 1, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Strong in wine country and craft spirits markets. "
                             "SC muscadine wine + Firefly Distillery (SC-based) "
                             "creates authentic Lowcountry story.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "celebration_decoration", "rank": 17,
        "name": "Room Celebration Decoration Package",
        "prevalence_pct": 42,
        "category": "Romance & Celebration",
        "icon": "🎉",
        "typical_components": [
            "Balloon arrangement in room color theme",
            "Birthday / anniversary / milestone banner",
            "Confetti or rose petals",
            "Custom cake or cupcakes from local bakery",
        ],
        "national_avg_upsell": 95, "national_range": (55, 185),
        "national_take_rate": 0.14,
        "operational_complexity": "medium",
        "lead_time_days": 3, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Strong secondary to romance/anniversary packages. "
                             "Local bakery partnership elevates experience significantly. "
                             "Seasonal add: holiday-themed decorations in Nov-Dec.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "stargazing_package", "rank": 18,
        "name": "Stargazing / Night Sky Experience",
        "prevalence_pct": 12,
        "category": "Experience & Activities",
        "icon": "⭐",
        "typical_components": [
            "Telescope or binoculars for guest use",
            "Star map of current night sky",
            "Blankets and hot cocoa provided",
            "Outdoor fire pit or seating area access",
        ],
        "national_avg_upsell": 55, "national_range": (35, 95),
        "national_take_rate": 0.18,
        "operational_complexity": "low",
        "lead_time_days": 0, "seasonality": "year_round",
        "best_room_types": ["all"],
        "competitive_notes": "Low prevalence = strong differentiator where offered. "
                             "Best for rural properties with dark skies. "
                             "Low operational cost, high guest delight.",
        "revenue_model": "fixed_add_on",
    },
    {
        "id": "fishing_trip", "rank": 19,
        "name": "Guided Fishing Trip",
        "prevalence_pct": 16,
        "category": "Experience & Activities",
        "icon": "🎣",
        "typical_components": [
            "Half-day guided fishing with licensed captain",
            "All equipment provided",
            "Fishing license included",
            "Optional: inn will cook your catch for dinner",
        ],
        "national_avg_upsell": 175, "national_range": (95, 350),
        "national_take_rate": 0.11,
        "operational_complexity": "medium",
        "lead_time_days": 3, "seasonality": "seasonal",
        "seasonality_months": [3, 4, 5, 6, 7, 8, 9, 10],
        "best_room_types": ["all"],
        "competitive_notes": "Strong coastal and lake markets. Beaufort/Lowcountry "
                             "shrimping and redfish charter scene is nationally known. "
                             "Cook-your-catch element is an extraordinary differentiator.",
        "revenue_model": "per_person",
    },
    {
        "id": "bike_rental", "rank": 20,
        "name": "Bicycle Rental / Cycling Package",
        "prevalence_pct": 33,
        "category": "Experience & Activities",
        "icon": "🚲",
        "typical_components": [
            "Complimentary or discounted bike rental for duration of stay",
            "Local cycling route map",
            "Lock and helmet provided",
            "Optional: guided group bike tour add-on",
        ],
        "national_avg_upsell": 35, "national_range": (15, 75),
        "national_take_rate": 0.26,
        "operational_complexity": "low",
        "lead_time_days": 0, "seasonality": "seasonal",
        "seasonality_months": [3, 4, 5, 6, 7, 8, 9, 10],
        "best_room_types": ["all"],
        "competitive_notes": "Third highest take rate nationally. Very low cost to "
                             "deliver if inn owns bikes. Downtown/walkable properties "
                             "see highest uptake. Beaufort's flat terrain and waterfront "
                             "path is ideal for this.",
        "revenue_model": "fixed_add_on",
    },
]

# Coastal markets used by the location-fit bonus in fit scoring.
_COASTAL_MARKETS = {
    "beaufort", "hilton head", "savannah", "charleston",
    "myrtle beach", "outer banks", "tybee island",
    "amelia island", "st augustine", "key west",
}


class PackageIntelligenceEngine:
    """
    Analyzes national package data + local competitor offerings
    to recommend the optimal 5–10 packages for a specific property.
    """

    def __init__(self, property_config: dict, competitor_data: list):
        self.property    = property_config
        self.competitors = competitor_data
        self.city        = property_config.get("city", "")
        self.state       = property_config.get("state", "")

    # ── Public API ──────────────────────────────────────────────────

    def get_all_national_packages(self) -> list:
        """Return all 20 national packages with computed per-property fields."""
        total_rooms      = self.property.get("total_rooms", 14)
        avg_occ          = 0.75
        nights_per_month = 30

        result = []
        for pkg in NATIONAL_PACKAGES:
            enriched = dict(pkg)
            est_monthly = int(
                total_rooms * avg_occ * nights_per_month
                * pkg["national_take_rate"]
                * pkg["national_avg_upsell"]
            )
            enriched["est_monthly_rev"]   = est_monthly
            enriched["est_monthly_label"] = (
                f"Est. ${est_monthly:,}/mo @ "
                f"{int(pkg['national_take_rate']*100)}% take rate"
            )
            lo, hi = pkg["national_range"]
            enriched["price_range_label"] = f"${lo}–${hi} nationally"

            enriched["competitors_offering"]  = self._competitors_offering(pkg["id"])
            enriched["competitor_avg_price"]  = self._competitor_avg_price(pkg["id"])
            result.append(enriched)
        return result

    def get_top_20_ranked(self) -> list:
        """All 20 national packages ranked by fit score for this property."""
        packages   = self.get_all_national_packages()
        is_coastal = self.city.lower().strip() in _COASTAL_MARKETS

        for pkg in packages:
            score = 0.0
            # Prevalence (0–30 pts)
            score += pkg["prevalence_pct"] * 0.30

            # Revenue potential (0–40 pts), normalized to $5k/mo ceiling
            score += min(40, (pkg["est_monthly_rev"] / 5000) * 40)

            # Operational complexity (0–15 pts)
            complexity_pts = {"low": 15, "medium": 8, "high": 0}
            score += complexity_pts.get(pkg["operational_complexity"], 8)

            # Coastal-fit bonus (0–10 pts)
            coastal_packages = {
                "sunset_boat_tour", "adventure_outdoor",
                "fishing_trip", "bike_rental", "historic_cultural_tour",
            }
            if is_coastal and pkg["id"] in coastal_packages:
                score += 10

            # Competitive-gap bonus (0–5 pts) when <30% of comps offer it
            offering_pct = len(pkg["competitors_offering"]) / max(1, len(self.competitors))
            if offering_pct < 0.30:
                score += 5

            pkg["fit_score"] = round(score, 1)
            pkg["fit_label"] = (
                "Excellent fit" if score >= 65
                else "Strong fit"  if score >= 50
                else "Good fit"    if score >= 35
                else "Consider"
            )

        return sorted(packages, key=lambda x: x["fit_score"], reverse=True)

    def recommend_packages(self, selected_ids: Optional[list] = None) -> list:
        """
        Return 5–10 recommended packages with competitive pricing.
        If *selected_ids* is None, auto-recommend by fit + category balance.
        """
        all_pkgs = {p["id"]: p for p in self.get_top_20_ranked()}

        if selected_ids is None:
            selected = self._auto_select()
        else:
            selected = [all_pkgs[pid] for pid in selected_ids if pid in all_pkgs]

        selected = selected[:10]
        if len(selected) < 5:
            for pkg in self.get_top_20_ranked():
                if pkg["id"] not in [s["id"] for s in selected]:
                    selected.append(pkg)
                if len(selected) >= 5:
                    break

        for pkg in selected:
            pkg["recommended_price"] = self._recommend_price(pkg)
            pkg["pricing_rationale"] = self._pricing_rationale(pkg)
        return selected

    # ── Private helpers ─────────────────────────────────────────────

    def _auto_select(self) -> list:
        """Pick best packages with category diversity (max 2 per high-value cat)."""
        ranked = self.get_top_20_ranked()
        selected: list = []
        categories_used: dict = {}
        for pkg in ranked:
            cat = pkg["category"]
            count_in_cat = categories_used.get(cat, 0)
            max_per_cat = 2 if cat in ("Romance & Celebration", "Food & Beverage") else 1
            if count_in_cat < max_per_cat:
                selected.append(pkg)
                categories_used[cat] = count_in_cat + 1
            if len(selected) >= 8:
                break
        return selected

    def _competitors_offering(self, package_id: str) -> list:
        """
        Return list of competitor names that offer this package.
        Production: scrape competitor websites + OTA package listings.
        Demo: deterministic synthetic mapping seeded by (comp_name, package_id)
              against national prevalence.
        """
        pkg = next((p for p in NATIONAL_PACKAGES if p["id"] == package_id), None)
        if not pkg:
            return []
        prevalence = pkg["prevalence_pct"] / 100
        offering: list = []
        for comp in self.competitors:
            seed = int(hashlib.md5(
                f"{comp.get('name','')}{package_id}".encode()
            ).hexdigest(), 16) % 100
            if seed < (prevalence * 100):
                offering.append(comp.get("name", "Unknown"))
        return offering

    def _competitor_avg_price(self, package_id: str) -> Optional[float]:
        """Average competitor price, with a Southeast regional discount factor."""
        pkg = next((p for p in NATIONAL_PACKAGES if p["id"] == package_id), None)
        if not pkg:
            return None
        lo, hi = pkg["national_range"]
        regional_factor = 0.92  # Beaufort/Southeast slightly below national avg
        return round((lo + hi) / 2 * regional_factor, 0)

    def _recommend_price(self, pkg: dict) -> int:
        """Price at or slightly above competitor average; never below floor."""
        comp_avg  = pkg.get("competitor_avg_price") or pkg["national_avg_upsell"]
        offering  = len(pkg["competitors_offering"])
        total     = max(1, len(self.competitors))
        adoption  = offering / total

        if adoption < 0.25:
            base = pkg["national_avg_upsell"]    # differentiated → price at national
        elif adoption < 0.50:
            base = comp_avg * 1.05               # +5% over local
        else:
            base = comp_avg                       # price-competitive

        if base < 50:
            return int(round(base / 5) * 5)
        elif base < 100:
            return int(round(base / 10) * 10)
        else:
            return int(round(base / 25) * 25)

    def _pricing_rationale(self, pkg: dict) -> str:
        comp_names = pkg["competitors_offering"][:2]
        comp_count = len(pkg["competitors_offering"])
        price      = pkg.get("recommended_price") or self._recommend_price(pkg)
        comp_avg   = pkg.get("competitor_avg_price") or pkg["national_avg_upsell"]

        if comp_count == 0:
            return (f"None of your tracked competitors offer this package — "
                    f"positioning at ${price} establishes you as the market "
                    f"leader. National average is ${int(pkg['national_avg_upsell'])}.")
        if comp_count <= 2:
            names = " and ".join(comp_names) if comp_names else "one competitor"
            verb = "offer" if len(comp_names) != 1 else "offers"
            return (f"Only {names} {verb} this locally at around ${int(comp_avg)}. "
                    f"At ${price} you match market pricing with stronger presentation.")
        return (f"{comp_count} competitors offer this at an average of ${int(comp_avg)}. "
                f"At ${price} you are positioned competitively. "
                f"Differentiate on quality of execution, not price.")


__all__ = ["NATIONAL_PACKAGES", "PackageIntelligenceEngine"]
