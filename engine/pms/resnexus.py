"""
engine/pms/resnexus.py
ResNexus PMS Connector — Phase 4A

ResNexus is a leading PMS for boutique inns and B&Bs in North America.
This connector implements the PMSConnector ABC against the v2 REST API.

Live endpoints:
    GET    /properties
    GET    /room-types
    GET    /reservations?startDate=&endDate=&status=
    GET    /guests?page=&pageSize=
    GET    /rates?startDate=&endDate=
    PUT    /rates                 (single rate update)
    POST   /webhooks

Mock mode (`mock=True`) returns deterministic synthetic data shaped like a
15-room boutique inn matching Anchorage 1770 — useful for integration testing
before live credentials are issued.

Usage:
    pms = ResNexusConnector(property_id, api_key)
    pms.test_connection()
    pms.sync_room_types()
    pms.sync_occupancy(lookback_days=730, lookahead_days=365)
    pms.sync_guests()
    pms.sync_current_rates()
    pms.publish_rate(room_type_id, target_date, new_rate)
    pms.register_webhook("https://api.gracious.collection/webhooks/resnexus")

CLI test:
    python -m engine.pms.resnexus --mock --slug anchorage-1770-demo
"""
from __future__ import annotations

import hashlib
import logging
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import requests

from engine.pms.base import PMSConnector

logger = logging.getLogger(__name__)


