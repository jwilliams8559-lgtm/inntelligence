"""Weather intelligence via the National Weather Service public API.

The NWS API is free and requires no key, but does require a descriptive
User-Agent header. Workflow: hit /points/{lat},{lon} to discover the
forecast endpoint for that location, then hit that endpoint for the
seven-day forecast. We cache aggressively (one hour) since NWS data
refreshes infrequently and the inn-owner UX does not need real-time.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
import json as _json
from datetime import date
from typing import Any

NWS_USER_AGENT = "TheGraciousCollection-PricingEngine (jwilliams8559@gmail.com)"

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SEC = 3600


def _http_get(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={
        "User-Agent": NWS_USER_AGENT,
        "Accept":     "application/geo+json",
    })
    with urllib.request.urlopen(req, timeout=8) as resp:
        return _json.loads(resp.read().decode())


def _cached(key: str, fetch_fn) -> Any:
    now = time.time()
    if key in _CACHE:
        ts, val = _CACHE[key]
        if now - ts < _CACHE_TTL_SEC:
            return val
    val = fetch_fn()
    _CACHE[key] = (now, val)
    return val


def _icon_for(short_forecast: str) -> str:
    s = short_forecast.lower()
    if "thunder" in s or "storm" in s: return "⛈"
    if "rain"    in s or "shower" in s: return "🌧"
    if "snow"    in s:                  return "❄"
    if "fog"     in s or "mist" in s:   return "🌫"
    if "cloud"   in s and "partly" in s:return "⛅"
    if "cloud"   in s:                  return "☁"
    if "sun"     in s or "clear" in s or "fair" in s: return "☀"
    return "🌤"


def _is_good_weather(period: dict[str, Any]) -> bool:
    temp = period.get("temperature", 70)
    short = (period.get("shortForecast", "") or "").lower()
    return (
        60 <= temp <= 92
        and not any(w in short for w in ("rain", "storm", "snow", "thunder", "shower"))
    )


def get_forecast(lat: float, lon: float) -> dict[str, Any]:
    """Return a 7-day daytime-period forecast with icons and demand hints."""
    def _fetch():
        # Step 1: discover endpoint
        meta = _http_get(f"https://api.weather.gov/points/{lat},{lon}")
        fc_url = meta["properties"]["forecast"]
        # Step 2: fetch forecast
        fc = _http_get(fc_url)
        periods = fc["properties"]["periods"]
        # Filter to daytime periods only (isDaytime: true)
        daytime = [p for p in periods if p.get("isDaytime")][:7]
        out = []
        good_count = 0
        for p in daytime:
            start = p["startTime"][:10]
            icon = _icon_for(p["shortForecast"])
            good = _is_good_weather(p)
            if good: good_count += 1
            out.append({
                "date":         start,
                "name":         p["name"],
                "temp":         p["temperature"],
                "temp_unit":    p["temperatureUnit"],
                "wind":         p.get("windSpeed", ""),
                "short":        p["shortForecast"],
                "detailed":     p.get("detailedForecast", ""),
                "icon":         icon,
                "good_weather": good,
                "demand_blend": 0.05 if good else (-0.03 if "rain" in p["shortForecast"].lower() else 0.0),
            })
        return {
            "location":         meta["properties"].get("relativeLocation", {}).get("properties", {}),
            "forecast":         out,
            "good_day_count":   good_count,
            "good_day_pct":     round(good_count / len(out) * 100) if out else 0,
            "data_source":      "api.weather.gov",
            "fetched_at":       int(time.time()),
        }

    try:
        return _cached(f"fc:{lat},{lon}", _fetch)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, _json.JSONDecodeError) as e:
        return {
            "error":      f"Weather service unavailable: {type(e).__name__}",
            "forecast":   [],
            "data_source": "api.weather.gov",
            "fetched_at": int(time.time()),
        }


def get_summary(property_config: dict[str, Any]) -> dict[str, Any]:
    lat = property_config.get("latitude", 32.4316)   # Beaufort, SC fallback
    lon = property_config.get("longitude", -80.6698)
    return get_forecast(lat, lon)


def demand_modifier_for(target_date: date, property_config: dict[str, Any]) -> float:
    """Return a small ([-0.03, +0.05]) demand modifier for a specific date, or 0 if outside the 7-day window."""
    summary = get_summary(property_config)
    iso = target_date.isoformat()
    for day in summary.get("forecast", []):
        if day.get("date") == iso:
            return day.get("demand_blend", 0.0)
    return 0.0
