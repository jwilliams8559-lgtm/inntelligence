"""
modules/hospitality/competitor_discovery.py

Competitor discovery — STUB.

Given a subject property (address, type, room count, rack-rate band) this returns
a tiered competitor set:

    tier 1  Direct competitors   (weight 1.0)  — same class, overlapping rate band
    tier 2  Market reference     (weight 0.4)  — adjacent class / partial overlap
    tier 3  Market anchors       (weight 0.1)  — budget floor + luxury ceiling

The current implementation is deterministic stub logic over a curated Beaufort
candidate pool. It is intentionally side-effect free and returns the same shape
the live integration will, so callers (and config/settings.PROPERTIES) can be
wired to it without change later.

PRODUCTION INTEGRATION (later):
    • Google Places / Maps API  — discover lodging within a radius of `address`
    • OTA Insight / Lighthouse  — pull each candidate's rate band + class
    • classify into tiers using rate-band overlap + property type + distance
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

TIER_LABELS = {1: "Your Direct Competitors", 2: "Market Reference", 3: "Market Anchors"}
TIER_WEIGHTS = {1: 1.0, 2: 0.4, 3: 0.1}

# Curated Beaufort SC candidate pool the stub draws from. Each carries a typical
# (low-season weekday, peak-season weekend) rate band and a coarse class. A live
# source would populate this dynamically.
_CANDIDATE_POOL: List[Dict[str, Any]] = [
    {"key": "rhett_house",    "name": "Rhett House Inn",              "base_low": 239, "base_high": 439,  "klass": "boutique_inn"},
    {"key": "cuthbert_house", "name": "Cuthbert House Inn",           "base_low": 249, "base_high": 425,  "klass": "boutique_inn"},
    {"key": "anchorage_1770", "name": "Anchorage 1770 Inn",           "base_low": 289, "base_high": 469,  "klass": "boutique_inn"},
    {"key": "bay_inn_607",    "name": "607 Bay Inn",                  "base_low": 189, "base_high": 349,  "klass": "boutique_inn"},
    {"key": "beaufort_inn",   "name": "Beaufort Inn",                 "base_low": 199, "base_high": 375,  "klass": "upscale_hotel"},
    {"key": "city_loft",      "name": "City Loft Hotel",              "base_low": 169, "base_high": 295,  "klass": "upscale_hotel"},
    {"key": "airbnb_avg",     "name": "Airbnb Near Bay Street (avg)", "base_low": 149, "base_high": 325,  "klass": "str"},
    {"key": "hampton_inn",    "name": "Hampton Inn Beaufort",         "base_low": 129, "base_high": 219,  "klass": "select_service"},
    {"key": "montage",        "name": "Montage Palmetto Bluff",       "base_low": 695, "base_high": 1295, "klass": "luxury_resort"},
]

# Classes treated as "same category" as a boutique inn for tier-1 purposes.
# (STRs are market anchors, not direct comps → tier 3.)
_DIRECT_CLASSES = {"boutique_inn"}


def _bands_overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Fractional overlap of two rate bands (0.0–1.0 of the smaller band)."""
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    if hi <= lo:
        return 0.0
    smaller = min(a[1] - a[0], b[1] - b[0]) or 1.0
    return (hi - lo) / smaller


