import os
from dataclasses import dataclass, field
from typing import Dict, List, Any

from dotenv import load_dotenv

load_dotenv()


@dataclass
class TenantConfig:
    tenant_id: str
    tenant_name: str
    vertical: str  # 'telecom' | 'hospitality'
    features: List[str]
    model_params: Dict[str, Any]


TENANTS: Dict[str, TenantConfig] = {
    "telecom_001": TenantConfig(
        tenant_id="telecom_001",
        tenant_name="TelecomCorp",
        vertical="telecom",
        features=[
            "usage_minutes",
            "data_gb",
            "roaming_days",
            "contract_months",
            "churn_score",
        ],
        model_params={
            "model_type": "gradient_boost",
            "n_estimators": 200,
            "learning_rate": 0.05,
            "price_floor": 9.99,
            "price_ceiling": 299.99,
        },
    ),
    "hospitality_001": TenantConfig(
        tenant_id="hospitality_001",
        tenant_name="LuxuryHotels",
        vertical="hospitality",
        features=[
            "occupancy_rate",
            "lead_time_days",
            "season_index",
            "competitor_rate",
            "demand_score",
        ],
        model_params={
            "model_type": "random_forest",
            "n_estimators": 150,
            "learning_rate": 0.08,
            "price_floor": 49.99,
            "price_ceiling": 2999.99,
        },
    ),
}

VERTICAL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "telecom": {
        "data_sources": ["usage_db", "crm_db", "competitor_api"],
        "refresh_interval_hours": 24,
        "pricing_strategy": "value_based",
    },
    "hospitality": {
        "data_sources": ["pms_db", "channel_manager", "weather_api", "events_api"],
        "refresh_interval_hours": 6,
        "pricing_strategy": "dynamic",
    },
}

# Filesystem paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
DATA_EXPORTS_DIR = os.path.join(BASE_DIR, "data", "exports")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Nightly scheduler
NIGHTLY_JOB_HOUR = 2
NIGHTLY_JOB_MINUTE = 0

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_ROTATION = "midnight"
LOG_BACKUP_COUNT = 30


# ════════════════════════════════════════════════════════════════════════════
# The Gracious Collection — single-property Flask dashboard constants (v2)
# Added 2026-05-18 alongside the legacy TenantConfig schema above.
# ════════════════════════════════════════════════════════════════════════════

ACTIVE_PROPERTY = {
    "name": "Anchorage 1770 Inn",
    "address": "1103 Bay Street",
    "city": "Beaufort",
    "state": "SC",
    "zip": "29902",
    "timezone": "America/New_York",
    "total_rooms": 14,
    "target_occupancy_min": 0.70,
    "target_occupancy_max": 0.85,
    "max_discount_floor_pct": 0.15,
    "pms": "cloudbeds",
    "plan_tier": "professional",
}

ROOM_TYPES = [
    {"id": "private_cottage", "name": "Private Cottage", "icon": "🏡", "count": 1, "base": 489, "min": 350, "max": 695, "category": "premium"},
    {"id": "waterfront_201",  "name": "Waterfront 201",  "icon": "🌊", "count": 1, "base": 419, "min": 295, "max": 695, "category": "waterfront"},
    {"id": "waterfront_202",  "name": "Waterfront 202",  "icon": "🌊", "count": 1, "base": 419, "min": 295, "max": 695, "category": "waterfront"},
    {"id": "waterfront_203",  "name": "Waterfront 203",  "icon": "🌊", "count": 1, "base": 419, "min": 295, "max": 695, "category": "waterfront"},
    {"id": "waterfront_204",  "name": "Waterfront 204",  "icon": "🌊", "count": 1, "base": 429, "min": 295, "max": 695, "category": "waterfront"},
    {"id": "waterview_301",   "name": "Water View 301",  "icon": "💧", "count": 1, "base": 339, "min": 265, "max": 595, "category": "waterview"},
    {"id": "waterview_302",   "name": "Water View 302",  "icon": "💧", "count": 1, "base": 339, "min": 265, "max": 595, "category": "waterview"},
    {"id": "waterview_303",   "name": "Water View 303",  "icon": "💧", "count": 1, "base": 339, "min": 265, "max": 595, "category": "waterview"},
    {"id": "waterview_304",   "name": "Water View 304",  "icon": "💧", "count": 1, "base": 259, "min": 225, "max": 495, "category": "waterview"},
    {"id": "waterview_305",   "name": "Water View 305",  "icon": "💧", "count": 1, "base": 259, "min": 225, "max": 495, "category": "waterview"},
    {"id": "garden_101",      "name": "Garden Room 101", "icon": "🌿", "count": 1, "base": 279, "min": 225, "max": 495, "category": "garden"},
    {"id": "garden_102",      "name": "Garden Room 102", "icon": "🌿", "count": 1, "base": 279, "min": 225, "max": 495, "category": "garden"},
    {"id": "garden_103",      "name": "Garden Room 103", "icon": "🌿", "count": 1, "base": 279, "min": 225, "max": 495, "category": "garden"},
    {"id": "garden_104",      "name": "Garden Room 104", "icon": "🌿", "count": 1, "base": 279, "min": 225, "max": 495, "category": "garden"},
]

