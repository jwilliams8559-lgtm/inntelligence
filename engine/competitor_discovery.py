"""
engine/competitor_discovery.py
Autonomous Competitor Discovery via Google Places API

Uses Google Places Nearby Search (legacy API) when GOOGLE_PLACES_API_KEY is set;
falls back to a realistic Beaufort SC mock for demo / offline use.

Usage:
    python -m engine.competitor_discovery --slug anchorage-1770-demo \\
        --address "1103 Bay Street, Beaufort, SC 29902" --radius 25

    python -m engine.competitor_discovery --savannah   # multi-city proof
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

_HERE         = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from engine.description_parser import classify_lodging_tier, parse_room_description
from engine.competitor_ranker   import CompetitorRanker

logger = logging.getLogger(__name__)

_PLACES_BASE     = "https://maps.googleapis.com/maps/api/place"
_GEO_BASE        = "https://maps.googleapis.com/maps/api/geocode/json"
_PLACES_NEW_BASE = "https://places.googleapis.com/v1/places"

_PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_INEXPENSIVE":  1,
    "PRICE_LEVEL_MODERATE":     2,
    "PRICE_LEVEL_EXPENSIVE":    3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

def _normalize_new_place(p: dict) -> dict:
    """Convert a Places API (New) place object to legacy-compatible format."""
    loc = p.get("location", {})
    pl_str = p.get("priceLevel", "")
    return {
        "place_id":  p.get("id", ""),
        "name":      p.get("displayName", {}).get("text", ""),
        "geometry":  {"location": {"lat": loc.get("latitude", 0.0),
                                   "lng": loc.get("longitude", 0.0)}},
        "rating":    p.get("rating"),
        "price_level": _PRICE_LEVEL_MAP.get(pl_str),
        "types":     p.get("types", []),
        "vicinity":  p.get("formattedAddress", ""),
    }


def _places_new_nearby(
    lat: float, lng: float, radius_m: int,
    keyword: str | None, api_key: str,
) -> list[dict]:
    """Places API (New) — nearbySearch or searchText depending on keyword."""
    field_mask = ("places.id,places.displayName,places.location,"
                  "places.rating,places.priceLevel,places.types,"
                  "places.formattedAddress")
    headers = {
        "Content-Type":     "application/json",
        "X-Goog-Api-Key":   api_key,
        "X-Goog-FieldMask": field_mask,
    }

    if keyword:
        # Text search: query = "keyword near lat,lng"
        body = {
            "textQuery": keyword,
            "includedType": "lodging",
            "locationBias": {
                "circle": {
                    "center":  {"latitude": lat, "longitude": lng},
                    "radius":  float(radius_m),
                }
            },
            "maxResultCount": 20,
        }
        resp = requests.post(f"{_PLACES_NEW_BASE}:searchText",
                             headers=headers, json=body, timeout=15)
    else:
        body = {
            "includedTypes": ["lodging"],
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius_m),
                }
            },
            "maxResultCount": 20,
        }
        resp = requests.post(f"{_PLACES_NEW_BASE}:searchNearby",
                             headers=headers, json=body, timeout=15)

    if resp.status_code != 200:
        logger.warning("Places API (New) HTTP %d: %s", resp.status_code, resp.text[:200])
        return []
    return [_normalize_new_place(p) for p in resp.json().get("places", [])]


def _places_new_details(place_id: str, api_key: str) -> dict:
    """Places API (New) — fetch place details; return legacy-compatible dict."""
    fields = ("displayName,formattedAddress,rating,priceLevel,"
              "websiteUri,nationalPhoneNumber,businessStatus,"
              "types,userRatingCount")
    resp = requests.get(
        f"{_PLACES_NEW_BASE}/{place_id}",
        headers={"X-Goog-Api-Key": api_key,
                 "X-Goog-FieldMask": fields},
        timeout=15,
    )
    if resp.status_code != 200:
        logger.warning("Places API (New) details HTTP %d for %r",
                       resp.status_code, place_id)
        return {}
    d = resp.json()
    pl_str = d.get("priceLevel", "")
    return {
        "name":                   d.get("displayName", {}).get("text", ""),
        "formatted_address":      d.get("formattedAddress", ""),
        "rating":                 d.get("rating"),
        "price_level":            _PRICE_LEVEL_MAP.get(pl_str),
        "website":                d.get("websiteUri", ""),
        "formatted_phone_number": d.get("nationalPhoneNumber", ""),
        "business_status":        d.get("businessStatus", ""),
        "types":                  d.get("types", []),
        "user_ratings_total":     d.get("userRatingCount", 0),
    }

# ─────────────────────────────────────────────────────────────────────────────
#  Public Google Places API helpers
# ─────────────────────────────────────────────────────────────────────────────

def geocode_address(address: str) -> tuple[float, float]:
    """
    Geocode *address* → (latitude, longitude).
    Raises ValueError with a clear message if geocoding fails.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_PLACES_API_KEY not set in environment")

    resp = requests.get(
        _GEO_BASE,
        params={"address": address, "key": api_key},
        timeout=15,
    )
    data = resp.json()
    if data.get("status") == "OK" and data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]

    raise ValueError(
        f"Geocoding failed for {address!r}: "
        f"status={data.get('status')} message={data.get('error_message', '')}"
    )


