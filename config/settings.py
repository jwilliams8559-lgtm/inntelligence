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
