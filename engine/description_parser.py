"""
engine/description_parser.py
Room Description Parser — uses Claude API to extract structured attributes.

Results are cached in room_description_cache (30-day TTL).
Confidence < 70 → needs_review=True, never auto-applied.
Graceful fallback when ANTHROPIC_API_KEY is not set.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

_MODEL          = "claude-sonnet-4-6"
_MAX_TOKENS     = 500
_REVIEW_THRESH  = 70
_CACHE_DAYS     = 30
_HEADERS_WEB    = {"User-Agent": "TGC-PricingEngine/1.0"}


# ─────────────────────────────────────────────────────────────────────────────
#  Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RoomAttributes:
    bathroom_type:              str     # shower_only|tub_shower_combo|soaking_tub_separate_shower|jacuzzi
    has_rain_shower:            bool
    has_dual_head_shower:       bool
    view_type:                  str     # waterfront|water_view|garden_view|city_view|no_view|unknown
    has_fireplace:              bool
    has_balcony_or_porch:       bool
    has_four_poster_bed:        bool
    ceiling_description:        str     # high_ceiling|standard|unknown
    room_tier:                  str     # premium|standard|economy
    luxury_features:            list[str]
    bathroom_premium_suggested: float   # 0.0–0.15
    confidence_score:           int     # 0–100
    needs_review:               bool = False
    source_description:         str = ""


_JSON_TEMPLATE = """{
  "bathroom_type": "shower_only|tub_shower_combo|soaking_tub_separate_shower|jacuzzi",
  "has_rain_shower": true,
  "has_dual_head_shower": false,
  "view_type": "waterfront|water_view|garden_view|city_view|no_view|unknown",
  "has_fireplace": false,
  "has_balcony_or_porch": true,
  "has_four_poster_bed": false,
  "ceiling_description": "high_ceiling|standard|unknown",
  "room_tier": "premium|standard|economy",
  "luxury_features": ["panoramic views", "private balcony"],
  "bathroom_premium_suggested": 0.03,
  "confidence_score": 85
}"""

_BATH_PREMIUM_GUIDE = (
    "Bathroom premium guide:\n"
    "  soaking_tub_separate_shower: 0.12\n"
    "  jacuzzi: 0.10\n"
    "  tub_shower_combo: 0.06\n"
    "  shower_only with rain head or dual head: 0.03\n"
    "  shower_only standard: 0.00"
)


# ─────────────────────────────────────────────────────────────────────────────
#  Primary parse function
# ─────────────────────────────────────────────────────────────────────────────

def parse_room_description(
    description_text: str,
    property_name:    str = "",
    use_cache:        bool = True,
    *,
    supabase_url:  str | None = None,
    service_key:   str | None = None,
) -> RoomAttributes:
    """
    Extract structured room attributes from a natural-language description.
    Uses Claude API; falls back to keyword heuristics when key is absent.
    Results cached for 30 days to avoid redundant API calls.
    """
    desc  = description_text.strip()
    dHash = hashlib.sha256(desc.encode()).hexdigest()

    url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
    key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")

    if use_cache:
        cached = _check_cache(dHash, url, key)
        if cached:
            return _dict_to_attrs(cached, desc)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using keyword heuristics")
        attrs = _heuristic_attrs(desc)
        return attrs

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=(
                "You are a hospitality revenue management expert. "
                "Extract room attributes from hotel descriptions. "
                "Return ONLY valid JSON, no other text, no markdown."
            ),
            messages=[{"role": "user", "content": (
                f"Extract attributes from this room description"
                f"{' for ' + property_name if property_name else ''}:\n\n"
                f"{desc}\n\n"
                f"Return this exact JSON:\n{_JSON_TEMPLATE}\n\n"
                f"{_BATH_PREMIUM_GUIDE}"
            )}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        result = json.loads(raw)
        _store_cache(dHash, result, url, key)
        return _dict_to_attrs(result, desc)

    except Exception as exc:
        logger.error("Claude parse failed: %s — falling back to heuristics", exc)
        return _heuristic_attrs(desc)


# ─────────────────────────────────────────────────────────────────────────────
#  Parse all property room types
# ─────────────────────────────────────────────────────────────────────────────

def parse_property_rooms(
    property_id:  str,
    property_name: str = "",
    *,
    supabase_url: str | None = None,
    service_key:  str | None = None,
    dry_run:      bool = False,
) -> list[dict[str, Any]]:
    """
    Parse all room_types for a property. Auto-applies results with
    confidence ≥ 70. Returns a list of result dicts for reporting.
    """
    url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
    key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": "count=none",
    }

    resp = requests.get(
        f"{url}/rest/v1/room_types",
        headers=hdrs,
        params={"property_id": f"eq.{property_id}",
                "select": "id,name,description,bathroom_description"},
        timeout=30,
    )
    resp.raise_for_status()
    room_types = resp.json()

    results = []
    for rt in room_types:
        desc = " ".join(filter(None, [
            rt.get("description", ""),
            rt.get("bathroom_description", ""),
        ])).strip()
        if not desc:
            continue

        attrs = parse_room_description(
            desc, property_name=property_name or "Property",
            supabase_url=url, service_key=key,
        )
        rain_premium = 0.03 if (attrs.has_rain_shower or attrs.has_dual_head_shower) else 0.00
        if attrs.bathroom_premium_suggested > 0:
            rain_premium = attrs.bathroom_premium_suggested

        result = {
            "room_type_id":     rt["id"],
            "room_name":        rt["name"],
            "bathroom_type":    attrs.bathroom_type,
            "bathroom_premium": rain_premium,
            "has_rain_shower":  attrs.has_rain_shower,
            "view_type":        attrs.view_type,
            "has_balcony":      attrs.has_balcony_or_porch,
            "has_fireplace":    attrs.has_fireplace,
            "room_tier":        attrs.room_tier,
            "luxury_features":  attrs.luxury_features,
            "confidence_score": attrs.confidence_score,
            "needs_review":     attrs.needs_review,
            "auto_applied":     False,
        }

        if not dry_run and not attrs.needs_review:
            requests.patch(
                f"{url}/rest/v1/room_types",
                headers={**hdrs, "Prefer": "return=minimal"},
                params={"id": f"eq.{rt['id']}"},
                json={
                    "bathroom_type":    attrs.bathroom_type,
                    "bathroom_premium": rain_premium,
                    "view_type":        attrs.view_type,
                    "has_fireplace":    attrs.has_fireplace,
                    "has_balcony":      attrs.has_balcony_or_porch,
                    "auto_parsed":      True,
                    "parse_confidence": attrs.confidence_score,
                },
                timeout=30,
            ).raise_for_status()
            result["auto_applied"] = True

        results.append(result)
        time.sleep(0.2)

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Lodging tier classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_lodging_tier(
    property_name: str,
    brand:         str = "",
    price_level:   int = 2,
    rating:        float = 0.0,
    description:   str = "",
) -> dict[str, Any]:
    """
    Classify a property into competitive tiers (1–4) using Claude.
    Falls back to keyword heuristics when API key is absent.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _heuristic_tier(property_name, brand, price_level, rating)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=200,
            system=(
                "Classify lodging into competitive tiers for a boutique "
                "historic inn. Return ONLY JSON."
            ),
            messages=[{"role": "user", "content": (
                f"Property: {property_name}\n"
                f"Brand affiliation: {brand or 'Independent'}\n"
                f"Price level (1-4): {price_level}\n"
                f"Guest rating: {rating or 'unknown'}\n"
                f"Description: {description}\n\n"
                'Return JSON:\n'
                '{"tier":1,"category":"boutique_inn","reasoning":"one sentence"}\n\n'
                "Tier guide:\n"
                "1=Direct boutique competitor (inn, B&B, small historic hotel)\n"
                "2=Upscale hotel (branded/independent, 50-300 rooms, $200-500/night)\n"
                "3=Luxury reference (Ritz Carlton, Four Seasons, $400+/night)\n"
                "4=Budget anchor (Hampton Inn, Holiday Inn Express, under $200 typical)"
            )}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error("classify_lodging_tier failed: %s", exc)
        return _heuristic_tier(property_name, brand, price_level, rating)


# ─────────────────────────────────────────────────────────────────────────────
#  Cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_cache(desc_hash: str, url: str, key: str) -> dict | None:
    try:
        resp = requests.get(
            f"{url}/rest/v1/room_description_cache",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Prefer": "count=none"},
            params={"description_hash": f"eq.{desc_hash}",
                    "select": "parsed_result,parsed_at"},
            timeout=10,
        )
        rows = resp.json()
        if rows and rows[0].get("parsed_result"):
            parsed_at = datetime.fromisoformat(
                rows[0]["parsed_at"].replace("Z", "+00:00")
            )
            age_days = (datetime.now(timezone.utc) - parsed_at).days
            if age_days <= _CACHE_DAYS:
                return rows[0]["parsed_result"]
    except Exception:
        pass
    return None


def _store_cache(desc_hash: str, result: dict, url: str, key: str) -> None:
    try:
        requests.post(
            f"{url}/rest/v1/room_description_cache",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "return=minimal,resolution=merge-duplicates"},
            json={"description_hash": desc_hash, "parsed_result": result,
                  "model_version": _MODEL,
                  "parsed_at": datetime.now(timezone.utc).isoformat()},
            timeout=10,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Fallback heuristics (no API key)
# ─────────────────────────────────────────────────────────────────────────────

def _dict_to_attrs(d: dict, source: str = "") -> RoomAttributes:
    score = int(d.get("confidence_score", 50))
    return RoomAttributes(
        bathroom_type=              d.get("bathroom_type", "shower_only"),
        has_rain_shower=            bool(d.get("has_rain_shower", False)),
        has_dual_head_shower=       bool(d.get("has_dual_head_shower", False)),
        view_type=                  d.get("view_type", "unknown"),
        has_fireplace=              bool(d.get("has_fireplace", False)),
        has_balcony_or_porch=       bool(d.get("has_balcony_or_porch", False)),
        has_four_poster_bed=        bool(d.get("has_four_poster_bed", False)),
        ceiling_description=        d.get("ceiling_description", "unknown"),
        room_tier=                  d.get("room_tier", "standard"),
        luxury_features=            list(d.get("luxury_features", [])),
        bathroom_premium_suggested= float(d.get("bathroom_premium_suggested", 0.0)),
        confidence_score=           score,
        needs_review=               score < _REVIEW_THRESH,
        source_description=         source,
    )


def _heuristic_attrs(desc: str) -> RoomAttributes:
    d = desc.lower()
    # Bathroom
    if any(w in d for w in ["rain shower", "rain head", "rainfall shower",
                              "dual head", "dual-head"]):
        btype, rain, dual, premium, conf = "shower_only", True, "dual" in d, 0.03, 65
    elif any(w in d for w in ["soaking tub", "clawfoot", "deep soaking",
                                "freestanding tub"]):
        btype, rain, dual, premium, conf = "soaking_tub_separate_shower", False, False, 0.12, 65
    elif any(w in d for w in ["jacuzzi", "jetted tub", "whirlpool", "jet tub"]):
        btype, rain, dual, premium, conf = "jacuzzi", False, False, 0.10, 65
    elif any(w in d for w in ["tub and shower", "bath and shower", "tub/shower",
                                "tub shower combo", "combination"]):
        btype, rain, dual, premium, conf = "tub_shower_combo", False, False, 0.06, 60
    else:
        btype, rain, dual, premium, conf = "shower_only", False, False, 0.00, 40

    # View
    if any(w in d for w in ["waterfront", "beaufort river", "river view",
                              "river front", "panoramic water"]):
        view = "waterfront"
    elif any(w in d for w in ["water view", "partial river", "bay view"]):
        view = "water_view"
    elif "garden" in d:
        view = "garden_view"
    else:
        view = "no_view"

    has_balcony = any(w in d for w in ["balcony", "porch", "veranda", "terrace"])
    has_fire    = any(w in d for w in ["fireplace", "fire place", "hearth"])
    has_poster  = any(w in d for w in ["four poster", "four-poster", "canopy bed"])

    luxury: list[str] = []
    if "king" in d:       luxury.append("king bed")
    if "queen" in d:      luxury.append("queen bed")
    if has_balcony:       luxury.append("private balcony")
    if has_fire:          luxury.append("fireplace")
    if rain:              luxury.append("rain shower")
    if "panoramic" in d:  luxury.append("panoramic views")

    tier = ("premium"  if any(w in d for w in ["suite", "premier", "luxury", "waterfront"])
            else "economy" if any(w in d for w in ["standard", "economy", "basic"])
            else "standard")

    return RoomAttributes(
        bathroom_type=btype, has_rain_shower=rain, has_dual_head_shower=dual,
        view_type=view, has_fireplace=has_fire, has_balcony_or_porch=has_balcony,
        has_four_poster_bed=has_poster, ceiling_description="unknown",
        room_tier=tier, luxury_features=luxury,
        bathroom_premium_suggested=premium, confidence_score=conf,
        needs_review=conf < _REVIEW_THRESH, source_description=desc,
    )


def _heuristic_tier(name: str, brand: str, price: int, rating: float) -> dict:
    n = name.lower()
    b = brand.lower()
    if any(w in b for w in ["hampton", "holiday inn", "comfort inn", "days inn",
                              "super 8", "motel 6", "fairfield"]):
        return {"tier": 4, "category": "select_service_hotel",
                "reasoning": "National budget/select-service brand"}
    if any(w in b for w in ["marriott", "hilton", "hyatt", "westin", "sheraton",
                              "doubletree", "embassy suites"]):
        return {"tier": 2, "category": "upscale_hotel",
                "reasoning": "Upscale branded hotel chain"}
    if any(w in b for w in ["ritz", "four seasons", "rosewood", "aman",
                              "mandarin oriental", "park hyatt"]):
        return {"tier": 3, "category": "luxury_hotel",
                "reasoning": "Luxury reference property"}
    if any(w in n for w in ["inn", "bed", "b&b", "house", "manor", "cottage"]):
        return {"tier": 1, "category": "boutique_inn",
                "reasoning": "Boutique inn or B&B — direct competitor tier"}
    return {"tier": 1 if price <= 2 else 2, "category": "boutique_hotel",
            "reasoning": "Small independent hotel"}