# NOTE: All competitors verified as active lodging properties.
# 601 Bay Street ("Bay Street Inn") removed 2026-05-19 — private residence, not a hotel.
# Always verify Google Places results before adding to competitor set.
COMPETITORS = [
    {"id": "c1", "name": "607 Bay Inn",            "city": "Beaufort", "state": "SC", "avail_color": "yellow"},
    {"id": "c2", "name": "Airbnb Near Bay (avg)",  "city": "Beaufort", "state": "SC", "avail_color": "green"},
    {"id": "c3", "name": "Beaufort Inn",            "city": "Beaufort", "state": "SC", "avail_color": "red"},
    {"id": "c4", "name": "City Loft Hotel",         "city": "Beaufort", "state": "SC", "avail_color": "green"},
    {"id": "c5", "name": "Cuthbert House Inn",      "city": "Beaufort", "state": "SC", "avail_color": "green"},
    {"id": "c6", "name": "Rhett House Inn",         "city": "Beaufort", "state": "SC", "avail_color": "yellow"},
]

GUEST_PACKAGES = [
    {"id": "romance",       "icon": "💑", "name": "Romance Package",
     "components": "Room · Dinner for Two at Ribaut Social Club · Bottle of Wine",
     "description": "An unforgettable evening: premium room, in-room dining at the legendary Ribaut Social Club, and a selected South Carolina wine awaiting on arrival.",
     "upsell_price": 85, "take_rate": 0.20, "seasonal": None,
     "room_restriction": ["waterfront_201","waterfront_202","waterfront_203","waterfront_204","waterview_301","waterview_302","waterview_303"],
     "active": True,  "coming_soon": False},
    {"id": "anniversary",   "icon": "🥂", "name": "Anniversary Package",
     "components": "Room · Fresh Flowers · Champagne on Arrival",
     "description": "In-room fresh floral arrangement from a local Beaufort florist and chilled champagne waiting when you arrive.",
     "upsell_price": 65, "take_rate": 0.22, "seasonal": None,
     "room_restriction": None, "active": True,  "coming_soon": False},
    {"id": "adventure",     "icon": "🚣", "name": "Adventure Package",
     "components": "Room · Kayak Rental · Packed Lowcountry Lunch",
     "description": "Full-day kayak rental on the Beaufort River estuary with a packed Lowcountry lunch to enjoy on the water.",
     "upsell_price": 75, "take_rate": 0.18, "seasonal": "May–October",
     "room_restriction": None, "active": True,  "coming_soon": False},
    {"id": "spa",           "icon": "💆", "name": "Spa Enhancement",
     "components": "In-Room Massage for Two (90 min)",
     "description": "A licensed therapist comes to you — 90-minute couples massage in the comfort of your room. Add to any booking.",
     "upsell_price": 120,"take_rate": 0.20, "seasonal": None,
     "room_restriction": None, "active": True,  "coming_soon": False},
    {"id": "breakfast",     "icon": "☕", "name": "Breakfast Upgrade",
     "components": "Private Porch Breakfast for Two",
     "description": "Skip the continental buffet — enjoy a private, fully-served breakfast for two delivered to your porch or balcony.",
     "upsell_price": 35, "take_rate": 0.20, "seasonal": None,
     "room_restriction": None, "active": True,  "coming_soon": False},
    {"id": "sunset_cruise", "icon": "🌅", "name": "Sunset Cruise",
     "components": "Chartered Boat Sunset Cruise for Two",
     "description": "A private 2-hour chartered sunset cruise on the Beaufort River — one of the most scenic waterways in the Lowcountry.",
     "upsell_price": 95, "take_rate": 0.20, "seasonal": "April–October",
     "room_restriction": None, "active": False, "coming_soon": True},
    {"id": "pet",           "icon": "🐾", "name": "Pet Package",
     "components": "Pet Welcome Kit · $50 Pet Fee Waived · Pet-Friendly Amenities",
     "description": "Rooms 101–103 only. The welcome kit includes a bed, treats, and a local trail guide. Pet fee waived.",
     "upsell_price": 45, "take_rate": 0.20, "seasonal": None,
     "room_restriction": ["garden_101","garden_102","garden_103"],
     "active": True,  "coming_soon": False},
]

