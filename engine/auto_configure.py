"""
engine/auto_configure.py
Module 4 — Onboarding Auto-Discovery

Orchestrates the full autonomous property configuration pipeline:
  1. Parse all room descriptions from DB using Claude
  2. Scrape property website for any additional room descriptions
  3. Run competitor ranking
  4. Parse top competitor rooms
  5. Return auto_config_report

Usage:
    python -m engine.auto_configure \\
      --slug anchorage-1770-demo \\
      --website https://anchorage1770.com/guest-rooms/
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from engine.description_parser import (
    parse_room_description,
    parse_all_property_rooms,
    parse_competitor_room,
    scrape_property_website,
)
from engine.competitor_ranker import CompetitorRanker

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-configure report
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AutoConfigReport:
    property_id:          str
    property_name:        str
    rooms_configured:     list[dict]
    primary_competitor:   dict | None
    competitors_ranked:   list[dict]
    website_rooms_found:  int
    items_needing_review: list[str]
    auto_applied:         list[str]
    competitor_rooms_parsed: list[str]
    summary:              str


def auto_configure_property(
    property_id:          str,
    tenant_id:            str,
    property_name:        str = "",
    property_website_url: str | None = None,
    *,
    supabase_url:  str | None = None,
    service_key:   str | None = None,
    dry_run:       bool = False,
) -> AutoConfigReport:
    """
    Full autonomous property configuration pipeline.
    When a new property is onboarded, call this once to:
      - Set bathroom_type, view_type from room descriptions
      - Identify primary competitor via scoring
      - Parse competitor rooms for benchmarking context
      - No human data entry required
    """
    url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
    key =  service_key  or os.getenv("SUPABASE_SERVICE_KEY", "")
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=none"}

    print(f"\n  ╔══ AUTO-CONFIGURE PROPERTY ══╗")
    print(f"  Property ID   : {property_id}")
    print(f"  Property Name : {property_name or '(lookup from DB)'}")
    if property_website_url:
        print(f"  Website       : {property_website_url}")
    print()

    # ── Step 1: Parse room descriptions from DB ────────────────────────
    print("  STEP 1 — Parse room descriptions from database…")
    db_results = parse_all_property_rooms(
        property_id, tenant_id,
        supabase_url=url, service_key=key,
        dry_run=dry_run,
    )

    needs_review = [r["room_name"] for r in db_results if r.get("needs_review")]
    auto_applied = [r["room_name"] for r in db_results if r.get("auto_applied")]

    for r in db_results:
        prefix = "✓" if r.get("auto_applied") else "⚠" if r.get("needs_review") else "○"
        print(f"    {prefix} {r['room_name']:<22} "
              f"→ {r['bathroom_type']:<28} view={r['view_type']:<12} "
              f"conf={r['confidence_score']}%"
              + (" [REVIEW]" if r.get("needs_review") else ""))

    # ── Step 2: Scrape property website ───────────────────────────────
    website_rooms: list[dict] = []
    if property_website_url:
        print(f"\n  STEP 2 — Scraping property website…")
        scraped = scrape_property_website(property_website_url)
        print(f"    Found {len(scraped)} room description(s) on the website")

        for room in scraped:
            attrs = parse_room_description(
                room["description"],
                property_name=property_name,
                supabase_url=url,
                service_key=key,
            )
            website_rooms.append({
                "name":           room["name"],
                "bathroom_type":  attrs.bathroom_type,
                "view_type":      attrs.view_type,
                "has_rain_shower": attrs.has_rain_shower,
                "luxury_features": attrs.luxury_features,
                "confidence":     attrs.confidence_score,
                "needs_review":   attrs.needs_review,
            })
            print(f"    → {room['name'][:40]:<42} "
                  f"bath={attrs.bathroom_type:<28} "
                  f"conf={attrs.confidence_score}%")
    else:
        print(f"\n  STEP 2 — No website URL provided, skipping website scrape")

    # ── Step 3: Rank competitors ───────────────────────────────────────
    print(f"\n  STEP 3 — Running autonomous competitor proximity scoring…")
    ranker = CompetitorRanker(supabase_url=url, service_key=key)
    rankings = ranker.rank_competitors(property_id, tenant_id)

    print(f"    {'Rank':<5} {'Competitor':<24} {'Score':>6}  "
          f"{'Price$':>7} {'Amenity':>8} {'Distance':>9}  Why")
    print(f"    {'─' * 90}")
    for r in rankings:
        print(
            f"    {r.rank:<5} {r.competitor_name:<24} {r.composite_score:>5.1f}  "
            f"{r.price_band_score:>6.0f}%  {r.amenity_score:>7.0f}%  "
            f"{r.distance_score:>8.0f}%  {r.rank_reason}"
        )

    primary = None
    if rankings:
        r1 = rankings[0]
        primary = {
            "id":             r1.competitor_id,
            "name":           r1.competitor_name,
            "composite_score": r1.composite_score,
            "rank_reason":    r1.rank_reason,
        }
        print(f"\n    ★ PRIMARY COMPETITOR: {r1.competitor_name} "
              f"(score {r1.composite_score:.0f}/100 — {r1.rank_reason})")

    # ── Step 4: Parse top 3 competitor rooms ──────────────────────────
    print(f"\n  STEP 4 — Parsing competitor room types (top 3)…")
    parsed_comps: list[str] = []
    for r in rankings[:3]:
        rooms = parse_competitor_room(
            r.competitor_id, tenant_id,
            supabase_url=url, service_key=key,
        )
        if rooms:
            parsed_comps.append(r.competitor_name)
            for room in rooms:
                print(f"    {r.competitor_name:<22} | {room.room_name[:30]:<30} "
                      f"→ {room.attributes.bathroom_type:<28} "
                      f"conf={room.attributes.confidence_score}%")

    # ── Step 5: Build report ──────────────────────────────────────────
    summary_parts = [
        f"{len(db_results)} room(s) parsed from DB",
        f"{len(auto_applied)} auto-applied",
        f"{len(needs_review)} flagged for review",
    ]
    if website_rooms:
        summary_parts.append(f"{len(website_rooms)} room(s) found on website")
    if primary:
        summary_parts.append(f"Primary competitor: {primary['name']}")

    report = AutoConfigReport(
        property_id=property_id,
        property_name=property_name,
        rooms_configured=db_results,
        primary_competitor=primary,
        competitors_ranked=[
            {"name": r.competitor_name, "rank": r.rank,
             "composite_score": r.composite_score, "reason": r.rank_reason}
            for r in rankings
        ],
        website_rooms_found=len(website_rooms),
        items_needing_review=needs_review,
        auto_applied=auto_applied,
        competitor_rooms_parsed=parsed_comps,
        summary=" | ".join(summary_parts),
    )

    return report


# ─────────────────────────────────────────────────────────────────────────────
#  REST helper
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_slug(slug: str, url: str, key: str) -> tuple[str, str, str]:
    """Returns (tenant_id, property_id, property_name)."""
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=none"}
    tenants = requests.get(
        f"{url}/rest/v1/tenants",
        headers=hdrs,
        params={"slug": f"eq.{slug}", "select": "id,name"},
        timeout=30,
    ).json()
    if not tenants:
        raise ValueError(f"Tenant slug {slug!r} not found")
    tid   = tenants[0]["id"]
    tname = tenants[0]["name"]

    props = requests.get(
        f"{url}/rest/v1/properties",
        headers=hdrs,
        params={"tenant_id": f"eq.{tid}", "select": "id,name", "limit": "1"},
        timeout=30,
    ).json()
    if not props:
        raise ValueError(f"No property for tenant {slug}")
    return tid, props[0]["id"], props[0].get("name", tname)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(description="The Gracious Collection — Auto-Configure Property")
    parser.add_argument("--slug",    default="anchorage-1770-demo")
    parser.add_argument("--website", default=None,
                        help="Property website URL to scrape for room descriptions")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse but don't write to DB")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")

    tenant_id, property_id, property_name = _resolve_slug(args.slug, url, key)

    report = auto_configure_property(
        property_id=property_id,
        tenant_id=tenant_id,
        property_name=property_name,
        property_website_url=args.website,
        supabase_url=url,
        service_key=key,
        dry_run=args.dry_run,
    )

    # ── Final report ──────────────────────────────────────────────────
    W = 88
    print(f"\n  {'═' * W}")
    print(f"  AUTO-CONFIGURATION COMPLETE — {report.summary}")
    print(f"  {'═' * W}")

    if report.items_needing_review:
        print(f"\n  ⚠  NEEDS HUMAN REVIEW ({len(report.items_needing_review)} items):")
        for item in report.items_needing_review:
            print(f"     • {item}")
        print(f"     Confidence < 70% — verify bathroom_type and view_type manually")

    if report.auto_applied:
        print(f"\n  ✓  AUTO-APPLIED ({len(report.auto_applied)} rooms):")
        for item in report.auto_applied:
            print(f"     • {item}")

    if report.website_rooms_found:
        print(f"\n  🌐 Website scraped: {report.website_rooms_found} additional room descriptions found")

    if report.primary_competitor:
        p = report.primary_competitor
        print(f"\n  ★  PRIMARY COMPETITOR: {p['name']}")
        print(f"     Score {p['composite_score']:.0f}/100 — {p['rank_reason']}")
        print(f"     Rate engine will use this as the dynamic pricing anchor")

    if report.competitor_rooms_parsed:
        print(f"\n  🎯 Competitor rooms parsed: {', '.join(report.competitor_rooms_parsed)}")

    print(f"\n  {'─' * W}")
    print(f"  Run `python -m engine.rate_engine --update-db` to refresh all rate recommendations")
    print(f"  {'═' * W}\n")


if __name__ == "__main__":
    main()