def search_nearby_lodging(
    lat: float,
    lng: float,
    radius_meters: int,
    lodging_type: str | None = None,
    keyword:      str | None = None,
) -> list[dict]:
    """
    Google Places Nearby Search — type=lodging within *radius_meters*.
    Tries the legacy nearbysearch API first; automatically falls back to
    Places API (New) if the legacy API returns REQUEST_DENIED.
    Returns a list of legacy-format place dicts (always has 'place_id' key).
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_PLACES_API_KEY not set in environment")

    # ── Attempt 1: legacy nearbysearch ───────────────────────────────────────
    endpoint = f"{_PLACES_BASE}/nearbysearch/json"
    params: dict[str, Any] = {
        "location": f"{lat},{lng}",
        "radius":   radius_meters,
        "type":     "lodging",
        "key":      api_key,
    }
    if keyword:
        params["keyword"] = keyword

    all_results: list[dict] = []
    legacy_denied = False

    for _page in range(3):
        resp   = requests.get(endpoint, params=params, timeout=15)
        data   = resp.json()
        status = data.get("status")

        if status == "REQUEST_DENIED":
            logger.info("Legacy Places API denied (keyword=%r); using Places API (New)",
                        keyword)
            legacy_denied = True
            break
        if status in ("ZERO_RESULTS", "INVALID_REQUEST"):
            break
        if status != "OK":
            logger.warning("Places nearbysearch: %s — keyword=%r", status, keyword)
            break

        all_results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token:
            break
        time.sleep(2)
        params = {"pagetoken": token, "key": api_key}

    if legacy_denied:
        return _places_new_nearby(lat, lng, radius_meters, keyword, api_key)

    return all_results


def get_place_details(place_id: str) -> dict:
    """
    Fetch full Place Details for *place_id*.
    Tries the legacy Place Details API first; falls back to Places API (New)
    if REQUEST_DENIED. Always returns a legacy-compatible dict.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        return {}

    fields = (
        "name,formatted_address,rating,price_level,"
        "website,formatted_phone_number,business_status,"
        "types,user_ratings_total,photos"
    )
    resp = requests.get(
        f"{_PLACES_BASE}/details/json",
        params={"place_id": place_id, "fields": fields, "key": api_key},
        timeout=15,
    )
    data = resp.json()
    status = data.get("status")
    if status == "OK":
        return data.get("result", {})
    if status == "REQUEST_DENIED":
        logger.debug("Legacy Place Details denied for %r; using Places API (New)", place_id)
        return _places_new_details(place_id, api_key)
    logger.warning("Place Details %r: %s", place_id, status)
    return {}