GIFT_SHOP_CATEGORIES = [
    {"id": "lowcountry_food", "icon": "🍯", "name": "Lowcountry Food & Pantry",
     "items": "Sweetgrass Jams · Hot Sauces · Stone-Ground Grits · Pralines · Local Honey",
     "item_count": 24, "est_monthly_rev": 1200,
     "note": "Best sellers: jams and pralines", "margin": 0.55,
     "integration": None,
     "items_detail": [
         {"id":"lc_jam","name":"Sweetgrass Strawberry Fig Jam","price":12.00,
          "est_monthly_units":28,"active":True,"notes":"Local farm sourced"},
         {"id":"lc_honey","name":"Lowcountry Raw Honey","price":18.00,
          "est_monthly_units":15,"active":True,"notes":""},
         {"id":"lc_grits","name":"Stone-Ground White Grits","price":9.00,
          "est_monthly_units":20,"active":True,"notes":""},
         {"id":"lc_pralines","name":"Pecan Pralines (3-pack)","price":8.00,
          "est_monthly_units":32,"active":True,"notes":"Top seller"},
         {"id":"lc_hotsauce","name":"Beaufort Hot Sauce","price":10.00,
          "est_monthly_units":18,"active":True,"notes":""},
         {"id":"lc_bbqsauce","name":"Lowcountry BBQ Sauce","price":11.00,
          "est_monthly_units":12,"active":True,"notes":""},
     ]},
    {"id": "branded", "icon": "👕", "name": "Anchorage 1770 Branded",
     "items": "Monogrammed Robes · Canvas Totes · Soy Candles · Coffee Mugs · Embroidered Hats",
     "item_count": 12, "est_monthly_rev": 800,
     "note": "High-margin, strong during holiday season", "margin": 0.70,
     "integration": None,
     "items_detail": [
         {"id":"br_robe","name":"Monogrammed Robe","price":85.00,
          "est_monthly_units":4,"active":True,"notes":"Premium cotton"},
         {"id":"br_tote","name":"Canvas Tote Bag","price":28.00,
          "est_monthly_units":12,"active":True,"notes":""},
         {"id":"br_mug","name":"Ceramic Coffee Mug","price":22.00,
          "est_monthly_units":18,"active":True,"notes":"Bestseller"},
         {"id":"br_hat","name":"Embroidered Baseball Cap","price":32.00,
          "est_monthly_units":8,"active":True,"notes":""},
         {"id":"br_candle","name":"Soy Candle – Bay Breeze Scent","price":24.00,
          "est_monthly_units":10,"active":True,"notes":""},
     ]},
    {"id": "artisan", "icon": "🎨", "name": "Local Artisan Goods",
     "items": "Sweetgrass Baskets · Lowcountry Prints · Sea Glass Jewelry · Handmade Pottery",
     "item_count": 18, "est_monthly_rev": 650,
     "note": "Curated from Beaufort artists — consignment model", "margin": 0.30,
     "integration": None,
     "items_detail": [
         {"id":"art_basket","name":"Sweetgrass Basket (small)","price":65.00,
          "est_monthly_units":3,"active":True,"notes":"Gullah tradition"},
         {"id":"art_print","name":"Beaufort Waterfront Print","price":45.00,
          "est_monthly_units":5,"active":True,"notes":"Local artist"},
         {"id":"art_jewelry","name":"Sea Glass Necklace","price":38.00,
          "est_monthly_units":6,"active":True,"notes":""},
         {"id":"art_pottery","name":"Handmade Pottery Mug","price":32.00,
          "est_monthly_units":7,"active":True,"notes":""},
     ]},
    {"id": "wine_spirits", "icon": "🍷", "name": "Wines & Spirits",
     "items": "SC Muscadine Wine · Firefly Sweet Tea Vodka · Striped Pig Rum · Local Craft Ales",
     "item_count": 8, "est_monthly_rev": 950,
     "note": "Requires SC liquor license compliance", "margin": 0.40,
     "integration": None,
     "items_detail": [
         {"id":"ws_muscadine","name":"SC Muscadine Wine","price":22.00,
          "est_monthly_units":18,"active":True,
          "notes":"Local vineyard"},
         {"id":"ws_firefly","name":"Firefly Sweet Tea Vodka","price":28.00,
          "est_monthly_units":12,"active":True,
          "notes":"SC distillery — requires license"},
         {"id":"ws_stripedpig","name":"Striped Pig Rum","price":26.00,
          "est_monthly_units":10,"active":True,
          "notes":"SC distillery — requires license"},
         {"id":"ws_craftale","name":"Local Craft Ale 4-Pack","price":16.00,
          "est_monthly_units":15,"active":True,"notes":""},
     ]},
]

