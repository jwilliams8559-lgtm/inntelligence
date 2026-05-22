"""
Rate Recommendation Engine — S-Curve Pricing Algorithm
Maps demand score 0-100 to rate multiplier using cubic interpolation.

Also exports CPP pricing intelligence classes:
  - PocketPriceWaterfallEngine
  - EVEEngine
  - Price fence helpers (apply_fence_discount)
"""
from datetime import date
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateRecommendation:
    room_id: str
    room_name: str
    target_date: str
    recommended_rate: float
    rack_low: float
    rack_high: float
    current_rate: float
    rate_change_dollars: float
    rate_change_pct: float
    demand_score: int
    demand_label: str
    confidence: int
    reasoning: str
    minimum_stay: Optional[int]
    comp_avg: Optional[float]
    competitive_position: str  # Premium / At Market / Below Market
    segment_rates: dict = field(default_factory=dict)  # Section 2 — CPP
    # Boutique-classification fields (fdfa5d3 follow-up). Defaults keep
    # legacy callers safe — these only populate when comp_entries is used.
    comp_pos: Optional[float]  = None
    str_floor_applied: bool    = False
    str_baseline_avg: Optional[float] = None
    amenity_premium:  int      = 0
    top_boutique_comp_name: Optional[str]   = None
    top_boutique_comp_rate: Optional[float] = None


def enforce_hierarchy_top_down(rates_by_room: dict) -> dict:
    """Snap a per-room rate dict to the canonical room hierarchy:
    Waterfront > Water View > Cottage >= Garden. Caps each tier as a
    band relative to the tier above so Garden never accidentally exceeds
    Cottage, etc. Top-down (Waterfront anchors everything) so the boutique
    peer floor on Waterfront cascades naturally to lower tiers.
    """
    def find(aliases):
        for a in aliases:
            if a in rates_by_room:
                return a, rates_by_room[a]
        return None, None

    wf_key, wf = find(["Waterfront Suite", "Waterfront 201", "Waterfront 202",
                       "Waterfront 203", "Waterfront 204"])
    wv_key, wv = find(["Water View Suite", "Waterview Suite",
                       "Water View 301", "Water View 302", "Water View 303",
                       "Water View 304", "Water View 305"])
    co_key, co = find(["Cottage Room", "Private Cottage", "Cottage"])
    gv_key, gv = find(["Garden View Room", "Garden Room", "Garden View",
                       "Garden Room 101", "Garden Room 102",
                       "Garden Room 103", "Garden Room 104"])

    if wf is None:
        return rates_by_room
    out = dict(rates_by_room)

    if wv_key:
        wv_new = max(round(wf * 0.72), min(round(wf * 0.88), wv or 0))
        out[wv_key] = wv_new
        wv = wv_new
    if co_key and wv:
        co_new = max(round(wv * 0.78), min(round(wv * 0.92), co or 0))
        out[co_key] = co_new
        co = co_new
    if gv_key and co:
        gv_new = max(round(co * 0.85), min(round(co * 0.97), gv or 0))
        out[gv_key] = gv_new
    return out