def search_by_text(query: str) -> list[dict]:
    """
    Google Places Text Search — find a specific named property by free-text query.
    Uses Places API (New) searchText endpoint. Returns up to 3 normalized
    legacy-format place dicts (guaranteed to have 'place_id' key).
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        return []

    field_mask = ("places.id,places.displayName,places.location,"
                  "places.rating,places.priceLevel,places.types,"
                  "places.formattedAddress")
    headers = {
        "Content-Type":     "application/json",
        "X-Goog-Api-Key":   api_key,
        "X-Goog-FieldMask": field_mask,
    }
    resp = requests.post(
        f"{_PLACES_NEW_BASE}:searchText",
        headers=headers,
        json={"textQuery": query, "maxResultCount": 3},
        timeout=15,
    )
    if resp.status_code != 200:
        logger.warning("Text search %r: HTTP %d", query, resp.status_code)
        return []
    places = resp.json().get("places", [])
    logger.info("Text search %r → %d result(s)", query, len(places))
    return [_normalize_new_place(p) for p in places]


# ─────────────────────────────────────────────────────────────────────────────
#  Primary discovery pipeline
# ─────────────────────────────────────────────────────────────────────────────

def discover_competitors_google(
    property_id:      str | None,
    property_address: str,
    radius_miles:     float = 25.0,
    db_conn:          Any        = None,
    text_searches:    list[str] | None = None,
) -> dict[str, Any]:
    """
    Full Google Places competitor discovery pipeline (hybrid approach).

    Step 1  — Geocode property_address → lat/lng.
    Step 2  — 7 nearby searches + text searches for known competitors.
    Step 3  — Fetch full details, compute distance, classify tier via Claude,
              apply force-tier overrides for known chains.
    Step 4  — Group into tier1 / tier2 / tier3 / tier4 buckets.
    Step 5  — Upsert → seed rates for new competitors → re-rank.

    Returns a discovery_result dict compatible with discover_competitors().
    text_searches: list of query strings for search_by_text(); pass
                   _BEAUFORT_TEXT_SEARCHES for the Beaufort SC property.
    """
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }

    # ── Step 1: Geocode ───────────────────────────────────────────────────────
    logger.info("Geocoding: %r", property_address)
    lat, lng = geocode_address(property_address)
    logger.info("  → (%.5f, %.5f)", lat, lng)

    # Look up property name for subject-property filtering
    prop_name = ""
    tenant_id = ""
    if property_id and url and key:
        rows = requests.get(
            f"{url}/rest/v1/properties",
            headers={**hdrs, "Prefer": "count=none"},
            params={"id": f"eq.{property_id}", "select": "name,tenant_id"},
            timeout=10,
        ).json()
        if rows:
            prop_name = rows[0].get("name", "")
            tenant_id = rows[0].get("tenant_id", "")

    # ── Step 2: Seven targeted searches ──────────────────────────────────────
    r_m  = int(radius_miles * 1609)
    r15  = int(min(15,  radius_miles) * 1609)
    r75  = int(min(75,  radius_miles) * 1609)
    r10  = int(min(10,  radius_miles) * 1609)

    searches = [
        (r_m,  "boutique inn"),
        (r_m,  "bed and breakfast"),
        (r_m,  "historic inn"),
        (r15,  None),                # all lodging within 15 mi
        (r75,  "luxury resort"),
        (r10,  "Hampton Inn"),
        (r10,  "budget hotel"),
    ]

    raw_by_id: dict[str, dict] = {}
    for radius, kw in searches:
        try:
            results = search_nearby_lodging(lat, lng, radius, keyword=kw)
            for p in results:
                pid = p.get("place_id", "")
                if pid and pid not in raw_by_id:
                    raw_by_id[pid] = p
        except RuntimeError as exc:
            logger.error("search_nearby_lodging failed: %s", exc)
            raise

    # ── Text searches for specific known competitors (hybrid approach) ────────
    if text_searches:
        logger.info("Running %d text searches for known competitors", len(text_searches))
        for query in text_searches:
            try:
                for p in search_by_text(query):
                    pid = p.get("place_id", "")
                    if pid and pid not in raw_by_id:
                        raw_by_id[pid] = p
            except Exception as exc:
                logger.warning("Text search %r failed: %s", query, exc)

    logger.info("Deduplicated: %d unique places across all searches", len(raw_by_id))

    # ── Step 3: Details + distance + tier classification ──────────────────────
    tier1_suggested: list[dict] = []
    tier1_other:     list[dict] = []
    tier2_hotels:    list[dict] = []
    tier3_luxury:    list[dict] = []
    tier4_budget:    list[dict] = []

    processed: list[dict] = []

    for place_id, place in raw_by_id.items():
        name = place.get("name", "")

        # Skip the subject property itself
        if prop_name and name and prop_name.lower() in name.lower():
            continue

        # Get full details
        details = get_place_details(place_id)
        if details.get("business_status") == "CLOSED_PERMANENTLY":
            continue

        # Coordinates + distance
        geom = place.get("geometry", {}).get("location", {})
        p_lat = geom.get("lat", 0.0)
        p_lng = geom.get("lng", 0.0)
        dist  = round(_haversine(lat, lng, p_lat, p_lng), 2)

        # Skip if < 0.02 mi (same-block building effectively at same location)
        if dist < 0.02:
            continue

        # Price level: details overrides place-level if present
        price_level = details.get("price_level") or place.get("price_level")
        rating      = details.get("rating")      or place.get("rating")
        types       = details.get("types")       or place.get("types", [])
        address     = details.get("formatted_address", place.get("vicinity", ""))
        website     = details.get("website", "")
        phone       = details.get("formatted_phone_number", "")
        n_reviews   = details.get("user_ratings_total", 0)

        # Tier classification via Claude (falls back to heuristics automatically)
        brand = _infer_brand(name)
        tier_result = classify_lodging_tier(
            property_name=name,
            brand=brand,
            price_level=price_level or 2,
            rating=float(rating or 0),
            description=address,
        )
        tier     = tier_result.get("tier", 1)
        category = tier_result.get("category", "boutique_inn")

        # Force-tier overrides for known chains (Claude can be inconsistent)
        nl = name.lower()
        if any(k in nl for k in _FORCE_T3_KW):
            tier, category = 3, "luxury_hotel"
        elif any(k in nl for k in _FORCE_T4_KW):
            tier, category = 4, "select_service_hotel"

        # Tier-specific radius filter
        if tier == 1 and dist > radius_miles:
            continue
        if tier == 2 and dist > min(15, radius_miles):
            continue
        if tier == 3 and dist > min(75, radius_miles):
            continue
        if tier == 4 and dist > min(10, radius_miles):
            continue

        comp = {
            "name":           name,
            "category":       category,
            "tier":           tier,
            "reasoning":      tier_result.get("reasoning", ""),
            "lat":            p_lat,
            "lng":            p_lng,
            "distance_miles": dist,
            "price_level":    price_level,
            "rating":         rating,
            "n_reviews":      n_reviews,
            "address":        address,
            "website":        website,
            "phone":          phone,
            "place_id":       place_id,
            "brand":          brand,
            "google_maps_url": f"https://maps.google.com/maps/place/?q=place_id:{place_id}",
        }
        processed.append(comp)

    # Sort within each tier by distance, then bucket
    processed.sort(key=lambda c: c["distance_miles"])
    for comp in processed:
        tier = comp["tier"]
        if tier == 1:
            if len(tier1_suggested) < 3:
                tier1_suggested.append(comp)
            else:
                tier1_other.append(comp)
        elif tier == 2:
            tier2_hotels.append(comp)
        elif tier == 3:
            tier3_luxury.append(comp)
        else:
            tier4_budget.append(comp)

    # ── Step 5: Upsert → seed rates → re-rank ────────────────────────────────
    upserted      = 0
    rates_seeded  = 0
    ranked_comps: list[dict] = []

    if property_id and tenant_id and url and key:
        all_comps = (tier1_suggested + tier1_other +
                     tier2_hotels + tier3_luxury + tier4_budget)

        for comp in all_comps:
            try:
                _upsert_from_places(comp, property_id, tenant_id, url, hdrs)
                upserted += 1
            except Exception as exc:
                logger.warning("Upsert failed for %r: %s", comp["name"], exc)
        logger.info("Upserted %d competitors to competitor_properties", upserted)

        # Seed synthetic rates for any newly discovered competitors
        if upserted > 0:
            rates_seeded = _seed_new_competitor_rates(
                property_id, tenant_id, all_comps, url, hdrs
            )
            logger.info("Seeded %d rate rows for new competitors", rates_seeded)

        # Re-rank the full competitor set
        try:
            ranker = CompetitorRanker(supabase_url=url, service_key=key)
            ranked = ranker.rank_competitors(property_id, tenant_id)
            ranked_comps = [
                {"rank": r.rank, "name": r.competitor_id,
                 "score": r.composite_score}
                for r in ranked
            ]
            # Replace competitor_id with name via quick lookup
            comp_ids = [r.competitor_id for r in ranked]
            if comp_ids:
                id_filter = ",".join(comp_ids)
                name_rows = requests.get(
                    f"{url}/rest/v1/competitor_properties",
                    headers={**hdrs, "Prefer": "count=none"},
                    params={"id": f"in.({id_filter})",
                            "select": "id,competitor_name,property_tier"},
                    timeout=15,
                ).json()
                name_by_id = {r["id"]: r for r in (name_rows or [])}
                ranked_comps = [
                    {
                        "rank":  r.rank,
                        "name":  name_by_id.get(r.competitor_id, {}).get("competitor_name", r.competitor_id),
                        "tier":  name_by_id.get(r.competitor_id, {}).get("property_tier", 1),
                        "score": r.composite_score,
                    }
                    for r in ranked
                ]
            logger.info("Ranking updated: top comp = %s (score %.1f)",
                        ranked_comps[0]["name"] if ranked_comps else "—",
                        ranked_comps[0]["score"] if ranked_comps else 0)
        except Exception as exc:
            logger.warning("Re-ranking failed: %s", exc)

    return {
        "property_id":           property_id,
        "property_address":      property_address,
        "geocoded_lat":          lat,
        "geocoded_lng":          lng,
        "radius_miles":          radius_miles,
        "source":                "google_places",
        "total_raw":             len(raw_by_id),
        "total_found":           len(processed),
        "upserted":              upserted,
        "rates_seeded":          rates_seeded,
        "suggested_competitors": tier1_suggested,
        "other_tier1":           tier1_other,
        "tier2_hotels":          tier2_hotels,
        "tier3_luxury":          tier3_luxury,
        "tier4_budget":          tier4_budget,
        "ranked_competitors":    ranked_comps,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Legacy public API — updated to route through Google when key is present
# ─────────────────────────────────────────────────────────────────────────────

def discover_competitors(
    property_id:  str,
    tenant_id:    str,
    radius_miles: float = 25.0,
    *,
    address:      str | None = None,
    supabase_url: str | None = None,
    service_key:  str | None = None,
) -> dict[str, Any]:
    """
    Discover competitors around a property.
    Routes to discover_competitors_google() when GOOGLE_PLACES_API_KEY + address
    are available; otherwise returns the Beaufort SC mock dataset.
    """
    google_key = os.getenv("GOOGLE_PLACES_API_KEY", "")

    if google_key and address:
        try:
            return discover_competitors_google(property_id, address, radius_miles)
        except Exception as exc:
            logger.warning("Google discovery failed (%s); falling back to mock", exc)

    # ── Mock fallback ─────────────────────────────────────────────────────────
    logger.info("Using Beaufort SC mock dataset")
    candidates = _filter_by_radius(_BEAUFORT_MOCK, radius_miles)

    tier1_suggested: list[dict] = []
    tier1_other:     list[dict] = []
    tier2_hotels:    list[dict] = []
    tier3_luxury:    list[dict] = []
    tier4_budget:    list[dict] = []

    for c in candidates:
        tier = c.get("tier", 1)
        dist = c.get("distance_miles", 0)

        if dist < 0.05:
            continue
        if tier == 1 and dist > radius_miles:
            continue
        if tier == 2 and dist > min(15, radius_miles):
            continue
        if tier == 3 and dist > min(75, radius_miles):
            continue
        if tier == 4 and dist > min(10, radius_miles):
            continue

        if tier == 1:
            (tier1_suggested if len(tier1_suggested) < 3 else tier1_other).append(c)
        elif tier == 2:
            tier2_hotels.append(c)
        elif tier == 3:
            tier3_luxury.append(c)
        else:
            tier4_budget.append(c)

    return {
        "property_id":           property_id,
        "radius_miles":          radius_miles,
        "source":                "beaufort_mock",
        "total_raw":             len(candidates),
        "total_found":           len(candidates),
        "upserted":              0,
        "suggested_competitors": tier1_suggested,
        "other_tier1":           tier1_other,
        "tier2_hotels":          tier2_hotels,
        "tier3_luxury":          tier3_luxury,
        "tier4_budget":          tier4_budget,
    }


def confirm_competitors(
    property_id:    str,
    tenant_id:      str,
    confirmed_ids:  list[str],
    added_manually: list[dict],
    *,
    supabase_url: str | None = None,
    service_key:  str | None = None,
) -> None:
    """Persist confirmed competitors and trigger a re-rank."""
    url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
    key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=minimal"}

    for mock in _BEAUFORT_MOCK:
        if mock["name"] in confirmed_ids:
            _upsert_competitor(mock, property_id, tenant_id, url, hdrs)

    for m in added_manually:
        _upsert_competitor(m, property_id, tenant_id, url, hdrs)

    ranker = CompetitorRanker(supabase_url=url, service_key=key)
    ranker.rank_competitors(property_id, tenant_id)


def auto_enrich_competitor(
    competitor_id: str,
    tenant_id:     str,
    *,
    supabase_url:  str | None = None,
    service_key:   str | None = None,
) -> dict[str, Any]:
    """Enrich a competitor with Claude-parsed room descriptions."""
    url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
    key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "count=none"}

    comps = requests.get(
        f"{url}/rest/v1/competitor_properties",
        headers=hdrs,
        params={"id": f"eq.{competitor_id}",
                "select": "competitor_name,name,notes"},
        timeout=15,
    ).json()
    if not comps:
        return {"status": "not_found", "competitor_id": competitor_id}

    comp_name = comps[0].get("competitor_name") or comps[0].get("name", "")
    desc      = comps[0].get("notes") or f"{comp_name} — boutique B&B in Beaufort SC"

    attrs = parse_room_description(desc, property_name=comp_name,
                                   supabase_url=url, service_key=key)
    row = {
        "tenant_id":       tenant_id,
        "competitor_id":   competitor_id,
        "room_name":       comp_name,
        "description":     desc[:500],
        "bathroom_type":   attrs.bathroom_type,
        "has_rain_shower": attrs.has_rain_shower,
        "view_type":       attrs.view_type,
        "has_fireplace":   attrs.has_fireplace,
        "has_balcony":     attrs.has_balcony_or_porch,
        "room_tier":       attrs.room_tier,
        "luxury_features": attrs.luxury_features,
        "confidence_score": attrs.confidence_score,
        "needs_review":    attrs.needs_review,
    }
    requests.post(f"{url}/rest/v1/competitor_room_types",
                  headers={**hdrs, "Prefer": "return=minimal"},
                  json=row, timeout=15)

    return {"status": "enriched", "competitor_id": competitor_id,
            "comp_name": comp_name, "confidence": attrs.confidence_score,
            "needs_review": attrs.needs_review}


def auto_configure_property(
    property_id:          str,
    tenant_id:            str,
    property_name:        str = "",
    property_website_url: str | None = None,
    *,
    supabase_url: str | None = None,
    service_key:  str | None = None,
) -> dict[str, Any]:
    """
    Full autonomous property configuration:
      1. Parse all room type descriptions
      2. Discover competitors
      3. Return auto_config_report
    """
    from engine.description_parser import parse_property_rooms

    url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
    key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")

    rooms_parsed = parse_property_rooms(property_id, property_name,
                                        supabase_url=url, service_key=key)
    comps_found  = discover_competitors(property_id, tenant_id,
                                        supabase_url=url, service_key=key)
    review_items = [r["room_name"] for r in rooms_parsed if r.get("needs_review")]

    return {
        "property_id":       property_id,
        "property_name":     property_name,
        "rooms_parsed":      rooms_parsed,
        "competitors_found": comps_found,
        "primary_competitor": comps_found["suggested_competitors"][0]
            if comps_found["suggested_competitors"] else None,
        "items_needing_review": review_items,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Mock data (Beaufort SC — used when API key absent)
# ─────────────────────────────────────────────────────────────────────────────

_BEAUFORT_MOCK: list[dict] = [
    {
        "name": "Cuthbert House Inn", "category": "boutique_inn", "tier": 1,
        "lat": 32.4315, "lng": -80.6698, "distance_miles": 0.3,
        "room_count": 10, "price_level": 3, "rating": 4.5,
        "notes": "Antebellum mansion B&B on Bay Street; waterfront; premium historic property",
        "booking_com_id": "bdc-cuthbert-house",
    },
    {
        "name": "Rhett House Inn", "category": "boutique_inn", "tier": 1,
        "lat": 32.4318, "lng": -80.6701, "distance_miles": 0.2,
        "room_count": 17, "price_level": 3, "rating": 4.0,
        "notes": "Historic B&B on Craven St; garden property; direct competitor",
        "booking_com_id": "bdc-rhett-house",
    },
    # "Bay Street Inn" removed 2026-05-19 — 601 Bay Street is a private
    # residence, not a lodging property. Verify Google Places results
    # against real lodging registrations before adding to competitor sets.
    {
        "name": "Beaufort Inn", "category": "boutique_hotel", "tier": 1,
        "lat": 32.4320, "lng": -80.6700, "distance_miles": 0.4,
        "room_count": 21, "price_level": 3, "rating": 4.2,
        "notes": "Downtown inn; strong OTA presence",
        "booking_com_id": "bdc-beaufort-inn",
    },
    {
        "name": "Hilton Head Marriott Resort", "category": "upscale_hotel", "tier": 2,
        "lat": 32.1707, "lng": -80.7323, "distance_miles": 29.5,
        "room_count": 512, "price_level": 3, "rating": 4.2,
        "notes": "Tier 2 upscale hotel — 30 miles south on Hilton Head Island",
        "booking_com_id": "bdc-hhmarriott",
    },
    {
        "name": "Westin Hilton Head Island", "category": "upscale_hotel", "tier": 2,
        "lat": 32.1800, "lng": -80.7400, "distance_miles": 31.0,
        "room_count": 412, "price_level": 3, "rating": 4.3,
        "notes": "Tier 2 Marriott brand; Hilton Head beach resort",
        "booking_com_id": "bdc-westin-hhi",
    },
    {
        "name": "Hampton Inn Beaufort", "category": "select_service_hotel", "tier": 4,
        "lat": 32.4089, "lng": -80.6617, "distance_miles": 2.8,
        "room_count": 118, "price_level": 2, "rating": 3.8,
        "notes": "Tier 4 Hilton select-service; market floor",
        "booking_com_id": "bdc-hampton-bft",
    },
    {
        "name": "Holiday Inn Express Beaufort", "category": "budget_hotel", "tier": 4,
        "lat": 32.4100, "lng": -80.6600, "distance_miles": 3.1,
        "room_count": 89, "price_level": 1, "rating": 3.5,
        "notes": "Tier 4 IHG budget brand",
        "booking_com_id": "bdc-hiexpress-bft",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

# Force-tier overrides (applied after Claude classification to catch inconsistencies)
_FORCE_T3_KW = {
    "montage", "four seasons", "ritz-carlton", "ritz carlton",
    "rosewood", "auberge", "waldorf astoria", "park hyatt",
}
_FORCE_T4_KW = {
    "hampton inn", "holiday inn express", "holiday inn & suites",
    "holiday inn", "comfort inn", "comfort suites",
    "best western", "days inn", "super 8", "motel 6",
    "sleep inn", "fairfield inn", "courtyard by marriott", "courtyard",
    "la quinta", "microtel", "quality inn", "econo lodge", "travelodge",
    "baymont", "ramada", "red roof", "extended stay", "home2 suites",
    "springhill suites", "towneplace suites", "tru by hilton",
    "hilton garden inn", "homewood suites", "drury", "woodspring",
    "oyo hotel", "americas best", "suburban studios", "country inn & suites",
}

# Specific known-competitor text searches for Beaufort SC
_BEAUFORT_TEXT_SEARCHES: list[str] = [
    "Rhett House Inn Beaufort SC",
    "Cuthbert House Inn Beaufort SC",
    "Beaufort Inn Beaufort SC",
    # "Bay Street Inn Beaufort SC" — removed 2026-05-19, private residence
    "City Loft Hotel Beaufort SC",
    "Best Western Sea Island Inn Beaufort SC",
    "Magnolia Court Suites Beaufort SC",
    "Hampton Inn Beaufort SC",
    "Hilton Garden Inn Beaufort SC",
    "Montage Palmetto Bluff Bluffton SC",
]

# Tier-based parameters for synthetic rate seeding of newly discovered competitors
_TIER_BASE_RATE = {1: 275, 2: 325, 3: 600, 4: 130}
_SEED_SEASONAL  = {
    1: 0.88, 2: 0.90, 3: 0.96,  4: 1.22, 5: 1.27,
    6: 1.12, 7: 1.18, 8: 1.08,  9: 1.02,
    10: 1.08, 11: 0.94, 12: 1.01,
}
_SEED_DOW       = {0: 0.94, 1: 0.92, 2: 0.94, 3: 0.97, 4: 1.12, 5: 1.18, 6: 1.06}
_SEED_TIER_DAMP = {1: 1.0, 2: 0.45, 3: 0.08, 4: 0.60}

_KNOWN_BRANDS = [
    "hampton inn", "holiday inn express", "holiday inn", "comfort inn",
    "comfort suites", "best western", "days inn", "super 8", "motel 6",
    "sleep inn", "fairfield inn", "courtyard by marriott", "courtyard",
    "la quinta", "microtel", "quality inn", "econo lodge", "travelodge",
    "baymont", "ramada", "red roof", "extended stay america", "home2 suites",
    "springhill suites", "towneplace suites", "marriott", "westin", "hilton",
    "hyatt", "sheraton", "renaissance", "loews", "kimpton", "doubletree",
    "embassy suites", "omni", "wyndham", "four seasons", "ritz-carlton",
    "ritz carlton", "montage", "rosewood", "auberge",
]


def _infer_brand(name: str) -> str:
    """Return brand affiliation string if name contains a known chain keyword."""
    nl = name.lower()
    for brand in _KNOWN_BRANDS:
        if brand in nl:
            return brand.title()
    return ""


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _filter_by_radius(candidates: list[dict], radius: float) -> list[dict]:
    """Compute haversine distance from Anchorage 1770 coords for mock data."""
    _lat, _lng = 32.4312, -80.6695
    out = []
    for c in candidates:
        dist = _haversine(_lat, _lng, c.get("lat", 0), c.get("lng", 0))
        out.append({**c, "distance_miles": round(dist, 2)})
    return sorted(out, key=lambda x: x["distance_miles"])


def _seed_new_competitor_rates(
    property_id: str,
    tenant_id:   str,
    comps:       list[dict],
    url:         str,
    hdrs:        dict,
    days:        int = 90,
) -> int:
    """
    Seed 90 days of synthetic rates for competitors that have none yet.
    Uses tier-based base rates + seasonal/DOW multipliers.
    Returns total rows inserted.
    """
    from datetime import date as _date, datetime as _dt, timedelta as _td, timezone as _tz

    # Map competitor_name → (id, tier) from DB
    comp_rows = requests.get(
        f"{url}/rest/v1/competitor_properties",
        headers={**hdrs, "Prefer": "count=none"},
        params={"property_id": f"eq.{property_id}",
                "select":      "id,competitor_name,property_tier"},
        timeout=15,
    ).json()
    id_by_name: dict[str, tuple[str, int]] = {
        r["competitor_name"]: (r["id"], r.get("property_tier") or 1)
        for r in (comp_rows or []) if r.get("competitor_name")
    }

    today   = _date.today()
    now_utc = _dt.now(_tz.utc).isoformat()
    batch:  list[dict] = []

    for comp in comps:
        name = comp.get("name", "")
        if name not in id_by_name:
            continue
        comp_id, tier = id_by_name[name]

        # Skip if this competitor already has future rates
        chk = requests.get(
            f"{url}/rest/v1/competitor_rates",
            headers={**hdrs, "Prefer": "count=none"},
            params={"competitor_id": f"eq.{comp_id}",
                    "rate_date":     f"gte.{today.isoformat()}",
                    "select":        "id",
                    "limit":         "1"},
            timeout=10,
        ).json()
        if chk:
            continue

        base = _TIER_BASE_RATE.get(tier, 275)
        damp = _SEED_TIER_DAMP.get(tier, 1.0)

        for offset in range(days + 1):
            d          = today + _td(days=offset)
            s_raw      = _SEED_SEASONAL.get(d.month, 1.0)
            seasonal   = 1.0 + (s_raw - 1.0) * damp
            dow        = _SEED_DOW.get(d.weekday(), 1.0)
            is_wf      = (d.month == 7 and 17 <= d.day <= 26)
            effective  = 1.5 * dow if is_wf else seasonal * dow
            noise      = ((hash(f"{comp_id}:{d.isoformat()}") % 10000) - 5000) / 62500
            rate       = max(round(base * 0.70 / 5) * 5,
                             round(base * effective * (1 + noise) / 5) * 5)
            batch.append({
                "tenant_id":        tenant_id,
                "property_id":      property_id,
                "competitor_id":    comp_id,
                "rate_date":        d.isoformat(),
                "rate_amount":      float(rate),
                "room_description": "Standard room (estimated)",
                "platform":         "google_places",
                "is_sold_out":      False,
                "is_stale":         False,
                "scraped_at":       now_utc,
            })

    inserted = 0
    for i in range(0, len(batch), 500):
        chunk = batch[i:i + 500]
        r = requests.post(
            f"{url}/rest/v1/competitor_rates",
            headers={**hdrs, "Prefer": "return=minimal"},
            json=chunk, timeout=30,
        )
        if r.ok:
            inserted += len(chunk)
        else:
            logger.warning("Rate seed insert failed: %s", r.text[:200])
    return inserted


def _upsert_competitor(
    mock: dict, property_id: str, tenant_id: str, url: str, hdrs: dict
) -> None:
    """Upsert a mock-format competitor row into competitor_properties."""
    payload = {
        "tenant_id":           tenant_id,
        "property_id":         property_id,
        "name":                mock["name"],
        "competitor_name":     mock["name"],
        "booking_com_id":      mock.get("booking_com_id", ""),
        "property_tier":       mock.get("tier", 1),
        "property_category":   mock.get("category", "boutique_inn"),
        "room_count":          mock.get("room_count"),
        "trip_advisor_rating": mock.get("rating"),
        "distance_miles":      mock.get("distance_miles"),
        "latitude":            mock.get("lat"),
        "longitude":           mock.get("lng"),
        "notes":               mock.get("notes", ""),
        "active":              True,
    }
    requests.post(
        f"{url}/rest/v1/competitor_properties",
        headers={**hdrs, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=payload, timeout=15,
    )


def _upsert_from_places(
    comp: dict, property_id: str, tenant_id: str, url: str, hdrs: dict
) -> None:
    """Upsert a Places-format competitor dict into competitor_properties."""
    notes_parts = []
    if comp.get("address"):
        notes_parts.append(comp["address"])
    if comp.get("reasoning"):
        notes_parts.append(comp["reasoning"])
    if comp.get("website"):
        notes_parts.append(f"Website: {comp['website']}")
    if comp.get("phone"):
        notes_parts.append(f"Phone: {comp['phone']}")
    notes = " | ".join(notes_parts)

    payload = {
        "tenant_id":           tenant_id,
        "property_id":         property_id,
        "name":                comp["name"],
        "competitor_name":     comp["name"],
        "property_tier":       comp.get("tier", 1),
        "property_category":   comp.get("category", "boutique_inn"),
        "brand_affiliation":   comp.get("brand") or None,
        "trip_advisor_rating": comp.get("rating"),
        "distance_miles":      comp.get("distance_miles"),
        "latitude":            comp.get("lat"),
        "longitude":           comp.get("lng"),
        "google_maps_url":     comp.get("google_maps_url", ""),
        "notes":               notes[:500],
        "active":              True,
    }
    requests.post(
        f"{url}/rest/v1/competitor_properties",
        headers={**hdrs, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=payload, timeout=15,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def _print_result(result: dict, label: str) -> None:
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"  Address : {result.get('property_address', '—')}")
    print(f"  Geocoded: ({result.get('geocoded_lat','—'):.5f}, "
          f"{result.get('geocoded_lng','—'):.5f})")
    print(f"  Source  : {result['source']}  |  "
          f"Raw: {result.get('total_raw','—')}  |  "
          f"After filter: {result['total_found']}  |  "
          f"Upserted: {result.get('upserted', 0)}")
    print(f"{'='*65}")

    def _section(title: str, items: list[dict]) -> None:
        if not items:
            return
        pad = max(0, 52 - len(title))
        print(f"\n  ── {title} {'─'*pad}")
        for c in items:
            rating  = c.get("rating") or "—"
            pl      = c.get("price_level")
            pl_str  = ("$" * pl) if pl else "—"
            n_rev   = c.get("n_reviews") or ""
            note    = (c.get("reasoning") or c.get("notes", ""))[:45]
            print(f"     {c['name']:<38} {c.get('distance_miles',0):5.1f} mi  "
                  f"T{c.get('tier',1)}  ★{str(rating):<4}  {pl_str:<5}  {note}")

    _section("Suggested Direct Competitors (Tier 1)", result["suggested_competitors"])
    _section("Other Tier 1 Boutique Properties",      result["other_tier1"])
    _section("Upscale Hotels (Tier 2)",               result["tier2_hotels"])
    _section("Luxury Reference (Tier 3)",             result["tier3_luxury"])
    _section("Budget Anchors (Tier 4)",               result["tier4_budget"])

    if result.get("ranked_competitors"):
        print(f"\n  ── Final Ranked Competitor List {'─'*34}")
        for r in result["ranked_competitors"][:10]:
            print(f"     #{r['rank']:<3} T{r['tier']}  {r['name']:<40}  score {r['score']:.1f}")
    print()


def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--slug",     default="anchorage-1770-demo")
    parser.add_argument("--radius",   type=float, default=25.0)
    parser.add_argument("--address",  default=None,
                        help="Property street address (geocoded as search origin)")
    parser.add_argument("--savannah", action="store_true",
                        help="Run Test 2: Savannah multi-city proof")
    args = parser.parse_args()

    url  = os.getenv("SUPABASE_URL", "").rstrip("/")
    key  = os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=none"}

    # ── Test 1: Anchorage 1770 ────────────────────────────────────────────────
    if not args.savannah:
        tenants = requests.get(f"{url}/rest/v1/tenants", headers=hdrs,
                               params={"slug": f"eq.{args.slug}",
                                       "select": "id,name"}, timeout=15).json()
        if not tenants:
            print(f"Tenant {args.slug!r} not found"); return
        tid   = tenants[0]["id"]
        props = requests.get(f"{url}/rest/v1/properties", headers=hdrs,
                             params={"tenant_id": f"eq.{tid}",
                                     "select": "id,name"}, timeout=15).json()
        pid   = props[0]["id"]
        pname = props[0]["name"]

        address = args.address or "1103 Bay Street, Beaufort, SC 29902"
        print(f"\n  TEST 1 — {pname}  ({args.slug})")
        print(f"  Radius: {args.radius} miles")
        print(f"  Hybrid: {len(_BEAUFORT_TEXT_SEARCHES)} targeted text searches\n")

        result = discover_competitors_google(
            pid, address, args.radius,
            text_searches=_BEAUFORT_TEXT_SEARCHES,
        )
        _print_result(result, f"TEST 1 — {pname}")

        # Compare against seeded mock set
        seeded = {m["name"] for m in _BEAUFORT_MOCK}
        found  = {c["name"] for c in
                  result["suggested_competitors"] + result["other_tier1"] +
                  result["tier2_hotels"] + result["tier3_luxury"] +
                  result["tier4_budget"]}
        new_finds   = found - seeded
        not_in_api  = seeded - found
        print(f"  ── Comparison vs seeded mock set {'─'*30}")
        print(f"     New properties found by Google  : {len(new_finds)}")
        for n in sorted(new_finds):
            print(f"       + {n}")
        print(f"     Seeded properties NOT in API    : {len(not_in_api)}")
        for n in sorted(not_in_api):
            print(f"       - {n}")
        print()

    # ── Test 2: Savannah ──────────────────────────────────────────────────────
    else:
        address = "47 West Perry Street, Savannah, GA 31401"
        print(f"\n  TEST 2 — Savannah multi-city proof")
        print(f"  Address: {address}")
        print(f"  Radius: {args.radius} miles\n")

        result = discover_competitors_google(
            property_id=None,
            property_address=address,
            radius_miles=args.radius,
        )
        _print_result(result, "TEST 2 — Savannah GA")


if __name__ == "__main__":
    main()