KNOWN_ANNUAL_EVENTS = [
    {"name": "Parris Island USMC Graduation",     "month": 5,  "day": 6,  "pricing_nudge": 20, "source": "City Visitors Bureau"},
    {"name": "Downtown Farmers Market",            "month": 5,  "day": 9,  "pricing_nudge": 8,  "source": "Tourist Board"},
    {"name": "Original Gullah Festival",           "month": 5,  "day": 20, "pricing_nudge": 18, "source": "Eventbrite"},
    {"name": "First Friday Art Walk",              "month": 6,  "day": 5,  "pricing_nudge": 20, "source": "City Visitors Bureau"},
    {"name": "Music Festival of the Lowcountry",  "month": 6,  "day": 17, "pricing_nudge": 13, "source": "Tourist Board"},
    {"name": "4th of July Celebrations",          "month": 7,  "day": 1,  "pricing_nudge": 18, "source": "Tourist Board"},
    {"name": "Black Roses Freedom Festival",      "month": 7,  "day": 3,  "pricing_nudge": 15, "source": "Eventbrite"},
    {"name": "Beaufort Water Festival",           "month": 7,  "day": 17, "pricing_nudge": 25, "duration_days": 10, "source": "Tourist Board"},
    {"name": "Beaufort Film Festival",            "month": 2,  "day": 14, "pricing_nudge": 12, "source": "Tourist Board"},
    {"name": "Shrimp Festival",                   "month": 10, "day": 15, "pricing_nudge": 15, "source": "City Visitors Bureau"},
    {"name": "Holiday Parade & Tree Lighting",    "month": 12, "day": 5,  "pricing_nudge": 10, "source": "City Visitors Bureau"},
    {"name": "USCB Commencement",                 "month": 5,  "day": 2,  "pricing_nudge": 12, "source": "Tourist Board"},
    {"name": "Martin Luther King Jr. Weekend",    "month": 1,  "day": 18, "pricing_nudge": 10, "source": "Tourist Board"},
    {"name": "Memorial Day Weekend",              "month": 5,  "day": 23, "pricing_nudge": 20, "duration_days": 3, "source": "Tourist Board"},
    {"name": "Labor Day Weekend",                 "month": 9,  "day": 4,  "pricing_nudge": 20, "duration_days": 3, "source": "Tourist Board"},
    {"name": "Thanksgiving Weekend",              "month": 11, "day": 26, "pricing_nudge": 15, "duration_days": 4, "source": "Tourist Board"},
]

EVENT_SOURCES = {
    "city_visitors_bureau": {"enabled": True,  "label": "City Visitors Bureau"},
    "tourist_board_rss":    {"enabled": True,  "label": "Tourist Board RSS"},
    "eventbrite_api":       {"enabled": True,  "label": "Eventbrite API"},
    "facebook_events":      {"enabled": False, "label": "Facebook Events"},
    "chamber_of_commerce":  {"enabled": False, "label": "Chamber of Commerce"},
    "sports_venues":        {"enabled": False, "label": "Sports Venue Calendar"},
}

FEATURE_GATES = {
    "essentials":   {"max_competitors": 5,  "calendar_days": 30,  "max_events": 10,
                     "fb_module": False, "packages_module": False, "gift_shop_module": False,
                     "optimization_engine": False, "autopilot": False, "price_per_month": 399},
    "professional": {"max_competitors": 10, "calendar_days": 90,  "max_events": 999,
                     "fb_module": True,  "packages_module": True,  "gift_shop_module": True,
                     "optimization_engine": True,  "autopilot": True,  "price_per_month": 699},
    "portfolio":    {"max_competitors": 10, "calendar_days": 365, "max_events": 999,
                     "fb_module": True,  "packages_module": True,  "gift_shop_module": True,
                     "optimization_engine": True,  "autopilot": True,  "multi_property": True,
                     "white_label": True, "api_access": True, "price_per_month": 1199},
}

FB_CONFIG = {
    "restaurant_name":         "Ribaut Social Club",
    "covers_per_night":        40,
    "avg_check":               65,
    "nights_open_per_week":    4,
    "bar_avg_daily_revenue":   800,
    "event_avg_revenue":       3500,
    "event_nights_per_month":  2,
    "take_rate_est":           0.20,
}

