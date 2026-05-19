"""
engine/pms/factory.py — Phase 4C

DB-backed PMS connector factory. Given a property_id, reads pms_type +
pms_api_key + pms_base_url (and Cloudbeds-specific pms_refresh_token /
pms_external_id) from the properties row and returns a ready-to-use connector.

Public API:
    get_connector(property_id, *, mock=False) -> PMSConnector
        Reads properties.pms_type from DB. Raises ValueError if pms_type is
        not configured for the property or is not a supported integration.

The stateless `engine.pms.__init__.get_connector(property_id, pms_type, api_key)`
factory is preserved for callers that already have credentials in hand (e.g.
the onboarding wizard during OAuth callback, before the row exists). This
module's `get_connector` is the runtime-DB-lookup variant used by the
scheduler and webhook handlers.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests
from dotenv import load_dotenv

from engine.pms.base import PMSConnector
from engine.pms.cloudbeds import CloudbedsConnector
from engine.pms.resnexus import ResNexusConnector

logger = logging.getLogger(__name__)

_SUPPORTED = {
    "resnexus":  ResNexusConnector,
    "cloudbeds": CloudbedsConnector,
}


def get_connector(property_id: str, *, mock: bool = False) -> PMSConnector:
    """
    Look up the PMS configuration for *property_id* and return the matching
    connector. Raises ValueError when the property has no PMS configured or
    the pms_type is unsupported.

    Lookup columns (properties table):
        pms_type, pms_api_key, pms_base_url,
        pms_refresh_token, pms_external_id   (Cloudbeds only)
    """
    load_dotenv()
    sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    sb_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not sb_url or not sb_key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")

    r = requests.get(
        f"{sb_url}/rest/v1/properties",
        headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                 "Prefer": "count=none"},
        params={
            "id":     f"eq.{property_id}",
            "select": "pms_type,pms_api_key,pms_base_url,"
                      "pms_refresh_token,pms_external_id",
        },
        timeout=15,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError(f"Property {property_id} not found")

    row = rows[0]
    pms_type = (row.get("pms_type") or "").strip().lower()
    if not pms_type:
        raise ValueError(f"Property {property_id} has no pms_type configured")
    if pms_type not in _SUPPORTED:
        raise ValueError(f"Unsupported PMS type: {pms_type!r}. "
                         f"Supported: {sorted(_SUPPORTED.keys())}")

    api_key  = row.get("pms_api_key") or ""
    base_url = row.get("pms_base_url") or None

    if pms_type == "cloudbeds":
        return CloudbedsConnector(
            property_id, api_key,
            base_url=base_url, mock=mock,
            refresh_token=row.get("pms_refresh_token"),
            cb_property_id=row.get("pms_external_id"),
        )
    cls = _SUPPORTED[pms_type]
    return cls(property_id, api_key, base_url=base_url, mock=mock)


__all__ = ["get_connector"]
