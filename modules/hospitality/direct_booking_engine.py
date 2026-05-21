"""Direct booking conversion tools.

Surfaces the commission savings from shifting OTA bookings to direct, helps
the innkeeper configure an incentive (discount, perk, or both), and emits a
HTML widget snippet to paste on their property site.
"""
from __future__ import annotations

import json
import os
from typing import Any

from config.settings import (
    CHANNEL_COST_STRUCTURE,
    CHANNEL_MIX,
    TOTAL_VARIABLE_COST_PER_BOOKING,
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "direct_booking_config.json")

DEFAULT_INCENTIVE = {
    "discount_pct":   5,
    "perk_label":     "Complimentary welcome bottle of wine",
    "headline":       "Save more — book direct",
    "subhead":        "Best rate guaranteed. Plus a small thank-you on arrival.",
    "primary_color":  "#1A3A5C",
    "accent_color":   "#A07830",
}


def _load_config() -> dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_INCENTIVE)
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        return {**DEFAULT_INCENTIVE, **data}
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_INCENTIVE)


def _save_config(payload: dict[str, Any]) -> dict[str, Any]:
    merged = {**_load_config(), **{k: v for k, v in payload.items() if k in DEFAULT_INCENTIVE}}
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(merged, f, indent=2)
    return merged


def commission_math(adr: float, monthly_bookings: int) -> dict[str, Any]:
    """Compute current OTA leakage and the recovery available at three shift levels."""
    rows = []
    for channel, mix_pct in CHANNEL_MIX.items():
        meta = CHANNEL_COST_STRUCTURE.get(channel, {})
        total_cost_pct = (
            meta.get("ota_commission", 0)
            + meta.get("credit_card_fee", 0)
            + meta.get("channel_manager_fee", 0)
            + meta.get("booking_engine_fee", 0)
        )
        bookings = round(monthly_bookings * mix_pct)
        cost_per_booking = adr * total_cost_pct
        rows.append({
            "channel":          channel,
            "label":            meta.get("label", channel),
            "mix_pct":          round(mix_pct * 100, 1),
            "monthly_bookings": bookings,
            "ota_commission":   round(meta.get("ota_commission", 0) * 100, 1),
            "cost_per_booking": round(cost_per_booking, 2),
            "monthly_cost":     round(cost_per_booking * bookings, 2),
        })

    ota_channels  = ["booking_com", "expedia", "airbnb", "vrbo", "tripadvisor"]
    current_ota_pct = sum(CHANNEL_MIX.get(c, 0) for c in ota_channels)
    avg_ota_commission = (
        sum(CHANNEL_MIX.get(c, 0) * CHANNEL_COST_STRUCTURE[c]["ota_commission"] for c in ota_channels)
        / current_ota_pct
    ) if current_ota_pct else 0

    scenarios = []
    for shift in (5, 10, 15):
        bookings_shifted_monthly = round(monthly_bookings * (shift / 100))
        saved_per_booking = adr * avg_ota_commission
        annual_savings = bookings_shifted_monthly * saved_per_booking * 12
        scenarios.append({
            "shift_pct":            shift,
            "monthly_bookings":     bookings_shifted_monthly,
            "saved_per_booking":    round(saved_per_booking, 2),
            "monthly_savings":      round(bookings_shifted_monthly * saved_per_booking, 2),
            "annual_savings":       round(annual_savings, 2),
        })

    return {
        "current_ota_pct":     round(current_ota_pct * 100, 1),
        "avg_ota_commission":  round(avg_ota_commission * 100, 1),
        "channel_breakdown":   rows,
        "shift_scenarios":     scenarios,
    }


def break_even_discount(adr: float, ota_commission_pct: float = 0.15) -> dict[str, Any]:
    """Largest direct-book discount the property can offer and still come out ahead."""
    ota_lost_revenue   = adr * ota_commission_pct          # what the OTA would have taken
    direct_card_fee    = adr * 0.025                        # rough merchant fee on direct
    breakeven_discount = ota_lost_revenue - direct_card_fee
    return {
        "ota_commission_per_booking": round(ota_lost_revenue, 2),
        "direct_card_fee":            round(direct_card_fee, 2),
        "breakeven_discount":         round(breakeven_discount, 2),
        "breakeven_discount_pct":     round(breakeven_discount / adr * 100, 1) if adr else 0,
        "recommended_discount":       round(breakeven_discount * 0.6, 2),
        "recommended_discount_pct":   round(breakeven_discount * 0.6 / adr * 100, 1) if adr else 0,
    }


def widget_embed_html(property_name: str, config: dict[str, Any]) -> str:
    """Static HTML snippet the innkeeper drops into their site."""
    headline      = config.get("headline", DEFAULT_INCENTIVE["headline"])
    subhead       = config.get("subhead", DEFAULT_INCENTIVE["subhead"])
    discount_pct  = config.get("discount_pct", 5)
    perk          = config.get("perk_label", "")
    primary       = config.get("primary_color", "#1A3A5C")
    accent        = config.get("accent_color", "#A07830")
    perk_line     = f'<div style="font-size:12px;color:#fff;opacity:.85;margin-top:4px">+ {perk}</div>' if perk else ""

    return f"""<!-- INNtelligence direct-book widget for {property_name} -->
<a href="#book" style="display:block;max-width:380px;text-decoration:none;border-radius:12px;overflow:hidden;font-family:Georgia,serif;box-shadow:0 4px 16px rgba(0,0,0,.12)">
  <div style="background:{primary};padding:18px 22px;color:#fff">
    <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{accent};font-weight:bold">{discount_pct}% Off · Direct Only</div>
    <div style="font-size:20px;font-weight:bold;margin-top:4px">{headline}</div>
    <div style="font-size:13px;opacity:.9;margin-top:6px">{subhead}</div>{perk_line}
  </div>
  <div style="background:{accent};color:#fff;padding:10px;text-align:center;font-weight:bold;font-size:14px;letter-spacing:1px">
    BOOK NOW →
  </div>
</a>
""".strip()


def get_summary(property_config: dict[str, Any]) -> dict[str, Any]:
    from config.settings import ROOM_TYPES
    rooms = property_config.get("total_rooms") or property_config.get("rooms", 14)
    occ_min = property_config.get("target_occupancy_min", 0.70)
    occ_max = property_config.get("target_occupancy_max", 0.85)
    occupancy = float(property_config.get("target_occupancy", (occ_min + occ_max) / 2))
    if ROOM_TYPES:
        total_count = sum(r.get("count", 1) for r in ROOM_TYPES)
        avg_adr = sum(r["base"] * r.get("count", 1) for r in ROOM_TYPES) / total_count
    else:
        avg_adr = float(property_config.get("base_adr", 380))
    monthly_bookings = round(rooms * occupancy * 30)

    cfg = _load_config()
    return {
        "property_name":    property_config.get("name", "Property"),
        "monthly_bookings": monthly_bookings,
        "adr":              avg_adr,
        "commission_math":  commission_math(avg_adr, monthly_bookings),
        "break_even":       break_even_discount(avg_adr),
        "incentive":        cfg,
        "widget_html":      widget_embed_html(property_config.get("name", "Property"), cfg),
        "variable_cost_per_booking": TOTAL_VARIABLE_COST_PER_BOOKING,
    }


def save_incentive(payload: dict[str, Any]) -> dict[str, Any]:
    return _save_config(payload)
