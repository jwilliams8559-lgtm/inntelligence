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


if __name__ == "__main__":  # quick manual check
    import json
    result = competitor_discovery(
        address="Bay Street, Beaufort SC",
        property_type="boutique_inn",
        room_count=19,
        rack_rate_range=(229, 659),
    )
    print(json.dumps(result, indent=2))