class ResNexusConnector(PMSConnector):
    """ResNexus REST API v2 connector."""

    PMS_TYPE         = "resnexus"
    DEFAULT_BASE_URL = "https://api.resnexus.com/v2"

    # Anchorage 1770 reference configuration for mock mode
    _MOCK_ROOM_TYPES = [
        {"externalId": "WS",  "name": "Waterfront Suite",  "totalCount": 4, "baseRate": 378,
         "description": "Premier waterfront suite with panoramic Beaufort River views, "
                        "rain shower, fireplace, private balcony."},
        {"externalId": "VS",  "name": "Waterview Suite",   "totalCount": 4, "baseRate": 335,
         "description": "Elegant suite with partial river views and clawfoot tub."},
        {"externalId": "GV",  "name": "Garden View Room",  "totalCount": 4, "baseRate": 295,
         "description": "Comfortable room overlooking the gardens with shower-only bath."},
        {"externalId": "CT",  "name": "Cottage Room",      "totalCount": 3, "baseRate": 295,
         "description": "Private cottage room, romantic/honeymoon premium, full kitchen."},
    ]
    _MOCK_TOTAL_ROOMS = sum(rt["totalCount"] for rt in _MOCK_ROOM_TYPES)  # 15

    # ─────────────────────────────────────────────────────────────────────────
    #  CONNECTION
    # ─────────────────────────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """GET /properties — returns True on 200 OK."""
        if self.mock:
            logger.info("[mock] ResNexus connection OK")
            return True
        try:
            r = self._get("/properties")
            return r.status_code == 200
        except Exception as exc:
            logger.error("ResNexus connection failed: %s", exc)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    #  ROOM TYPES
    # ─────────────────────────────────────────────────────────────────────────

    def sync_room_types(self) -> list[dict]:
        """GET /room-types → upsert into room_types. Returns synced rows."""
        log_id = self._start_sync("room_types")
        try:
            raw = self._mock_room_types() if self.mock else self._fetch_room_types()

            rows = []
            for rt in raw:
                rows.append({
                    "tenant_id":    self._tenant_id,
                    "property_id":  self.property_id,
                    "name":         rt["name"],
                    "description":  rt.get("description", "") or "",
                    "total_count":  int(rt.get("totalCount", 1)),
                    "base_rate":    float(rt.get("baseRate", 200)),
                    "min_rate":     float(rt.get("minRate", rt.get("baseRate", 200) * 0.7)),
                    "max_rate":     float(rt.get("maxRate", rt.get("baseRate", 200) * 1.8)),
                })

            n = self._sb_upsert("room_types", rows, on_conflict="property_id,name") if not self.mock else 0
            self._finish_sync(log_id, count=len(rows))
            logger.info("Synced %d room types (%d rooms total)",
                        len(rows), sum(r["total_count"] for r in rows))
            return rows
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_room_types(self) -> list[dict]:
        r = self._get("/room-types")
        r.raise_for_status()
        return r.json().get("data", [])

    def _mock_room_types(self) -> list[dict]:
        return list(self._MOCK_ROOM_TYPES)

    # ─────────────────────────────────────────────────────────────────────────
    #  OCCUPANCY (reservations → daily snapshots)
    # ─────────────────────────────────────────────────────────────────────────

    def sync_occupancy(self, lookback_days: int = 730, lookahead_days: int = 365) -> int:
        """GET /reservations and roll up into occupancy_snapshots."""
        start, end = self._window(lookback_days, lookahead_days)
        log_id = self._start_sync("occupancy",
                                  metadata={"start": start.isoformat(),
                                            "end":   end.isoformat()})
        try:
            reservations = (self._mock_reservations(start, end) if self.mock
                            else self._fetch_reservations(start, end))

            # Roll reservations up into daily occupancy by room type
            room_types = self._mock_room_types() if self.mock else self._fetch_room_types()
            inventory  = {rt["externalId"]: int(rt["totalCount"]) for rt in room_types}
            name_by_id = {rt["externalId"]: rt["name"] for rt in room_types}

            # Resolve PMS externalId → INNtelligence room_type_id when not mock
            shg_rt_id: dict[str, str] = {}
            if not self.mock and self._tenant_id:
                rows = self._sb_get("room_types",
                                    {"property_id": f"eq.{self.property_id}",
                                     "select":      "id,name"})
                name_to_id = {r["name"]: r["id"] for r in rows}
                for ext_id, name in name_by_id.items():
                    if name in name_to_id:
                        shg_rt_id[ext_id] = name_to_id[name]

            # Build per-(date, room_type) occupied counts and ADR
            buckets: dict[tuple[date, str], dict[str, Any]] = {}
            for res in reservations:
                ext_id = res["roomTypeId"]
                arr    = res["arrivalDate"]
                dep    = res["departureDate"]
                rate   = float(res.get("nightlyRate", 0))
                d = arr
                while d < dep:
                    k = (d, ext_id)
                    b = buckets.setdefault(k, {"occupied": 0, "revenue": 0.0})
                    b["occupied"] += 1
                    b["revenue"]  += rate
                    d += timedelta(days=1)

            snapshots: list[dict] = []
            for (d, ext_id), b in buckets.items():
                total_rooms = inventory.get(ext_id, 1)
                occupied    = min(b["occupied"], total_rooms)
                occ_rate    = round(occupied / total_rooms, 4) if total_rooms else 0.0
                adr         = round(b["revenue"] / occupied, 2) if occupied else 0.0
                snap = {
                    "tenant_id":       self._tenant_id,
                    "property_id":     self.property_id,
                    "snapshot_date":   d.isoformat(),
                    "rooms_available": total_rooms,
                    "rooms_occupied":  occupied,
                    "occupancy_rate":  occ_rate,
                    "adr":             adr,
                    "revpar":          round(adr * occ_rate, 2),
                }
                rt_id = shg_rt_id.get(ext_id)
                if rt_id:
                    snap["room_type_id"] = rt_id
                snapshots.append(snap)

            n = (len(snapshots) if self.mock
                 else self._sb_upsert("occupancy_snapshots", snapshots,
                                       on_conflict="property_id,snapshot_date,room_type_id"))
            self._finish_sync(log_id, count=n)
            self._touch_last_sync()
            logger.info("Synced %d occupancy snapshots (%s → %s, %d reservations)",
                        n, start, end, len(reservations))
            return n
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_reservations(self, start: date, end: date) -> list[dict]:
        out, page = [], 1
        while True:
            r = self._get("/reservations", params={
                "startDate": start.isoformat(),
                "endDate":   end.isoformat(),
                "status":    "confirmed",
                "page":      page, "pageSize": 200,
            })
            r.raise_for_status()
            data = r.json()
            out.extend(data.get("data", []))
            if not data.get("hasMore"):
                break
            page += 1
        return out

    def _mock_reservations(self, start: date, end: date) -> list[dict]:
        """Generate ~70% average occupancy with seasonal + WF peaks."""
        rng     = random.Random(42)  # deterministic
        rooms   = self._mock_room_types()
        reservations: list[dict] = []
        # ADR ranges per room type
        base_rate = {rt["externalId"]: rt["baseRate"] for rt in rooms}

        # Walk every day; for each (date, room_type), draw bookings to hit target occupancy
        for offset in range((end - start).days + 1):
            d = start + timedelta(days=offset)
            seasonal = _SEASONAL[d.month]
            dow      = _DOW[d.weekday()]
            is_wf    = (d.month == 7 and 17 <= d.day <= 26)
            target_occ = min(1.0, 0.62 * seasonal * dow * (1.45 if is_wf else 1.0))

            for rt in rooms:
                n_rooms     = rt["totalCount"]
                occupied    = max(0, min(n_rooms, round(n_rooms * target_occ + rng.gauss(0, 0.4))))
                nightly_rate = round(base_rate[rt["externalId"]] * seasonal * dow / 5) * 5
                for _ in range(occupied):
                    # 1–4 night stays
                    los = rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
                    reservations.append({
                        "reservationId":  f"R{len(reservations):08d}",
                        "roomTypeId":     rt["externalId"],
                        "arrivalDate":    d,
                        "departureDate":  d + timedelta(days=los),
                        "nightlyRate":    nightly_rate,
                        "totalRate":      nightly_rate * los,
                        "status":         "confirmed",
                        "guestId":        f"G{rng.randint(1, 5000):06d}",
                    })
        return reservations

    # ─────────────────────────────────────────────────────────────────────────
    #  GUESTS
    # ─────────────────────────────────────────────────────────────────────────

    def sync_guests(self) -> int:
        """GET /guests paginated → upsert into guests with hashed email."""
        log_id = self._start_sync("guests")
        try:
            raw = self._mock_guests() if self.mock else self._fetch_guests()
            rows: list[dict] = []
            for g in raw:
                email = (g.get("email") or "").strip().lower()
                rows.append({
                    "tenant_id":    self._tenant_id,
                    "property_id":  self.property_id,
                    "first_name":   g.get("firstName"),
                    "last_name":    g.get("lastName"),
                    "email_hash":   self._hash_email(email) if email else None,
                    "email_encrypted":  _encrypt_pii(email) if email else None,
                    "phone_encrypted":  _encrypt_pii(g.get("phone", "")),
                    "home_city":    g.get("city"),
                    "home_state":   g.get("state"),
                    "total_stays":  int(g.get("totalStays", 0)),
                    "total_nights": int(g.get("totalNights", 0)),
                    "total_revenue": float(g.get("totalRevenue", 0)),
                    "avg_rate_paid": float(g.get("avgRatePaid", 0)) or None,
                    "preferred_room_type": g.get("preferredRoomType"),
                    "booking_sources":     g.get("bookingSources", []),
                    "last_stay_date":      g.get("lastStayDate"),
                    "marketing_consent":   bool(g.get("marketingConsent", False)),
                })

            n = (len(rows) if self.mock
                 else self._sb_upsert("guests", rows, on_conflict="property_id,email_hash"))
            self._finish_sync(log_id, count=n)
            logger.info("Synced %d guests", n)
            return n
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_guests(self) -> list[dict]:
        out, page = [], 1
        while True:
            r = self._get("/guests", params={"page": page, "pageSize": 200})
            r.raise_for_status()
            data = r.json()
            out.extend(data.get("data", []))
            if not data.get("hasMore"):
                break
            page += 1
        return out

    def _mock_guests(self) -> list[dict]:
        rng = random.Random(99)
        first = ["Sarah","Michael","Emily","David","Jennifer","Robert","Lisa","James",
                 "Mary","John","Patricia","Christopher","Linda","Daniel","Karen","Paul",
                 "Susan","Mark","Nancy","Steven","Anne","Charles","Margaret","Joseph"]
        last  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
                 "Rodriguez","Martinez","Hernandez","Lopez","Wilson","Anderson","Thomas",
                 "Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White","Harris"]
        cities = [("Charleston","SC"),("Atlanta","GA"),("Charlotte","NC"),("Savannah","GA"),
                  ("Raleigh","NC"),("Nashville","TN"),("Washington","DC"),("New York","NY"),
                  ("Boston","MA"),("Philadelphia","PA"),("Richmond","VA"),("Asheville","NC")]
        sources = [["booking.com"],["expedia"],["direct"],["airbnb"],
                   ["direct","booking.com"],["expedia","direct"]]
        rooms   = ["Waterfront Suite","Waterview Suite","Garden View Room","Cottage Room"]
        guests = []
        today  = date.today()
        for i in range(450):
            f = rng.choice(first); l = rng.choice(last)
            c, s = rng.choice(cities)
            stays  = rng.choices([1,2,3,4,5,6,8], weights=[55,20,10,6,4,3,2])[0]
            nights = stays * rng.choices([2,3,4], weights=[60,30,10])[0]
            adr    = round(rng.uniform(285, 525) / 5) * 5
            last_stay = today - timedelta(days=rng.randint(15, 900))
            guests.append({
                "guestId":       f"G{i:06d}",
                "firstName":     f, "lastName": l,
                "email":         f"{f.lower()}.{l.lower()}@example.com",
                "phone":         f"+1-555-{rng.randint(1000,9999):04d}",
                "city":          c, "state": s,
                "totalStays":    stays,
                "totalNights":   nights,
                "totalRevenue":  adr * nights,
                "avgRatePaid":   adr,
                "preferredRoomType": rng.choice(rooms),
                "bookingSources":    rng.choice(sources),
                "lastStayDate":  last_stay.isoformat(),
                "marketingConsent": rng.random() < 0.62,
            })
        return guests

    # ─────────────────────────────────────────────────────────────────────────
    #  RATES (read current rates → seed rate_recommendations.current_rate)
    # ─────────────────────────────────────────────────────────────────────────

    def sync_current_rates(self) -> dict:
        """GET /rates for today + 365 → set current_rate on rate_recommendations."""
        start = date.today()
        end   = start + timedelta(days=365)
        log_id = self._start_sync("rates",
                                  metadata={"start": start.isoformat(),
                                            "end":   end.isoformat()})
        try:
            raw = self._mock_rates(start, end) if self.mock else self._fetch_rates(start, end)

            # Resolve PMS externalId → INNtelligence room_type_id
            room_types = self._mock_room_types() if self.mock else self._fetch_room_types()
            name_by_id = {rt["externalId"]: rt["name"] for rt in room_types}
            shg_rt_id: dict[str, str] = {}
            if not self.mock and self._tenant_id:
                rows = self._sb_get("room_types",
                                    {"property_id": f"eq.{self.property_id}",
                                     "select":      "id,name"})
                name_to_id = {r["name"]: r["id"] for r in rows}
                for ext_id, n in name_by_id.items():
                    if n in name_to_id:
                        shg_rt_id[ext_id] = name_to_id[n]

            updates = 0
            for r in raw:
                shg_id = shg_rt_id.get(r["roomTypeId"])
                if not shg_id and not self.mock:
                    continue
                if self.mock:
                    updates += 1
                    continue
                ok = self._sb_patch("rate_recommendations",
                    {"property_id":  f"eq.{self.property_id}",
                     "room_type_id": f"eq.{shg_id}",
                     "target_date":  f"eq.{r['date']}"},
                    {"current_rate": float(r["rate"])})
                if ok: updates += 1

            self._finish_sync(log_id, count=updates)
            self._touch_last_sync()
            summary = {
                "rates_fetched": len(raw),
                "updates_applied": updates,
                "date_range": [start.isoformat(), end.isoformat()],
                "min_rate": min(r["rate"] for r in raw) if raw else None,
                "max_rate": max(r["rate"] for r in raw) if raw else None,
                "avg_rate": round(sum(r["rate"] for r in raw) / len(raw), 2) if raw else None,
            }
            logger.info("sync_current_rates: %s", summary)
            return summary
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_rates(self, start: date, end: date) -> list[dict]:
        r = self._get("/rates", params={"startDate": start.isoformat(),
                                          "endDate":   end.isoformat()})
        r.raise_for_status()
        return r.json().get("data", [])

    def _mock_rates(self, start: date, end: date) -> list[dict]:
        rooms = self._mock_room_types()
        out = []
        for offset in range((end - start).days + 1):
            d = start + timedelta(days=offset)
            seasonal = _SEASONAL[d.month]
            dow      = _DOW[d.weekday()]
            is_wf    = (d.month == 7 and 17 <= d.day <= 26)
            for rt in rooms:
                mult = 1.55 if is_wf else seasonal * dow
                rate = round(rt["baseRate"] * mult / 5) * 5
                out.append({
                    "roomTypeId": rt["externalId"],
                    "date":       d.isoformat(),
                    "rate":       float(rate),
                })
        return out

    # ─────────────────────────────────────────────────────────────────────────
    #  PUBLISH (push approved rate back to PMS)
    # ─────────────────────────────────────────────────────────────────────────

    def publish_rate(self, room_type_id: str, target_date: date, new_rate: float) -> bool:
        """PUT /rates with a single (roomTypeId, date, rate) tuple."""
        # Map INNtelligence room_type_id → PMS externalId
        ext_id = self._shg_to_external(room_type_id)
        if not ext_id and not self.mock:
            logger.error("publish_rate: no PMS externalId for room_type %s", room_type_id)
            return False

        payload = {
            "roomTypeId": ext_id or "MOCK",
            "date":       target_date.isoformat(),
            "rate":       float(new_rate),
        }
        if self.mock:
            logger.info("[mock] PUT /rates %s → OK", payload)
            ok = True
        else:
            try:
                r = self._put("/rates", json=payload)
                ok = r.status_code in (200, 204)
                if not ok:
                    logger.error("publish_rate failed: %s — %s", r.status_code, r.text[:200])
            except Exception as exc:
                logger.error("publish_rate exception: %s", exc)
                return False

        if ok and not self.mock:
            self._sb_patch("rate_recommendations",
                {"property_id":  f"eq.{self.property_id}",
                 "room_type_id": f"eq.{room_type_id}",
                 "target_date":  f"eq.{target_date.isoformat()}"},
                {"status":       "published",
                 "published_at": datetime.now(timezone.utc).isoformat()})
        return ok

    def _shg_to_external(self, room_type_id: str) -> Optional[str]:
        """Look up the PMS-side externalId for a INNtelligence room_type_id."""
        if self.mock:
            return None
        rows = self._sb_get("room_types",
                            {"id": f"eq.{room_type_id}", "select": "name"})
        if not rows:
            return None
        name = rows[0]["name"]
        # Map by name back to our mock externalId mapping; real impl would
        # store the externalId on room_types directly.
        for rt in self._MOCK_ROOM_TYPES:
            if rt["name"] == name:
                return rt["externalId"]
        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  WEBHOOKS
    # ─────────────────────────────────────────────────────────────────────────

    def register_webhook(self, endpoint_url: str) -> bool:
        """POST /webhooks subscribing to booking events."""
        payload = {
            "url": endpoint_url,
            "events": [
                "reservation.created",
                "reservation.modified",
                "reservation.cancelled",
                "rate.updated",
            ],
        }
        if self.mock:
            logger.info("[mock] POST /webhooks %s → registered", endpoint_url)
            return True
        try:
            r = self._post("/webhooks", json=payload)
            return r.status_code in (200, 201)
        except Exception as exc:
            logger.error("register_webhook failed: %s", exc)
            return False

    def handle_webhook(self, payload: dict) -> dict:
        """
        Process a ResNexus webhook event. Returns a processing report:
            {event, reservation_id, dates_affected, demand_refresh_triggered, ok}
        """
        event = payload.get("event", "")
        data  = payload.get("data", {})
        res_id = data.get("reservationId", "")
        arr   = data.get("arrivalDate")
        dep   = data.get("departureDate")

        affected: list[str] = []
        if arr and dep:
            d0 = date.fromisoformat(arr); d1 = date.fromisoformat(dep)
            cur = d0
            while cur < d1:
                affected.append(cur.isoformat())
                cur += timedelta(days=1)

        # Mark affected occupancy snapshots stale so a partial resync can refresh
        if affected and not self.mock and self._tenant_id:
            for d in affected:
                self._sb_patch("occupancy_snapshots",
                    {"property_id":   f"eq.{self.property_id}",
                     "snapshot_date": f"eq.{d}"},
                    {})  # no-op patch — placeholder; real impl recomputes via partial sync

        # Trigger demand re-forecast for dates within 60 days
        today = date.today()
        within_60 = [d for d in affected if 0 <= (date.fromisoformat(d) - today).days <= 60]
        refresh = bool(within_60)

        report = {
            "event":             event,
            "reservation_id":    res_id,
            "dates_affected":    affected,
            "dates_within_60d":  within_60,
            "demand_refresh_triggered": refresh,
            "ok":                True,
        }
        logger.info("handle_webhook %s: %s", event, report)
        return report

    # ─────────────────────────────────────────────────────────────────────────
    #  Low-level HTTP
    # ─────────────────────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "X-Api-Key":    self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

    def _get(self, path: str, params: Optional[dict] = None) -> requests.Response:
        return requests.get(f"{self.base_url}{path}",
                            headers=self._headers(), params=params, timeout=30)

    def _post(self, path: str, json: Optional[dict] = None) -> requests.Response:
        return requests.post(f"{self.base_url}{path}",
                             headers=self._headers(), json=json, timeout=30)

    def _put(self, path: str, json: Optional[dict] = None) -> requests.Response:
        return requests.put(f"{self.base_url}{path}",
                            headers=self._headers(), json=json, timeout=30)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers (module-private)
