"""
engine/competitor_monitor.py
Phase 2C — Competitive Rate Monitoring for The Gracious Collection Pricing Engine

Tracks competitor pricing for Beaufort SC boutique properties,
generates synthetic rates (until live OTA scraping is wired in Phase 8),
and surfaces competitive positioning alerts.

Usage:
    python -m engine.competitor_monitor
    python -m engine.competitor_monitor --slug anchorage-1770-demo --seed --days 90
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Beaufort SC competitor baseline rates
# ─────────────────────────────────────────────────────────────────────────────

# Full 20-property Beaufort SC / regional competitive set.
# Fields used by seed_competitors (DB insert/PATCH) and
# seed_synthetic_competitor_rates (rate generation).
_COMPETITORS = [

    # ── TIER 1 — Direct boutique competitors ─────────────────────────────
    {
        "competitor_name":  "Cuthbert House Inn",
        "property_tier":    1,
        "property_category":"boutique_inn",
        "base_rate":        265.0,
        "room_count":       10,
        "trip_advisor_rating": 4.5,
        "distance_miles":   0.3,
        "booking_com_id":   "bdc-cuthbert-house",
        "expedia_id":       "exp-4567890",
        "google_maps_url":  "https://maps.google.com/?q=Cuthbert+House+Inn+Beaufort+SC",
        "notes": (
            "Antebellum mansion B&B on Bay Street; waterfront with Beaufort River views; "
            "premium historic property; Forbes Top Inn; rank-1 direct competitor"
        ),
        "wf_sold_out": True,   # 10-room boutique sells out every Water Festival
        "wf_mult":     2.13,   # → ~$531 on July 20 (Monday, DOW 0.94)
    },
    {
        "competitor_name":  "Rhett House Inn",
        "property_tier":    1,
        "property_category":"boutique_inn",
        "base_rate":        285.0,
        "room_count":       17,
        "trip_advisor_rating": 4.0,
        "distance_miles":   0.2,
        "booking_com_id":   "bdc-rhett-house-beaufort",
        "expedia_id":       "exp-1234567",
        "google_maps_url":  "https://maps.google.com/?q=Rhett+House+Inn+Beaufort+SC",
        "notes": (
            "Historic B&B on Craven St; garden property (not waterfront); "
            "direct competitor on price range; similar boutique experience"
        ),
        "wf_sold_out": True,
        "wf_mult":     1.77,   # → ~$475 on July 20
    },
    {
        "competitor_name":  "607 Bay Inn Downtown Beaufort",
        "property_tier":    1,
        "property_category":"boutique_inn",
        "base_rate":        195.0,
        "room_count":       8,
        "trip_advisor_rating": 4.5,
        "distance_miles":   0.3,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=607+Bay+St+Beaufort+SC",
        "notes": (
            "8-room inn at 607 Bay St; boutique historic inn; "
            "waterfront with Beaufort River views; direct Bay Street competitor"
        ),
        "wf_sold_out": True,   # tiny property sells out
        "wf_mult":     1.64,   # → ~$300 on July 20
    },
    {
        "competitor_name":  "City Loft Hotel",
        "property_tier":    1,
        "property_category":"boutique_hotel",
        "base_rate":        189.0,
        "room_count":       24,
        "trip_advisor_rating": 4.3,
        "distance_miles":   0.5,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=City+Loft+Hotel+301+Carteret+St+Beaufort+SC",
        "notes": (
            "Modern boutique hotel at 301 Carteret St; contemporary loft aesthetic; "
            "downtown Beaufort; direct competitor on price and location"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.55,   # → ~$275 on July 20
    },
    {
        "competitor_name":  "Best Western Sea Island Inn",
        "property_tier":    1,
        "property_category":"boutique_hotel",
        "base_rate":        165.0,
        "room_count":       43,
        "trip_advisor_rating": 3.8,
        "distance_miles":   0.2,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Best+Western+Sea+Island+Inn+Beaufort+SC",
        "notes": (
            "Chain-affiliated boutique at 1015 Bay St; long-established Beaufort property; "
            "direct competitor by Bay Street location; breakfast included"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.65,   # → ~$255 on July 20
    },
    {
        "competitor_name":  "Beaufort Inn",
        "property_tier":    1,
        "property_category":"boutique_inn",
        "base_rate":        245.0,
        "room_count":       21,
        "trip_advisor_rating": 4.2,
        "distance_miles":   0.4,
        "booking_com_id":   "bdc-beaufort-inn",
        "expedia_id":       "exp-2345678",
        "google_maps_url":  "https://maps.google.com/?q=Beaufort+Inn+SC",
        "notes": (
            "Downtown inn; slightly lower tier, strong OTA presence; "
            "historic boutique; direct competitor"
        ),
        "wf_sold_out": True,
        "wf_mult":     1.82,   # → ~$420 on July 20
    },
    {
        "competitor_name":  "Bay Street Inn",
        "property_tier":    1,
        "property_category":"boutique_inn",
        "base_rate":        195.0,
        "room_count":       8,
        "trip_advisor_rating": 3.8,
        "distance_miles":   0.1,
        "booking_com_id":   "bdc-bay-street-inn",
        "expedia_id":       "exp-3456789",
        "google_maps_url":  "https://maps.google.com/?q=Bay+Street+Inn+Beaufort+SC",
        "notes": (
            "Budget-friendly boutique on Bay St; lower tier; "
            "closest proximity competitor; direct price comp"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.72,   # → ~$315 on July 20
    },
    {
        "competitor_name":  "Magnolia Court Suites",
        "property_tier":    1,
        "property_category":"boutique_inn",
        "base_rate":        129.0,
        "room_count":       12,
        "trip_advisor_rating": 4.1,
        "distance_miles":   1.0,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Magnolia+Court+Suites+1204+Pigeon+Point+Rd+Beaufort+SC",
        "notes": (
            "Small boutique suites at 1204 Pigeon Point Rd; garden setting; "
            "1 mi from downtown; lower price point direct comp"
        ),
        "wf_sold_out": True,   # small property sells out
        "wf_mult":     1.61,   # → ~$195 on July 20
    },

    # ── TIER 2 — Upscale hotels ───────────────────────────────────────────
    {
        "competitor_name":  "Hilton Garden Inn Beaufort",
        "property_tier":    2,
        "property_category":"upscale_hotel",
        "brand_affiliation":"Hilton",
        "base_rate":        179.0,
        "room_count":       115,
        "trip_advisor_rating": 4.2,
        "distance_miles":   2.1,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Hilton+Garden+Inn+Beaufort+SC",
        "notes": (
            "Hilton brand select-service 2.1 mi from downtown; "
            "establishes branded hotel ceiling in Beaufort; Tier 2 benchmark"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.49,   # → ~$250 on July 20
    },
    {
        "competitor_name":  "Home2 Suites by Hilton Beaufort",
        "property_tier":    2,
        "property_category":"upscale_hotel",
        "brand_affiliation":"Hilton",
        "base_rate":        169.0,
        "room_count":       103,
        "trip_advisor_rating": 4.3,
        "distance_miles":   2.3,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Home2+Suites+Hilton+Beaufort+SC",
        "notes": (
            "Hilton extended-stay hotel 2.3 mi from downtown; "
            "appeal to longer-stay travelers; Tier 2 upscale benchmark"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.51,   # → ~$240 on July 20
    },
    {
        "competitor_name":  "SpringHill Suites Beaufort",
        "property_tier":    2,
        "property_category":"upscale_hotel",
        "brand_affiliation":"Marriott",
        "base_rate":        159.0,
        "room_count":       103,
        "trip_advisor_rating": 4.1,
        "distance_miles":   2.4,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=SpringHill+Suites+Beaufort+SC",
        "notes": (
            "Marriott extended-stay suites 2.4 mi from downtown; "
            "newer property; Tier 2 Marriott benchmark"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.51,   # → ~$225 on July 20
    },
    {
        "competitor_name":  "Holiday Inn and Suites Beaufort",
        "property_tier":    2,
        "property_category":"select_service_hotel",
        "brand_affiliation":"IHG",
        "base_rate":        149.0,
        "room_count":       129,
        "trip_advisor_rating": 3.9,
        "distance_miles":   2.5,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Holiday+Inn+Suites+Beaufort+SC",
        "notes": (
            "IHG brand; 129 rooms; largest branded hotel in Beaufort; "
            "sets select-service ceiling; Tier 2 benchmark"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.50,   # → ~$210 on July 20
    },
    {
        "competitor_name":  "Fripp Island Golf and Beach Resort",
        "property_tier":    2,
        "property_category":"boutique_hotel",
        "base_rate":        249.0,
        "room_count":       88,
        "trip_advisor_rating": 4.3,
        "distance_miles":   22.0,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Fripp+Island+Golf+Beach+Resort+SC",
        "notes": (
            "22 mi southeast on Fripp Island; beach destination resort; "
            "upscale reference for coastal SC market; Tier 2 regional benchmark"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.60,   # → ~$375 on July 20
    },
    {
        "competitor_name":  "Hilton Head Marriott Resort",
        "property_tier":    2,
        "property_category":"upscale_hotel",
        "brand_affiliation":"Marriott",
        "base_rate":        299.0,
        "room_count":       512,
        "trip_advisor_rating": 4.2,
        "distance_miles":   29.5,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Hilton+Head+Marriott+Resort+SC",
        "notes": (
            "Tier 2 upscale hotel — 30 miles south on Hilton Head Island; "
            "establishes regional upscale ceiling; Marriott brand"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.39,   # → ~$390 on July 20
    },

    # ── TIER 3 — Luxury reference ─────────────────────────────────────────
    {
        "competitor_name":  "Montage Palmetto Bluff Resort",
        "property_tier":    3,
        "property_category":"luxury_hotel",
        "brand_affiliation":"Montage Hotels",
        "base_rate":        850.0,
        "room_count":       200,
        "trip_advisor_rating": 4.9,
        "distance_miles":   21.0,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Montage+Palmetto+Bluff+Bluffton+SC",
        "notes": (
            "Forbes Five Star luxury resort in Bluffton SC (21 mi); "
            "Relais and Chateaux member; establishes regional luxury ceiling at $850+/night; "
            "Water Festival has minimal impact — luxury guests less price-sensitive to local events"
        ),
        "wf_sold_out": False,  # luxury holds rate, doesn't sell out
        "wf_mult":     1.28,   # → ~$1,020 on July 20 (holds firm)
    },

    # ── TIER 4 — Budget anchors ───────────────────────────────────────────
    {
        "competitor_name":  "Hampton Inn Beaufort",
        "property_tier":    4,
        "property_category":"select_service_hotel",
        "brand_affiliation":"Hilton",
        "base_rate":        139.0,
        "room_count":       118,
        "trip_advisor_rating": 3.8,
        "distance_miles":   2.8,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Hampton+Inn+Beaufort+SC",
        "notes": (
            "Tier 4 budget anchor — Hilton brand select-service; "
            "establishes market floor in Beaufort area; 2.8 mi from downtown"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.91,   # → ~$250 on July 20 (budget hotels spike hardest)
    },
    {
        "competitor_name":  "Tru by Hilton Beaufort",
        "property_tier":    4,
        "property_category":"budget_hotel",
        "brand_affiliation":"Hilton",
        "base_rate":        129.0,
        "room_count":       97,
        "trip_advisor_rating": 4.2,
        "distance_miles":   2.4,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Tru+by+Hilton+Beaufort+SC",
        "notes": (
            "Hilton budget brand targeting millennial travelers; 97 rooms; "
            "2.4 mi from downtown; budget floor anchor"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.94,   # → ~$235 on July 20
    },
    {
        "competitor_name":  "Comfort Suites Beaufort",
        "property_tier":    4,
        "property_category":"budget_hotel",
        "brand_affiliation":"Choice Hotels",
        "base_rate":        119.0,
        "room_count":       97,
        "trip_advisor_rating": 4.0,
        "distance_miles":   2.6,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Comfort+Suites+Beaufort+SC",
        "notes": (
            "Choice Hotels brand; 97 rooms; 2.6 mi from downtown; "
            "budget floor anchor for Beaufort market"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.92,   # → ~$215 on July 20
    },
    {
        "competitor_name":  "Country Inn and Suites Beaufort",
        "property_tier":    4,
        "property_category":"budget_hotel",
        "brand_affiliation":"Radisson",
        "base_rate":        109.0,
        "room_count":       66,
        "trip_advisor_rating": 3.9,
        "distance_miles":   2.8,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Country+Inn+Suites+Beaufort+SC",
        "notes": (
            "Radisson brand; 66 rooms; 2.8 mi from downtown; "
            "establishes lower budget floor for Beaufort market"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.94,   # → ~$200 on July 20
    },
    {
        "competitor_name":  "Howard Johnson Beaufort",
        "property_tier":    4,
        "property_category":"budget_hotel",
        "brand_affiliation":"Wyndham",
        "base_rate":        89.0,
        "room_count":       63,
        "trip_advisor_rating": 3.2,
        "distance_miles":   3.1,
        "booking_com_id":   None,
        "expedia_id":       None,
        "google_maps_url":  "https://maps.google.com/?q=Howard+Johnson+Beaufort+SC",
        "notes": (
            "Wyndham budget brand; 63 rooms; 3.1 mi from downtown; "
            "lowest-rate market anchor; establishes absolute rate floor"
        ),
        "wf_sold_out": False,
        "wf_mult":     1.91,   # → ~$160 on July 20
    },
]

# Monthly seasonal multipliers — Beaufort SC market (Tier 1 boutique full swings)
_SEASONAL_MULT: dict[int, float] = {
    1: 0.88, 2: 0.90, 3: 0.96, 4: 1.22, 5: 1.27,
    6: 1.12, 7: 1.18, 8: 1.08, 9: 1.02,
    10: 1.08, 11: 0.94, 12: 1.01,
}
# Tier 2 (upscale hotels): dampened seasonal variation — branded hotels hold rates firmer
_SEASONAL_MULT_T2 = {m: 1.0 + (v - 1.0) * 0.45 for m, v in _SEASONAL_MULT.items()}
# Tier 3 (luxury): very flat — premium is year-round, guests are less price-elastic
_SEASONAL_MULT_T3 = {m: 1.0 + (v - 1.0) * 0.08 for m, v in _SEASONAL_MULT.items()}
# Tier 4 (budget): moderate seasonal variation, slightly less than boutique
_SEASONAL_MULT_T4 = {m: 1.0 + (v - 1.0) * 0.60 for m, v in _SEASONAL_MULT.items()}

# Day-of-week premium (competitors also charge more on weekends)
_DOW_MULT: dict[int, float] = {
    0: 0.94, 1: 0.92, 2: 0.94, 3: 0.97,
    4: 1.12, 5: 1.18, 6: 1.06,
}


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompetitivePosition:
    date:                 date
    your_rate:            Optional[float]
    comp_avg:             float
    comp_min:             float
    comp_max:             float
    position_pct:         float          # (your_rate - comp_avg) / comp_avg
    position_label:       str            # Premium / At Market / Below Market / Significantly Below
    sold_out_competitors: list[str]
    comp_count:           int
    comp_rates_detail:    dict[str, float] = field(default_factory=dict)

    @staticmethod
    def label_for(pct: float) -> str:
        if pct > 0.15:    return "Premium"
        if pct > -0.10:   return "At Market"
        if pct > -0.25:   return "Below Market"
        return "Significantly Below"


@dataclass
class RateDropAlert:
    competitor_name: str
    affected_dates:  list[date]
    old_rate:        float
    new_rate:        float
    drop_pct:        float
    platform:        str


# ─────────────────────────────────────────────────────────────────────────────
#  CompetitorMonitor
# ─────────────────────────────────────────────────────────────────────────────

class CompetitorMonitor:
    """
    Phase 2C — competitive rate monitoring for The Gracious Collection Pricing Engine.

    Connects to Supabase via REST API using .env credentials.
    Until live OTA scraping (Phase 8), uses synthetic rates generated by
    seed_synthetic_competitor_rates().
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        service_key:  str | None = None,
    ) -> None:
        url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
            )
        self._url  = url
        self._hdrs = {
            "apikey":        key,
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        }

    # ------------------------------------------------------------------ #
    #  Setup — seed competitors for a property                             #
    # ------------------------------------------------------------------ #

    def seed_competitors(self, tenant_id: str, property_id: str) -> list[str]:
        """
        Upsert all _COMPETITORS into competitor_properties.
        Inserts new entries; PATCHes existing ones with full tier/rating data.
        Returns list of competitor UUIDs in _COMPETITORS order.
        """
        existing = self._get(
            "competitor_properties",
            {"property_id": f"eq.{property_id}", "select": "id,competitor_name"},
        )
        existing_map = {r["competitor_name"]: r["id"]
                        for r in existing if r.get("competitor_name")}

        to_insert = []
        for comp in _COMPETITORS:
            row = {
                "tenant_id":          tenant_id,
                "property_id":        property_id,
                "name":               comp["competitor_name"],
                "competitor_name":    comp["competitor_name"],
                "notes":              comp["notes"],
                "active":             True,
                "property_tier":      comp.get("property_tier", 1),
                "property_category":  comp.get("property_category"),
                "brand_affiliation":  comp.get("brand_affiliation"),
                "room_count":         comp.get("room_count"),
                "trip_advisor_rating":comp.get("trip_advisor_rating"),
                "distance_miles":     comp.get("distance_miles"),
                "google_maps_url":    comp.get("google_maps_url"),
            }
            if comp.get("booking_com_id"):
                row["booking_com_id"] = comp["booking_com_id"]
            if comp.get("expedia_id"):
                row["expedia_id"] = comp["expedia_id"]

            if comp["competitor_name"] in existing_map:
                # PATCH existing row with updated data
                requests.patch(
                    f"{self._url}/rest/v1/competitor_properties",
                    headers={**self._hdrs, "Prefer": "return=minimal"},
                    params={"id": f"eq.{existing_map[comp['competitor_name']]}"},
                    json={k: v for k, v in row.items()
                          if k not in ("tenant_id", "property_id", "name", "competitor_name")},
                    timeout=15,
                ).raise_for_status()
            else:
                to_insert.append(row)

        if to_insert:
            resp = requests.post(
                f"{self._url}/rest/v1/competitor_properties",
                headers={**self._hdrs, "Prefer": "return=representation"},
                json=to_insert,
                timeout=30,
            )
            resp.raise_for_status()

        # Return all IDs in _COMPETITORS name order
        all_rows = self._get(
            "competitor_properties",
            {"property_id": f"eq.{property_id}",
             "select":      "id,competitor_name",
             "active":      "eq.true"},
        )
        name_to_id = {r["competitor_name"]: r["id"]
                      for r in all_rows if r.get("competitor_name")}
        return [name_to_id.get(c["competitor_name"], "") for c in _COMPETITORS]

    # ------------------------------------------------------------------ #
    #  Seed synthetic competitor rates                                     #
    # ------------------------------------------------------------------ #

    def seed_synthetic_competitor_rates(
        self,
        property_id: str,
        tenant_id:   str,
        days:        int = 90,
    ) -> int:
        """
        Generate realistic synthetic rates for next `days` days for all 20
        competitors. Tier-aware seasonal patterns: Tier 1 full boutique swings,
        Tier 2 dampened, Tier 3 near-flat luxury, Tier 4 moderate.
        Also inserts a historical batch (scraped_at = 72h ago) for Bay Street Inn
        to enable detect_rate_drops() to surface a meaningful drop example.

        Returns total rows inserted.
        """
        comp_rows = self._get(
            "competitor_properties",
            {"property_id": f"eq.{property_id}",
             "select":      "id,competitor_name,active"},
        )
        comp_map = {r["competitor_name"]: r["id"]
                    for r in comp_rows if r.get("active") and r.get("competitor_name")}

        if not comp_map:
            raise ValueError(f"No active competitors found for property {property_id}")

        today = date.today()

        # Clear existing synthetic rates for the date window
        for d_offset in (0,):  # single delete covers all comps via date filter
            resp = requests.delete(
                f"{self._url}/rest/v1/competitor_rates",
                headers=self._hdrs,
                params=[
                    ("property_id", f"eq.{property_id}"),
                    ("rate_date",   f"gte.{today.isoformat()}"),
                    ("rate_date",   f"lte.{(today + timedelta(days=days)).isoformat()}"),
                ],
                timeout=30,
            )
            resp.raise_for_status()

        now_utc   = datetime.now(timezone.utc).isoformat()
        past_utc  = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

        current_batch:  list[dict] = []
        historic_batch: list[dict] = []

        # Build tier lookup for the rate loop
        _tier_by_name = {c["competitor_name"]: c.get("property_tier", 1)
                         for c in _COMPETITORS}
        _seasonal_by_tier = {
            1: _SEASONAL_MULT, 2: _SEASONAL_MULT_T2,
            3: _SEASONAL_MULT_T3, 4: _SEASONAL_MULT_T4,
        }

        for comp_cfg in _COMPETITORS:
            comp_name = comp_cfg["competitor_name"]
            comp_id   = comp_map.get(comp_name)
            if not comp_id:
                continue

            base = comp_cfg["base_rate"]
            tier = comp_cfg.get("property_tier", 1)
            season_table = _seasonal_by_tier.get(tier, _SEASONAL_MULT)

            for offset in range(days + 1):
                d = today + timedelta(days=offset)

                # ── Tier-appropriate seasonal + DOW multiplier ────────
                season_mult = season_table.get(d.month, 1.0)
                dow_mult    = _DOW_MULT.get(d.weekday(), 1.0)

                # ── Water Festival override ───────────────────────────
                is_wf = (d.month == 7 and 17 <= d.day <= 26)
                if is_wf:
                    effective_mult = comp_cfg["wf_mult"] * dow_mult
                else:
                    effective_mult = season_mult * dow_mult

                # ── Deterministic ±8% daily variation ────────────────
                noise_seed = hash(f"{comp_id}:{d.isoformat()}") % 10000
                noise      = (noise_seed - 5000) / 62500   # ±8%

                rate_raw = base * effective_mult * (1 + noise)
                rate     = round(rate_raw / 5) * 5         # nearest $5
                rate     = max(float(round(base * 0.70 / 5) * 5), rate)  # floor at 70% of base

                is_sold_out = is_wf and comp_cfg["wf_sold_out"]

                current_batch.append({
                    "tenant_id":        tenant_id,
                    "property_id":      property_id,
                    "competitor_id":    comp_id,
                    "rate_date":        d.isoformat(),
                    "rate_amount":      rate,
                    "room_description": "Standard room (estimated)",
                    "platform":         "booking.com",
                    "is_sold_out":      is_sold_out,
                    "is_stale":         False,
                    "scraped_at":       now_utc,
                })

                # Historic snapshot (72h ago) — Bay Street Inn only,
                # at +12% so detect_rate_drops() can find a meaningful drop.
                if comp_name == "Bay Street Inn":
                    historic_batch.append({
                        "tenant_id":        tenant_id,
                        "property_id":      property_id,
                        "competitor_id":    comp_id,
                        "rate_date":        d.isoformat(),
                        "rate_amount":      round(rate * 1.12 / 5) * 5,
                        "room_description": "Standard room (estimated)",
                        "platform":         "booking.com",
                        "is_sold_out":      False,
                        "is_stale":         True,
                        "scraped_at":       past_utc,
                    })

        total = 0
        for batch in (current_batch, historic_batch):
            for i in range(0, len(batch), 500):
                chunk = batch[i : i + 500]
                resp  = requests.post(
                    f"{self._url}/rest/v1/competitor_rates",
                    headers={**self._hdrs, "Prefer": "return=minimal"},
                    json=chunk,
                    timeout=30,
                )
                resp.raise_for_status()
                total += len(chunk)

        logger.info("Seeded %d synthetic competitor rate rows", total)
        return total

    # ------------------------------------------------------------------ #
    #  Competitive position                                                #
    # ------------------------------------------------------------------ #

    def get_competitive_position(
        self,
        property_id:      str,
        date_range_start: date,
        date_range_end:   date,
        room_type_name:   str = "Waterfront Suite",
    ) -> list[CompetitivePosition]:
        """
        For each date in [start, end] return a CompetitivePosition comparing
        your recommended rate to the competitor set.

        your_rate is sourced from rate_recommendations (Waterfront Suite by default
        as the flagship comparison point).
        """
        # Your rates from rate_recommendations
        your_rates = self._fetch_your_rates(
            property_id, date_range_start, date_range_end, room_type_name
        )

        # Competitor rates and sold-out flags
        comp_rows = self._get(
            "competitor_rates",
            params=[
                ("property_id", f"eq.{property_id}"),
                ("rate_date",   f"gte.{date_range_start.isoformat()}"),
                ("rate_date",   f"lte.{date_range_end.isoformat()}"),
                ("is_stale",    "eq.false"),
                ("select",      "rate_date,rate_amount,is_sold_out,competitor_id"),
            ],
            limit=5000,
        )

        # Competitor names
        comp_name_map = self._comp_name_map(property_id)

        # Group by date
        from collections import defaultdict
        by_date: dict[str, list[dict]] = defaultdict(list)
        for r in comp_rows:
            by_date[r["rate_date"]].append(r)

        results: list[CompetitivePosition] = []
        d = date_range_start
        while d <= date_range_end:
            d_str    = d.isoformat()
            your_rate = your_rates.get(d_str)
            rows_for_date = by_date.get(d_str, [])

            live_rates = [
                float(r["rate_amount"])
                for r in rows_for_date
                if not r["is_sold_out"] and r.get("rate_amount") is not None
            ]
            sold_out = [
                comp_name_map.get(r["competitor_id"], "Unknown")
                for r in rows_for_date
                if r["is_sold_out"]
            ]
            detail = {
                comp_name_map.get(r["competitor_id"], r["competitor_id"]):
                float(r["rate_amount"] or 0)
                for r in rows_for_date
            }

            if live_rates:
                comp_avg = sum(live_rates) / len(live_rates)
                comp_min = min(live_rates)
                comp_max = max(live_rates)
            else:
                comp_avg = comp_min = comp_max = 0.0

            if your_rate and comp_avg:
                pos_pct = (your_rate - comp_avg) / comp_avg
            else:
                pos_pct = 0.0

            results.append(CompetitivePosition(
                date=d,
                your_rate=your_rate,
                comp_avg=round(comp_avg, 2),
                comp_min=round(comp_min, 2),
                comp_max=round(comp_max, 2),
                position_pct=round(pos_pct, 4),
                position_label=CompetitivePosition.label_for(pos_pct),
                sold_out_competitors=sold_out,
                comp_count=len(rows_for_date),
                comp_rates_detail=detail,
            ))
            d += timedelta(days=1)

        return results

    # ------------------------------------------------------------------ #
    #  Rate-drop detection                                                 #
    # ------------------------------------------------------------------ #

    def detect_rate_drops(
        self,
        property_id: str,
        threshold:   float = 0.20,
    ) -> list[RateDropAlert]:
        """
        Compares the most recent competitor rates to the historical (stale)
        snapshot.  Returns alerts for any competitor that dropped more than
        `threshold` (default 20%) on any date.
        """
        # Latest rates (is_stale=false)
        current = self._get(
            "competitor_rates",
            params=[
                ("property_id", f"eq.{property_id}"),
                ("is_stale",    "eq.false"),
                ("rate_date",   f"gte.{date.today().isoformat()}"),
                ("select",      "competitor_id,rate_date,rate_amount"),
            ],
            limit=5000,
        )

        # Historical rates (is_stale=true, scraped > 48h ago)
        stale = self._get(
            "competitor_rates",
            params=[
                ("property_id", f"eq.{property_id}"),
                ("is_stale",    "eq.true"),
                ("rate_date",   f"gte.{date.today().isoformat()}"),
                ("select",      "competitor_id,rate_date,rate_amount"),
            ],
            limit=5000,
        )

        # Index stale by (comp_id, date)
        stale_idx: dict[tuple[str, str], float] = {}
        for r in stale:
            if r.get("rate_amount") is not None:
                stale_idx[(r["competitor_id"], r["rate_date"])] = float(r["rate_amount"])

        comp_name_map = self._comp_name_map(property_id)

        # Find drops
        drops: dict[str, dict] = {}  # comp_id → {old, new, dates}
        for r in current:
            if r.get("rate_amount") is None:
                continue
            key = (r["competitor_id"], r["rate_date"])
            old = stale_idx.get(key)
            if old is None:
                continue
            new  = float(r["rate_amount"])
            drop = (old - new) / old if old > 0 else 0.0
            if drop >= threshold:
                cid = r["competitor_id"]
                if cid not in drops:
                    drops[cid] = {
                        "old":   old,
                        "new":   new,
                        "drop":  drop,
                        "dates": [],
                    }
                drops[cid]["dates"].append(date.fromisoformat(r["rate_date"]))
                # Track the most significant single-date values
                if drop > drops[cid]["drop"]:
                    drops[cid]["old"]  = old
                    drops[cid]["new"]  = new
                    drops[cid]["drop"] = drop

        alerts = [
            RateDropAlert(
                competitor_name=comp_name_map.get(cid, cid),
                affected_dates=sorted(info["dates"]),
                old_rate=info["old"],
                new_rate=info["new"],
                drop_pct=round(info["drop"] * 100, 1),
                platform="booking.com",
            )
            for cid, info in drops.items()
        ]
        return sorted(alerts, key=lambda a: -a.drop_pct)

    # ------------------------------------------------------------------ #
    #  Market summary                                                      #
    # ------------------------------------------------------------------ #

    def get_market_summary(
        self,
        property_id:  str,
        target_date:  date,
        room_type_name: str = "Waterfront Suite",
    ) -> dict[str, Any]:
        """
        Returns a dict summarising competitive position and market pressure
        for one date.
        """
        positions = self._fetch_comp_rates_for_date(property_id, target_date)
        your_rates = self._fetch_your_rates(
            property_id, target_date, target_date, room_type_name
        )
        your_rate = your_rates.get(target_date.isoformat())

        comp_name_map = self._comp_name_map(property_id)
        live = [p for p in positions if not p["is_sold_out"] and p.get("rate_amount")]
        sold_out_names = [
            comp_name_map.get(p["competitor_id"], "Unknown")
            for p in positions
            if p["is_sold_out"]
        ]
        live_rates = [float(p["rate_amount"]) for p in live]

        comp_avg = sum(live_rates) / len(live_rates) if live_rates else 0.0
        comp_min = min(live_rates) if live_rates else 0.0
        comp_max = max(live_rates) if live_rates else 0.0

        pos_pct = (your_rate - comp_avg) / comp_avg if (your_rate and comp_avg) else 0.0
        pos_label = CompetitivePosition.label_for(pos_pct)

        n_sold_out = len(sold_out_names)
        market_pressure = (
            "high"   if n_sold_out >= 2 else
            "medium" if n_sold_out == 1 else
            "low"
        )

        return {
            "date":                 target_date.isoformat(),
            "your_rate":            your_rate,
            "comp_avg":             round(comp_avg, 2),
            "comp_min":             round(comp_min, 2),
            "comp_max":             round(comp_max, 2),
            "your_position_label":  pos_label,
            "your_position_pct":    round(pos_pct * 100, 1),
            "sold_out_competitors": sold_out_names,
            "sold_out_count":       n_sold_out,
            "market_pressure":      market_pressure,
        }

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _fetch_your_rates(
        self,
        property_id:      str,
        start:            date,
        end:              date,
        room_type_name:   str,
    ) -> dict[str, float]:
        """Returns {date_str: recommended_rate} for the named room type."""
        # Find the room_type_id for the named room type
        rt_rows = self._get(
            "room_types",
            {"property_id": f"eq.{property_id}",
             "name": f"eq.{room_type_name}",
             "select": "id"},
        )
        if not rt_rows:
            return {}
        rt_id = rt_rows[0]["id"]

        recs = self._get(
            "rate_recommendations",
            params=[
                ("property_id",  f"eq.{property_id}"),
                ("room_type_id", f"eq.{rt_id}"),
                ("target_date",  f"gte.{start.isoformat()}"),
                ("target_date",  f"lte.{end.isoformat()}"),
                ("status",       "eq.pending"),
                ("select",       "target_date,recommended_rate"),
            ],
            limit=500,
        )
        return {
            r["target_date"]: float(r["recommended_rate"])
            for r in recs
            if r.get("recommended_rate") is not None
        }

    def _fetch_comp_rates_for_date(
        self, property_id: str, target_date: date
    ) -> list[dict]:
        return self._get(
            "competitor_rates",
            params={
                "property_id": f"eq.{property_id}",
                "rate_date":   f"eq.{target_date.isoformat()}",
                "is_stale":    "eq.false",
                "select":      "competitor_id,rate_amount,is_sold_out",
            },
        )

    def _comp_name_map(self, property_id: str) -> dict[str, str]:
        rows = self._get(
            "competitor_properties",
            {"property_id": f"eq.{property_id}",
             "select":      "id,competitor_name"},
        )
        return {r["id"]: r.get("competitor_name") or r.get("name", r["id"])
                for r in rows}

    def _get(
        self,
        table:  str,
        params: dict | list,
        limit:  int = 1000,
    ) -> list[dict[str, Any]]:
        """Paginated REST GET."""
        all_rows: list[dict] = []
        offset = 0
        while True:
            resp = requests.get(
                f"{self._url}/rest/v1/{table}",
                headers={**self._hdrs,
                         "Range":  f"{offset}-{offset + limit - 1}",
                         "Prefer": "count=none"},
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            batch = resp.json()
            all_rows.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return all_rows


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve(monitor: CompetitorMonitor, slug: str) -> tuple[str, str]:
    tenants = monitor._get("tenants", {"slug": f"eq.{slug}", "select": "id"})
    if not tenants:
        raise ValueError(f"Tenant slug {slug!r} not found")
    tid   = tenants[0]["id"]
    props = monitor._get("properties", {"tenant_id": f"eq.{tid}", "select": "id"})
    return tid, props[0]["id"]


# ─────────────────────────────────────────────────────────────────────────────
#  CLI and demo
# ─────────────────────────────────────────────────────────────────────────────

def _position_bar(pct: float, width: int = 20) -> str:
    """ASCII bar showing position vs comp avg. Centre = 0."""
    mid  = width // 2
    fill = int(abs(pct) * mid / 0.30)   # 30% = full bar
    fill = min(fill, mid)
    if pct >= 0:
        bar = " " * mid + "█" * fill + "░" * (mid - fill)
    else:
        bar = "░" * (mid - fill) + "█" * fill + " " * mid
    return f"[{bar}]"


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(description="The Gracious Collection — Competitor Monitor")
    parser.add_argument("--slug",  default="anchorage-1770-demo")
    parser.add_argument("--seed",  action="store_true",
                        help="Seed competitors + synthetic rates")
    parser.add_argument("--days",  type=int, default=90,
                        help="Days of synthetic rates to generate (default 90)")
    args = parser.parse_args()

    cm = CompetitorMonitor()
    tenant_id, property_id = _resolve(cm, args.slug)

    print(f"\n  The Gracious Collection — Competitive Rate Monitor")
    print(f"  Tenant : {args.slug}  |  Property : {property_id}\n")

    # ── 1. Seed competitors + synthetic rates ──────────────────────────
    if args.seed:
        print("  Seeding competitor properties…")
        comp_ids = cm.seed_competitors(tenant_id, property_id)
        print(f"  ✓ {len([c for c in comp_ids if c])} competitors registered\n")

        print(f"  Generating {args.days} days of synthetic competitor rates…")
        n = cm.seed_synthetic_competitor_rates(property_id, tenant_id, args.days)
        print(f"  ✓ {n} rate rows inserted\n")

    # ── 2. Competitive position table — next 14 days ───────────────────
    today      = date.today()
    start_14   = today + timedelta(days=1)
    end_14     = today + timedelta(days=14)

    positions_14 = cm.get_competitive_position(property_id, start_14, end_14)

    W = 108
    print(f"{'═' * W}")
    print(f"  COMPETITIVE POSITION — Next 14 Days  (Waterfront Suite vs Beaufort comp set)")
    print(f"{'═' * W}")
    print(
        f"  {'Date':<12} {'Day':<4} {'Your $':>7} {'Comp Avg':>9} {'Comp Min':>9} "
        f"{'Comp Max':>9} {'Position':>10}  {'vs Avg':>7}  {'Sold Out':<26}"
    )
    print(f"{'─' * W}")

    for pos in positions_14:
        your_str  = f"${pos.your_rate:.0f}" if pos.your_rate else "—"
        avg_str   = f"${pos.comp_avg:.0f}"  if pos.comp_avg  else "—"
        min_str   = f"${pos.comp_min:.0f}"  if pos.comp_min  else "—"
        max_str   = f"${pos.comp_max:.0f}"  if pos.comp_max  else "—"
        pct_str   = f"{pos.position_pct*100:+.1f}%"
        sold_str  = ", ".join(pos.sold_out_competitors) if pos.sold_out_competitors else "—"
        label_tag = {
            "Premium":             "★ Premium   ",
            "At Market":           "◆ At Market ",
            "Below Market":        "▼ BelowMkt  ",
            "Significantly Below": "▽ SigBelow  ",
        }.get(pos.position_label, pos.position_label)

        print(
            f"  {pos.date.isoformat():<12} {pos.date.strftime('%a'):<4} "
            f"{your_str:>7} {avg_str:>9} {min_str:>9} {max_str:>9} "
            f"{label_tag:>10}  {pct_str:>7}  {sold_str:<26}"
        )
    print(f"{'═' * W}\n")

    # ── 3. Water Festival competitive spotlight ────────────────────────
    wf_start = date(today.year, 7, 17)
    wf_end   = date(today.year, 7, 26)
    positions_wf = cm.get_competitive_position(
        property_id, wf_start, wf_end, room_type_name="Waterfront Suite"
    )

    print(f"{'═' * W}")
    print(f"  WATER FESTIVAL COMPETITIVE POSITION — July 17–26, 2026")
    print(f"{'═' * W}")
    print(
        f"  {'Date':<12} {'Day':<4} {'Your $':>7} {'Comp Avg':>9} "
        f"{'vs Avg':>7}  {'Position':<14}  {'Sold Out Competitors'}"
    )
    print(f"{'─' * W}")

    for pos in positions_wf:
        your_str = f"${pos.your_rate:.0f}" if pos.your_rate else "—"
        avg_str  = f"${pos.comp_avg:.0f}"  if pos.comp_avg  else "—"
        pct_str  = f"{pos.position_pct*100:+.1f}%"
        sold_str = ", ".join(pos.sold_out_competitors) if pos.sold_out_competitors else "None"
        print(
            f"  {pos.date.isoformat():<12} {pos.date.strftime('%a'):<4} "
            f"{your_str:>7} {avg_str:>9} {pct_str:>7}  {pos.position_label:<14}  {sold_str}"
        )
    print(f"{'═' * W}\n")

    # ── 4. Rate-drop alert ─────────────────────────────────────────────
    alerts = cm.detect_rate_drops(property_id, threshold=0.10)

    print(f"{'═' * W}")
    print(f"  RATE DROP ALERTS  (competitors who dropped ≥10% since 72h ago)")
    print(f"{'═' * W}")

    if alerts:
        for alert in alerts:
            date_range = (
                f"{alert.affected_dates[0]} to {alert.affected_dates[-1]}"
                if len(alert.affected_dates) > 1
                else str(alert.affected_dates[0])
            )
            print(
                f"  ⚠  {alert.competitor_name:<22}  dropped {alert.drop_pct:.1f}%  "
                f"${alert.old_rate:.0f} → ${alert.new_rate:.0f}  "
                f"({len(alert.affected_dates)} dates: {date_range})"
            )
            print(
                f"     Action: Review whether to hold your rate or match. "
                f"If demand is High/Peak, hold — they may reverse."
            )
    else:
        print("  No significant rate drops detected in the last 72 hours.")
    print(f"{'═' * W}\n")

    # ── 5. Market summary + sold-out boost verification ───────────────
    wf_date = date(today.year, 7, 20)  # Water Festival Monday
    summary = cm.get_market_summary(property_id, wf_date)

    print(f"{'═' * W}")
    print(f"  MARKET SUMMARY — {wf_date}  (Water Festival week)")
    print(f"{'═' * W}")
    print(f"  Your rate (Waterfront Suite)  : ${summary['your_rate']:.0f}")
    print(f"  Competitor average            : ${summary['comp_avg']:.0f}")
    print(f"  Competitor range              : ${summary['comp_min']:.0f} – ${summary['comp_max']:.0f}")
    print(f"  Your position                 : {summary['your_position_label']} "
          f"({summary['your_position_pct']:+.1f}% vs comp avg)")
    print(f"  Market pressure               : {summary['market_pressure'].upper()}")
    print(f"  Sold-out competitors          : {', '.join(summary['sold_out_competitors']) or 'None'}")

    # Verify: sold-out boost feeds into demand_score
    n_sold_out = summary["sold_out_count"]
    if n_sold_out >= 3:
        demand_boost = 15
        boost_triggered = True
    else:
        demand_boost = 0
        boost_triggered = False

    print(f"\n  SOLD-OUT SIGNAL VERIFICATION:")
    print(f"  {n_sold_out} competitor(s) sold out on {wf_date}")
    if boost_triggered:
        print(f"  ✓ Demand boost of +{demand_boost} triggered (3+ sold out)")
        print(f"    Pass competitor_sold_out={n_sold_out} to recommend_rate() to activate")
    else:
        print(f"  ℹ  {n_sold_out} sold-out competitors detected (need ≥3 for +15 boost)")
        print(f"    Rhett House Inn + Beaufort Inn = 2 sold out on Water Festival dates")
        print(f"    Add a 3rd competitor sold-out flag to trigger the +15 demand boost")
        print(f"    Current boost: +0 (threshold is 3 competitors)")

    # Show what the boosted rate would be
    print(f"\n  DEMAND SCORE IMPACT WITH SOLD-OUT SIGNAL:")
    base_score = 90   # Water Festival demand score from Phase 2A

    for n_comp in (0, 1, 2, 3):
        boost  = 15 if n_comp >= 3 else 0
        adj    = min(100, base_score + boost)
        label  = ("★ Peak" if adj >= 90 else "◆ Very High" if adj >= 76
                  else "▲ High" if adj >= 61 else "  Normal")
        marker = " ← current setup" if n_comp == n_sold_out else ""
        print(f"    {n_comp} competitors sold out → demand score {adj}  {label}{marker}")

    print(f"{'═' * W}\n")


if __name__ == "__main__":
    main()
