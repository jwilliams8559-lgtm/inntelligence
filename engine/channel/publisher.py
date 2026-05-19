"""
engine/channel/publisher.py
Rate publish workflow.

Public API:
    publish_approved_rate(recommendation_id, mock=False) -> PushResult
        - Fetches the recommendation + room/property/tenant context
        - Looks up the channel connector via factory
        - Calls push_rate_bulk([RateUpdate])
        - Logs to rate_publish_log
        - Updates rate_recommendations.status to 'published' / 'publish_failed'

    publish_all_pending(property_id, date_from=None, date_to=None, mock=False) -> dict
        - Fetches all pending/approved recommendations for the property
          (optionally filtered by date range)
        - Groups by room_type for one bulk push per room_type
        - Logs each batch result to rate_publish_log
        - Updates each recommendation's status
        - Returns {total, published, failed, skipped, batches:[...]}
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date as _date
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from engine.channel.base import ChannelManagerConnector, PushResult, RateUpdate
from engine.channel.factory import get_channel_connector

logger = logging.getLogger(__name__)


def _sb_url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def _sb_hdrs() -> dict:
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"}


def _sb_get(table: str, params: dict) -> list[dict]:
    r = requests.get(f"{_sb_url()}/rest/v1/{table}",
                     headers={**_sb_hdrs(), "Prefer": "count=none"},
                     params=params, timeout=20)
    r.raise_for_status()
    return r.json() if r.text else []


def _sb_post(table: str, body: dict | list[dict], *,
             prefer: str = "return=minimal") -> Optional[list[dict]]:
    r = requests.post(f"{_sb_url()}/rest/v1/{table}",
                      headers={**_sb_hdrs(), "Prefer": prefer},
                      json=body, timeout=20)
    if not r.ok:
        logger.warning("Supabase POST %s failed: %s — %s",
                       table, r.status_code, r.text[:200])
        return None
    return r.json() if "representation" in prefer and r.text else None


def _sb_patch(table: str, params: dict, body: dict) -> bool:
    r = requests.patch(f"{_sb_url()}/rest/v1/{table}",
                       headers={**_sb_hdrs(), "Prefer": "return=minimal"},
                       params=params, json=body, timeout=20)
    return r.ok


def _log_publish(
    *,
    tenant_id:         Optional[str],
    property_id:       str,
    recommendation_id: Optional[str],
    channel_manager:   str,
    result:            PushResult,
    error:             Optional[str] = None,
    status_override:   Optional[str] = None,
) -> Optional[str]:
    """Insert a row into rate_publish_log; return its id (or None)."""
    status = status_override or (
        "success" if result.success and not result.errors
        else ("partial" if result.success and result.errors else "failed")
    )
    body = {
        "tenant_id":         tenant_id,
        "property_id":       property_id,
        "recommendation_id": recommendation_id,
        "channel_manager":   channel_manager,
        "status":            status,
        "otas_updated":      result.otas_updated or [],
        "response_body":     result.to_jsonable(),
        "published_at":      result.published_at.isoformat(),
        "error_message":     error or ("; ".join(result.errors) if result.errors else None),
    }
    out = _sb_post("rate_publish_log", body, prefer="return=representation")
    return out[0]["id"] if out else None


# ─────────────────────────────────────────────────────────────────────────────
#  publish_approved_rate
# ─────────────────────────────────────────────────────────────────────────────

def publish_approved_rate(
    recommendation_id: str,
    *,
    mock:    bool = False,
    db_conn: Any  = None,    # kept for API compatibility — REST is used
) -> PushResult:
    """
    Publish a single rate_recommendation to its property's channel manager.

    Side effects:
        - rate_publish_log row inserted (success/partial/failed)
        - rate_recommendations.status set to 'published' or 'publish_failed'
        - rate_recommendations.published_at set on success

    Returns the PushResult exactly as the connector produced it (with the
    `published_at` set to the publish timestamp).
    """
    load_dotenv()

    rows = _sb_get("rate_recommendations", {
        "id":     f"eq.{recommendation_id}",
        "select": "id,tenant_id,property_id,room_type_id,target_date,"
                  "recommended_rate,status",
    })
    if not rows:
        msg = f"recommendation {recommendation_id} not found"
        logger.error(msg)
        return PushResult(False, "no_push", [], [msg])
    rec = rows[0]

    if rec.get("recommended_rate") is None:
        msg = f"recommendation {recommendation_id} has no recommended_rate"
        logger.warning(msg)
        return PushResult(False, "no_push", [], [msg])

    # Build connector
    try:
        cm = get_channel_connector(rec["property_id"], mock=mock)
    except (ValueError, NotImplementedError, RuntimeError) as exc:
        logger.error("Could not build channel connector: %s", exc)
        result = PushResult(False, "no_push", [], [str(exc)])
        _log_publish(
            tenant_id=rec.get("tenant_id"),
            property_id=rec["property_id"],
            recommendation_id=rec["id"],
            channel_manager="unknown",
            result=result, error=str(exc),
        )
        return result

    # Push
    update = RateUpdate(
        room_type_id=rec["room_type_id"],
        date=_date.fromisoformat(rec["target_date"]),
        rate=float(rec["recommended_rate"]),
    )
    result = cm.push_rate_bulk([update])

    # Log
    log_id = _log_publish(
        tenant_id=rec.get("tenant_id"),
        property_id=rec["property_id"],
        recommendation_id=rec["id"],
        channel_manager=cm.CHANNEL_TYPE,
        result=result,
    )

    # Update recommendation status
    if result.success:
        _sb_patch("rate_recommendations", {"id": f"eq.{rec['id']}"}, {
            "status":       "published",
            "published_at": result.published_at.isoformat(),
        })
        logger.info("Published rec %s via %s · OTAs=%s · log=%s",
                    rec["id"], cm.CHANNEL_TYPE, result.otas_updated, log_id)
    else:
        _sb_patch("rate_recommendations", {"id": f"eq.{rec['id']}"}, {
            "status": "publish_failed",
        })
        logger.warning("Publish FAILED rec %s via %s · errors=%s",
                       rec["id"], cm.CHANNEL_TYPE, result.errors)

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  publish_all_pending
# ─────────────────────────────────────────────────────────────────────────────

def publish_all_pending(
    property_id: str,
    *,
    date_from: Optional[_date] = None,
    date_to:   Optional[_date] = None,
    statuses:  tuple[str, ...] = ("pending", "approved"),
    mock:      bool            = False,
    db_conn:   Any             = None,
) -> dict:
    """
    Bulk-publish every pending / approved recommendation for *property_id*.

    Recommendations are grouped by room_type so each channel manager push
    contains all dates for one room_type — far fewer HTTP calls than
    per-recommendation publishing.

    Returns a summary dict:
        {
          property_id, channel_manager,
          total,    published,    failed,    skipped,
          batches:  [ {room_type_id, push_id, success, otas_updated,
                       records_count, errors:[...]}, ... ],
          duration_seconds, ran_at
        }
    """
    load_dotenv()
    started = datetime.now(timezone.utc)
    import time
    t0 = time.monotonic()

    # Connector
    try:
        cm = get_channel_connector(property_id, mock=mock)
    except (ValueError, NotImplementedError, RuntimeError) as exc:
        logger.error("publish_all_pending: factory failed — %s", exc)
        return {
            "property_id":     property_id,
            "channel_manager": "unknown",
            "total":           0, "published": 0, "failed": 0, "skipped": 0,
            "batches":         [],
            "error":           str(exc),
            "duration_seconds": 0.0,
            "ran_at":          started.isoformat(),
        }

    # Fetch
    params = {
        "property_id": f"eq.{property_id}",
        "status":      f"in.({','.join(statuses)})",
        "select":      "id,tenant_id,room_type_id,target_date,recommended_rate,status",
        "order":       "target_date.asc",
    }
    if date_from:
        params["target_date"] = f"gte.{date_from.isoformat()}"
        if date_to:
            params["and"] = f"(target_date.lte.{date_to.isoformat()})"
    elif date_to:
        params["target_date"] = f"lte.{date_to.isoformat()}"

    recs = _sb_get("rate_recommendations", params)
    if not recs:
        return {
            "property_id":     property_id,
            "channel_manager": cm.CHANNEL_TYPE,
            "total":           0, "published": 0, "failed": 0, "skipped": 0,
            "batches":         [],
            "duration_seconds": round(time.monotonic() - t0, 3),
            "ran_at":          started.isoformat(),
        }

    # Group by room_type — skip recs missing a recommended_rate.
    grouped: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    for r in recs:
        if r.get("recommended_rate") is None:
            skipped += 1
            continue
        grouped[r["room_type_id"]].append(r)

    tenant_id = recs[0].get("tenant_id")

    batches:    list[dict] = []
    published   = 0
    failed      = 0

    for room_type_id, group in grouped.items():
        updates = [
            RateUpdate(
                room_type_id=r["room_type_id"],
                date=_date.fromisoformat(r["target_date"]),
                rate=float(r["recommended_rate"]),
            )
            for r in group
        ]
        result = cm.push_rate_bulk(updates)

        # Log one rate_publish_log row for this room_type batch (no per-rec id).
        _log_publish(
            tenant_id=tenant_id, property_id=property_id,
            recommendation_id=None, channel_manager=cm.CHANNEL_TYPE,
            result=result,
        )

        if result.success:
            published += len(group)
            # Bulk-mark this room_type's recs as published
            ids_filter = ",".join(r["id"] for r in group)
            _sb_patch("rate_recommendations",
                      {"id": f"in.({ids_filter})"},
                      {"status": "published",
                       "published_at": result.published_at.isoformat()})
        else:
            failed += len(group)
            ids_filter = ",".join(r["id"] for r in group)
            _sb_patch("rate_recommendations",
                      {"id": f"in.({ids_filter})"},
                      {"status": "publish_failed"})
            logger.warning("Bulk publish FAILED room_type=%s · %d recs · errors=%s",
                           room_type_id, len(group), result.errors)

        batches.append({
            "room_type_id":  room_type_id,
            "push_id":       result.push_id,
            "success":       result.success,
            "otas_updated":  result.otas_updated,
            "records_count": len(group),
            "errors":        result.errors,
        })

    duration = time.monotonic() - t0
    summary = {
        "property_id":      property_id,
        "channel_manager":  cm.CHANNEL_TYPE,
        "total":            published + failed + skipped,
        "published":        published,
        "failed":           failed,
        "skipped":          skipped,
        "batches":          batches,
        "duration_seconds": round(duration, 3),
        "ran_at":           started.isoformat(),
    }
    logger.info("publish_all_pending(%s) → %s", property_id, summary)
    return summary


__all__ = ["publish_approved_rate", "publish_all_pending"]
