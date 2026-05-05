import logging
from datetime import datetime
from typing import Any, Dict

import numpy as np
import pandas as pd

from config.settings import TenantConfig

logger = logging.getLogger(__name__)

# Columns that should never be treated as numeric features for outlier removal
_ID_COLS = frozenset({"customer_id", "room_id"})


class DataProcessor:
    """
    Module 2 — cleans and validates raw data.
    Outputs a processed DataFrame plus a quality report.
    """

    def __init__(self, tenant: TenantConfig) -> None:
        self.tenant = tenant
        self.quality_report: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[{self.tenant.tenant_id}] Data processing starting")
        df = raw_data["primary"].copy()
        original_count = len(df)

        try:
            df = self._remove_duplicates(df)
            df = self._handle_missing_values(df)
            df = self._remove_outliers(df)
            df = self._normalize_types(df)
            self._build_quality_report(original_count, df)

            retention = self.quality_report["retention_rate"]
            logger.info(
                f"[{self.tenant.tenant_id}] Processing complete: "
                f"{original_count:,} → {len(df):,} records ({retention:.1%} retention)"
            )
            return {
                "processed": df,
                "quality_report": self.quality_report,
                "metadata": raw_data.get("metadata", {}),
            }

        except Exception as exc:
            logger.error(f"[{self.tenant.tenant_id}] Data processing failed: {exc}", exc_info=True)
            raise

    # ------------------------------------------------------------------ #
    #  Steps                                                               #
    # ------------------------------------------------------------------ #

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates()
        removed = before - len(df)
        if removed:
            logger.debug(f"[{self.tenant.tenant_id}] Removed {removed} duplicate row(s)")
        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

        categorical_cols = df.select_dtypes(include=["object", "category"]).columns
        df[categorical_cols] = df[categorical_cols].fillna("unknown")
        return df

    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """1–99th percentile IQR fence on all numeric feature columns."""
        numeric_cols = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c not in _ID_COLS
        ]
        for col in numeric_cols:
            q1, q99 = df[col].quantile(0.01), df[col].quantile(0.99)
            iqr = q99 - q1
            lo, hi = q1 - 1.5 * iqr, q99 + 1.5 * iqr
            before = len(df)
            df = df[(df[col] >= lo) & (df[col] <= hi)]
            removed = before - len(df)
            if removed:
                logger.debug(f"[{self.tenant.tenant_id}] Outlier removal on '{col}': dropped {removed} row(s)")
        return df

    def _normalize_types(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].round(4)
        return df

    def _build_quality_report(self, original_count: int, df: pd.DataFrame) -> None:
        self.quality_report = {
            "original_count": original_count,
            "processed_count": len(df),
            "retention_rate": len(df) / original_count if original_count else 0.0,
            "null_counts": df.isnull().sum().to_dict(),
            "generated_at": datetime.utcnow().isoformat(),
        }
