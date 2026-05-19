"""
engine/channel/base.py
ChannelManagerConnector — abstract base class for OTA & channel-manager
integrations that push approved rates out to Booking.com, Expedia, VRBO,
Airbnb, etc.

Dataclasses:
    RateUpdate(room_type_id, date, rate, rate_plan_code='BAR')
    PushResult(success, push_id, otas_updated, errors, published_at,
               recommendations_updated)

Concrete subclasses only need to implement vendor-specific HTTP/XML
mapping; this base class wires up the Supabase REST helpers, the
auth-token lifecycle, and the supported-OTA registry.
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime, timezone
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


@dataclass
class RateUpdate:
    """A single rate to push to a channel manager."""
    room_type_id:   str
    date:           _date
    rate:           float
    rate_plan_code: str = "BAR"  # Best Available Rate


@dataclass
class PushResult:
    """Result of a single push_rate / push_rate_bulk call."""
    success:                 bool
    push_id:                 str
    otas_updated:            list[str]     = field(default_factory=list)
    errors:                  list[str]     = field(default_factory=list)
    published_at:            datetime      = field(default_factory=lambda: datetime.now(timezone.utc))
    recommendations_updated: int           = 0

    def to_jsonable(self) -> dict:
        return {
            "success":                 self.success,
            "push_id":                 self.push_id,
            "otas_updated":            list(self.otas_updated),
            "errors":                  list(self.errors),
            "published_at":            self.published_at.isoformat(),
            "recommendations_updated": int(self.recommendations_updated),
        }


class ChannelManagerConnector(ABC):
    """Abstract base for OTA / channel manager connectors."""

    CHANNEL_TYPE: str = "unknown"
    DEFAULT_ENDPOINT: str = ""

    def __init__(
        self,
        property_id: str,
        api_key:     str,
        *,
        endpoint:    Optional[str] = None,
        hotel_code:  Optional[str] = None,
        mock:        bool          = False,
        **kwargs:    Any,
    ) -> None:
        self.property_id = property_id
        self.api_key     = api_key
        self.endpoint    = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
        self.hotel_code  = hotel_code or ""
        self.mock        = mock
        self.extra       = kwargs
        self._session_token: Optional[str] = None

        # Supabase REST creds
        self._sb_url  = os.getenv("SUPABASE_URL", "").rstrip("/")
        self._sb_key  = os.getenv("SUPABASE_SERVICE_KEY", "")
        self._sb_hdrs = {
            "apikey":        self._sb_key,
            "Authorization": f"Bearer {self._sb_key}",
            "Content-Type":  "application/json",
        }

        self._tenant_id: Optional[str] = None
        if not mock and self._sb_url and property_id:
            try:
                rows = self._sb_get("properties",
                                     {"id": f"eq.{property_id}", "select": "tenant_id"})
                if rows:
                    self._tenant_id = rows[0]["tenant_id"]
            except Exception as exc:
                logger.warning("Could not load tenant_id for %s: %s", property_id, exc)

    # ── Abstract methods ─────────────────────────────────────────────────────

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate against the channel manager. Returns True on success."""

    @abstractmethod
    def push_rate(self, room_type_id: str, target_date: _date, rate: float) -> PushResult:
        """Push a single rate (convenience wrapper over push_rate_bulk)."""

    @abstractmethod
    def push_rate_bulk(self, rates: list[RateUpdate]) -> PushResult:
        """Push many rates in one HTTP call. Returns a unified PushResult."""

    @abstractmethod
    def get_push_confirmation(self, push_id: str) -> dict:
        """Fetch the confirmation/echo for a previously pushed batch."""

    @abstractmethod
    def get_supported_otas(self) -> list[str]:
        """Names of OTAs the integration syndicates rates to."""

    def handle_error(self, error: Exception | str) -> None:
        """
        Default error handler — subclasses may override to add vendor-specific
        retry / circuit-breaker logic. Default: log at ERROR level so the
        publisher can capture the message in rate_publish_log.error_message.
        """
        logger.error("[%s] channel manager error: %s", self.CHANNEL_TYPE, error)

    # ── Shared helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _new_push_id() -> str:
        """Generate a stable identifier for a push batch."""
        return f"push_{uuid.uuid4().hex[:16]}"

    def _sb_get(self, table: str, params: dict) -> list[dict]:
        r = requests.get(
            f"{self._sb_url}/rest/v1/{table}",
            headers={**self._sb_hdrs, "Prefer": "count=none"},
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        return r.json() if r.text else []

    def _sb_patch(self, table: str, params: dict, body: dict) -> bool:
        r = requests.patch(
            f"{self._sb_url}/rest/v1/{table}",
            headers={**self._sb_hdrs, "Prefer": "return=minimal"},
            params=params, json=body, timeout=15,
        )
        return r.ok

    def _room_code_for(self, room_type_id: str) -> str:
        """
        Resolve a SHG room_type_id to the code the channel manager expects.

        Preference order:
          1. room_types.external_id (if populated during onboarding)
          2. room_types.name        (fallback — most channel managers will
                                     reject this; flagged in publish log)
        """
        if self.mock:
            return f"MOCK-{room_type_id[:8]}"
        try:
            rows = self._sb_get("room_types",
                                {"id": f"eq.{room_type_id}",
                                 "select": "name,external_id"})
            if not rows:
                return room_type_id
            row = rows[0]
            return row.get("external_id") or row.get("name") or room_type_id
        except Exception as exc:
            logger.warning("room_code lookup failed for %s: %s", room_type_id, exc)
            return room_type_id