class RateEngine:
    # S-curve control points: (demand_score, multiplier)
    CURVE = [
        (0,   0.75),
        (25,  0.88),
        (50,  1.00),
        (65,  1.15),
        (75,  1.30),
        (85,  1.55),
        (95,  1.90),
        (100, 2.10),
    ]

    def multiplier(self, score: int) -> float:
        score = max(0, min(100, score))
        for i in range(len(self.CURVE) - 1):
            s0, m0 = self.CURVE[i]
            s1, m1 = self.CURVE[i + 1]
            if s0 <= score <= s1:
                t = (score - s0) / (s1 - s0)
                # Cubic ease (smoothstep)
                t = t * t * (3 - 2 * t)
                return m0 + t * (m1 - m0)
        return 1.0

    @staticmethod
    def round_to_5(rate: float) -> float:
        return round(rate / 5) * 5

    def recommend(self, room: dict, demand_score: int, demand_label: str,
                  demand_drivers: list, confidence: int,
                  comp_rates: list = None, target_date: date = None,
                  comp_entries: list = None) -> RateRecommendation:
        """
        comp_rates    legacy flat list of rates — every entry weighted equally
        comp_entries  preferred: list of {"rate", "property_type"} dicts so the
                      math honors PROPERTY_TYPES weights (boutique 1.0, hotel
                      0.4, luxury 0.1, budget 0.05, STR 0.0) and applies the
                      BOUTIQUE_INN_PREMIUM (1.45x) over the STR baseline.
        """
        from config.settings import (
            PROPERTY_TYPES, BOUTIQUE_INN_PREMIUM, AMENITY_PREMIUM_OVER_STR_TOTAL,
        )

        base = room["base"]
        lo   = room["min"]
        hi   = room["max"]

        mult  = self.multiplier(demand_score)
        raw   = base * mult
        final = self.round_to_5(max(lo, min(hi, raw)))

        # Competitive adjustment
        comp_avg = None
        comp_pos = "At Market"
        str_baseline_avg = None
        has_str_in_set = False

        boutique_peer_avg = None
        top_boutique_comp_name: str | None = None
        top_boutique_comp_rate: float | None = None
        if comp_entries:
            # Weighted average using property_type weights from settings.
            # Top boutique anchor drives the target — not the avg.
            num, denom = 0.0, 0.0
            str_rates: list[float] = []
            peer_with_equiv: list[tuple[str, float]] = []  # (name, rate)
            for e in comp_entries:
                rate = e.get("rate")
                if rate is None:
                    continue
                ptype = e.get("property_type", "upscale_hotel")
                weight = PROPERTY_TYPES.get(ptype, {}).get("weight", 0.4)
                num   += rate * weight
                denom += weight
                if ptype == "airbnb_str":
                    has_str_in_set = True
                    str_rates.append(rate)
                # Only count boutique_inn comps WITH an equivalent room as
                # peers. A boutique inn without a waterfront listing is not
                # a valid waterfront peer — using its base rate would
                # artificially lower the floor.
                elif ptype == "boutique_inn" and e.get("has_equivalent", True):
                    peer_with_equiv.append((e.get("name", "Comp"), rate))
            if denom > 0:
                comp_avg = num / denom
            if peer_with_equiv:
                rates_only = [r for _, r in peer_with_equiv]
                boutique_peer_avg = sum(rates_only) / len(rates_only)
                # TOP comp = highest-priced boutique peer with an equivalent
                top_name, top_rate = max(peer_with_equiv, key=lambda x: x[1])
                top_boutique_comp_name = top_name
                top_boutique_comp_rate = top_rate
            if str_rates:
                str_baseline_avg = sum(str_rates) / len(str_rates)
                # STR floor: a boutique inn should never quote below STR avg * 1.45
                premium_floor = self.round_to_5(str_baseline_avg * BOUTIQUE_INN_PREMIUM)
                if final < premium_floor:
                    final = self.round_to_5(min(max(final, premium_floor), hi))

            # Top-boutique-comp anchor — INNtelligence prices at or above
            # the top boutique peer (Cuthbert House etc) on every date.
            # New ownership at Anchorage 1770 earns small premiums on
            # weekends and peak events; never quotes below the top peer.
            if top_boutique_comp_rate:
                # Demand-tier premium
                if   demand_score < 50: demand_premium = 0.00
                elif demand_score < 70: demand_premium = 0.00
                elif demand_score < 85: demand_premium = 0.03
                else:                   demand_premium = 0.05
                # Weekend bonus (Fri/Sat) — leisure travel demand the
                # demand_engine score does not fully capture
                weekend_bonus = 0.02 if (target_date and target_date.weekday() in (4, 5)) else 0.0
                premium_pct = max(demand_premium + weekend_bonus, 0.0)

                target_rate  = top_boutique_comp_rate * (1 + premium_pct)
                # Round the floor UP to the next $5 so we never dip below
                # Cuthbert by a couple dollars due to floor rounding.
                import math as _math
                floor_rate   = _math.ceil(top_boutique_comp_rate / 5) * 5
                ceiling_rate = top_boutique_comp_rate * 1.12     # never more than 12% above

                final = max(final, target_rate)
                final = min(ceiling_rate, max(floor_rate, final))
                # Snap to nearest $5 but never below floor
                final = self.round_to_5(final)
                if final < floor_rate:
                    final = floor_rate
                final = min(max(final, lo), hi)
        elif comp_rates:
            comp_avg = sum(comp_rates) / len(comp_rates)

        if comp_avg:
            # Soft ceiling: don't price more than 25% above comp_avg in soft demand
            if final > comp_avg * 1.25 and demand_score < 70:
                final = self.round_to_5(min(final, comp_avg * 1.15))
            pct_vs_comp = (final - comp_avg) / comp_avg
            if pct_vs_comp > 0.12:
                comp_pos = "Premium"
            elif pct_vs_comp < -0.12:
                comp_pos = "Below Market"
            else:
                comp_pos = "At Market"

        # Minimum stay rule
        min_stay = None
        if target_date:
            dow = target_date.weekday()
            if dow in (4, 5) and demand_score >= 60:
                min_stay = 2

        # Rate change vs base (rack midpoint)
        rack_mid = base
        change_dollars = final - rack_mid
        change_pct = (change_dollars / rack_mid) * 100

        # Rack display range
        rack_low = int(base * 0.78)
        rack_high = int(base * 1.12)

        # Plain-English reasoning
        reason_parts = [f"Demand is {demand_label} (score {demand_score}/100)."]
        if demand_drivers:
            reason_parts.append(demand_drivers[0] + ".")
        if change_dollars > 0:
            reason_parts.append(
                f"Rate of ${int(final):,} is ${int(change_dollars):+,} above base rack, capturing strong demand."
            )
        elif change_dollars < 0:
            reason_parts.append(
                f"Rate of ${int(final):,} is ${int(abs(change_dollars)):,} below rack to stimulate occupancy."
            )
        if comp_avg:
            reason_parts.append(
                f"Comp set average is ${int(comp_avg):,} — you are {comp_pos.lower()}."
            )
        if top_boutique_comp_rate and top_boutique_comp_name:
            pct_vs_top = (final - top_boutique_comp_rate) / top_boutique_comp_rate * 100
            if pct_vs_top >= 0:
                reason_parts.append(
                    f"Boutique peer positioning: {top_boutique_comp_name} at "
                    f"${int(top_boutique_comp_rate):,}. Your ${int(final):,} is "
                    f"+{pct_vs_top:.1f}% above. Anchorage 1770 offers Ribaut Social "
                    f"Club restaurant, rooftop bar, and chef breakfast — amenities "
                    f"{top_boutique_comp_name} does not have."
                )
            else:
                reason_parts.append(
                    f"Boutique peer positioning: {top_boutique_comp_name} at "
                    f"${int(top_boutique_comp_rate):,}. Your ${int(final):,} is "
                    f"{pct_vs_top:.1f}% (soft demand)."
                )
        if has_str_in_set and str_baseline_avg:
            reason_parts.append(
                f"Boutique inn amenity premium over comparable STR: "
                f"+${int(AMENITY_PREMIUM_OVER_STR_TOTAL)}/night (breakfast $38 + "
                f"innkeeper service $28 + premium amenities $20 + historic character "
                f"$35 + quality assurance $15). Your rate of ${int(final):,} reflects "
                f"this premium and is justified vs Airbnb/VRBO averaging "
                f"${int(str_baseline_avg)}."
            )
        reasoning = " ".join(reason_parts)

        # Section 2 — segment-specific rates
        segment_rates = {}
        try:
            from config.settings import CHANNEL_SEGMENTS
            for seg_id, seg in CHANNEL_SEGMENTS.items():
                modifier = seg.get("rate_modifier", 0)
                seg_rate = self.round_to_5(final * (1 + modifier))
                seg_rate = max(room["min"], min(room["max"], seg_rate))
                segment_rates[seg_id] = {
                    "segment":      seg["label"],
                    "icon":         seg.get("icon", "•"),
                    "rate":         seg_rate,
                    "modifier_pct": int(modifier * 100),
                    "note":         seg["description"],
                    "strategy":     seg.get("rate_strategy"),
                }
        except ImportError:
            pass

        # comp_pos: numeric 0..10 position score derived from your rate vs comp_avg
        comp_pos_score = None
        if comp_avg and final:
            ratio = final / comp_avg
            # Map ratio 0.80..1.30 → 0..10
            comp_pos_score = max(0.0, min(10.0, (ratio - 0.80) / 0.50 * 10))
            comp_pos_score = round(comp_pos_score, 1)

        str_floor_applied_flag = bool(str_baseline_avg and final >= (str_baseline_avg or 0) * BOUTIQUE_INN_PREMIUM)

        return RateRecommendation(
            room_id=room["id"],
            room_name=room["name"],
            target_date=target_date.isoformat() if target_date else "",
            recommended_rate=final,
            rack_low=rack_low,
            rack_high=rack_high,
            current_rate=rack_mid,
            rate_change_dollars=change_dollars,
            rate_change_pct=change_pct,
            demand_score=demand_score,
            demand_label=demand_label,
            confidence=confidence,
            reasoning=reasoning,
            minimum_stay=min_stay,
            comp_avg=comp_avg,
            competitive_position=comp_pos,
            segment_rates=segment_rates,
            comp_pos=comp_pos_score,
            str_floor_applied=str_floor_applied_flag,
            str_baseline_avg=str_baseline_avg,
            amenity_premium=int(AMENITY_PREMIUM_OVER_STR_TOTAL) if has_str_in_set else 0,
            top_boutique_comp_name=top_boutique_comp_name,
            top_boutique_comp_rate=top_boutique_comp_rate,
        )

    # ── Section 3: Price fence helper ──────────────────────────────────

    def apply_fence_discount(self, base_rate: float, fence_id: str,
                              nights: int = 1, lead_days: int = 0) -> dict:
        """Apply a price-fence discount and return the fenced rate + rationale."""
        from config.settings import PRICE_FENCES
        fence = next((f for f in PRICE_FENCES if f["id"] == fence_id), None)
        if not fence or not fence.get("active"):
            return {"rate": base_rate, "discount_pct": 0, "fence": None}

        discount = 0.0
        if "discount_pct" in fence:
            discount = fence["discount_pct"] / 100
        elif "discount_schedule" in fence:
            sched = fence["discount_schedule"]
            keys = sorted(sched.keys(), reverse=True)
            if fence["fence_type"] == "length_of_stay":
                for k in keys:
                    if nights >= k:
                        discount = sched[k]; break
            elif fence["fence_type"] == "booking_window":
                for k in keys:
                    if lead_days >= k:
                        discount = sched[k]; break

        fenced_rate = self.round_to_5(base_rate * (1 - discount))
        return {
            "rate":             fenced_rate,
            "discount_pct":     int(discount * 100),
            "discount_dollars": round(base_rate - fenced_rate, 2),
            "fence_name":       fence["name"],
            "fence_id":         fence_id,
            "verification":     fence.get("verification_method"),
            "rationale":        fence.get("rationale", ""),
        }