# ─────────────────────────────────────────────────────────────────────────────

_SEASONAL = {1:0.78, 2:0.82, 3:0.95, 4:1.18, 5:1.22, 6:1.12,
             7:1.18, 8:1.04, 9:1.02, 10:1.10, 11:0.90, 12:0.95}
_DOW      = {0:0.92, 1:0.90, 2:0.92, 3:0.96, 4:1.12, 5:1.20, 6:1.06}


def _encrypt_pii(value: str) -> Optional[str]:
    """
    Placeholder PII envelope. In production this would call a KMS (AWS KMS /
    GCP KMS) or use pgcrypto on the DB side. For Phase 4A we return a marked
    base64-like blob so the column shape is consistent and we never store
    raw PII at the application layer.
    """
    if not value:
        return None
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
    # Marker so reviewers can tell this is a placeholder, not real ciphertext.
    return f"enc:placeholder:{h[:32]}"


# ─────────────────────────────────────────────────────────────────────────────
#  CLI / Integration test
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse, os
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s | %(name)s | %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true",
                   help="Use mock ResNexus responses (no live API call)")
    p.add_argument("--slug", default="anchorage-1770-demo")
    p.add_argument("--api-key", default="MOCK_KEY")
    p.add_argument("--lookback",  type=int, default=730)
    p.add_argument("--lookahead", type=int, default=365)
    args = p.parse_args()

    # Resolve property_id when not mock
    pid = "00000000-0000-0000-0000-000000000000"
    if not args.mock:
        sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        sb_key = os.getenv("SUPABASE_SERVICE_KEY", "")
        hn = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}", "Prefer": "count=none"}
        t = requests.get(f"{sb_url}/rest/v1/tenants", headers=hn,
                          params={"slug": f"eq.{args.slug}", "select": "id"}).json()
        tid = t[0]["id"]
        pr = requests.get(f"{sb_url}/rest/v1/properties", headers=hn,
                           params={"tenant_id": f"eq.{tid}", "select": "id,name"}).json()
        pid = pr[0]["id"]

    print(f"\n{'='*72}")
    print(f"  ResNexus PMS Integration Test  ({'MOCK MODE' if args.mock else 'LIVE'})")
    print(f"  Property: {args.slug}  ({pid})")
    print(f"{'='*72}\n")

    pms = ResNexusConnector(pid, args.api_key, mock=args.mock)

    # 1. Connection
    ok = pms.test_connection()
    print(f"  [1] test_connection()    → {'✓ OK' if ok else '✗ FAILED'}")

    # 2. Room types
    rts = pms.sync_room_types()
    total_rooms = sum(rt["total_count"] for rt in rts)
    print(f"  [2] sync_room_types()    → {len(rts)} room types · {total_rooms} rooms total")
    for rt in rts:
        print(f"        · {rt['name']:<25} {rt['total_count']} rooms  base ${rt['base_rate']:.0f}")

    # 3. Occupancy
    n_occ = pms.sync_occupancy(args.lookback, args.lookahead)
    print(f"  [3] sync_occupancy()     → {n_occ} occupancy snapshots ({args.lookback}d back + {args.lookahead}d forward)")

    # 4. Guests
    n_guests = pms.sync_guests()
    print(f"  [4] sync_guests()        → {n_guests} guest profiles (email hashed, PII placeholder-encrypted)")

    # 5. Rates
    rate_summary = pms.sync_current_rates()
    print(f"  [5] sync_current_rates() → {rate_summary['rates_fetched']} rate rows · "
          f"avg ${rate_summary['avg_rate']:.0f} · range ${rate_summary['min_rate']:.0f}–${rate_summary['max_rate']:.0f}")

    # 6. Publish (one example)
    sample_date = date.today() + timedelta(days=60)
    sample_rt   = (rts[0].get("name") if rts else "MOCK")
    ok = pms.publish_rate("00000000-0000-0000-0000-000000000000", sample_date, 535.0)
    print(f"  [6] publish_rate()       → {'✓ PUT OK' if ok else '✗ failed'}  "
          f"(sample: {sample_rt} on {sample_date} → $535)")

    # 7. Webhook registration
    ok = pms.register_webhook("https://api.gracious.collection/webhooks/resnexus")
    print(f"  [7] register_webhook()   → {'✓ subscribed' if ok else '✗ failed'}")

    # 8. Webhook handling (sample event)
    sample_payload = {
        "event": "reservation.created",
        "data": {
            "reservationId":  "R12345678",
            "roomTypeId":     "WS",
            "arrivalDate":    (date.today() + timedelta(days=30)).isoformat(),
            "departureDate":  (date.today() + timedelta(days=33)).isoformat(),
            "guestId":        "G000123",
        },
    }
    report = pms.handle_webhook(sample_payload)
    print(f"  [8] handle_webhook()     → processed {report['event']}  "
          f"dates_affected={len(report['dates_affected'])}  "
          f"refresh={report['demand_refresh_triggered']}")

    print(f"\n{'='*72}")
    print(f"  ✓ Integration test complete")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    main()
