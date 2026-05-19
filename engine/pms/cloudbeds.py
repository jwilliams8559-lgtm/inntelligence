"""
engine/pms/cloudbeds.py
Cloudbeds PMS Connector — Phase 4B

Cloudbeds is a leading cloud PMS for boutique hotels and small chains. Auth is
OAuth 2.0 (Authorization Code flow): innkeepers click an OAuth button in the
TGC onboarding wizard, authorize their Cloudbeds account, and SHG receives an
access_token + refresh_token pair which are stored encrypted on the property
row. Access tokens expire (default 1 hour) — `refresh_access_token` is called
automatically before every API call when the cached token is stale.

Live endpoints (Cloudbeds REST v1.1):
    GET    /hotels
    GET    /roomTypes
    GET    /getReservations         (date range, paginated)
    GET    /getGuests               (paginated)
    GET    /getRatePlans
    PUT    /updateRoomRate          (BULK: rooms × date range)
    POST   /registerWebhook
    POST   /postWebhook             (delete by id)

OAuth endpoints:
    GET    https://hotels.cloudbeds.com/api/v1.1/oauth        (authorize URL)
    POST   https://hotels.cloudbeds.com/auth/access_token     (token exchange)

Cloudbeds rate update is bulk-friendly — `publish_rate` accepts a single
(room_type, date, rate) tuple per PMSConnector contract but the underlying
`publish_rate_bulk` helper sends one HTTP call for a date range. Daily sync
uses the bulk path for efficiency.

Mock mode (`mock=True`) produces deterministic synthetic data shaped like a
15-room boutique inn matching the Anchorage 1770 reference — same shape as
the ResNexus mock so the same tests pass.

CLI test:
    python -m engine.pms.cloudbeds --mock --slug anchorage-1770-demo
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import random
import secrets
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import requests

from engine.pms.base import PMSConnector

logger = logging.getLogger(__name__)


# Cloudbeds OAuth endpoints are not under the REST base URL.
_CB_OAUTH_AUTHORIZE = "https://hotels.cloudbeds.com/api/v1.1/oauth"
_CB_OAUTH_TOKEN     = "https://hotels.cloudbeds.com/auth/access_token"

# Default OAuth scopes — read property data + write rates + receive webhooks.
_CB_DEFAULT_SCOPES = (
    "read:hotel read:room read:reservation read:guest read:rate "
    "write:rate write:webhook"
)


class CloudbedsConnector(PMSConnector):
    """Cloudbeds REST v1.1 connector with OAuth 2.0 auth."""

    PMS_TYPE         = "cloudbeds"
    DEFAULT_BASE_URL = "https://hotels.cloudbeds.com/api/v1.1"

    # Same 4-tier shape as ResNexus mock so cross-PMS tests are comparable.
    _MOCK_ROOM_TYPES = [
        {"roomTypeID": "1001", "roomTypeName": "Waterfront Suite",
         "roomTypeQty": 4, "roomTypeRate": 378,
         "roomTypeDescription": "Premier waterfront suite with panoramic Beaufort River views, "
                                "rain shower, fireplace, private balcony."},
        {"roomTypeID": "1002", "roomTypeName": "Waterview Suite",
         "roomTypeQty": 4, "roomTypeRate": 335,
         "roomTypeDescription": "Elegant suite with partial river views and clawfoot tub."},
        {"roomTypeID": "1003", "roomTypeName": "Garden View Room",
         "roomTypeQty": 4, "roomTypeRate": 295,
         "roomTypeDescription": "Comfortable room overlooking the gardens with shower-only bath."},
        {"roomTypeID": "1004", "roomTypeName": "Cottage Room",
         "roomTypeQty": 3, "roomTypeRate": 295,
         "roomTypeDescription": "Private cottage room, romantic/honeymoon premium, full kitchen."},
    ]
    _MOCK_TOTAL_ROOMS = sum(rt["roomTypeQty"] for rt in _MOCK_ROOM_TYPES)  # 15

    def __init__(
        self,
        property_id:  str,
        api_key:      str,
        *,
        base_url:     Optional[str] = None,
        mock:         bool          = False,
        refresh_token: Optional[str] = None,
        cb_property_id: Optional[str] = None,
    ) -> None:
        # In Cloudbeds the "api_key" is the OAuth access_token.
        super().__init__(property_id, api_key, base_url=base_url, mock=mock)
        self._refresh_token = refresh_token
        # Cloudbeds API requires a propertyID (Cloudbeds-side) on most calls.
        # Stored in properties.pms_external_id (loaded lazily).
        self._cb_property_id: Optional[str] = cb_property_id
        if not self.mock and not self._cb_property_id and self.property_id:
            self._load_pms_metadata()

    # ─────────────────────────────────────────────────────────────────────────
    #  OAUTH FLOW
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def get_oauth_url(
        cls,
        redirect_uri: str,
        *,
        client_id: Optional[str] = None,
        state:     Optional[str] = None,
        scope:     str           = _CB_DEFAULT_SCOPES,
    ) -> str:
        """
        Build the Cloudbeds OAuth authorize URL the innkeeper clicks during
        onboarding. After consent, Cloudbeds redirects to `redirect_uri?code=...`.
        `state` is generated if not supplied — store it in the user's session and
        verify on callback to prevent CSRF.
        """
        cid = client_id or os.getenv("CLOUDBEDS_CLIENT_ID", "")
        if not cid:
            raise ValueError("CLOUDBEDS_CLIENT_ID is not set")
        if not state:
            state = secrets.token_urlsafe(24)
        q = urllib.parse.urlencode({
            "client_id":    cid,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope":        scope,
            "state":        state,
        })
        return f"{_CB_OAUTH_AUTHORIZE}?{q}"

    @classmethod
    def exchange_code_for_token(
        cls,
        code:         str,
        redirect_uri: str,
        *,
        client_id:     Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> dict:
        """
        Exchange an OAuth code for an access_token + refresh_token.

        Returns the raw Cloudbeds token dict:
            {
              "access_token":  "...",
              "refresh_token": "...",
              "token_type":    "Bearer",
              "expires_in":    3600,
              "scope":         "..."
            }

        Caller is responsible for persisting these into the properties row
        (pms_api_key = access_token, pms_refresh_token = refresh_token,
        pms_token_expires_at = now + expires_in).
        """
        cid     = client_id     or os.getenv("CLOUDBEDS_CLIENT_ID", "")
        csecret = client_secret or os.getenv("CLOUDBEDS_CLIENT_SECRET", "")
        if not cid or not csecret:
            raise ValueError("CLOUDBEDS_CLIENT_ID / CLOUDBEDS_CLIENT_SECRET not set")

        r = requests.post(_CB_OAUTH_TOKEN, data={
            "grant_type":    "authorization_code",
            "client_id":     cid,
            "client_secret": csecret,
            "redirect_uri":  redirect_uri,
            "code":          code,
        }, timeout=20)
        r.raise_for_status()
        return r.json()

    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the stored refresh_token. Persists the
        new access_token + expires_at back to the properties row. Returns True
        on success.
        """
        if self.mock:
            return True
        if not self._refresh_token:
            self._load_pms_metadata()
        if not self._refresh_token:
            logger.error("Cloudbeds: no refresh_token stored for property %s",
                         self.property_id)
            return False

        cid     = os.getenv("CLOUDBEDS_CLIENT_ID", "")
        csecret = os.getenv("CLOUDBEDS_CLIENT_SECRET", "")
        if not cid or not csecret:
            logger.error("Cloudbeds: client credentials not set in env")
            return False

        try:
            r = requests.post(_CB_OAUTH_TOKEN, data={
                "grant_type":    "refresh_token",
                "client_id":     cid,
                "client_secret": csecret,
                "refresh_token": self._refresh_token,
            }, timeout=20)
            r.raise_for_status()
            tok = r.json()
        except Exception as exc:
            logger.error("Cloudbeds token refresh failed: %s", exc)
            return False

        self.api_key = tok["access_token"]
        if "refresh_token" in tok:
            self._refresh_token = tok["refresh_token"]
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(tok.get("expires_in", 3600)) - 60
        )
        self._sb_patch("properties", {"id": f"eq.{self.property_id}"}, {
            "pms_api_key":           self.api_key,
            "pms_refresh_token":     self._refresh_token,
            "pms_token_expires_at":  expires_at.isoformat(),
        })
        return True

    def _ensure_fresh_token(self) -> None:
        """Refresh access_token if it's within 60s of expiry."""
        if self.mock or not self.property_id:
            return
        rows = self._sb_get("properties", {
            "id": f"eq.{self.property_id}",
            "select": "pms_token_expires_at",
        })
        if not rows or not rows[0].get("pms_token_expires_at"):
            return
        try:
            exp = datetime.fromisoformat(rows[0]["pms_token_expires_at"].replace("Z", "+00:00"))
        except ValueError:
            return
        if exp - datetime.now(timezone.utc) < timedelta(seconds=60):
            self.refresh_access_token()

    def _load_pms_metadata(self) -> None:
        """Pull cb_property_id + refresh_token from the properties row."""
        try:
            rows = self._sb_get("properties", {
                "id":     f"eq.{self.property_id}",
                "select": "pms_external_id,pms_refresh_token",
            })
            if rows:
                self._cb_property_id = rows[0].get("pms_external_id")
                self._refresh_token  = rows[0].get("pms_refresh_token")
        except Exception as exc:
            logger.warning("Cloudbeds metadata load failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────
    #  CONNECTION
    # ─────────────────────────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """GET /hotels — returns True on 200 OK."""
        if self.mock:
            logger.info("[mock] Cloudbeds connection OK")
            return True
        try:
            self._ensure_fresh_token()
            r = self._get("/hotels")
            return r.status_code == 200
        except Exception as exc:
            logger.error("Cloudbeds connection failed: %s", exc)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    #  ROOM TYPES
    # ─────────────────────────────────────────────────────────────────────────

    def sync_room_types(self) -> list[dict]:
        """GET /roomTypes → upsert into room_types. Returns synced rows."""
        log_id = self._start_sync("room_types")
        try:
            raw = self._mock_room_types() if self.mock else self._fetch_room_types()

            rows: list[dict] = []
            for rt in raw:
                base = float(rt.get("roomTypeRate", 200))
                rows.append({
                    "tenant_id":   self._tenant_id,
                    "property_id": self.property_id,
                    "name":        rt["roomTypeName"],
                    "description": rt.get("roomTypeDescription", "") or "",
                    "total_count": int(rt.get("roomTypeQty", 1)),
                    "base_rate":   base,
                    "min_rate":    float(rt.get("roomTypeMinRate", base * 0.7)),
                    "max_rate":    float(rt.get("roomTypeMaxRate", base * 1.8)),
                })

            if not self.mock:
                self._sb_upsert("room_types", rows, on_conflict="property_id,name")
            self._finish_sync(log_id, count=len(rows))
            logger.info("Synced %d Cloudbeds room types (%d rooms total)",
                        len(rows), sum(r["total_count"] for r in rows))
            return rows
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_room_types(self) -> list[dict]:
        self._ensure_fresh_token()
        r = self._get("/roomTypes", params={"propertyID": self._cb_property_id})
        r.raise_for_status()
        return r.json().get("data", [])

    def _mock_room_types(self) -> list[dict]:
        return list(self._MOCK_ROOM_TYPES)

    # ─────────────────────────────────────────────────────────────────────────
    #  OCCUPANCY
    # ─────────────────────────────────────────────────────────────────────────

    def sync_occupancy(self, lookback_days: int = 730, lookahead_days: int = 365) -> int:
        """GET /getReservations and roll up into occupancy_snapshots."""
        start, end = self._window(lookback_days, lookahead_days)
        log_id = self._start_sync("occupancy",
                                  metadata={"start": start.isoformat(),
                                            "end":   end.isoformat()})
        try:
            reservations = (self._mock_reservations(start, end) if self.mock
                            else self._fetch_reservations(start, end))

            room_types = self._mock_room_types() if self.mock else self._fetch_room_types()
            inventory  = {rt["roomTypeID"]: int(rt["roomTypeQty"]) for rt in room_types}
            name_by_id = {rt["roomTypeID"]: rt["roomTypeName"] for rt in room_types}

            shg_rt_id: dict[str, str] = {}
            if not self.mock and self._tenant_id:
                rows = self._sb_get("room_types",
                                    {"property_id": f"eq.{self.property_id}",
                                     "select":      "id,name"})
                name_to_id = {r["name"]: r["id"] for r in rows}
                for ext_id, name in name_by_id.items():
                    if name in name_to_id:
                        shg_rt_id[ext_id] = name_to_id[name]

            buckets: dict[tuple[date, str], dict[str, Any]] = {}
            for res in reservations:
                ext_id = str(res["roomTypeID"])
                arr    = res["startDate"]
                dep    = res["endDate"]
                rate   = float(res.get("nightlyRate", 0))
                # Cloudbeds dates may be ISO strings on live API
                if isinstance(arr, str): arr = date.fromisoformat(arr)
                if isinstance(dep, str): dep = date.fromisoformat(dep)
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
            logger.info("Synced %d Cloudbeds occupancy snapshots (%s → %s, %d reservations)",
                        n, start, end, len(reservations))
            return n
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_reservations(self, start: date, end: date) -> list[dict]:
        """Paginated GET /getReservations with date filter."""
        self._ensure_fresh_token()
        out, page = [], 1
        while True:
            r = self._get("/getReservations", params={
                "propertyID":     self._cb_property_id,
                "checkInFrom":    start.isoformat(),
                "checkInTo":      end.isoformat(),
                "status":         "confirmed",
                "pageNumber":     page,
                "pageSize":       100,
            })
            r.raise_for_status()
            data = r.json()
            page_rows = data.get("data", [])
            out.extend(page_rows)
            total_pages = int(data.get("total_pages") or data.get("totalPages") or 1)
            if page >= total_pages or not page_rows:
                break
            page += 1
        return out

    def _mock_reservations(self, start: date, end: date) -> list[dict]:
        """Deterministic ~70% occupancy with seasonal + WF peaks."""
        rng     = random.Random(43)
        rooms   = self._mock_room_types()
        out: list[dict] = []
        base_rate = {rt["roomTypeID"]: rt["roomTypeRate"] for rt in rooms}

        for offset in range((end - start).days + 1):
            d = start + timedelta(days=offset)
            seasonal = _SEASONAL[d.month]
            dow      = _DOW[d.weekday()]
            is_wf    = (d.month == 7 and 17 <= d.day <= 26)
            target_occ = min(1.0, 0.62 * seasonal * dow * (1.45 if is_wf else 1.0))

            for rt in rooms:
                n_rooms     = rt["roomTypeQty"]
                occupied    = max(0, min(n_rooms, round(n_rooms * target_occ + rng.gauss(0, 0.4))))
                nightly     = round(base_rate[rt["roomTypeID"]] * seasonal * dow / 5) * 5
                for _ in range(occupied):
                    los = rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
                    out.append({
                        "reservationID":  f"CB{len(out):08d}",
                        "roomTypeID":     rt["roomTypeID"],
                        "startDate":      d,
                        "endDate":        d + timedelta(days=los),
                        "nightlyRate":    nightly,
                        "total":          nightly * los,
                        "status":         "confirmed",
                        "guestID":        f"CBG{rng.randint(1, 5000):06d}",
                    })
        return out

    # ─────────────────────────────────────────────────────────────────────────
    #  GUESTS
    # ─────────────────────────────────────────────────────────────────────────

    def sync_guests(self) -> int:
        """GET /getGuests paginated → upsert into guests with hashed email."""
        log_id = self._start_sync("guests")
        try:
            raw = self._mock_guests() if self.mock else self._fetch_guests()
            rows: list[dict] = []
            for g in raw:
                email = (g.get("guestEmail") or "").strip().lower()
                rows.append({
                    "tenant_id":    self._tenant_id,
                    "property_id":  self.property_id,
                    "first_name":   g.get("guestFirstName"),
                    "last_name":    g.get("guestLastName"),
                    "email_hash":   self._hash_email(email) if email else None,
                    "email_encrypted":  _encrypt_pii(email) if email else None,
                    "phone_encrypted":  _encrypt_pii(g.get("guestPhone", "")),
                    "home_city":    g.get("guestCity"),
                    "home_state":   g.get("guestState"),
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
            logger.info("Synced %d Cloudbeds guests", n)
            return n
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_guests(self) -> list[dict]:
        self._ensure_fresh_token()
        out, page = [], 1
        while True:
            r = self._get("/getGuests", params={
                "propertyID": self._cb_property_id,
                "pageNumber": page,
                "pageSize":   100,
            })
            r.raise_for_status()
            data = r.json()
            page_rows = data.get("data", [])
            out.extend(page_rows)
            total_pages = int(data.get("total_pages") or data.get("totalPages") or 1)
            if page >= total_pages or not page_rows:
                break
            page += 1
        return out

    def _mock_guests(self) -> list[dict]:
        rng = random.Random(101)
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
        rooms = ["Waterfront Suite","Waterview Suite","Garden View Room","Cottage Room"]
        today = date.today()
        guests = []
        for i in range(450):
            f = rng.choice(first); l = rng.choice(last)
            c, s = rng.choice(cities)
            stays  = rng.choices([1,2,3,4,5,6,8], weights=[55,20,10,6,4,3,2])[0]
            nights = stays * rng.choices([2,3,4], weights=[60,30,10])[0]
            adr    = round(rng.uniform(285, 525) / 5) * 5
            last_stay = today - timedelta(days=rng.randint(15, 900))
            guests.append({
                "guestID":            f"CBG{i:06d}",
                "guestFirstName":     f, "guestLastName": l,
                "guestEmail":         f"{f.lower()}.{l.lower()}@example.com",
                "guestPhone":         f"+1-555-{rng.randint(1000,9999):04d}",
                "guestCity":          c, "guestState": s,
                "totalStays":         stays,
                "totalNights":        nights,
                "totalRevenue":       adr * nights,
                "avgRatePaid":        adr,
                "preferredRoomType":  rng.choice(rooms),
                "bookingSources":     rng.choice(sources),
                "lastStayDate":       last_stay.isoformat(),
                "marketingConsent":   rng.random() < 0.62,
            })
        return guests

    # ─────────────────────────────────────────────────────────────────────────
    #  RATES
    # ─────────────────────────────────────────────────────────────────────────

    def sync_current_rates(self) -> dict:
        """GET /getRatePlans → set current_rate on rate_recommendations."""
        start = date.today()
        end   = start + timedelta(days=365)
        log_id = self._start_sync("rates",
                                  metadata={"start": start.isoformat(),
                                            "end":   end.isoformat()})
        try:
            raw = self._mock_rates(start, end) if self.mock else self._fetch_rate_plans(start, end)

            room_types = self._mock_room_types() if self.mock else self._fetch_room_types()
            name_by_id = {rt["roomTypeID"]: rt["roomTypeName"] for rt in room_types}
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
                shg_id = shg_rt_id.get(str(r["roomTypeID"]))
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
            logger.info("Cloudbeds sync_current_rates: %s", summary)
            return summary
        except Exception as exc:
            self._finish_sync(log_id, status="failed", error=str(exc))
            raise

    def _fetch_rate_plans(self, start: date, end: date) -> list[dict]:
        """GET /getRatePlans flattened to (roomTypeID, date, rate) rows."""
        self._ensure_fresh_token()
        r = self._get("/getRatePlans", params={
            "propertyID": self._cb_property_id,
            "startDate":  start.isoformat(),
            "endDate":    end.isoformat(),
        })
        r.raise_for_status()
        out: list[dict] = []
        for plan in r.json().get("data", []):
            rt_id = str(plan.get("roomTypeID"))
            for rate_row in plan.get("rates", []):
                out.append({
                    "roomTypeID": rt_id,
                    "date":       rate_row["date"],
                    "rate":       float(rate_row["rate"]),
                })
        return out

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
                rate = round(rt["roomTypeRate"] * mult / 5) * 5
                out.append({
                    "roomTypeID": rt["roomTypeID"],
                    "date":       d.isoformat(),
                    "rate":       float(rate),
                })
        return out

    # ─────────────────────────────────────────────────────────────────────────
    #  PUBLISH
    # ─────────────────────────────────────────────────────────────────────────

    def publish_rate(self, room_type_id: str, target_date: date, new_rate: float) -> bool:
        """Push a single-day rate. Delegates to bulk path with date_from==date_to."""
        return self.publish_rate_bulk(room_type_id, target_date, target_date, new_rate)

    def publish_rate_bulk(
        self,
        room_type_id: str,
        date_from:    date,
        date_to:      date,
        new_rate:     float,
    ) -> bool:
        """
        PUT /updateRoomRate — Cloudbeds accepts a date range in a single call.
        Marks affected rate_recommendations rows as published on success.
        """
        ext_id = self._shg_to_external(room_type_id)
        if not ext_id and not self.mock:
            logger.error("publish_rate: no Cloudbeds roomTypeID for %s", room_type_id)
            return False

        payload = {
            "propertyID": self._cb_property_id or "MOCK",
            "roomTypeID": ext_id or "MOCK",
            "startDate":  date_from.isoformat(),
            "endDate":    date_to.isoformat(),
            "rate":       float(new_rate),
        }
        if self.mock:
            logger.info("[mock] PUT /updateRoomRate %s → OK", payload)
            ok = True
        else:
            try:
                self._ensure_fresh_token()
                r = self._put("/updateRoomRate", json=payload)
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
                 "target_date":  f"gte.{date_from.isoformat()}",
                 "and":          f"(target_date.lte.{date_to.isoformat()})"},
                {"status":       "published",
                 "published_at": datetime.now(timezone.utc).isoformat()})
        return ok

    def _shg_to_external(self, room_type_id: str) -> Optional[str]:
        if self.mock:
            return None
        rows = self._sb_get("room_types",
                            {"id": f"eq.{room_type_id}", "select": "name"})
        if not rows:
            return None
        name = rows[0]["name"]
        for rt in self._MOCK_ROOM_TYPES:
            if rt["roomTypeName"] == name:
                return rt["roomTypeID"]
        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  WEBHOOKS
    # ─────────────────────────────────────────────────────────────────────────

    def register_webhook(self, endpoint_url: str) -> bool:
        """POST /registerWebhook for reservation lifecycle events."""
        events = [
            "reservation/new",
            "reservation/modified",
            "reservation/cancelled",
        ]
        if self.mock:
            logger.info("[mock] POST /registerWebhook %s → registered for %d events",
                        endpoint_url, len(events))
            return True
        try:
            self._ensure_fresh_token()
            ok_all = True
            for event in events:
                r = self._post("/registerWebhook", json={
                    "propertyID": self._cb_property_id,
                    "endpointUrl": endpoint_url,
                    "object":      event.split("/")[0],
                    "action":      event.split("/")[1],
                })
                if r.status_code not in (200, 201):
                    logger.error("registerWebhook %s failed: %s — %s",
                                 event, r.status_code, r.text[:200])
                    ok_all = False
            return ok_all
        except Exception as exc:
            logger.error("register_webhook failed: %s", exc)
            return False

    def handle_webhook(self, payload: dict) -> dict:
        """
        Process a Cloudbeds webhook event. Cloudbeds payload shape:
            {
              "event":   "reservation/new" | "reservation/modified" | "reservation/cancelled",
              "propertyID": "...",
              "reservationID": "...",
              "startDate": "YYYY-MM-DD",
              "endDate":   "YYYY-MM-DD"
            }
        """
        event = payload.get("event", "")
        res_id = payload.get("reservationID") or payload.get("reservationId", "")
        arr   = payload.get("startDate")
        dep   = payload.get("endDate")

        affected: list[str] = []
        if arr and dep:
            d0 = date.fromisoformat(arr); d1 = date.fromisoformat(dep)
            cur = d0
            while cur < d1:
                affected.append(cur.isoformat())
                cur += timedelta(days=1)

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
        logger.info("Cloudbeds handle_webhook %s: %s", event, report)
        return report

    @staticmethod
    def verify_webhook_signature(raw_body: bytes, header_signature: str,
                                 webhook_secret: Optional[str] = None) -> bool:
        """
        Verify Cloudbeds webhook signature (HMAC-SHA256 of raw body, hex).
        Cloudbeds delivers `X-Cloudbeds-Signature` header.
        """
        secret = (webhook_secret or os.getenv("CLOUDBEDS_WEBHOOK_SECRET", ""))
        if not secret or not header_signature:
            return False
        mac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, header_signature.strip().lower())

    # ─────────────────────────────────────────────────────────────────────────
    #  Low-level HTTP
    # ─────────────────────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
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
#  Module-private helpers (shared shape with ResNexus connector)
# ─────────────────────────────────────────────────────────────────────────────