# ════════════════════════════════════════════════════════════════════════
# Section 1: Pocket Price Waterfall
# ════════════════════════════════════════════════════════════════════════

@dataclass
class WaterfallLine:
    label:        str
    amount:       float
    cumulative:   float
    pct_of_rack:  float
    is_deduction: bool
    color:        str = "#ffffff"


@dataclass
class ChannelWaterfall:
    channel_id:                str
    channel_label:             str
    channel_icon:              str
    rack_rate:                 float
    lines:                     list
    gross_revenue:             float
    net_after_fees:            float
    contribution_margin:       float
    contribution_margin_pct:   float
    effective_rate_pct:        float
    vs_direct_delta:           float
    recommendation:            str


class PocketPriceWaterfallEngine:
    """
    CPP pocket-price waterfall. Walks from rack rate down through every
    deduction (OTA commission, payment processing, channel manager fee,
    booking engine fee, variable costs) to arrive at true contribution margin.
    """

    def compute_channel_waterfall(self, rack_rate: float,
                                   channel_id: str, nights: int = 1) -> ChannelWaterfall:
        from config.settings import (CHANNEL_COST_STRUCTURE,
                                     TOTAL_VARIABLE_COST_PER_BOOKING)
        ch = CHANNEL_COST_STRUCTURE.get(channel_id)
        if not ch:
            raise ValueError(f"Unknown channel: {channel_id}")
        lines: list = []
        rack_total = rack_rate * nights
        current = rack_total

        lines.append(WaterfallLine(
            label=f"Rack Rate ({nights} night{'s' if nights > 1 else ''})",
            amount=current, cumulative=current, pct_of_rack=100.0,
            is_deduction=False, color="#c9a84c",
        ))

        deduction_map = [
            ("ota_commission",      "Commission",                "#e74c3c"),
            ("credit_card_fee",     "Credit Card Processing",    "#e67e22"),
            ("channel_manager_fee", "Channel Manager Fee",       "#f39c12"),
            ("booking_engine_fee",  "Booking Engine Fee",        "#f39c12"),
        ]
        for key, friendly, color in deduction_map:
            pct = ch.get(key, 0)
            if pct <= 0:
                continue
            ded = current * pct
            current -= ded
            lines.append(WaterfallLine(
                label=f"{ch['label']} {friendly} ({pct * 100:.1f}%)" if key == "ota_commission"
                      else f"{friendly} ({pct * 100:.1f}%)",
                amount=-ded, cumulative=current,
                pct_of_rack=round(current / rack_total * 100, 1),
                is_deduction=True, color=color,
            ))

        gross_revenue = current

        # Variable costs (per booking, not per night)
        current -= TOTAL_VARIABLE_COST_PER_BOOKING
        lines.append(WaterfallLine(
            label="Variable Costs (cleaning, amenities, laundry)",
            amount=-TOTAL_VARIABLE_COST_PER_BOOKING,
            cumulative=current,
            pct_of_rack=round(current / rack_total * 100, 1),
            is_deduction=True, color="#8e44ad",
        ))

        contribution_margin = current
        cm_pct = (contribution_margin / rack_total) * 100

        if channel_id == "direct_web":
            rec = "Best net revenue. Prioritize direct booking incentives."
        elif cm_pct >= 65:
            rec = f"Strong margin. {ch['label']} bookings are profitable at this rate."
        elif cm_pct >= 50:
            rec = (f"Acceptable margin. Consider a slight rate premium on "
                   f"{ch['label']} to improve net.")
        else:
            rec = (f"Low margin after {ch['label']} commission. Raise rate or "
                   f"shift marketing to direct.")

        return ChannelWaterfall(
            channel_id=channel_id,
            channel_label=ch["label"],
            channel_icon=ch["icon"],
            rack_rate=rack_total,
            lines=lines,
            gross_revenue=round(gross_revenue, 2),
            net_after_fees=round(gross_revenue, 2),
            contribution_margin=round(contribution_margin, 2),
            contribution_margin_pct=round(cm_pct, 1),
            effective_rate_pct=round(cm_pct, 1),
            vs_direct_delta=0.0,
            recommendation=rec,
        )

    def compute_all_channels(self, rack_rate: float, nights: int = 1) -> dict:
        from config.settings import CHANNEL_COST_STRUCTURE
        results: dict = {}
        for ch_id in CHANNEL_COST_STRUCTURE:
            results[ch_id] = self.compute_channel_waterfall(rack_rate, ch_id, nights)
        direct_cm = results["direct_web"].contribution_margin
        for wf in results.values():
            wf.vs_direct_delta = round(wf.contribution_margin - direct_cm, 2)
        return results

    def compute_rate_parity_recommendation(self, rack_rate: float,
                                            nights: int = 1) -> dict:
        from config.settings import (CHANNEL_COST_STRUCTURE,
                                     TOTAL_VARIABLE_COST_PER_BOOKING)
        direct_wf  = self.compute_channel_waterfall(rack_rate, "direct_web", nights)
        target_cm  = direct_wf.contribution_margin
        parity: dict = {}
        for ch_id, ch in CHANNEL_COST_STRUCTURE.items():
            if ch_id == "direct_web":
                parity[ch_id] = {"channel": ch["label"], "icon": ch["icon"],
                                  "rate_for_parity": rack_rate, "note": "Base rate"}
                continue
            total_pct = (ch["ota_commission"] + ch["credit_card_fee"]
                          + ch["channel_manager_fee"] + ch["booking_engine_fee"])
            required_gross = target_cm + TOTAL_VARIABLE_COST_PER_BOOKING
            parity_rate = required_gross / max(0.01, (1 - total_pct))
            parity_rate_rounded = round(parity_rate / 5) * 5
            parity[ch_id] = {
                "channel":           ch["label"],
                "icon":              ch["icon"],
                "rate_for_parity":   parity_rate_rounded,
                "premium_vs_direct": round(parity_rate_rounded - rack_rate, 0),
                "premium_pct":       round((parity_rate_rounded - rack_rate) / rack_rate * 100, 1),
                "note":              f"Charge ${parity_rate_rounded:.0f} on {ch['label']} "
                                     f"to net the same as ${rack_rate:.0f} direct",
            }
        return {
            "direct_rate":                rack_rate,
            "target_contribution_margin": round(target_cm, 2),
            "parity_rates":               parity,
        }

    def blended_revenue_analysis(self, rack_rate: float,
                                  channel_mix: Optional[dict] = None,
                                  nights: int = 1) -> dict:
        from config.settings import CHANNEL_MIX
        mix = channel_mix or CHANNEL_MIX
        all_wf = self.compute_all_channels(rack_rate, nights)
        blended_cm    = 0.0
        blended_gross = 0.0
        breakdown: list = []
        for ch_id, pct in mix.items():
            if ch_id not in all_wf:
                continue
            wf = all_wf[ch_id]
            contribution = wf.contribution_margin * pct
            blended_cm    += contribution
            blended_gross += wf.gross_revenue * pct
            breakdown.append({
                "channel":      wf.channel_label,
                "icon":         wf.channel_icon,
                "mix_pct":      int(pct * 100),
                "cm_per_booking": round(wf.contribution_margin, 2),
                "weighted_cm":  round(contribution, 2),
            })
        return {
            "rack_rate":                    rack_rate,
            "blended_gross_revenue":        round(blended_gross, 2),
            "blended_contribution_margin":  round(blended_cm, 2),
            "blended_cm_pct":               round(blended_cm / rack_rate * 100, 1),
            "channel_breakdown":            breakdown,
            "insight":                      self._blended_insight(blended_cm, rack_rate, mix),
        }

    @staticmethod
    def _blended_insight(blended_cm: float, rack_rate: float, mix: dict) -> str:
        cm_pct = blended_cm / rack_rate * 100
        direct_pct = (mix.get("direct_web", 0) + mix.get("direct_phone", 0)) * 100
        if direct_pct < 30:
            return (f"Only {direct_pct:.0f}% of bookings are direct. "
                    f"Increasing direct to 50% would add ~${rack_rate * 0.12:.0f} "
                    f"per booking to net revenue.")
        if cm_pct < 55:
            return (f"Blended margin of {cm_pct:.0f}% is below target. "
                    f"Review OTA rate premiums and direct booking incentives.")
        return (f"Blended margin of {cm_pct:.0f}% is healthy. "
                f"Direct booking share of {direct_pct:.0f}% is strong.")


