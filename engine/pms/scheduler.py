"""
engine/pms/scheduler.py — Phase 4C

Daily PMS sync orchestrator. Designed to be invoked by a cron (or Supabase
Scheduled Edge Function / pg_cron) at 3am local property time:

  run_daily_sync(property_id)
      → sync_occupancy
      → sync_guests
      → sync_current_rates
      → demand_forecaster.update_recommendations_table
      → rate_engine.update_all_recommendations
      → log to pms_sync_log

  run_all_properties_sync()
      → all properties where pms_type IS NOT NULL
      → returns summary {success, failed, total_duration, per_property}

Each step's exception is captured (the rest still runs) — partial failures
log as status='partial' with an errors[] jsonb of {step, error} entries.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from engine.demand_forecaster import DemandForecaster
from engine.pms.base import PMSConnector
from engine.pms.factory import get_connector
from engine.rate_engine import RateRecommender

logger = logging.getLogger(__name__)


def _sb_headers() -> dict:
    return {
        "apikey":        os.getenv("SUPABASE_SERVICE_KEY", ""),
        "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_KEY','')}",
        "Content-Type":  "application/json",
        "Prefer":        "count=none",
    }


def _sb_url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def _get_tenant_id(property_id: str) -> Optional[str]:
    r = requests.get(f"{_sb_url()}/rest/v1/properties",
                     headers=_sb_headers(),
                     params={"id": f"eq.{property_id}", "select": "tenant_id"},
                     timeout=15)
    if r.ok and r.json():
        return r.json()[0]["tenant_id"]
    return None


def _log_run(
    *,
    tenant_id:    Optional[str],
    property_id:  str,
    pms_type:     str,
    records:      int,
    errors:       list[dict],
    duration_s:   float,
    status:       str,
    metadata:     dict,
) -> Optional[str]:
    """Insert a single summary row into pms_sync_log for the whole daily run."""
    body = {
        "tenant_id":         tenant_id,
        "property_id":       property_id,
        "pms_type":          pms_type,
        "sync_kind":         "daily",
        "sync_date":         date.today().isoformat(),
        "started_at":        (datetime.now(timezone.utc).isoformat()),
        "finished_at":       datetime.now(timezone.utc).isoformat(),
        "duration_seconds":  round(duration_s, 3),
        "records_synced":    records,
        "records_count":     records,  # legacy alias
        "status":            status,
        "errors":            errors or None,
        "error_message":     (errors[0]["error"] if errors else None),
        "metadata":          metadata,
    }
    try:
        r = requests.post(f"{_sb_url()}/rest/v1/pms_sync_log",
                          headers={**_sb_headers(),
                                   "Prefer": "return=representation"},
                          json=body, timeout=20)
        if r.ok and r.text:
            return r.json()[0]["id"]
    except Exception as exc:
        logger.warning("Could not log sync run: %s", exc)
    return None


def run_daily_sync(property_id: str, *, mock: bool = False) -> dict:
    """
    Full daily refresh for one property:
        1. sync_occupancy           (1y back / 1y forward)
        2. sync_guests
        3. sync_current_rates
        4. demand_forecaster.update_recommendations_table
        5. rate_engine.update_all_recommendations

    Each step's failure is captured but the run continues — final status is
    'success' if all steps passed, 'partial' if any step raised, 'failed' if
    the connector could not be constructed at all.

    Returns:
        {
          property_id, pms_type, status,
          records: {occupancy, guests, rates, demand_recs, rate_recs},
          errors: [...],
          duration_seconds, finished_at
        }
    """
    load_dotenv()
    t0 = time.monotonic()
    errors: list[dict] = []
    records = {"occupancy": 0, "guests": 0, "rates": 0,
               "demand_recs": 0, "rate_recs": 0}
    pms_type = "unknown"
    tenant_id = _get_tenant_id(property_id) if not mock else None

    # Construct connector
    try:
        pms: PMSConnector = get_connector(property_id, mock=mock)
        pms_type = pms.PMS_TYPE
    except Exception as exc:
        logger.exception("Could not build connector for %s", property_id)
        duration = time.monotonic() - t0
        _log_run(tenant_id=tenant_id, property_id=property_id,
                 pms_type=pms_type, records=0,
                 errors=[{"step": "get_connector", "error": str(exc)}],
                 duration_s=duration, status="failed",
                 metadata={"mock": mock})
        return {
            "property_id":      property_id,
            "pms_type":         pms_type,
            "status":           "failed",
            "records":          records,
            "errors":           [{"step": "get_connector", "error": str(exc)}],
            "duration_seconds": round(duration, 3),
            "finished_at":      datetime.now(timezone.utc).isoformat(),
        }

    # Step 1 — occupancy
    try:
        records["occupancy"] = pms.sync_occupancy(lookback_days=365,
                                                   lookahead_days=365)
    except Exception as exc:
        logger.exception("sync_occupancy failed")
        errors.append({"step": "sync_occupancy", "error": str(exc)})

    # Step 2 — guests
    try:
        records["guests"] = pms.sync_guests()
    except Exception as exc:
        logger.exception("sync_guests failed")
        errors.append({"step": "sync_guests", "error": str(exc)})

    # Step 3 — current rates
    try:
        summary = pms.sync_current_rates()
        records["rates"] = int(summary.get("updates_applied", 0)
                               or summary.get("rates_fetched", 0))
    except Exception as exc:
        logger.exception("sync_current_rates failed")
        errors.append({"step": "sync_current_rates", "error": str(exc)})

    # Step 4 — demand forecast recompute
    if not mock and tenant_id:
        try:
            df = DemandForecaster()
            records["demand_recs"] = df.update_recommendations_table(
                tenant_id, property_id, days_ahead=90,
            )
        except Exception as exc:
            logger.exception("DemandForecaster failed")
            errors.append({"step": "demand_forecast", "error": str(exc)})
    elif mock:
        # Mock path: skip DB-bound recompute but report the call would have run.
        records["demand_recs"] = 0

    # Step 5 — rate engine recompute
    if not mock and tenant_id:
        try:
            re_ = RateRecommender()
            records["rate_recs"] = re_.update_all_recommendations(
                tenant_id, property_id, days_ahead=90,
            )
        except Exception as exc:
            logger.exception("RateRecommender failed")
            errors.append({"step": "rate_engine", "error": str(exc)})

    duration = time.monotonic() - t0
    total = sum(records.values())
    status = ("success" if not errors
              else ("partial" if total > 0 else "failed"))

    log_id = _log_run(tenant_id=tenant_id, property_id=property_id,
                      pms_type=pms_type, records=total,
                      errors=errors, duration_s=duration, status=status,
                      metadata={"records": records, "mock": mock})

    logger.info("run_daily_sync(%s) → status=%s · records=%s · errors=%d · %.2fs",
                property_id, status, records, len(errors), duration)

    return {
        "property_id":      property_id,
        "pms_type":         pms_type,
        "status":           status,
        "records":          records,
        "errors":           errors,
        "duration_seconds": round(duration, 3),
        "finished_at":      datetime.now(timezone.utc).isoformat(),
        "log_id":           log_id,
    }


def run_all_properties_sync(*, mock: bool = False) -> dict:
    """
    Run daily sync for every property with pms_type set. Returns a summary
    report; per-property results are in `properties[]`.
    """
    load_dotenv()
    t0 = time.monotonic()

    r = requests.get(
        f"{_sb_url()}/rest/v1/properties",
        headers=_sb_headers(),
        params={"select": "id,name,pms_type",
                "pms_type": "not.is.null"},
        timeout=20,
    )
    r.raise_for_status()
    active = r.json() or []
    logger.info("Found %d active PMS-integrated properties", len(active))

    results: list[dict] = []
    success = failed = partial = 0
    for row in active:
        res = run_daily_sync(row["id"], mock=mock)
        results.append({"name": row.get("name"), **res})
        if res["status"] == "success": success += 1
        elif res["status"] == "partial": partial += 1
        else: failed += 1

    duration = time.monotonic() - t0
    return {
        "ran_at":          datetime.now(timezone.utc).isoformat(),
        "properties_count": len(active),
        "success":         success,
        "partial":         partial,
        "failed":          failed,
        "duration_seconds": round(duration, 3),
        "properties":      results,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse, json
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s | %(name)s | %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--property-id", help="Run daily sync for a single property")
    p.add_argument("--all", action="store_true",
                   help="Run daily sync for every PMS-integrated property")
    p.add_argument("--mock", action="store_true",
                   help="Use mock connectors (no live API calls)")
    args = p.parse_args()

    if args.all:
        result = run_all_properties_sync(mock=args.mock)
    elif args.property_id:
        result = run_daily_sync(args.property_id, mock=args.mock)
    else:
        p.error("--property-id or --all required")
        return
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
