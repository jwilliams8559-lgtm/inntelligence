"""
engine/channel/direct_booking.py
Direct OTA connectors — Booking.com and Expedia.

Use these when a property is NOT on a channel manager (SiteMinder /
Cloudbeds CM). Each connector talks directly to one OTA's partner API
and therefore only updates a small set of OTAs:

    DirectBookingComConnector  → Booking.com
    DirectExpediaConnector     → Expedia + Hotels.com (Expedia Group)

Both follow the same shape as SiteMinderConnector but speak JSON, not
XML, and use vendor-specific auth schemes (Basic for Booking.com,
OAuth-style API key + EQC partner header for Expedia).
"""
from __future__ import annotations

import base64
import logging
from datetime import date as _date
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from engine.channel.base import ChannelManagerConnector, PushResult, RateUpdate

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Booking.com (direct)
# ─────────────────────────────────────────────────────────────────────────────

class DirectBookingComConnector(ChannelManagerConnector):
    """Booking.com Rates & Availability API (direct integration)."""

    CHANNEL_TYPE     = "booking_com_direct"
    DEFAULT_ENDPOINT = "https://supply-xml.booking.com/hotels/xml/rates"

    def __init__(self, property_id: str, api_key: str, *,
                 hotel_id: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(property_id, api_key, **kwargs)
        # Hotel ID may also live in hotel_code field — prefer explicit kwarg.
        self.hotel_id = hotel_id or self.hotel_code or kwargs.get("hotel_code", "")

    def authenticate(self) -> bool:
        """Basic auth — credentials are validated on the first push."""
        if self.mock:
            self._session_token = "MOCK_BDC_TOKEN"
            return True
        if not (self.hotel_id and self.api_key):
            self.handle_error("Booking.com hotel_id / api_key missing")
            return False
        # Cache the encoded header rather than make a probe call.
        token = f"{self.hotel_id}:{self.api_key}".encode("utf-8")
        self._session_token = base64.b64encode(token).decode("ascii")
        return True

    def push_rate(self, room_type_id: str, target_date: _date, rate: float) -> PushResult:
        return self.push_rate_bulk([RateUpdate(room_type_id, target_date, rate)])

    def push_rate_bulk(self, rates: list[RateUpdate]) -> PushResult:
        push_id = self._new_push_id()
        if not rates:
            return PushResult(True, push_id, [], [], recommendations_updated=0)

        payload = {
            "hotel_id": self.hotel_id,
            "rates": [
                {
                    "room_id":        self._room_code_for(u.room_type_id),
                    "rate_plan":      u.rate_plan_code,
                    "date":           u.date.isoformat(),
                    "rate":           round(float(u.rate), 2),
                    "currency":       "USD",
                }
                for u in rates
            ],
        }

        if self.mock:
            logger.info("[mock] Booking.com push %s · %d rates", push_id, len(rates))
            return PushResult(
                success=True, push_id=push_id,
                otas_updated=["Booking.com"], errors=[],
                recommendations_updated=len(rates),
            )

        if not self._session_token:
            self.authenticate()
        try:
            r = requests.post(
                self.endpoint,
                headers={"Authorization": f"Basic {self._session_token}",
                         "Content-Type":  "application/json",
                         "Accept":        "application/json"},
                json=payload, timeout=45,
            )
        except Exception as exc:
            self.handle_error(exc)
            return PushResult(False, push_id, [], [str(exc)])

        body = r.json() if r.text else {}
        if r.ok and not body.get("errors"):
            return PushResult(True, push_id, ["Booking.com"], [],
                              recommendations_updated=len(rates))
        errors = body.get("errors") or [f"HTTP {r.status_code}: {r.text[:160]}"]
        return PushResult(False, push_id, [], list(map(str, errors)))

    def get_push_confirmation(self, push_id: str) -> dict:
        if self.mock:
            return {"push_id": push_id, "status": "confirmed",
                    "otas_updated": ["Booking.com"],
                    "echo_received_at": datetime.now(timezone.utc).isoformat()}
        # Booking.com supply-xml is fire-and-forget; echo not separately polled.
        return {"push_id": push_id, "status": "ack-only"}

    def get_supported_otas(self) -> list[str]:
        return ["Booking.com"]


# ─────────────────────────────────────────────────────────────────────────────
#  Expedia (direct — also pushes to Hotels.com via Expedia Group)
# ─────────────────────────────────────────────────────────────────────────────

class DirectExpediaConnector(ChannelManagerConnector):
    """Expedia Partner Central — Rates & Availability API (direct integration)."""

    CHANNEL_TYPE     = "expedia_direct"
    DEFAULT_ENDPOINT = "https://services.expediapartnercentral.com/eqc/ar"

    def __init__(self, property_id: str, api_key: str, *,
                 hotel_id: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(property_id, api_key, **kwargs)
        self.hotel_id = hotel_id or self.hotel_code or kwargs.get("hotel_code", "")

    def authenticate(self) -> bool:
        if self.mock:
            self._session_token = "MOCK_EXPEDIA_TOKEN"
            return True
        if not (self.hotel_id and self.api_key):
            self.handle_error("Expedia hotel_id / api_key missing")
            return False
        self._session_token = self.api_key  # EQC uses API key in header directly
        return True

    def push_rate(self, room_type_id: str, target_date: _date, rate: float) -> PushResult:
        return self.push_rate_bulk([RateUpdate(room_type_id, target_date, rate)])

    def push_rate_bulk(self, rates: list[RateUpdate]) -> PushResult:
        push_id = self._new_push_id()
        if not rates:
            return PushResult(True, push_id, [], [], recommendations_updated=0)

        payload = {
            "hotelId": self.hotel_id,
            "ar": [
                {
                    "roomTypeId":  self._room_code_for(u.room_type_id),
                    "ratePlanId":  u.rate_plan_code,
                    "date":        u.date.isoformat(),
                    "rate":        round(float(u.rate), 2),
                    "currency":    "USD",
                }
                for u in rates
            ],
        }

        if self.mock:
            logger.info("[mock] Expedia push %s · %d rates", push_id, len(rates))
            return PushResult(
                success=True, push_id=push_id,
                otas_updated=["Expedia", "Hotels.com"], errors=[],
                recommendations_updated=len(rates),
            )

        if not self._session_token:
            self.authenticate()
        try:
            r = requests.post(
                f"{self.endpoint}/{self.hotel_id}",
                headers={"Authorization": f"EQC {self._session_token}",
                         "Content-Type":  "application/json",
                         "Accept":        "application/json"},
                json=payload, timeout=45,
            )
        except Exception as exc:
            self.handle_error(exc)
            return PushResult(False, push_id, [], [str(exc)])

        body = r.json() if r.text else {}
        if r.ok and not body.get("errors"):
            return PushResult(True, push_id, ["Expedia", "Hotels.com"], [],
                              recommendations_updated=len(rates))
        errors = body.get("errors") or [f"HTTP {r.status_code}: {r.text[:160]}"]
        return PushResult(False, push_id, [], list(map(str, errors)))

    def get_push_confirmation(self, push_id: str) -> dict:
        if self.mock:
            return {"push_id": push_id, "status": "confirmed",
                    "otas_updated": ["Expedia", "Hotels.com"],
                    "echo_received_at": datetime.now(timezone.utc).isoformat()}
        return {"push_id": push_id, "status": "ack-only"}

    def get_supported_otas(self) -> list[str]:
        return ["Expedia", "Hotels.com"]