# ════════════════════════════════════════════════════════════════════════
# Section 4: Economic Value Estimation
# ════════════════════════════════════════════════════════════════════════

class EVEEngine:
    """
    Economic Value Estimation — quantifies the total value premium vs the
    next-best alternative, supporting confident premium pricing and guest
    communication.
    """

    def __init__(self, eve_config: dict):
        self.config = eve_config

    def compute_eve(self, room_category: str = "all") -> dict:
        from config.settings import AMENITY_PREMIUM_OVER_STR, AMENITY_PREMIUM_OVER_STR_TOTAL
        nba = self.config["next_best_alternative"]
        drivers = [
            d for d in self.config["value_drivers"]
            if "all" in d["applies_to"] or room_category in d["applies_to"]
        ]
        total_premium  = sum(d["value_estimate"] for d in drivers)
        justified_rate = nba["avg_rate"] + total_premium

        # Amenity premium over STR (Airbnb/VRBO) — separate from the value
        # drivers above because it explains the gap against short-term rentals
        # specifically, not hotels.
        str_amenity_premium = [
            {"key": k, "name": k.replace("_", " ").title(), "value_estimate": v}
            for k, v in AMENITY_PREMIUM_OVER_STR.items()
        ]
        return {
            "next_best_alternative": nba,
            "value_drivers":         drivers,
            "total_value_premium":   total_premium,
            "justified_rate":        justified_rate,
            "justified_rate_label":  f"${justified_rate:.0f}/night",
            "premium_vs_nba_pct":    round(total_premium / nba["avg_rate"] * 100, 1),
            "summary":               (f"Anchorage 1770 delivers ${total_premium} in "
                                       f"quantifiable value above {nba['name']} (${nba['avg_rate']}/night), "
                                       f"justifying a rack rate of ${justified_rate:.0f}+ per night."),
            "str_amenity_premium":         str_amenity_premium,
            "str_amenity_premium_total":   AMENITY_PREMIUM_OVER_STR_TOTAL,
            "str_summary": (
                f"Boutique inn amenity premium over comparable STR: "
                f"+${int(AMENITY_PREMIUM_OVER_STR_TOTAL)}/night "
                f"(breakfast for two ${AMENITY_PREMIUM_OVER_STR['breakfast_for_two']:.0f} + "
                f"innkeeper service ${AMENITY_PREMIUM_OVER_STR['innkeeper_service']:.0f} + "
                f"premium amenities ${AMENITY_PREMIUM_OVER_STR['premium_amenities']:.0f} + "
                f"historic character ${AMENITY_PREMIUM_OVER_STR['unique_character']:.0f} + "
                f"quality assurance ${AMENITY_PREMIUM_OVER_STR['quality_assurance']:.0f})."
            ),
        }

    def guest_facing_justification(self, rate: float, room_name: str,
                                    event_context: Optional[str] = None) -> str:
        eve = self.compute_eve()
        top_drivers = sorted(eve["value_drivers"], key=lambda x: x["value_estimate"], reverse=True)[:3]
        driver_text = " · ".join(d["name"].split(" Premium")[0].split(" Access")[0] for d in top_drivers)
        base = (
            f"The {room_name} at Anchorage 1770 Inn is priced at ${rate:.0f}/night, "
            f"reflecting our waterfront location on the National Register of Historic "
            f"Places, personal boutique service, and direct access to the Ribaut Social "
            f"Club restaurant — experiences unavailable at any other property in Beaufort. "
            f"Top value drivers: {driver_text}."
        )
        if event_context:
            base += (f" {event_context} brings exceptional demand to Beaufort, "
                     f"and our historic Bay Street location places guests at the heart "
                     f"of the celebration.")
        return base
