import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from config.settings import TenantConfig

logger = logging.getLogger(__name__)

_NON_FEATURE_COLS = frozenset({"customer_id", "room_id", "collected_at", "current_price"})


class FeatureEngineer:
    """
    Module 3 — derives domain-specific features and scales them for modelling.
    Outputs scaled features, the raw target series, and the fitted scaler.
    """

    def __init__(self, tenant: TenantConfig) -> None:
        self.tenant = tenant
        self.scaler = StandardScaler()
        self.feature_columns: List[str] = []

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def engineer(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(
            f"[{self.tenant.tenant_id}] Feature engineering starting "
            f"(vertical={self.tenant.vertical})"
        )
        df = processed_data["processed"].copy()

        try:
            if self.tenant.vertical == "telecom":
                df = self._engineer_telecom_features(df)
            elif self.tenant.vertical == "hospitality":
                df = self._engineer_hospitality_features(df)
            else:
                raise ValueError(f"Unsupported vertical: {self.tenant.vertical!r}")

            feature_df = self._select_and_scale(df)

            logger.info(
                f"[{self.tenant.tenant_id}] Engineered {len(feature_df.columns)} features "
                f"from {len(df):,} records"
            )
            return {
                "features": feature_df,
                "target": df["current_price"].reset_index(drop=True),
                "scaler": self.scaler,
                "feature_columns": self.feature_columns,
                "quality_report": processed_data.get("quality_report", {}),
                "metadata": processed_data.get("metadata", {}),
            }

        except Exception as exc:
            logger.error(f"[{self.tenant.tenant_id}] Feature engineering failed: {exc}", exc_info=True)
            raise

    # ------------------------------------------------------------------ #
    #  Vertical-specific feature derivation                               #
    # ------------------------------------------------------------------ #

    def _engineer_telecom_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df["usage_intensity"]     = df["usage_minutes"] / (df["contract_months"] + 1)
        df["data_per_minute"]     = df["data_gb"] / (df["usage_minutes"] + 1)
        df["loyalty_score"]       = np.log1p(df["contract_months"]) / np.log(25)
        df["risk_adjusted_score"] = df["churn_score"] * (1 - df["loyalty_score"])
        df["roaming_flag"]        = (df["roaming_days"] > 0).astype(int)
        return df

    def _engineer_hospitality_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df["price_to_competitor_ratio"]  = df["current_price"] / (df["competitor_rate"] + 1)
        df["booking_urgency"]            = 1 / np.log1p(df["lead_time_days"] + 1)
        df["demand_season_interaction"]  = df["demand_score"] * df["season_index"]
        df["occupancy_pressure"]         = np.where(df["occupancy_rate"] > 0.85, 1.5, 1.0)
        df["value_gap"]                  = df["competitor_rate"] - df["current_price"]
        return df

    # ------------------------------------------------------------------ #
    #  Feature selection + scaling                                         #
    # ------------------------------------------------------------------ #

    def _select_and_scale(self, df: pd.DataFrame) -> pd.DataFrame:
        # Base features declared in tenant config that actually exist in df
        base = [c for c in self.tenant.features if c in df.columns]

        # Derived numeric columns added during engineering
        engineered = [
            c for c in df.columns
            if c not in self.tenant.features
            and c not in _NON_FEATURE_COLS
            and pd.api.types.is_numeric_dtype(df[c])
        ]

        self.feature_columns = base + engineered
        feature_df = df[self.feature_columns].reset_index(drop=True)
        scaled = self.scaler.fit_transform(feature_df)
        return pd.DataFrame(scaled, columns=self.feature_columns)
