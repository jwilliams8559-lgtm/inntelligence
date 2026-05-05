"""
orchestrator/engine.py

Central orchestrator for the multi-tenant AI predictive pricing engine.

Pipeline (per tenant):
    DataCollector  →  DataProcessor  →  FeatureEngineer  →  PricingPredictor

Supports multiple industry verticals (telecom, hospitality) via config/settings.py.
Includes structured logging, full error handling, and a nightly 2 AM scheduler.
"""

import logging
import logging.handlers
import os
import signal
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import schedule

from config.settings import (
    DATA_EXPORTS_DIR,
    LOG_BACKUP_COUNT,
    LOG_LEVEL,
    LOG_ROTATION,
    LOGS_DIR,
    NIGHTLY_JOB_HOUR,
    NIGHTLY_JOB_MINUTE,
    TENANTS,
    TenantConfig,
)
from modules.module1_data_collection.collector import DataCollector
from modules.module2_data_processing.processor import DataProcessor
from modules.module3_feature_engineering.engineer import FeatureEngineer
from modules.module4_predictive_analytics.predictor import PricingPredictor
from modules.module5_optimization.optimizer import PricingOptimizer

logger = logging.getLogger(__name__)

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────────────────────
#  Logging bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def configure_logging(tenant_id: Optional[str] = None) -> None:
    """
    Set up console + rotating-file handlers on the root logger.
    Safe to call multiple times — handlers are only added once.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)
    suffix = f"_{tenant_id}" if tenant_id else ""
    log_file = os.path.join(LOGS_DIR, f"pricing_engine{suffix}.log")

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    if root.handlers:
        return  # already configured

    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Midnight-rotating file handler
    fh = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when=LOG_ROTATION,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)


# ─────────────────────────────────────────────────────────────────────────────
#  Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class PricingEngineOrchestrator:
    """
    Runs the four-module pricing pipeline for one or all configured tenants.

    Usage
    -----
    # Run all tenants once:
    orchestrator = PricingEngineOrchestrator()
    results = orchestrator.run_all_tenants()

    # Start the nightly 2 AM scheduler (blocking — call from main thread):
    orchestrator.start_scheduler(block=True)
    """

    def __init__(self, tenant_ids: Optional[List[str]] = None) -> None:
        configure_logging()
        self.tenant_ids: List[str] = tenant_ids or list(TENANTS.keys())
        self.results: Dict[str, Any] = {}

        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None

        unknown = [tid for tid in self.tenant_ids if tid not in TENANTS]
        if unknown:
            raise ValueError(f"Unknown tenant ID(s): {unknown}")

        logger.info(
            f"PricingEngineOrchestrator initialised — "
            f"tenants={self.tenant_ids}"
        )

    # ------------------------------------------------------------------ #
    #  Multi-tenant entry point                                            #
    # ------------------------------------------------------------------ #

    def run_all_tenants(self) -> Dict[str, Any]:
        """Execute the full pipeline for every configured tenant sequentially."""
        logger.info(f"Starting run for {len(self.tenant_ids)} tenant(s)")
        run_start = time.perf_counter()
        self.results = {}

        for tenant_id in self.tenant_ids:
            self.results[tenant_id] = self.run_pipeline(tenant_id)

        elapsed = time.perf_counter() - run_start
        success = sum(1 for r in self.results.values() if r["status"] == "success")
        logger.info(
            f"All tenants complete: {success}/{len(self.tenant_ids)} succeeded "
            f"in {elapsed:.1f}s"
        )
        return self.results

    # ------------------------------------------------------------------ #
    #  Single-tenant pipeline                                              #
    # ------------------------------------------------------------------ #

    def run_pipeline(self, tenant_id: str) -> Dict[str, Any]:
        """
        Execute the four-module pipeline for a single tenant.

        Data flow:
            collect()  →  process(raw)  →  engineer(processed)  →  predict(engineered)

        Returns a result dict with status, predictions, metrics, and duration.
        """
        tenant = TENANTS[tenant_id]
        logger.info(f"[{tenant_id}] ═══ Pipeline START ═══")
        pipeline_start = time.perf_counter()

        result: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "vertical":  tenant.vertical,
            "status":    "started",
            "errors":    [],
        }

        try:
            # ── Module 1: Data Collection ──────────────────────────────
            raw_data = self._run_step(
                tenant_id,
                step_name="module1_data_collection",
                fn=lambda: DataCollector(tenant).collect(),
            )

            # ── Module 2: Data Processing ──────────────────────────────
            processed_data = self._run_step(
                tenant_id,
                step_name="module2_data_processing",
                fn=lambda: DataProcessor(tenant).process(raw_data),
            )

            # ── Module 3: Feature Engineering ─────────────────────────
            engineered_data = self._run_step(
                tenant_id,
                step_name="module3_feature_engineering",
                fn=lambda: FeatureEngineer(tenant).engineer(processed_data),
            )

            # ── Module 4: Predictive Analytics ────────────────────────
            predictions = self._run_step(
                tenant_id,
                step_name="module4_predictive_analytics",
                fn=lambda: PricingPredictor(tenant).predict(engineered_data),
            )

            # ── Module 5: Optimization (hospitality only) ─────────────
            if tenant.vertical == "hospitality":
                optimizations = self._run_step(
                    tenant_id,
                    step_name="module5_optimization",
                    fn=lambda: PricingOptimizer().optimize(predictions),
                )
                result["optimizations"] = optimizations

            result["predictions"] = predictions
            result["status"] = "success"
            self._export_results(tenant, predictions)

        except Exception as exc:
            result["status"] = "failed"
            result["errors"].append(str(exc))
            logger.error(f"[{tenant_id}] Pipeline FAILED: {exc}", exc_info=True)

        finally:
            elapsed = time.perf_counter() - pipeline_start
            result["duration_seconds"] = round(elapsed, 2)
            logger.info(
                f"[{tenant_id}] ═══ Pipeline END  "
                f"status={result['status']}  {elapsed:.1f}s ═══"
            )

        return result

    # ------------------------------------------------------------------ #
    #  Step runner with timing + error propagation                        #
    # ------------------------------------------------------------------ #

    def _run_step(self, tenant_id: str, step_name: str, fn) -> Any:
        logger.info(f"[{tenant_id}] ── {step_name} ──")
        step_start = time.perf_counter()
        try:
            output = fn()
            elapsed = time.perf_counter() - step_start
            logger.info(f"[{tenant_id}] {step_name} completed in {elapsed:.2f}s")
            return output
        except Exception as exc:
            elapsed = time.perf_counter() - step_start
            logger.error(
                f"[{tenant_id}] {step_name} raised after {elapsed:.2f}s: {exc}"
            )
            raise

    # ------------------------------------------------------------------ #
    #  Export                                                              #
    # ------------------------------------------------------------------ #

    def _export_results(self, tenant: TenantConfig, predictions: Dict[str, Any]) -> None:
        os.makedirs(DATA_EXPORTS_DIR, exist_ok=True)
        recs = predictions.get("recommendations")
        if recs is None or recs.empty:
            logger.warning(f"[{tenant.tenant_id}] No recommendations to export")
            return

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(
            DATA_EXPORTS_DIR,
            f"{tenant.tenant_id}_{ts}_recommendations.csv",
        )
        recs.to_csv(path, index=True)

        metrics = predictions.get("metrics", {})
        logger.info(
            f"[{tenant.tenant_id}] Exported {len(recs):,} recommendations → {path}  "
            f"MAE={metrics.get('mae', '?'):.2f}  R²={metrics.get('r2', '?'):.3f}"
        )

    # ------------------------------------------------------------------ #
    #  Scheduler                                                           #
    # ------------------------------------------------------------------ #

    def _nightly_job(self) -> None:
        """Callback invoked by the scheduler at the configured nightly time."""
        logger.info("Nightly job triggered — running all tenant pipelines")
        try:
            self.run_all_tenants()
        except Exception as exc:
            logger.critical(f"Nightly job raised an unhandled exception: {exc}", exc_info=True)

    def start_scheduler(self, block: bool = False) -> None:
        """
        Register the nightly pipeline job and start a background scheduler thread.

        Parameters
        ----------
        block:
            If True, park the calling thread (useful when invoked directly from
            main()). The caller should send SIGINT/SIGTERM to trigger shutdown.
        """
        job_time = f"{NIGHTLY_JOB_HOUR:02d}:{NIGHTLY_JOB_MINUTE:02d}"
        schedule.every().day.at(job_time).do(self._nightly_job)
        logger.info(f"Nightly pricing job scheduled at {job_time} UTC (every 24 h)")

        self._stop_event.clear()

        def _scheduler_loop() -> None:
            logger.info("Scheduler thread running")
            while not self._stop_event.is_set():
                schedule.run_pending()
                time.sleep(30)  # 30-second tick — low CPU, still responsive
            logger.info("Scheduler thread exiting")

        self._scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            name="pricing-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()

        if block:
            self._block_until_signal()

    def stop_scheduler(self) -> None:
        """Signal the scheduler thread to stop and wait for it to join."""
        self._stop_event.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=10)
        schedule.clear()
        logger.info("Scheduler stopped and all jobs cleared")

    @staticmethod
    def _block_until_signal() -> None:
        """Park the main thread; SIGINT/SIGTERM unblocks it."""
        stop = threading.Event()

        def _handler(sig, _frame):
            logger.info(f"Received signal {sig} — initiating shutdown")
            stop.set()

        signal.signal(signal.SIGINT,  _handler)
        signal.signal(signal.SIGTERM, _handler)
        logger.info("Scheduler running. Send SIGINT (Ctrl-C) or SIGTERM to stop.")
        stop.wait()
