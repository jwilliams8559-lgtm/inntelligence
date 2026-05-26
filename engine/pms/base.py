"""
engine/pms/base.py
PMSConnector — abstract base class for all PMS integrations.

Provides:
  - Shared constructor (property_id, api_key, base_url, mock)
  - Supabase REST helpers (_get / _post / _patch / _upsert)
  - Sync-log lifecycle (_start_sync / _finish_sync)
  - PII helpers (_hash_email)
  - Abstract methods every PMS must implement

Concrete subclasses (ResNexusConnector, CloudbedsConnector, ...) only need to
implement the vendor-specific HTTP calls and payload mapping.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


class PMSConnector(ABC):
    """Abstract base for all PMS connectors."""

    # Subclasses must set this for sync_log filtering
    PMS_TYPE: str = "unknown"
    DEFAULT_BASE_URL: str = ""

    def __init__(
        self,
        property_id: str,
        api_key:     str,
        *,
        base_url:    Optional[str] = None,
        mock:        bool          = False,
    ) -> None:
        self.property_id = property_id
        self.api_key     = api_key
        self.base_url    = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.mock        = mock

        # Supabase REST credentials
        self._sb_url  = os.getenv("SUPABASE_URL", "").rstrip("/")
        self._sb_key  = os.getenv("SUPABASE_SERVICE_KEY", "")
        self._sb_hdrs = {
            "apikey":        self._sb_key,
            "Authorization": f"Bearer {self._sb_key}",
            "Content-Type":  "application/json",
        }

        # Cache tenant_id lookup once
        self._tenant_id: Optional[str] = None
        if not mock and self._sb_url and property_id:
            try:
                rows = self._sb_get("properties",
                                     {"id": f"eq.{property_id}", "select": "tenant_id"})
                if rows:
                    self._tenant_id = rows[0]["tenant_id"]
            except Exception as exc:
                logger.warning("Could not load tenant_id for %s: %s", property_id, exc)

    # ── Abstract methods every PMS must implement ────────────────────────────

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the PMS API responds OK with current credentials."""

    @abstractmethod
    def sync_room_types(self) -> list[dict]:
        """Pull all room types from PMS → upsert into room_types. Return list."""

    @abstractmethod
    def sync_occupancy(self, lookback_days: int = 730, lookahead_days: int = 365) -> int:
        """Pull reservations + occupancy → upsert into occupancy_snapshots. Return count."""

    @abstractmethod
    def sync_guests(self) -> int:
        """Pull guest list → upsert into guests with hashed email. Return count."""

    @abstractmethod
    def sync_current_rates(self) -> dict:
        """Pull current rates → set current_rate on rate_recommendations. Return summary."""

    @abstractmethod
    def publish_rate(self, room_type_id: str, target_date: date, new_rate: float) -> bool:
        """Push a single rate back to the PMS. Update rate_recommendations on success."""

    @abstractmethod
    def register_webhook(self, endpoint_url: str) -> bool:
        """Subscribe INNtelligence to PMS booking/cancellation webhooks."""

    @abstractmethod
    def handle_webhook(self, payload: dict) -> dict:
        """Process an incoming PMS webhook event; update occupancy and demand."""

    # ── Shared helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _hash_email(email: str) -> str:
        """SHA-256 hex digest of lowercased email — used as a stable dedup key."""
        if not email:
            return ""
        return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()

    def _sb_get(self, table: str, params: dict) -> list[dict]:
        """Supabase REST GET with count=none."""
        r = requests.get(
            f"{self._sb_url}/rest/v1/{table}",
            headers={**self._sb_hdrs, "Prefer": "count=none"},
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        return r.json() if r.text else []

    def _sb_post(self, table: str, rows: list[dict] | dict, *,
                 prefer: str = "return=minimal") -> Optional[list[dict]]:
        """Supabase REST POST (insert)."""
        r = requests.post(
            f"{self._sb_url}/rest/v1/{table}",
            headers={**self._sb_hdrs, "Prefer": prefer},
            json=rows,
            timeout=30,
        )
        if not r.ok:
            logger.warning("Supabase POST %s failed: %s — %s",
                           table, r.status_code, r.text[:200])
            return None
        return r.json() if "representation" in prefer and r.text else None

    def _sb_patch(self, table: str, params: dict, body: dict) -> bool:
        """Supabase REST PATCH (update) by filter."""
        r = requests.patch(
            f"{self._sb_url}/rest/v1/{table}",
            headers={**self._sb_hdrs, "Prefer": "return=minimal"},
            params=params, json=body, timeout=15,
        )
        return r.ok

    def _sb_upsert(self, table: str, rows: list[dict],
                   on_conflict: Optional[str] = None) -> int:
        """Supabase REST upsert (merge-duplicates). Returns number sent."""
        params = {"on_conflict": on_conflict} if on_conflict else {}
        r = requests.post(
            f"{self._sb_url}/rest/v1/{table}",
            headers={**self._sb_hdrs,
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
            params=params, json=rows, timeout=60,
        )
        if not r.ok:
            logger.warning("Upsert %s failed: %s — %s",
                           table, r.status_code, r.text[:300])
            return 0
        return len(rows)

    # ── Sync-log lifecycle ────────────────────────────────────────────────────

    def _start_sync(self, kind: str, metadata: Optional[dict] = None) -> Optional[str]:
        """Insert a 'running' row in pms_sync_log. Returns its id (or None)."""
        if self.mock or not self._tenant_id:
            return None
        out = self._sb_post("pms_sync_log", {
            "tenant_id":   self._tenant_id,
            "property_id": self.property_id,
            "pms_type":    self.PMS_TYPE,
            "sync_kind":   kind,
            "status":      "running",
            "metadata":    metadata or {},
        }, prefer="return=representation")
        return (out[0]["id"]) if out else None

    def _finish_sync(self, log_id: Optional[str], *, count: int = 0,
                     status: str = "success", error: Optional[str] = None) -> None:
        if not log_id:
            return
        self._sb_patch("pms_sync_log", {"id": f"eq.{log_id}"}, {
            "finished_at":  datetime.now(timezone.utc).isoformat(),
            "records_count": count,
            "status":       status,
            "error_message": error,
        })

    def _touch_last_sync(self) -> None:
        """Update properties.pms_last_sync_at to now()."""
        if self.mock or not self.property_id:
            return
        self._sb_patch("properties", {"id": f"eq.{self.property_id}"},
                       {"pms_last_sync_at": datetime.now(timezone.utc).isoformat()})

    # ── Standard date helpers ────────────────────────────────────────────────

    @staticmethod
    def _window(lookback_days: int, lookahead_days: int) -> tuple[date, date]:
        today = date.today()
        return today - timedelta(days=lookback_days), today + timedelta(days=lookahead_days)
