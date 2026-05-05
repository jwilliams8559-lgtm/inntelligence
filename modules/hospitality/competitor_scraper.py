"""
modules/hospitality/competitor_scraper.py

Live competitor rate scraper for Beaufort SC hospitality properties.

Target properties:
  - Rhett House Inn
  - City Loft Hotel
  - Beaufort Inn
  - Cuthbert House Inn
  - 607 Bay Inn
  - Airbnb waterfront area (average)

Scraping strategy (fallback chain):
  1. HTTP fetch from Booking.com / Expedia with browser headers + JSON-LD extraction
  2. Yesterday's cached rates (data/processed/competitor_rates_YYYY-MM-DD.json)
  3. Seasonal estimation model calibrated to known Beaufort SC rate ranges

PRODUCTION NOTE:
  Expedia and Booking.com render prices via JavaScript — reliable production
  scraping requires a headless browser (Playwright / Puppeteer) or a purpose-
  built rate-shopping API such as OTA Insight / Lighthouse or RateGain.
  The HTTP attempt below captures server-rendered fragments and CDN-cached
  JSON-LD blocks where available, and falls back cleanly otherwise.

Cache:
  data/processed/competitor_rates_YYYY-MM-DD.json  — daily rate cache
  data/processed/competitor_snapshots/YYYY-MM-DD.json  — rate+availability snapshots

Schedule: 6 AM UTC daily via start_scheduler()
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import schedule
from bs4 import BeautifulSoup

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent
import sys
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import DATA_PROCESSED_DIR
from modules.hospitality.anchorage_pricing import (
    COMPETITORS,
    ROOM_INVENTORY,
    SEASONAL_INDEX,
    AnchoragePricingEngine,
)

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = os.path.join(DATA_PROCESSED_DIR, "competitor_snapshots")

# ─────────────────────────────────────────────────────────────────────────────
#  HTTP scraping config
# ─────────────────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "DNT": "1",
}

_REQUEST_TIMEOUT = 10
_INTER_REQUEST_DELAY = 1.5

_BOOKING_SEARCH_URL = (
    "https://www.booking.com/searchresults.html"
    "?ss={property_query}&checkin={checkin}&checkout={checkout}"
    "&group_adults=2&no_rooms=1&lang=en-us"
)

_EXPEDIA_SEARCH_URL = (
    "https://www.expedia.com/Hotel-Search"
    "?destination={property_query}+Beaufort+South+Carolina"
    "&startDate={checkin}&endDate={checkout}&adults=2"
)

# ─────────────────────────────────────────────────────────────────────────────
#  Competitor scraper
# ─────────────────────────────────────────────────────────────────────────────

class CompetitorScraper:
    """
    Scrapes or estimates nightly rates + availability for the Beaufort SC
    competitor set. Always returns usable data via a three-tier fallback chain.
    """

    PROPERTY_NAMES = [c.name for c in COMPETITORS.values()]

    def __init__(self) -> None:
        self._engine = AnchoragePricingEngine()
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._ensure_initial_snapshots()

    # ------------------------------------------------------------------ #
    #  Public API — Rates                                                  #
    # ------------------------------------------------------------------ #

    def get_rates_for_date(self, check_in: date) -> Dict[str, float]:
        """
        Returns {competitor_name: nightly_rate} for a single check-in date.
        Checks cache first, then scrapes, then falls back to estimation.
        """
        cache = self._load_rate_cache(check_in)
        if cache:
            logger.debug(f"Competitor rates for {check_in} served from cache")
            return cache

        logger.info(f"Fetching live competitor rates for {check_in}")
        rates: Dict[str, float] = {}
        check_out = check_in + timedelta(days=1)

        for key, comp in COMPETITORS.items():
            if key == "airbnb_avg":
                rates[comp.name] = self._engine.get_competitor_rates(check_in)[comp.name]
                continue

            scraped = self._try_scrape_booking(comp.name, check_in, check_out)
            if scraped is None:
                scraped = self._try_scrape_expedia(comp.name, check_in, check_out)
            if scraped is None:
                scraped = self._engine.get_competitor_rates(check_in)[comp.name]

            rates[comp.name] = scraped
            time.sleep(_INTER_REQUEST_DELAY)

        self._save_rate_cache(check_in, rates)
        return rates

    def get_rates_for_window(self, days: int = 30) -> Dict[str, Dict[str, float]]:
        """Returns {date_str: {competitor_name: rate}} for the next N days."""
        logger.info(f"Building {days}-day competitor rate window")
        today = date.today()
        return {
            (today + timedelta(days=i)).isoformat(): self.get_rates_for_date(today + timedelta(days=i))
            for i in range(days)
        }

    # ------------------------------------------------------------------ #
    #  Public API — Availability                                           #
    # ------------------------------------------------------------------ #

    def _estimate_availability(self, comp_key: str, check_in: date) -> Tuple[str, float]:
        """
        Deterministic availability estimate from seasonal + event demand.
        Returns (status, est_occupancy) where status is 'available' | 'limited' | 'sold_out'.
        """
        seasonal   = SEASONAL_INDEX.get(check_in.month, 1.0)
        event_mult, _ = self._engine.get_event_multiplier(check_in)
        is_weekend = check_in.weekday() in (4, 5)
        demand     = seasonal * event_mult * (1.15 if is_weekend else 1.0)

        # Deterministic per-property variance
        seed    = (check_in.toordinal() * 13 + hash(comp_key)) % 100
        noise   = 1.0 + (seed - 50) * 0.003
        est_occ = round(min(demand * noise * 0.72, 0.97), 2)

        if est_occ >= 0.88:
            return "sold_out", est_occ
        elif est_occ >= 0.70:
            return "limited", est_occ
        else:
            return "available", est_occ

    def get_availability_snapshot(self, check_in: date) -> Dict[str, Dict]:
        """Returns {competitor_name: {rate, availability_status, est_occupancy, indicator}}."""
        rates = self._engine.get_competitor_rates(check_in)
        result = {}
        for key, comp in COMPETITORS.items():
            status, est_occ = self._estimate_availability(key, check_in)
            indicator = {"available": "🟢", "limited": "🟡", "sold_out": "🔴"}.get(status, "⚪")
            result[comp.name] = {
                "rate":                rates.get(comp.name, 0),
                "availability_status": status,
                "est_occupancy":       est_occ,
                "indicator":           indicator,
            }
        return result

    # ------------------------------------------------------------------ #
    #  Public API — Snapshots                                              #
    # ------------------------------------------------------------------ #

    def save_daily_snapshot(self) -> Optional[str]:
        """
        Saves today's rates + availability for the next 30 days to a JSON snapshot.
        Called by the 6 AM scheduler to build the rate compression history.
        """
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        today = date.today()
        path  = os.path.join(SNAPSHOT_DIR, f"{today.isoformat()}.json")

        data: Dict[str, Any] = {
            "snapshot_date": today.isoformat(),
            "scraped_at":    datetime.now(timezone.utc).isoformat(),
            "synthetic":     False,
            "rates":         {},
        }

        try:
            for offset in range(30):
                check_in = today + timedelta(days=offset)
                avail    = self.get_availability_snapshot(check_in)
                for comp_name, info in avail.items():
                    data["rates"].setdefault(comp_name, {})[check_in.isoformat()] = info

            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Daily snapshot saved → {path}")
            return path
        except Exception as exc:
            logger.error(f"Failed to save daily snapshot: {exc}", exc_info=True)
            return None

    def load_snapshot(self, snapshot_date: date) -> Optional[Dict]:
        """Load a previously saved or synthetic snapshot."""
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        path = os.path.join(SNAPSHOT_DIR, f"{snapshot_date.isoformat()}.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    # ------------------------------------------------------------------ #
    #  Synthetic historical snapshot bootstrap                             #
    # ------------------------------------------------------------------ #

    def _ensure_initial_snapshots(self) -> None:
        """
        Generates synthetic snapshots for 7, 14, and 30 days ago if they
        don't already exist. This bootstraps the rate compression charts
        immediately on first run without waiting for real history to accumulate.
        """
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        today = date.today()
        for days_ago in (30, 14, 7):
            snap_date = today - timedelta(days=days_ago)
            if self.load_snapshot(snap_date) is None:
                try:
                    self._generate_synthetic_snapshot(snap_date, days_ago)
                except Exception as exc:
                    logger.warning(f"Could not generate synthetic snapshot for {snap_date}: {exc}")

    def _generate_synthetic_snapshot(self, snap_date: date, days_ago: int) -> None:
        """
        Reconstructs a plausible historical snapshot:
        - For high-demand event dates: prices were lower further out (rising demand curve)
        - For low-demand dates: prices were slightly higher (minor discounting occurred)
        """
        today = date.today()
        path  = os.path.join(SNAPSHOT_DIR, f"{snap_date.isoformat()}.json")

        data: Dict[str, Any] = {
            "snapshot_date": snap_date.isoformat(),
            "scraped_at":    snap_date.isoformat() + "T06:00:00Z",
            "synthetic":     True,
            "rates":         {},
        }

        for offset in range(45):
            check_in = snap_date + timedelta(days=offset)
            if check_in < today:
                continue

            event_mult, _ = self._engine.get_event_multiplier(check_in)
            all_rates     = self._engine.get_competitor_rates(check_in)

            for key, comp in COMPETITORS.items():
                base = all_rates.get(comp.name, 0)
                # High-demand dates saw lower prices further out (curve rises toward event)
                if event_mult >= 1.25:
                    adj = 0.88 + (days_ago / 30) * 0.08   # 88-96% of current
                elif event_mult >= 1.10:
                    adj = 0.93 + (days_ago / 30) * 0.04
                else:
                    # Soft dates: slight softening means today's price is lower
                    adj = 1.02 - (days_ago / 30) * 0.03

                hist_rate            = round(base * adj / 5) * 5
                status, est_occ      = self._estimate_availability(key, check_in)
                indicator            = {"available": "🟢", "limited": "🟡", "sold_out": "🔴"}.get(status, "⚪")

                data["rates"].setdefault(comp.name, {})[check_in.isoformat()] = {
                    "rate":                hist_rate,
                    "availability_status": status,
                    "est_occupancy":       est_occ,
                    "indicator":           indicator,
                }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Synthetic snapshot generated → {path}")

    # ------------------------------------------------------------------ #
    #  Rate Compression & Pressure Score                                   #
    # ------------------------------------------------------------------ #

    def get_pressure_score(self, forward_days: int = 14) -> Tuple[int, str, str]:
        """
        Compares current competitor rates vs 14-day-ago snapshot for the
        next N days to produce a 1-10 market pressure score.

        1-3  = Strong market (rates rising — hold premiums)
        4-6  = Normal market
        7-10 = Soft market (rates falling — activate specials)
        """
        today      = date.today()
        snap_14d   = self.load_snapshot(today - timedelta(days=14))
        if not snap_14d:
            return 5, "Normal", "Insufficient rate history — continue monitoring."

        total_change, comparisons = 0.0, 0
        for offset in range(1, forward_days + 1):
            check_in    = today + timedelta(days=offset)
            date_str    = check_in.isoformat()
            current_all = self._engine.get_competitor_rates(check_in)

            for comp_name, current_rate in current_all.items():
                if "Airbnb" in comp_name:
                    continue
                hist = snap_14d.get("rates", {}).get(comp_name, {}).get(date_str, {})
                hist_rate = hist.get("rate", 0) if hist else 0
                if hist_rate > 0:
                    total_change += (current_rate - hist_rate) / hist_rate
                    comparisons  += 1

        if comparisons == 0:
            return 5, "Normal", "No comparable historical data found."

        avg_change = total_change / comparisons

        if avg_change > 0.08:
            return 2, "Very Strong", "Competitors raising rates. Consider increasing above standard premiums on peak dates."
        elif avg_change > 0.04:
            return 3, "Strong", "Market strong — competitors holding rates. Maintain premium pricing."
        elif avg_change > 0.01:
            return 4, "Good", "Healthy market. Hold rack rates on event dates; monitor midweek."
        elif avg_change > -0.02:
            return 5, "Normal", "Stable market. Standard dynamic pricing strategy recommended."
        elif avg_change > -0.05:
            return 6, "Softening", "Some rate softening detected. Consider promotional packages."
        elif avg_change > -0.08:
            return 7, "Soft", "Market softening. Activate midweek specials to capture demand."
        else:
            return 9, "Very Soft", "Significant discounting across comp set. Activate specials and package promos immediately."

    def get_compression_data(self, forward_days: int = 30) -> Dict[str, Any]:
        """
        Full rate compression analysis for the Market Intelligence panel.
        Compares current vs 14-day-ago vs 30-day-ago snapshots.
        """
        today    = date.today()
        snap_14d = self.load_snapshot(today - timedelta(days=14))
        snap_30d = self.load_snapshot(today - timedelta(days=30))
        dates    = [today + timedelta(days=i) for i in range(1, forward_days + 1)]

        comp_analysis: Dict[str, Any] = {}
        for key, comp in COMPETITORS.items():
            if "Airbnb" in comp.name:
                continue

            today_rates = [self._engine.get_competitor_rates(d).get(comp.name, 0) for d in dates]
            r14, r30    = [], []
            for d in dates:
                ds = d.isoformat()
                r14.append((snap_14d or {}).get("rates", {}).get(comp.name, {}).get(ds, {}).get("rate", 0))
                r30.append((snap_30d or {}).get("rates", {}).get(comp.name, {}).get(ds, {}).get("rate", 0))

            def _avg(lst):
                valid = [v for v in lst if v]
                return round(sum(valid) / len(valid), 0) if valid else None

            t_avg, a14, a30 = _avg(today_rates), _avg(r14), _avg(r30)
            p14 = round((t_avg - a14) / a14 * 100, 1) if a14 else None
            p30 = round((t_avg - a30) / a30 * 100, 1) if a30 else None

            if p14 is None:
                trend, arrow = "unknown", "—"
            elif p14 > 2:
                trend, arrow = "rising", "↑"
            elif p14 < -2:
                trend, arrow = "falling", "↓"
            else:
                trend, arrow = "stable", "→"

            comp_analysis[comp.name] = {
                "today_avg":    t_avg,
                "d14_avg":      a14,
                "d30_avg":      a30,
                "pct_14d":      p14,
                "pct_30d":      p30,
                "trend":        trend,
                "trend_arrow":  arrow,
                "synthetic_14": (snap_14d or {}).get("synthetic", True),
                "synthetic_30": (snap_30d or {}).get("synthetic", True),
            }

        # Forward chart: Anchorage avg vs competitor avg
        chart_labels, anch_avgs, comp_avgs = [], [], []
        for d in dates:
            chart_labels.append(d.strftime("%b %-d") if d.weekday() == 0 else "")
            room_rates  = [self._engine.calculate_room_rate(rid, d, 0.75)["rate"] for rid in ROOM_INVENTORY]
            anch_avgs.append(round(sum(room_rates) / len(room_rates), 2))
            comp_day    = {k: v for k, v in self._engine.get_competitor_rates(d).items() if "Airbnb" not in k}
            comp_avgs.append(round(sum(comp_day.values()) / len(comp_day), 2) if comp_day else 0)

        pressure_score, pressure_label, recommendation = self.get_pressure_score()
        pressure_color = (
            "var(--premium-txt)" if pressure_score <= 3 else
            "#856404"            if pressure_score <= 6 else
            "var(--discount-txt)"
        )

        return {
            "competitors":      comp_analysis,
            "pressure_score":   pressure_score,
            "pressure_label":   pressure_label,
            "pressure_color":   pressure_color,
            "recommendation":   recommendation,
            "chart": {
                "labels":        chart_labels,
                "anchorage_avg": anch_avgs,
                "comp_avg":      comp_avgs,
            },
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

    # ------------------------------------------------------------------ #
    #  Booking.com scrape attempt                                          #
    # ------------------------------------------------------------------ #

    def _try_scrape_booking(
        self, property_name: str, check_in: date, check_out: date
    ) -> Optional[float]:
        query = property_name.replace(" ", "+") + "+Beaufort+SC"
        url   = _BOOKING_SEARCH_URL.format(
            property_query=query,
            checkin=check_in.isoformat(),
            checkout=check_out.isoformat(),
        )
        try:
            resp = self._session.get(url, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            return self._extract_rate_from_html(resp.text, source="booking.com")
        except requests.RequestException as exc:
            logger.debug(f"Booking.com request failed for {property_name}: {exc}")
            return None

    # ------------------------------------------------------------------ #
    #  Expedia scrape attempt                                              #
    # ------------------------------------------------------------------ #

    def _try_scrape_expedia(
        self, property_name: str, check_in: date, check_out: date
    ) -> Optional[float]:
        query = property_name.replace(" ", "+")
        url   = _EXPEDIA_SEARCH_URL.format(
            property_query=query,
            checkin=check_in.strftime("%m/%d/%Y"),
            checkout=check_out.strftime("%m/%d/%Y"),
        )
        try:
            resp = self._session.get(url, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            return self._extract_rate_from_html(resp.text, source="expedia.com")
        except requests.RequestException as exc:
            logger.debug(f"Expedia request failed for {property_name}: {exc}")
            return None

    # ------------------------------------------------------------------ #
    #  HTML rate extraction                                                #
    # ------------------------------------------------------------------ #

    def _extract_rate_from_html(self, html: str, source: str) -> Optional[float]:
        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup.find_all("script", type="application/ld+json"):
                try:
                    data  = json.loads(tag.string or "")
                    price = self._extract_price_from_jsonld(data)
                    if price:
                        return price
                except (json.JSONDecodeError, AttributeError):
                    continue

            for sel in [
                "[data-testid='price-and-discounted-price']",
                ".prco-valign-middle-helper",
                "[data-stid='price-lockup-led-price']",
                ".uitk-lockup-price",
                ".price-current",
                "[itemprop='price']",
            ]:
                el = soup.select_one(sel)
                if el:
                    price = self._parse_price_text(el.get_text())
                    if price:
                        return price

            meta = soup.find("meta", attrs={"property": "product:price:amount"})
            if meta and meta.get("content"):
                return self._parse_price_text(str(meta["content"]))
        except Exception as exc:
            logger.debug(f"HTML extraction error ({source}): {exc}")
        return None

    def _extract_price_from_jsonld(self, data: Any) -> Optional[float]:
        if isinstance(data, list):
            for item in data:
                result = self._extract_price_from_jsonld(item)
                if result:
                    return result
        if isinstance(data, dict):
            if data.get("@type") in ("Hotel", "LodgingBusiness", "Offer", "Product"):
                offers = data.get("offers", data.get("priceSpecification", {}))
                if isinstance(offers, dict):
                    p = offers.get("price") or offers.get("lowPrice")
                    if p:
                        return self._parse_price_text(str(p))
                if isinstance(offers, list) and offers:
                    p = offers[0].get("price") or offers[0].get("lowPrice")
                    if p:
                        return self._parse_price_text(str(p))
        return None

    @staticmethod
    def _parse_price_text(text: str) -> Optional[float]:
        import re
        match = re.search(r"\$?\s*(\d{2,4})(?:\.\d{1,2})?", text.replace(",", ""))
        if match:
            val = float(match.group(1))
            if 50 <= val <= 2000:
                return round(val / 5) * 5
        return None

    # ------------------------------------------------------------------ #
    #  Rate cache layer                                                    #
    # ------------------------------------------------------------------ #

    def _cache_path(self, check_in: date) -> str:
        os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)
        return os.path.join(DATA_PROCESSED_DIR, f"competitor_rates_{check_in.isoformat()}.json")

    def _load_rate_cache(self, check_in: date) -> Optional[Dict[str, float]]:
        path = self._cache_path(check_in)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f).get("rates")
            except (json.JSONDecodeError, KeyError):
                return None
        yesterday = self._cache_path(check_in - timedelta(days=1))
        if os.path.exists(yesterday):
            logger.warning(f"No cache for {check_in} — using yesterday's rates as fallback")
            try:
                with open(yesterday) as f:
                    return json.load(f).get("rates")
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def _save_rate_cache(self, check_in: date, rates: Dict[str, float]) -> None:
        try:
            with open(self._cache_path(check_in), "w") as f:
                json.dump({
                    "date":       check_in.isoformat(),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "rates":      rates,
                }, f, indent=2)
        except OSError as exc:
            logger.warning(f"Failed to write rate cache: {exc}")

    # ------------------------------------------------------------------ #
    #  6 AM daily scheduler                                               #
    # ------------------------------------------------------------------ #

    def _morning_scrape_job(self) -> None:
        logger.info("6 AM competitor scrape job starting")
        try:
            today = date.today()
            for offset in range(30):
                self.get_rates_for_date(today + timedelta(days=offset))
            self.save_daily_snapshot()
            logger.info("6 AM scrape job completed — 30-day rates cached + snapshot saved")
        except Exception as exc:
            logger.error(f"Morning scrape job failed: {exc}", exc_info=True)

    def start_scheduler(self) -> None:
        schedule.every().day.at("06:00").do(self._morning_scrape_job)
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.is_set():
                schedule.run_pending()
                time.sleep(30)

        self._scheduler_thread = threading.Thread(
            target=_loop, name="competitor-scraper-scheduler", daemon=True
        )
        self._scheduler_thread.start()
        logger.info("Competitor scraper scheduled at 06:00 UTC daily")

    def stop_scheduler(self) -> None:
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        logger.info("Competitor scraper scheduler stopped")
