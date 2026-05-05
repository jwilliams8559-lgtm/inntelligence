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

Cache: data/processed/competitor_rates_YYYY-MM-DD.json
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
from typing import Any, Dict, List, Optional

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
    SEASONAL_INDEX,
    AnchoragePricingEngine,
)

logger = logging.getLogger(__name__)

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

_REQUEST_TIMEOUT = 10   # seconds
_INTER_REQUEST_DELAY = 1.5  # seconds between requests, be respectful

# Booking.com search URL template (server-rendered search page)
_BOOKING_SEARCH_URL = (
    "https://www.booking.com/searchresults.html"
    "?ss={property_query}&checkin={checkin}&checkout={checkout}"
    "&group_adults=2&no_rooms=1&lang=en-us"
)

# Expedia search URL template
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
    Scrapes or estimates nightly rates for the Beaufort SC competitor set.
    Always returns a usable rate via its three-tier fallback chain.
    """

    PROPERTY_NAMES = [c.name for c in COMPETITORS.values()]

    def __init__(self) -> None:
        self._engine = AnchoragePricingEngine()
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get_rates_for_date(self, check_in: date) -> Dict[str, float]:
        """
        Returns {competitor_name: nightly_rate} for a single check-in date.
        Checks cache first, then scrapes, then falls back to estimation.
        """
        cache = self._load_cache(check_in)
        if cache:
            logger.debug(f"Competitor rates for {check_in} served from cache")
            return cache

        logger.info(f"Fetching live competitor rates for {check_in}")
        rates: Dict[str, float] = {}

        check_out = check_in + timedelta(days=1)

        for key, comp in COMPETITORS.items():
            if key == "airbnb_avg":
                # Airbnb doesn't have a straightforward search to scrape
                rates[comp.name] = self._estimate_rate(comp, check_in)
                continue

            scraped = self._try_scrape_booking(comp.name, check_in, check_out)
            if scraped is None:
                scraped = self._try_scrape_expedia(comp.name, check_in, check_out)
            if scraped is None:
                logger.debug(f"Scrape failed for {comp.name} — using estimation fallback")
                scraped = self._estimate_rate(comp, check_in)

            rates[comp.name] = scraped
            time.sleep(_INTER_REQUEST_DELAY)

        self._save_cache(check_in, rates)
        return rates

    def get_rates_for_window(self, days: int = 30) -> Dict[str, Dict[str, float]]:
        """
        Returns {date_str: {competitor_name: rate}} for the next N days.
        Combines cached dates with fresh scrapes as needed.
        """
        logger.info(f"Building {days}-day competitor rate window")
        result: Dict[str, Dict[str, float]] = {}
        today = date.today()

        for offset in range(days):
            check_in = today + timedelta(days=offset)
            result[check_in.isoformat()] = self.get_rates_for_date(check_in)

        return result

    # ------------------------------------------------------------------ #
    #  Booking.com scrape attempt                                          #
    # ------------------------------------------------------------------ #

    def _try_scrape_booking(
        self, property_name: str, check_in: date, check_out: date
    ) -> Optional[float]:
        """
        Attempts to extract a nightly rate from Booking.com search results.
        Returns None on any failure — caller falls back to estimation.
        """
        query = property_name.replace(" ", "+") + "+Beaufort+SC"
        url = _BOOKING_SEARCH_URL.format(
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
        """
        Attempts to extract a nightly rate from Expedia search results.
        Returns None on any failure — caller falls back to estimation.
        """
        query = property_name.replace(" ", "+")
        url = _EXPEDIA_SEARCH_URL.format(
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
        """
        Tries to extract a price from raw HTML using multiple strategies:
          1. JSON-LD schema.org/Hotel or schema.org/Offer blocks
          2. Common price CSS class patterns
          3. Meta price tags

        OTA sites are heavily JS-rendered — this succeeds on server-rendered
        fragments and CDN-cached snapshots, and returns None otherwise so
        the caller can fall back to estimation.
        """
        try:
            soup = BeautifulSoup(html, "lxml")

            # Strategy 1: JSON-LD structured data
            for tag in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(tag.string or "")
                    price = self._extract_price_from_jsonld(data)
                    if price:
                        logger.debug(f"Extracted price ${price} via JSON-LD from {source}")
                        return price
                except (json.JSONDecodeError, AttributeError):
                    continue

            # Strategy 2: Common OTA price CSS patterns
            price_selectors = [
                "[data-testid='price-and-discounted-price']",
                ".prco-valign-middle-helper",  # Booking.com
                "[data-stid='price-lockup-led-price']",  # Expedia
                ".uitk-lockup-price",
                ".price-current",
                "[itemprop='price']",
            ]
            for sel in price_selectors:
                el = soup.select_one(sel)
                if el:
                    price = self._parse_price_text(el.get_text())
                    if price:
                        logger.debug(f"Extracted price ${price} via CSS selector from {source}")
                        return price

            # Strategy 3: Meta tags
            meta = soup.find("meta", attrs={"property": "product:price:amount"})
            if meta and meta.get("content"):
                price = self._parse_price_text(str(meta["content"]))
                if price:
                    return price

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
            schema_type = data.get("@type", "")
            if schema_type in ("Hotel", "LodgingBusiness", "Offer", "Product"):
                # Try offers → price
                offers = data.get("offers", data.get("priceSpecification", {}))
                if isinstance(offers, dict):
                    price = offers.get("price") or offers.get("lowPrice")
                    if price:
                        return self._parse_price_text(str(price))
                if isinstance(offers, list) and offers:
                    price = offers[0].get("price") or offers[0].get("lowPrice")
                    if price:
                        return self._parse_price_text(str(price))
        return None

    @staticmethod
    def _parse_price_text(text: str) -> Optional[float]:
        """Extract a numeric price from a text string like '$249', '249.00', '$249/night'."""
        import re
        match = re.search(r"\$?\s*(\d{2,4})(?:\.\d{1,2})?", text.replace(",", ""))
        if match:
            val = float(match.group(1))
            if 50 <= val <= 2000:  # sanity range for hotel rates
                return round(val / 5) * 5
        return None

    # ------------------------------------------------------------------ #
    #  Estimation fallback                                                 #
    # ------------------------------------------------------------------ #

    def _estimate_rate(self, comp, check_in: date) -> float:
        """
        Deterministic seasonal + event rate estimation.
        Matches the model used in anchorage_pricing.get_competitor_rates()
        so both sources are consistent.
        """
        return self._engine.get_competitor_rates(check_in)[comp.name]

    # ------------------------------------------------------------------ #
    #  Cache layer                                                         #
    # ------------------------------------------------------------------ #

    def _cache_path(self, check_in: date) -> str:
        os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)
        return os.path.join(
            DATA_PROCESSED_DIR,
            f"competitor_rates_{check_in.isoformat()}.json",
        )

    def _load_cache(self, check_in: date) -> Optional[Dict[str, float]]:
        path = self._cache_path(check_in)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                return data.get("rates")
            except (json.JSONDecodeError, KeyError):
                return None
        # Try yesterday's cache as fallback
        yesterday_path = self._cache_path(check_in - timedelta(days=1))
        if os.path.exists(yesterday_path):
            logger.warning(
                f"No cache for {check_in} — using yesterday's rates as fallback"
            )
            try:
                with open(yesterday_path) as f:
                    data = json.load(f)
                return data.get("rates")
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def _save_cache(self, check_in: date, rates: Dict[str, float]) -> None:
        path = self._cache_path(check_in)
        payload = {
            "date": check_in.isoformat(),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "rates": rates,
        }
        try:
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
            logger.debug(f"Competitor rates cached → {path}")
        except OSError as exc:
            logger.warning(f"Failed to write competitor cache: {exc}")

    # ------------------------------------------------------------------ #
    #  6 AM daily scheduler                                               #
    # ------------------------------------------------------------------ #

    def _morning_scrape_job(self) -> None:
        logger.info("6 AM competitor scrape job starting")
        try:
            today = date.today()
            for offset in range(30):
                check_in = today + timedelta(days=offset)
                self.get_rates_for_date(check_in)
            logger.info("6 AM competitor scrape job completed — 30-day window cached")
        except Exception as exc:
            logger.error(f"Morning scrape job failed: {exc}", exc_info=True)

    def start_scheduler(self) -> None:
        schedule.every().day.at("06:00").do(self._morning_scrape_job)
        self._stop_event.clear()

        def _loop() -> None:
            logger.info("Competitor scraper scheduler thread running")
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