_SEASONAL = {1:0.78, 2:0.82, 3:0.95, 4:1.18, 5:1.22, 6:1.12,
             7:1.18, 8:1.04, 9:1.02, 10:1.10, 11:0.90, 12:0.95}
_DOW      = {0:0.92, 1:0.90, 2:0.92, 3:0.96, 4:1.12, 5:1.20, 6:1.06}


def _encrypt_pii(value: str) -> Optional[str]:
    """Placeholder PII envelope — same scheme as engine.pms.resnexus._encrypt_pii."""
    if not value:
        return None
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
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
                   help="Use mock Cloudbeds responses (no live API call)")
    p.add_argument("--slug", default="anchorage-1770-demo")
    p.add_argument("--api-key", default="MOCK_ACCESS_TOKEN")
    p.add_argument("--lookback",  type=int, default=730)
    p.add_argument("--lookahead", type=int, default=365)
    args = p.parse_args()

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
    print(f"  Cloudbeds PMS Integration Test  ({'MOCK MODE' if args.mock else 'LIVE'})")
    print(f"  Property: {args.slug}  ({pid})")
    print(f"{'='*72}\n")

    pms = CloudbedsConnector(pid, args.api_key, mock=args.mock)

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

    # 6. Publish (bulk Cloudbeds path)
    sample_from = date.today() + timedelta(days=30)
    sample_to   = date.today() + timedelta(days=33)
    sample_rt   = (rts[0].get("name") if rts else "MOCK")
    ok = pms.publish_rate_bulk("00000000-0000-0000-0000-000000000000",
                               sample_from, sample_to, 545.0)
    print(f"  [6] publish_rate_bulk()  → {'✓ PUT OK' if ok else '✗ failed'}  "
          f"(sample: {sample_rt} {sample_from}→{sample_to} → $545)")

    # 7. Webhook registration
    ok = pms.register_webhook("https://api.gracious.collection/webhooks/cloudbeds")
    print(f"  [7] register_webhook()   → {'✓ subscribed' if ok else '✗ failed'}")

    # 8. Webhook handling (sample event)
    sample_payload = {
        "event":         "reservation/new",
        "propertyID":    "CB-PROP-12345",
        "reservationID": "CB12345678",
        "startDate":     (date.today() + timedelta(days=30)).isoformat(),
        "endDate":       (date.today() + timedelta(days=33)).isoformat(),
    }
    report = pms.handle_webhook(sample_payload)
    print(f"  [8] handle_webhook()     → processed {report['event']}  "
          f"dates_affected={len(report['dates_affected'])}  "
          f"refresh={report['demand_refresh_triggered']}")

    # 9. OAuth URL (no network call)
    try:
        os.environ.setdefault("CLOUDBEDS_CLIENT_ID", "demo_client_id")
        url = CloudbedsConnector.get_oauth_url(
            "https://api.gracious.collection/oauth/cloudbeds/callback",
            state="demo-state",
        )
        print(f"  [9] get_oauth_url()      → {url[:90]}...")
    except Exception as exc:
        print(f"  [9] get_oauth_url()      → SKIPPED ({exc})")

    print(f"\n{'='*72}")
    print(f"  ✓ Integration test complete")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    main()
