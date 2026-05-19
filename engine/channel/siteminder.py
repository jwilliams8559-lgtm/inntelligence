"""
engine/channel/siteminder.py
SiteMinder Channel Connect connector.

SiteMinder distributes rates to ~7 mainstream OTAs through a single XML
push (OTA_HotelRateAmountNotifRQ). One successful push updates every
downstream channel — Booking.com, Expedia, Hotels.com, Airbnb, VRBO,
Trip.com, Agoda — so this is the single most-leveraged connector in
the system for a typical boutique inn.

Auth: per-property hotel_code + API key. The CC API requires a session
token obtained via POST /auth/login; tokens expire so `authenticate`
refreshes when needed and `push_*` invokes it transparently.

Mock mode (mock=True) returns a deterministic ✓ PushResult without
network traffic — useful for the publisher integration tests and the
dashboard demo path.
"""
from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET

import requests

from engine.channel.base import ChannelManagerConnector, PushResult, RateUpdate

logger = logging.getLogger(__name__)


_SITEMINDER_OTAS = [
    "Booking.com", "Expedia", "Airbnb", "VRBO",
    "Hotels.com", "Trip.com", "Agoda",
]


class SiteMinderConnector(ChannelManagerConnector):
    """SiteMinder Channel Connect API (XML push)."""

    CHANNEL_TYPE     = "siteminder"
    DEFAULT_ENDPOINT = "https://api.siteminder.com/cc/v2"

    # ── Auth ────────────────────────────────────────────────────────────────

    def authenticate(self) -> bool:
        """POST /auth/login → session token cached on the instance."""
        if self.mock:
            self._session_token = "MOCK_SITEMINDER_SESSION"
            return True
        try:
            r = requests.post(
                f"{self.endpoint}/auth/login",
                headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
                json={"hotelCode": self.hotel_code},
                timeout=20,
            )
            r.raise_for_status()
            self._session_token = r.json().get("sessionToken")
            return bool(self._session_token)
        except Exception as exc:
            self.handle_error(exc)
            return False

    def _ensure_session(self) -> None:
        if not self._session_token:
            self.authenticate()

    # ── Push ────────────────────────────────────────────────────────────────

    def push_rate(self, room_type_id: str, target_date: _date, rate: float) -> PushResult:
        return self.push_rate_bulk([RateUpdate(room_type_id, target_date, rate)])

    def push_rate_bulk(self, rates: list[RateUpdate]) -> PushResult:
        if not rates:
            return PushResult(success=True, push_id=self._new_push_id(),
                              otas_updated=[], errors=[],
                              recommendations_updated=0)

        push_id = self._new_push_id()
        xml_payload = self._build_xml(rates)
        logger.debug("SiteMinder XML payload (%d rates):\n%s", len(rates), xml_payload)

        if self.mock:
            logger.info("[mock] SiteMinder push %s · %d rates · OTAs=%s",
                        push_id, len(rates), _SITEMINDER_OTAS)
            return PushResult(
                success=True, push_id=push_id,
                otas_updated=list(_SITEMINDER_OTAS),
                errors=[],
                recommendations_updated=len(rates),
            )

        self._ensure_session()
        try:
            r = requests.post(
                f"{self.endpoint}/rates/notify",
                headers={
                    "X-Api-Key":     self.api_key,
                    "Authorization": f"Bearer {self._session_token}",
                    "Content-Type":  "application/xml",
                    "Accept":        "application/xml",
                },
                data=xml_payload.encode("utf-8"),
                timeout=45,
            )
        except Exception as exc:
            self.handle_error(exc)
            return PushResult(False, push_id, [], [str(exc)],
                              recommendations_updated=0)

        otas_updated, errors = self._parse_response(r)
        success = r.ok and not errors
        return PushResult(
            success=success,
            push_id=push_id,
            otas_updated=otas_updated,
            errors=errors,
            recommendations_updated=len(rates) if success else 0,
        )

    def get_push_confirmation(self, push_id: str) -> dict:
        if self.mock:
            return {
                "push_id":      push_id,
                "status":       "confirmed",
                "otas_updated": _SITEMINDER_OTAS,
                "echo_received_at": datetime.now(timezone.utc).isoformat(),
            }
        self._ensure_session()
        try:
            r = requests.get(
                f"{self.endpoint}/rates/status/{push_id}",
                headers={"X-Api-Key": self.api_key,
                         "Authorization": f"Bearer {self._session_token}"},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            self.handle_error(exc)
            return {"push_id": push_id, "status": "unknown", "error": str(exc)}

    def get_supported_otas(self) -> list[str]:
        return list(_SITEMINDER_OTAS)

    # ── XML helpers ─────────────────────────────────────────────────────────

    def _build_xml(self, rates: list[RateUpdate]) -> str:
        """
        Build OTA_HotelRateAmountNotifRQ XML with one RateAmountMessage per
        RateUpdate. Conforms to the OTA 2017A schema that SiteMinder accepts.
        """
        root = ET.Element("HotelRateAmountNotifRQ", attrib={
            "xmlns":     "http://www.opentravel.org/OTA/2003/05",
            "Version":   "1.0",
            "TimeStamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        msgs = ET.SubElement(root, "RateAmountMessages", attrib={
            "HotelCode": self.hotel_code or "UNKNOWN",
        })

        for upd in rates:
            msg = ET.SubElement(msgs, "RateAmountMessage")
            ET.SubElement(msg, "StatusApplicationControl", attrib={
                "RatePlanCode": upd.rate_plan_code,
                "InvTypeCode":  self._room_code_for(upd.room_type_id),
            })
            rates_el = ET.SubElement(msg, "Rates")
            rate_el  = ET.SubElement(rates_el, "Rate")
            base_el  = ET.SubElement(rate_el, "BaseByGuestAmts")
            ET.SubElement(base_el, "BaseByGuestAmt", attrib={
                "AmountAfterTax": f"{upd.rate:.2f}",
                "CurrencyCode":   "USD",
            })
            ET.SubElement(rate_el, "TimeSpan", attrib={
                "Start": upd.date.isoformat(),
                "End":   upd.date.isoformat(),
            })

        # Pretty-print isn't required by the API; keep tight to save bytes.
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def _parse_response(self, r: requests.Response) -> tuple[list[str], list[str]]:
        """Extract `otas_updated` and `errors` from an OTA_HotelRateAmountNotifRS."""
        if not r.text:
            return ([], [f"empty response (status={r.status_code})"])
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError as exc:
            return ([], [f"invalid XML response: {exc}"])

        # Errors element typically appears as <Errors><Error ShortText="..."/></Errors>
        errors: list[str] = []
        for err in root.iter("{*}Error"):
            msg = (err.attrib.get("ShortText")
                   or err.text or err.attrib.get("Code") or "unknown error")
            errors.append(msg.strip())

        # Successful responses carry the OTA list as Distributor children.
        otas = [d.attrib.get("Name") for d in root.iter("{*}Distributor")
                if d.attrib.get("Name")]
        if not otas and not errors:
            otas = list(_SITEMINDER_OTAS)  # default echo set on plain success
        return (otas, errors)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI integration test (mock-only)
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse, json, logging
    from datetime import date, timedelta
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s | %(name)s | %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true", default=True)
    p.add_argument("--hotel-code", default="ANCHORAGE1770DEMO")
    args = p.parse_args()

    cm = SiteMinderConnector(
        property_id="00000000-0000-0000-0000-000000000000",
        api_key="MOCK_API_KEY",
        hotel_code=args.hotel_code,
        mock=args.mock,
    )
    print("authenticate():", cm.authenticate())
    print("supported OTAs:", cm.get_supported_otas())

    sample = [
        RateUpdate("00000000-0000-0000-0000-000000000001",
                   date.today() + timedelta(days=64), 535.0),
        RateUpdate("00000000-0000-0000-0000-000000000001",
                   date.today() + timedelta(days=65), 555.0),
    ]
    result = cm.push_rate_bulk(sample)
    print("\npush_rate_bulk result:")
    print(json.dumps(result.to_jsonable(), indent=2))


if __name__ == "__main__":
    main()
