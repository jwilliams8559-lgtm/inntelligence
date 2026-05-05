import logging
from datetime import datetime
from typing import Any, Dict, Type

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.base import RegressorMixin
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from config.settings import TenantConfig

logger = logging.getLogger(__name__)

_MODEL_REGISTRY: Dict[str, Type[RegressorMixin]] = {
    "gradient_boost": GradientBoostingRegressor,
    "random_forest":  RandomForestRegressor,
}


class PricingPredictor:
    """
    Module 4 — trains a pricing model and generates per-record recommendations.
    Outputs recommended prices, evaluation metrics, and action labels.
    """

    def __init__(self, tenant: TenantConfig) -> None:
        self.tenant = tenant
        self.model_params = tenant.model_params
        self.model: RegressorMixin | None = None
        self.metrics: Dict[str, float] = {}
        self.price_floor: float = float(self.model_params.get("price_floor", 0.0))
        self.price_ceiling: float = float(self.model_params.get("price_ceiling", 1e9))

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def predict(self, engineered_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[{self.tenant.tenant_id}] Predictive analytics starting")
        features: pd.DataFrame = engineered_data["features"]
        target: pd.Series = engineered_data["target"]

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                features, target, test_size=0.2, random_state=42
            )
            self._train(X_train, y_train)
            self._evaluate(X_test, y_test)
            recommendations = self._generate_recommendations(features, target)

            logger.info(
                f"[{self.tenant.tenant_id}] Predictions complete — "
                f"MAE={self.metrics['mae']:.2f}  RMSE={self.metrics['rmse']:.2f}  "
                f"R²={self.metrics['r2']:.3f}  records={len(recommendations):,}"
            )
            return {
                "recommendations": recommendations,
                "metrics": self.metrics,
                "model_type": self.model_params.get("model_type"),
                "feature_columns": engineered_data["feature_columns"],
                "quality_report": engineered_data.get("quality_report", {}),
                "metadata": engineered_data.get("metadata", {}),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.error(f"[{self.tenant.tenant_id}] Prediction failed: {exc}", exc_info=True)
            raise

    # ------------------------------------------------------------------ #
    #  Internal steps                                                      #
    # ------------------------------------------------------------------ #

    def _train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        model_type = self.model_params.get("model_type", "gradient_boost")
        model_class = _MODEL_REGISTRY.get(model_type)
        if model_class is None:
            raise ValueError(f"Unsupported model type: {model_type!r}")

        init_kwargs: Dict[str, Any] = {
            "n_estimators": int(self.model_params.get("n_estimators", 100)),
            "random_state": 42,
        }
        if model_type == "gradient_boost":
            init_kwargs["learning_rate"] = float(self.model_params.get("learning_rate", 0.1))

        self.model = model_class(**init_kwargs)
        logger.debug(
            f"[{self.tenant.tenant_id}] Training {model_type} "
            f"on {len(X_train):,} samples with {init_kwargs}"
        )
        self.model.fit(X_train, y_train)

    def _evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> None:
        preds = self.model.predict(X_test)
        self.metrics = {
            "mae":  float(mean_absolute_error(y_test, preds)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
            "r2":   float(r2_score(y_test, preds)),
            "mape": float(np.mean(np.abs((y_test.values - preds) / (y_test.values + 1e-9))) * 100),
        }

    def _generate_recommendations(
        self, features: pd.DataFrame, current_prices: pd.Series
    ) -> pd.DataFrame:
        raw_predicted = self.model.predict(features)
        predicted = np.clip(raw_predicted, self.price_floor, self.price_ceiling)
        current = current_prices.values
        delta = predicted - current
        pct_change = (delta / (current + 1e-9)) * 100

        return pd.DataFrame({
            "predicted_price": np.round(predicted, 2),
            "current_price":   np.round(current, 2),
            "price_delta":     np.round(delta, 2),
            "pct_change":      np.round(pct_change, 2),
            "action": np.where(delta > 0.01, "increase",
                      np.where(delta < -0.01, "decrease", "hold")),
        })
