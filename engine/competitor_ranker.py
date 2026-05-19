"""
engine/competitor_ranker.py
Competitor Proximity Scoring & Tiered Market Signals

Scores competitors on five dimensions, stores rankings in DB,
and provides tiered market signals for tier-aware rate pricing.
"""
from __future__ import annotations

import logging
import math
import os
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
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
#  Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompetitorRank:
    competitor_id:    str
    competitor_name:  str
    composite_score:  float
    rank:             int
    price_band_score: float
    amenity_score:    float
    distance_score:   float
    review_score:     float
    size_score:       float
    property_tier:    int = 1
    is_primary:       bool = False
    rank_reason:      str = ""


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def rank_competitors(
    property_id: str,
    tenant_id:   str,
    *,
    supabase_url: str | None = None,
    service_key:  str | None = None,
) -> list[CompetitorRank]:
    """
    Score and rank all active competitors for a property.
    Stores results in competitor_rankings. Returns ranked list.
    """
    ranker = CompetitorRanker(supabase_url=supabase_url, service_key=service_key)
    return ranker.rank_competitors(property_id, tenant_id)


def get_primary_competitor(
    property_id: str,
    *,
    supabase_url: str | None = None,
    service_key:  str | None = None,
) -> dict[str, Any] | None:
    ranker = CompetitorRanker(supabase_url=supabase_url, service_key=service_key)
    return ranker.get_primary_competitor(property_id)


def get_tiered_market_signals(
    property_id:  str,
    target_date:  date,
    *,
    supabase_url: str | None = None,
    service_key:  str | None = None,
) -> dict[str, Any]:
    """
    Return rich market context grouped by tier for tier-aware pricing.
    Dict keys:
      tier1_comps      — list of Tier 1 comp data with rate + sold_out
      tier1_primary    — rank-1 direct competitor (name, rate, sold_out)
      tier2_ceiling    — max rate among Tier 2 upscale hotels
      tier3_reference  — max rate among Tier 3 luxury properties
      tier4_floor      — average rate among Tier 4 budget anchors
      tier4_compression— True if budget hotel avg > 150% of historical avg
      market_ladder    — all comps sorted by rate for visualization
    """
    ranker = CompetitorRanker(supabase_url=supabase_url, service_key=service_key)
    return ranker.get_tiered_market_signals(property_id, target_date)


# ─────────────────────────────────────────────────────────────────────────────
#  CompetitorRanker class
# ─────────────────────────────────────────────────────────────────────────────

