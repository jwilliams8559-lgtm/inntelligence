"""
engine/pms — Property Management System integrations for The Gracious Collection.

Each PMS vendor implements the PMSConnector abstract base class:
  - ResNexus      — engine.pms.resnexus.ResNexusConnector
  - Cloudbeds     — engine.pms.cloudbeds.CloudbedsConnector (Phase 4B)
  - Little Hotelier, Mews, ThinkReservations — Phase 4C+

Usage:
    from engine.pms import get_connector
    pms = get_connector(property_id="...", pms_type="resnexus", api_key="...")
    pms.test_connection()
    pms.sync_room_types()
"""
from __future__ import annotations

from typing import Optional

from engine.pms.base import PMSConnector
from engine.pms.cloudbeds import CloudbedsConnector
from engine.pms.resnexus import ResNexusConnector

__all__ = [
    "PMSConnector",
    "ResNexusConnector",
    "CloudbedsConnector",
    "get_connector",
]


def get_connector(
    property_id: str,
    pms_type:    str,
    api_key:     str,
    *,
    base_url:    Optional[str] = None,
    mock:        bool          = False,
    **kwargs:    object,
) -> PMSConnector:
    """
    Stateless factory: return the appropriate PMSConnector subclass for
    *pms_type* given credentials in hand. For DB-backed lookup (reading
    pms_type from the properties row), use engine.pms.factory.get_connector.
    Raises ValueError for unknown PMS types.
    """
    pms_type = (pms_type or "").strip().lower()
    if pms_type == "resnexus":
        return ResNexusConnector(property_id, api_key, base_url=base_url, mock=mock)
    if pms_type == "cloudbeds":
        return CloudbedsConnector(
            property_id, api_key,
            base_url=base_url, mock=mock,
            refresh_token=kwargs.get("refresh_token"),
            cb_property_id=kwargs.get("cb_property_id"),
        )
    # Future: little_hotelier, mews, thinkreservations
    raise ValueError(f"Unknown PMS type: {pms_type!r}")
