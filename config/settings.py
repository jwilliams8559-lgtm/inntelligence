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
#  Demo property registry — multi-property dashboard support
# ════════════════════════════════════════════════════════════════════════════
# Each entry is display + pricing metadata for one demo property. Anchorage's
# actual pricing still flows through the untouched anchorage_pricing.py globals
# (its entry carries no `rooms`, signalling "use engine defaults"). Bay Street
# carries its own room inventory + params, which AnchoragePricingEngine accepts
# via its optional property_config argument. Rooms are plain dicts here (not
# Room objects) to avoid a circular import with anchorage_pricing.py.

# The dashboard manages The Bay Street Inn. Anchorage 1770 is a competitor,
# never a selectable managed property.
DEFAULT_PROPERTY = "bay_street_inn_demo"

PROPERTIES: dict = {
    # ── Anchorage 1770 Inn — UNCHANGED. Metadata only; pricing uses the
    #    existing anchorage_pricing.py globals (engine built with no config).
    "anchorage_1770_demo": {
        "id":            "anchorage_1770_demo",
        "name":          "Anchorage 1770 Inn",
        "city":          "Beaufort, SC",
        "show_address":  True,
        "address":       "1103 Bay Street · Beaufort, SC 29902",
        "restaurant":    "Ribaut Social Club",
        "rooftop_bar":   "Rooftop Bar",
        "room_count":    14,
        "fnb_tenant":    "bay-street-inn-demo",   # existing F&B demo dataset
        "use_engine_defaults": True,              # build engine with no config
    },

    # ── The Bay Street Inn — new demo property. Full config below.
    "bay_street_inn_demo": {
        "id":            "bay_street_inn_demo",
        "name":          "The Bay Street Inn",
        "city":          "Beaufort, SC",
        "show_address":  False,                   # never render a street address
        "restaurant":    "The Parlor at Bay Street Inn",
        "rooftop_bar":   "The Rooftop at Bay Street",
        "room_count":    19,
        "fnb_tenant":    "bay-street-inn-demo",   # map to existing F&B dataset
        "use_engine_defaults": False,
        # Pricing parameters consumed by AnchoragePricingEngine(property_config=…)
        "occ_target_low":     0.70,
        "occ_target_high":    0.85,
        "weekend_premium":    0.15,               # +15% Fri/Sat
        "discount_floor_pct": 0.85,               # never below 15% under rack_low
        "export_prefix":      "bay_street_inn",
        # Bay Street's own isolated competitor set — 9 properties across 3 tiers.
        # tier 1 (weight 1.0) direct comps · tier 2 (0.4) market reference ·
        # tier 3 (0.1) market anchors. (base_low, base_high) = low-season weekday
        # → peak-season weekend typical rates. Plain dicts → Competitor objects.
        "competitors": [
            {"key": "rhett_house",    "name": "Rhett House Inn",              "base_low": 239, "base_high": 439, "tier": 1, "weight": 1.0},
            {"key": "cuthbert_house", "name": "Cuthbert House Inn",           "base_low": 249, "base_high": 425, "tier": 1, "weight": 1.0},
            {"key": "anchorage_1770", "name": "Anchorage 1770 Inn",           "base_low": 289, "base_high": 469, "tier": 1, "weight": 1.0},
            {"key": "bay_inn_607",    "name": "607 Bay Inn",                  "base_low": 189, "base_high": 349, "tier": 1, "weight": 1.0},
            {"key": "beaufort_inn",   "name": "Beaufort Inn",                 "base_low": 199, "base_high": 375, "tier": 2, "weight": 0.4},
            {"key": "city_loft",      "name": "City Loft Hotel",              "base_low": 169, "base_high": 295, "tier": 2, "weight": 0.4},
            {"key": "airbnb_avg",     "name": "Airbnb Near Bay Street (avg)", "base_low": 149, "base_high": 325, "tier": 3, "weight": 0.1},
            {"key": "hampton_inn",    "name": "Hampton Inn Beaufort",         "base_low": 129, "base_high": 219, "tier": 3, "weight": 0.1},
            {"key": "montage",        "name": "Montage Palmetto Bluff",       "base_low": 695, "base_high": 1295, "tier": 3, "weight": 0.1},
        ],
        # 19 rooms; each (rack_low, rack_high) sits inside its tier band.
        "rooms": [
            # Waterfront — band $349–$409 (4)
            {"room_id": "bsw_1", "name": "Waterfront 1", "tier": "waterfront", "rack_low": 349, "rack_high": 389, "description": "Direct Beaufort River views, king bed"},
            {"room_id": "bsw_2", "name": "Waterfront 2", "tier": "waterfront", "rack_low": 359, "rack_high": 399, "description": "Direct river views, king bed, sitting area"},
            {"room_id": "bsw_3", "name": "Waterfront 3", "tier": "waterfront", "rack_low": 369, "rack_high": 399, "description": "Direct river views, private balcony"},
            {"room_id": "bsw_4", "name": "Waterfront 4", "tier": "waterfront", "rack_low": 389, "rack_high": 409, "description": "Corner river views, premium furnishings"},
            # Water View — band $279–$329 (5)
            {"room_id": "bsv_1", "name": "Water View 1", "tier": "water_view", "rack_low": 279, "rack_high": 309, "description": "Partial river views, queen bed"},
            {"room_id": "bsv_2", "name": "Water View 2", "tier": "water_view", "rack_low": 279, "rack_high": 319, "description": "Partial river views, king bed"},
            {"room_id": "bsv_3", "name": "Water View 3", "tier": "water_view", "rack_low": 289, "rack_high": 319, "description": "Partial river views, sitting area"},
            {"room_id": "bsv_4", "name": "Water View 4", "tier": "water_view", "rack_low": 299, "rack_high": 329, "description": "Partial river views, clawfoot tub"},
            {"room_id": "bsv_5", "name": "Water View 5", "tier": "water_view", "rack_low": 309, "rack_high": 329, "description": "Partial river views, updated bath"},
            # Garden — band $229–$279 (5)
            {"room_id": "bsg_1", "name": "Garden 1", "tier": "garden", "rack_low": 229, "rack_high": 259, "description": "Garden courtyard views, queen bed"},
            {"room_id": "bsg_2", "name": "Garden 2", "tier": "garden", "rack_low": 239, "rack_high": 269, "description": "Garden views, king bed"},
            {"room_id": "bsg_3", "name": "Garden 3", "tier": "garden", "rack_low": 249, "rack_high": 269, "description": "Garden views, private patio"},
            {"room_id": "bsg_4", "name": "Garden 4", "tier": "garden", "rack_low": 259, "rack_high": 279, "description": "Garden views, ground floor"},
            {"room_id": "bsg_5", "name": "Garden 5", "tier": "garden", "rack_low": 269, "rack_high": 279, "description": "Garden views, twin beds"},
            # Carriage House Suites — band $449–$509 (2)
            {"room_id": "bsc_1", "name": "Carriage House Suite 1", "tier": "carriage_house", "rack_low": 449, "rack_high": 489, "description": "Detached carriage house suite, full privacy"},
            {"room_id": "bsc_2", "name": "Carriage House Suite 2", "tier": "carriage_house", "rack_low": 469, "rack_high": 509, "description": "Detached carriage house suite, kitchenette"},
            # Signature Suites — band $499–$559 (2)
            {"room_id": "bss_1", "name": "Signature Suite 1", "tier": "signature_suite", "rack_low": 499, "rack_high": 539, "description": "Premier suite, river views, separate sitting room"},
            {"room_id": "bss_2", "name": "Signature Suite 2", "tier": "signature_suite", "rack_low": 519, "rack_high": 559, "description": "Premier suite, fireplace, soaking tub"},
            # Grand Parlor Suite — band $599–$659 (1)
            {"room_id": "bsp_1", "name": "Grand Parlor Suite", "tier": "grand_parlor", "rack_low": 599, "rack_high": 659, "description": "Signature top-floor suite, panoramic river views, private parlor"},
        ],
    },
}
