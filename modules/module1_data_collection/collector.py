import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd

from config.settings import VERTICAL_CONFIGS, TenantConfig

logger = logging.getLogger(__name__)


class DataCollector:
    """
    Module 1 — retrieves raw data for a tenant from all configured sources.
    Returns a dict with a 'primary' DataFrame and collection metadata.
    """

    def __init__(self, tenant: TenantConfig) -> None:
        self.tenant = tenant
        self.vertical_config = VERTICAL_CONFIGS[tenant.vertical]
        self._validate_sources()

    def _validate_sources(self) -> None:
        sources = self.vertical_config["data_sources"]
        logger.debug(f"[{self.tenant.tenant_id}] Validating {len(sources)} data source(s): {sources}")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def collect(self, lookback_days: int = 90) -> Dict[str, Any]:
        logger.info(
            f"[{self.tenant.tenant_id}] Data collection starting "
            f"(vertical={self.tenant.vertical}, lookback={lookback_days}d)"
        )
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)

        try:
            if self.tenant.vertical == "telecom":
                raw_data = self._collect_telecom(start_date, end_date)
            elif self.tenant.vertical == "hospitality":
                raw_data = self._collect_hospitality(start_date, end_date)
            else:
                raise ValueError(f"Unsupported vertical: {self.tenant.vertical!r}")

            record_count = len(raw_data["primary"])
            logger.info(f"[{self.tenant.tenant_id}] Collected {record_count:,} raw records")
            return raw_data

        except Exception as exc:
            logger.error(f"[{self.tenant.tenant_id}] Data collection failed: {exc}", exc_info=True)
            raise

    # ------------------------------------------------------------------ #
    #  Vertical-specific collectors                                        #
    # ------------------------------------------------------------------ #

    def _collect_telecom(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Stub — replace with actual DB/API calls for telecom usage data."""
        logger.debug(f"[{self.tenant.tenant_id}] Fetching telecom usage records")
        n = 1_000
        idx = range(n)
        primary_df = pd.DataFrame({
            "customer_id":      list(idx),
            "usage_minutes":    [100.0 + i * 0.5 for i in idx],
            "data_gb":          [1.0 + i * 0.01 for i in idx],
            "roaming_days":     [i % 30 for i in idx],
            "contract_months":  [12 + (i % 24) for i in idx],
            "churn_score":      [round((i % 100) / 100, 4) for i in idx],
            "current_price":    [29.99 + (i % 10) * 5.0 for i in idx],
            "collected_at":     datetime.utcnow(),
        })
        return {
            "primary": primary_df,
            "metadata": {"start": start_date, "end": end_date, "source": "telecom_stub"},
        }

    def _collect_hospitality(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Stub — replace with actual PMS/channel-manager calls."""
        logger.debug(f"[{self.tenant.tenant_id}] Fetching hospitality occupancy and rate records")
        n = 500
        idx = range(n)
        primary_df = pd.DataFrame({
            "room_id":           list(idx),
            "occupancy_rate":    [0.5 + (i % 50) / 100.0 for i in idx],
            "lead_time_days":    [i % 60 for i in idx],
            "season_index":      [0.8 + (i % 5) * 0.1 for i in idx],
            "competitor_rate":   [100.0 + (i % 200) for i in idx],
            "demand_score":      [round((i % 100) / 100, 4) for i in idx],
            "current_price":     [99.0 + (i % 50) * 10.0 for i in idx],
            "collected_at":      datetime.utcnow(),
        })
        return {
            "primary": primary_df,
            "metadata": {"start": start_date, "end": end_date, "source": "hospitality_stub"},
        }