def competitor_discovery(
    address: str,
    property_type: str,
    room_count: int,
    rack_rate_range: Tuple[float, float],
) -> Dict[str, Any]:
    """Discover and tier competitors for a subject property.

    Parameters
    ----------
    address:          subject property address (used by the live geocoder later)
    property_type:    e.g. "boutique_inn"
    room_count:       subject room count (small inns weight boutique peers higher)
    rack_rate_range:  (low, high) subject rack band, drives tier-1 overlap test

    Returns
    -------
    {
      "subject": {...echo of inputs...},
      "source":  "stub",
      "tiers": [
        {"tier": 1, "label": "Your Direct Competitors", "weight": 1.0,
         "competitors": [{"key","name","base_low","base_high","tier","weight"}, ...]},
        {"tier": 2, ...}, {"tier": 3, ...},
      ],
      "competitors": [ ...flat list, tier annotated... ],
    }
    """
    subj_band = (float(rack_rate_range[0]), float(rack_rate_range[1]))

    tiered: Dict[int, List[Dict[str, Any]]] = {1: [], 2: [], 3: []}
    for cand in _CANDIDATE_POOL:
        band = (cand["base_low"], cand["base_high"])
        overlap = _bands_overlap(subj_band, band)
        klass = cand["klass"]

        # Stub heuristic:
        #   tier 1 — same/adjacent class AND meaningful rate-band overlap
        #   tier 3 — market anchors (budget floor / luxury ceiling)
        #   tier 2 — everything else (adjacent reference)
        if klass in ("select_service", "luxury_resort"):
            tier = 3
        elif klass in _DIRECT_CLASSES and overlap >= 0.15:
            tier = 1
        elif klass == "str":
            tier = 3
        else:
            tier = 2

        tiered[tier].append({
            "key":       cand["key"],
            "name":      cand["name"],
            "base_low":  cand["base_low"],
            "base_high": cand["base_high"],
            "tier":      tier,
            "weight":    TIER_WEIGHTS[tier],
        })

    return {
        "subject": {
            "address":         address,
            "property_type":   property_type,
            "room_count":      room_count,
            "rack_rate_range": list(subj_band),
        },
        "source": "stub",
        "tiers": [
            {"tier": t, "label": TIER_LABELS[t], "weight": TIER_WEIGHTS[t],
             "competitors": tiered[t]}
            for t in (1, 2, 3)
        ],
        "competitors": [c for t in (1, 2, 3) for c in tiered[t]],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Live discovery — Google Places. Replaces the Beaufort stub for production.
#  Same return shape as competitor_discovery() so callers are unchanged.
# ─────────────────────────────────────────────────────────────────────────────

# Google Places API (New) priceLevel enum → 0–4 bucket used by the tiering logic.
_PRICE_ENUM = {
    "PRICE_LEVEL_FREE":           0,
    "PRICE_LEVEL_INEXPENSIVE":    1,
    "PRICE_LEVEL_MODERATE":       2,
    "PRICE_LEVEL_EXPENSIVE":      3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def _rate_to_price_level(rate_low: float, rate_high: float) -> int:
    """Map a nightly rate band midpoint to a Google price_level bucket (1–4)."""
    mid = (float(rate_low) + float(rate_high)) / 2.0 if (rate_low or rate_high) else 0
    if mid <= 0:    return 2        # unknown → assume mid-market
    if mid < 150:   return 1
    if mid < 300:   return 2
    if mid < 500:   return 3
    return 4


def _tier_for_place(place_level, subj_level: int, klass_hint: str = "") -> int:
    """Tier a discovered lodging by how close its price_level is to the subject.
    Google Places gives no nightly rate, so price_level (0–4) is the proxy."""
    if place_level is None:
        return 2                                    # unknown → market reference
    diff = abs(place_level - subj_level)
    if place_level >= 4 and subj_level < 3:
        return 3                                    # luxury ceiling anchor
    if place_level <= 1 and subj_level > 2:
        return 3                                    # budget floor anchor
    if diff <= 1:
        return 1                                    # direct competitor
    return 2


def discover_competitors_live(
    *,
    api_key: str,
    address: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    property_type: str = "boutique_inn",
    room_count: int = 0,
    rate_low: float = 0,
    rate_high: float = 0,
    radius_miles: float = 25.0,
    exclude_name: str = "",
    country: str = "",
    max_results: int = 20,
) -> Dict[str, Any]:
    """Discover nearby lodging via Google Places and tier it like the stub.

    Geocodes `address` (unless lat/lng given), runs a Nearby Search for lodging
    within `radius_miles`, and tiers results by price_level vs the subject's rate
    band. Returns source='google_places'. With no api_key (or on any error)
    returns source='none' with empty tiers — NEVER a hardcoded fallback set."""
    empty = {
        "subject": {"address": address, "property_type": property_type,
                    "room_count": room_count, "rack_rate_range": [rate_low, rate_high]},
        "source": "none",
        "tiers": [{"tier": t, "label": TIER_LABELS[t], "weight": TIER_WEIGHTS[t],
                   "competitors": []} for t in (1, 2, 3)],
        "competitors": [],
    }
    if not api_key:
        return empty

    import requests
    try:
        lat, lng = latitude, longitude
        if lat is None or lng is None:
            if not address:
                return empty
            # Geocoding API (not retired) → address to lat/lng. Biasing by country
            # keeps non-US addresses (UK, CA, EU, Caribbean) from resolving wrongly.
            geo_params = {"address": address, "key": api_key}
            if country:
                geo_params["components"] = f"country:{country}"
            g = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                             params=geo_params, timeout=15)
            gj = g.json() if g.ok else {}
            results = gj.get("results") or []
            if not results:
                return {**empty, "source": "geocode_failed"}
            loc = results[0]["geometry"]["location"]
            lat, lng = loc["lat"], loc["lng"]

        # Places API (New) — searchNearby. The legacy nearbysearch endpoint is not
        # available on newer projects, so we use the v1 API (POST + field mask).
        radius_m = int(min(max(radius_miles, 1), 31) * 1609.34)   # new API caps radius at 50 km (~31 mi)
        resp = requests.post(
            "https://places.googleapis.com/v1/places:searchNearby",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": ("places.id,places.displayName,places.formattedAddress,"
                                     "places.priceLevel,places.rating,places.userRatingCount,places.location"),
            },
            json={
                # Boutique inns / B&Bs are often typed specifically (not "lodging"),
                # so include the sub-types or they get silently dropped.
                "includedTypes": ["lodging", "bed_and_breakfast", "inn", "guest_house",
                                  "hotel", "motel", "resort_hotel", "extended_stay_hotel",
                                  "cottage", "farmstay"],
                "maxResultCount": 20,
                # Prominence (the default) returns established, reviewable properties
                # and demotes obscure individual-room sub-listings; DISTANCE surfaced
                # every room entry and crowded out real competitors.
                "rankPreference": "POPULARITY",
                "locationRestriction": {"circle": {
                    "center": {"latitude": lat, "longitude": lng}, "radius": radius_m}},
            }, timeout=20)
        rj = resp.json() if resp.ok else {}
        # Normalize the New API shape to the keys the tiering loop below expects.
        places = [{
            "place_id":           p.get("id"),
            "name":               (p.get("displayName") or {}).get("text"),
            "vicinity":           p.get("formattedAddress"),
            "price_level":        _PRICE_ENUM.get(p.get("priceLevel")),
            "rating":             p.get("rating"),
            "user_ratings_total": p.get("userRatingCount"),
        } for p in (rj.get("places") or [])]
    except Exception:  # noqa: BLE001
        return {**empty, "source": "error"}

    # Strip individual-room / unit sub-listings (e.g. "The Rhett House Room for Two"
    # when "The Rhett House" is present). Keep the better-reviewed canonical entry.
    import re as _re2
    _room_hint = _re2.compile(r"\b(room|rooms|suite|unit|apartment|apt|studio)\b|#\s*\d|\bno\.?\s*\d", _re2.I)
    places.sort(key=lambda p: (p.get("user_ratings_total") or 0), reverse=True)
    _deduped: List[Dict[str, Any]] = []
    _kept_names: List[str] = []
    for p in places:
        low = (p.get("name") or "").strip().lower()
        if not low:
            continue
        if any(low != k and low.startswith(k) and _room_hint.search(low[len(k):]) for k in _kept_names):
            continue
        _deduped.append(p)
        _kept_names.append(low)
    places = _deduped

    subj_level = _rate_to_price_level(rate_low, rate_high)
    excl = (exclude_name or "").strip().lower()
    tiered: Dict[int, List[Dict[str, Any]]] = {1: [], 2: [], 3: []}
    seen: set = set()
    for p in places:
        pid = p.get("place_id")
        name = (p.get("name") or "").strip()
        if not name or pid in seen:
            continue
        if excl and (excl in name.lower() or name.lower() in excl):
            continue                                # skip the subject property itself
        seen.add(pid)
        level = p.get("price_level")
        tier = _tier_for_place(level, subj_level)
        tiered[tier].append({
            "key": pid or name.lower().replace(" ", "_"),
            "name": name,
            "place_id": pid,
            "address": p.get("vicinity") or "",
            "price_level": level,
            "rating": p.get("rating"),
            "user_ratings_total": p.get("user_ratings_total"),
            "tier": tier,
            "weight": TIER_WEIGHTS[tier],
        })
        if sum(len(v) for v in tiered.values()) >= max_results:
            break

    return {
        "subject": {"address": address, "latitude": lat, "longitude": lng,
                    "property_type": property_type, "room_count": room_count,
                    "rack_rate_range": [rate_low, rate_high]},
        "source": "google_places",
        "tiers": [{"tier": t, "label": TIER_LABELS[t], "weight": TIER_WEIGHTS[t],
                   "competitors": tiered[t]} for t in (1, 2, 3)],
        "competitors": [c for t in (1, 2, 3) for c in tiered[t]],
    }


if __name__ == "__main__":  # quick manual check of the stub
    import json
    result = competitor_discovery(
        address="Bay Street, Beaufort SC",
        property_type="boutique_inn",
        room_count=19,
        rack_rate_range=(229, 659),
    )
    print(json.dumps(result, indent=2))