class CompetitorRanker:
    WEIGHTS = {"price_band": 0.30, "amenity": 0.25, "distance": 0.20,
               "review": 0.15, "size": 0.10}

    # Known waterfront properties on Beaufort River / Bay Street
    _WATERFRONT_NAMES = {"cuthbert", "anchorage", "bay street"}

    def __init__(self, supabase_url=None, service_key=None):
        url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")
        self._url  = url
        self._hdrs = {
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "count=none",
        }

    # ------------------------------------------------------------------ #
    #  Ranking                                                             #
    # ------------------------------------------------------------------ #

    def rank_competitors(self, property_id: str, tenant_id: str) -> list[CompetitorRank]:
        competitors = self._get("competitor_properties", {
            "property_id": f"eq.{property_id}",
            "active":      "eq.true",
            "select":      "id,competitor_name,name,notes,property_tier,"
                           "room_count,trip_advisor_rating,distance_miles,"
                           "latitude,longitude",
        })
        if not competitors:
            return []

        prop_info  = self._get("properties", {"id": f"eq.{property_id}",
                                               "select": "id,total_rooms,city"})
        prop_rooms = int(prop_info[0].get("total_rooms") or 15) if prop_info else 15
        prop_rates = self._fetch_property_rates(property_id)
        comp_rates = self._fetch_competitor_rates(property_id)

        ranked: list[CompetitorRank] = []
        for comp in competitors:
            cid       = comp["id"]
            cname     = comp.get("competitor_name") or comp.get("name", "")
            notes     = comp.get("notes") or ""
            tier      = int(comp.get("property_tier") or 1)
            c_rooms   = comp.get("room_count")
            c_rating  = comp.get("trip_advisor_rating")
            c_dist    = comp.get("distance_miles")
            rates     = comp_rates.get(cid, [])

            pb = self._price_band_score(prop_rates, rates)
            am = self._amenity_score(cname, notes, tier)
            ds = self._distance_score(cname, notes, c_dist)
            rv = self._review_score(c_rating)
            sz = self._size_score(prop_rooms, c_rooms, cname)

            composite = (pb * self.WEIGHTS["price_band"] +
                         am * self.WEIGHTS["amenity"]    +
                         ds * self.WEIGHTS["distance"]   +
                         rv * self.WEIGHTS["review"]     +
                         sz * self.WEIGHTS["size"])

            ranked.append(CompetitorRank(
                competitor_id=cid, competitor_name=cname,
                composite_score=round(composite, 2), rank=0,
                price_band_score=round(pb, 1), amenity_score=round(am, 1),
                distance_score=round(ds, 1), review_score=round(rv, 1),
                size_score=round(sz, 1), property_tier=tier,
            ))

        ranked.sort(key=lambda r: -r.composite_score)
        for i, r in enumerate(ranked, 1):
            r.rank       = i
            r.is_primary = (i == 1)
            r.rank_reason = self._explain(r)

        self._save_rankings(tenant_id, property_id, ranked)
        return ranked

    def get_primary_competitor(self, property_id: str) -> dict[str, Any] | None:
        rows = self._get("competitor_rankings",
                         {"property_id": f"eq.{property_id}", "rank": "eq.1",
                          "select": "competitor_id"})
        if rows:
            comp_id = rows[0]["competitor_id"]
            comps = self._get("competitor_properties",
                              {"id": f"eq.{comp_id}",
                               "select": "id,competitor_name,name,property_tier"})
            if comps:
                return comps[0]

        # Legacy fallback
        comps = self._get("competitor_properties",
                          {"property_id": f"eq.{property_id}",
                           "competitor_name": "ilike.*Cuthbert*",
                           "select": "id,competitor_name,name,property_tier"})
        return comps[0] if comps else None

    # ------------------------------------------------------------------ #
    #  Tiered market signals                                               #
    # ------------------------------------------------------------------ #

    def get_tiered_market_signals(
        self, property_id: str, target_date: date
    ) -> dict[str, Any]:
        # Fetch all active competitors with their tiers
        comps = self._get("competitor_properties", {
            "property_id": f"eq.{property_id}",
            "active": "eq.true",
            "select": "id,competitor_name,name,property_tier",
        })
        if not comps:
            return _empty_signals()

        # Build comp_id → tier map
        tier_map: dict[str, int] = {
            c["id"]: int(c.get("property_tier") or 1) for c in comps
        }
        name_map: dict[str, str] = {
            c["id"]: c.get("competitor_name") or c.get("name", "") for c in comps
        }

        # Fetch rates for target date
        date_str = target_date.isoformat()
        rate_rows = self._get("competitor_rates", [
            ("property_id", f"eq.{property_id}"),
            ("rate_date",   f"eq.{date_str}"),
            ("is_stale",    "eq.false"),
            ("select",      "competitor_id,rate_amount,is_sold_out"),
        ])
        rate_map: dict[str, dict] = {
            r["competitor_id"]: {
                "rate":      float(r["rate_amount"] or 0),
                "sold_out":  bool(r["is_sold_out"]),
            }
            for r in rate_rows if r.get("rate_amount") is not None
        }

        # Get primary competitor
        primary_comp = self.get_primary_competitor(property_id)
        primary_id   = primary_comp["id"] if primary_comp else None

        # Group by tier
        tier1_comps: list[dict]  = []
        tier2_rates: list[float] = []
        tier3_rates: list[float] = []
        tier4_rates: list[float] = []
        market_ladder: list[dict] = []

        for cid, tier in tier_map.items():
            cname = name_map[cid]
            rdata = rate_map.get(cid)
            rate  = rdata["rate"]     if rdata else None
            sold  = rdata["sold_out"] if rdata else False

            entry = {"competitor_id": cid, "name": cname, "tier": tier,
                     "rate": rate, "sold_out": sold,
                     "is_primary": cid == primary_id}

            if tier == 1:
                tier1_comps.append(entry)
            elif tier == 2 and rate:
                tier2_rates.append(rate)
            elif tier == 3 and rate:
                tier3_rates.append(rate)
            elif tier == 4 and rate:
                tier4_rates.append(rate)

            if rate:
                market_ladder.append(entry)

        market_ladder.sort(key=lambda x: -(x["rate"] or 0))

        tier1_primary = next(
            (c for c in tier1_comps if c["is_primary"]),
            tier1_comps[0] if tier1_comps else None,
        )

        # Budget compression: floor > 150% of historical Beaufort avg ($195)
        tier4_floor = statistics.mean(tier4_rates) if tier4_rates else None
        tier4_compression = bool(tier4_floor and tier4_floor > 195 * 1.50)

        return {
            "tier1_comps":      tier1_comps,
            "tier1_primary":    tier1_primary,
            "tier2_ceiling":    max(tier2_rates) if tier2_rates else None,
            "tier3_reference":  max(tier3_rates) if tier3_rates else None,
            "tier4_floor":      tier4_floor,
            "tier4_compression": tier4_compression,
            "market_ladder":    market_ladder,
        }

    # ------------------------------------------------------------------ #
    #  Scoring dimensions                                                  #
    # ------------------------------------------------------------------ #

    def _price_band_score(self, prop: list[float], comp: list[float]) -> float:
        if not prop or not comp:
            return 40.0
        p_lo, p_hi = min(prop), max(prop)
        c_lo, c_hi = min(comp), max(comp)
        overlap = max(0, min(p_hi, c_hi) - max(p_lo, c_lo))
        span    = max(p_hi, c_hi) - min(p_lo, c_lo)
        if span == 0:
            return 80.0
        p_med = statistics.median(prop)
        c_med = statistics.median(comp)
        med_pct  = abs(p_med - c_med) / max(p_med, c_med)
        med_bonus = max(0, 1.0 - med_pct * 2) * 40
        return min(100.0, (overlap / span) * 60 + med_bonus)

    def _amenity_score(self, name: str, notes: str, tier: int) -> float:
        """
        25% weight. Weighted similarity to Anchorage 1770:
          Waterfront on same waterway  +50
          Historic antebellum property +20
          Boutique inn under 15 rooms  +20
          Breakfast included           +10
          Description waterfront bonus +15 (additive if in notes)
        """
        n = name.lower()
        nt = notes.lower()
        combined = f"{n} {nt}"

        # Tier 2-4 have structural penalty — they're not direct comps
        if tier >= 2:
            return max(10.0, 50.0 - (tier - 1) * 20)

        score = 0.0

        # Waterfront — guard against negation phrases
        is_waterfront = (
            any(k in n for k in self._WATERFRONT_NAMES)
            or (
                any(w in combined for w in ["waterfront", "river view", "bay view",
                                             "river front", "beaufort river"])
                and not any(neg in combined for neg in
                            ["not waterfront", "garden property", "craven st",
                             "no waterfront", "no water"])
            )
        )
        if is_waterfront:
            score += 50

        if any(w in combined for w in ["historic", "antebellum", "1770",
                                        "plantation", "19th century"]):
            score += 20

        if any(w in combined for w in ["inn", "bed and breakfast", "b&b",
                                        "boutique", "manor"]):
            score += 20

        if any(w in combined for w in ["breakfast", "b&b", "morning meal"]):
            score += 10

        # Positive waterfront mention in notes (not negation)
        if any(w in nt for w in ["waterfront", "river view", "bay view"]) \
                and not any(neg in nt for neg in ["not waterfront", "no waterfront"]):
            score += 15

        return min(100.0, score)

    def _distance_score(self, name: str, notes: str,
                        dist_miles: float | None) -> float:
        if dist_miles is not None:
            return max(0.0, 100.0 - dist_miles * 4)
        combined = f"{name.lower()} {notes.lower()}"
        if any(w in combined for w in ["bay street", "craven", "port republic"]):
            return 90.0
        if any(w in combined for w in ["downtown", "historic district", "beaufort"]):
            return 60.0
        return 40.0

    def _review_score(self, rating: float | None) -> float:
        # Subject property (Anchorage) ≈ 4.5 rating
        if rating:
            diff = abs(4.5 - float(rating))
            return max(0.0, 100.0 - diff * 30)
        return 50.0

    def _size_score(self, prop_rooms: int, comp_rooms: int | None,
                    name: str = "") -> float:
        # Fallback estimates from known data
        _known = {"rhett": 17, "cuthbert": 10, "bay street": 8,
                  "beaufort inn": 21, "hampton": 118, "marriott": 512}
        if comp_rooms is None:
            for key, count in _known.items():
                if key in name.lower():
                    comp_rooms = count
                    break
        if comp_rooms is None:
            return 50.0
        diff = abs(prop_rooms - comp_rooms)
        return max(0.0, 100.0 - diff * 5)

    def _explain(self, r: CompetitorRank) -> str:
        parts = []
        if r.price_band_score >= 70:
            parts.append(f"rate overlap {r.price_band_score:.0f}/100")
        # Distance thresholds: 95+ = <1.25 mi (same block), 80-94 = Beaufort district
        if r.distance_score >= 95 and r.property_tier == 1:
            parts.append("same block (Bay Street)")
        elif r.distance_score >= 75 and r.property_tier == 1:
            parts.append("Beaufort historic district")
        if r.amenity_score >= 80:
            parts.append("waterfront boutique inn")
        elif r.amenity_score >= 55:
            parts.append("historic boutique property")
        if r.property_tier == 2:
            parts.append("Tier 2 upscale hotel benchmark")
        if r.property_tier == 4:
            parts.append(f"Tier 4 budget anchor ({r.distance_score:.0f}/100 proximity)")
        return "; ".join(parts) or f"composite {r.composite_score:.0f}/100"

    # ------------------------------------------------------------------ #
    #  DB helpers                                                          #
    # ------------------------------------------------------------------ #

    def _fetch_property_rates(self, property_id: str) -> list[float]:
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        rows   = self._get("rate_recommendations", {
            "property_id": f"eq.{property_id}",
            "target_date": f"gte.{cutoff}",
            "select":      "recommended_rate",
        })
        return [float(r["recommended_rate"]) for r in rows
                if r.get("recommended_rate")]

    def _fetch_competitor_rates(self, property_id: str) -> dict[str, list[float]]:
        rows = self._get("competitor_rates", {
            "property_id": f"eq.{property_id}",
            "is_stale":    "eq.false",
            "is_sold_out": "eq.false",
            "select":      "competitor_id,rate_amount",
        }, limit=5000)
        out: dict[str, list[float]] = {}
        for r in rows:
            amt = r.get("rate_amount")
            if amt:
                out.setdefault(r["competitor_id"], []).append(float(amt))
        return out

    def _save_rankings(self, tenant_id: str, property_id: str,
                       ranked: list[CompetitorRank]) -> None:
        requests.delete(
            f"{self._url}/rest/v1/competitor_rankings",
            headers=self._hdrs,
            params={"property_id": f"eq.{property_id}"},
            timeout=15,
        )
        if ranked:
            requests.post(
                f"{self._url}/rest/v1/competitor_rankings",
                headers={**self._hdrs, "Prefer": "return=minimal"},
                json=[{
                    "tenant_id": tenant_id, "property_id": property_id,
                    "competitor_id": r.competitor_id,
                    "composite_score": r.composite_score, "rank": r.rank,
                    "price_band_score": r.price_band_score,
                    "amenity_score": r.amenity_score,
                    "distance_score": r.distance_score,
                    "review_score": r.review_score,
                    "size_score": r.size_score,
                } for r in ranked],
                timeout=15,
            ).raise_for_status()

    def _get(self, table: str, params, limit: int = 1000) -> list[dict]:
        resp = requests.get(
            f"{self._url}/rest/v1/{table}",
            headers=self._hdrs, params=params, timeout=20,
        )
        resp.raise_for_status()
        return resp.json()


def _empty_signals() -> dict[str, Any]:
    return {"tier1_comps": [], "tier1_primary": None, "tier2_ceiling": None,
            "tier3_reference": None, "tier4_floor": None,
            "tier4_compression": False, "market_ladder": []}