# ── Section C — Room-type equivalency mapping ─────────────────────────────
# For each competitor, the closest equivalent room they offer per Anchorage
# room category. `rate_premium_vs_base` is applied on top of their blended
# rate to estimate what they charge for that specific room class.
# A `None` value means the competitor has no equivalent in that category.

COMPETITOR_ROOM_TYPES = {
    "Cuthbert House Inn": {
        "waterfront": {"comp_room_name": "Waterfront Suite",
                       "notes": "Panoramic Beaufort River views, private balcony",
                       "rate_premium_vs_base": 0.28},
        "waterview":  {"comp_room_name": "River View Room",
                       "notes": "Partial river views",
                       "rate_premium_vs_base": 0.12},
        "garden":     {"comp_room_name": "Garden Room",
                       "notes": "Garden courtyard setting",
                       "rate_premium_vs_base": 0.0},
        "cottage":    None,
    },
    "Rhett House Inn": {
        "waterfront": None,
        "waterview":  {"comp_room_name": "Verandah Suite",
                       "notes": "Large verandah, garden views",
                       "rate_premium_vs_base": 0.22},
        "garden":     {"comp_room_name": "Standard Room",
                       "notes": "Classic historic inn room",
                       "rate_premium_vs_base": 0.0},
        "cottage":    {"comp_room_name": "Cottage Suite",
                       "notes": "Detached cottage, full privacy",
                       "rate_premium_vs_base": 0.30},
    },
    "607 Bay Inn": {
        "waterfront": {"comp_room_name": "Premier Bay View",
                       "notes": "Top floor, river views",
                       "rate_premium_vs_base": 0.18},
        "waterview":  {"comp_room_name": "Standard Room",
                       "notes": "Downtown location",
                       "rate_premium_vs_base": 0.0},
        "garden":     {"comp_room_name": "Standard Room",
                       "notes": "Downtown location",
                       "rate_premium_vs_base": 0.0},
        "cottage":    None,
    },
    "Beaufort Inn": {
        "waterfront": None,
        "waterview":  {"comp_room_name": "Deluxe King",
                       "notes": "Larger rooms, upscale amenities",
                       "rate_premium_vs_base": 0.20},
        "garden":     {"comp_room_name": "Standard King",
                       "notes": "Standard hotel room",
                       "rate_premium_vs_base": 0.0},
        "cottage":    None,
    },
    "City Loft Hotel": {
        "waterfront": None,
        "waterview":  None,
        "garden":     {"comp_room_name": "Loft Room",
                       "notes": "Modern downtown loft style",
                       "rate_premium_vs_base": 0.0},
        "cottage":    None,
    },
    "Airbnb Near Bay (avg)": {
        "waterfront": None,
        "waterview":  {"comp_room_name": "Waterfront Airbnb (avg)",
                       "notes": "Range of Airbnb listings within 2 blocks of waterfront",
                       "rate_premium_vs_base": 0.15},
        "garden":     {"comp_room_name": "Downtown Airbnb (avg)",
                       "notes": "Average of downtown-Beaufort Airbnb units",
                       "rate_premium_vs_base": 0.0},
        "cottage":    {"comp_room_name": "Whole-house Airbnb (avg)",
                       "notes": "Entire-place rentals comparable to our private cottage",
                       "rate_premium_vs_base": 0.25},
    },
}

# Room type categories for Anchorage 1770 (UI labels + selector)
OUR_ROOM_CATEGORIES = [
    {"id": "waterfront",
     "label": "Waterfront Suites",
     "icon":  "🌊",
     "description": "Rooms 201-204: direct Beaufort River views",
     "room_ids":  ["waterfront_201","waterfront_202","waterfront_203","waterfront_204"],
     "base_rate": 419},
    {"id": "waterview",
     "label": "Water View Suites",
     "icon":  "💧",
     "description": "Rooms 301-305: partial river views",
     "room_ids":  ["waterview_301","waterview_302","waterview_303","waterview_304","waterview_305"],
     "base_rate": 299},
    {"id": "garden",
     "label": "Garden View Rooms",
     "icon":  "🌿",
     "description": "Rooms 101-104: garden courtyard setting",
     "room_ids":  ["garden_101","garden_102","garden_103","garden_104"],
     "base_rate": 279},
    {"id": "cottage",
     "label": "Private Cottage",
     "icon":  "🏡",
     "description": "Standalone cottage: premium privacy",
     "room_ids":  ["private_cottage"],
     "base_rate": 489},
]
