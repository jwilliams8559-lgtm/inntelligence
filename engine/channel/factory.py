"""
engine/channel/factory.py
DB-backed factory for the channel manager / OTA connector.

Reads properties.channel_manager_type (added in migration 005) plus the
vendor-specific credential columns and instantiates the right
ChannelManagerConnector subclass.

Supported channel_manager_type values:
    'siteminder'         → SiteMinderConnector
    'booking_com_direct' → DirectBookingComConnector
    'expedia_direct'     → DirectExpediaConnector
    'cloudbeds_cm'       → not yet implemented (raises NotImplementedError)
    'none' / NULL        → ValueError with onboarding hint
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from engine.channel.base import ChannelManagerConnector
from engine.channel.direct_booking import DirectBookingComConnector, DirectExpediaConnector
from engine.channel.siteminder import SiteMinderConnector

logger = logging.getLogger(__name__)

_SUPPORTED = {
    "siteminder":         SiteMinderConnector,
    "booking_com_direct": DirectBookingComConnector,
    "expedia_direct":     DirectExpediaConnector,
}


def _sb_url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def _sb_hdrs() -> dict:
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Prefer": "count=none"}


def get_channel_connector(
    property_id: str,
    *,
    mock:    bool          = False,
    db_conn: Any           = None,   # kept for API compatibility; not used (REST)
) -> ChannelManagerConnector:
    """
    Look up the channel manager configuration for *property_id* and return
    a ready-to-push connector. The optional ``db_conn`` parameter is part of
    the published contract but ignored — this codebase uses Supabase REST.

    Raises:
        ValueError      — property missing, channel_manager_type unset/'none'
        RuntimeError    — Supabase credentials missing in env
        NotImplementedError — recognised but unimplemented channel type
    """
    load_dotenv()
    if not _sb_url() or not os.getenv("SUPABASE_SERVICE_KEY"):
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")

    r = requests.get(
        f"{_sb_url()}/rest/v1/properties",
        headers=_sb_hdrs(),
        params={
            "id":     f"eq.{property_id}",
            "select": "id,name,channel_manager_type,channel_manager_api_key,"
                      "siteminder_hotel_code,booking_com_hotel_id,"
                      "expedia_hotel_id",
        },
        timeout=15,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError(f"Property {property_id} not found")
    row = rows[0]

    cm_type = (row.get("channel_manager_type") or "").strip().lower()
    if not cm_type or cm_type == "none":
        raise ValueError(
            f"Property '{row.get('name')}' has no channel manager configured. "
            "Set channel_manager_type via the onboarding wizard before "
            "publishing rates. Supported: " + ", ".join(_SUPPORTED.keys())
        )
    if cm_type == "cloudbeds_cm":
        raise NotImplementedError(
            "Cloudbeds-as-channel-manager is not yet implemented. "
            "Use the PMS Cloudbeds integration for now."
        )
    if cm_type not in _SUPPORTED:
        raise ValueError(
            f"Unsupported channel_manager_type: {cm_type!r}. "
            f"Supported: {sorted(_SUPPORTED.keys())}"
        )

    api_key = row.get("channel_manager_api_key") or ""

    if cm_type == "siteminder":
        return SiteMinderConnector(
            property_id, api_key,
            hotel_code=row.get("siteminder_hotel_code") or "",
            mock=mock,
        )
    if cm_type == "booking_com_direct":
        return DirectBookingComConnector(
            property_id, api_key,
            hotel_id=row.get("booking_com_hotel_id") or "",
            mock=mock,
        )
    if cm_type == "expedia_direct":
        return DirectExpediaConnector(
            property_id, api_key,
            hotel_id=row.get("expedia_hotel_id") or "",
            mock=mock,
        )
    # Unreachable — guarded by the dict membership check above.
    raise ValueError(f"Unsupported channel_manager_type: {cm_type!r}")


__all__ = ["get_channel_connector"]
