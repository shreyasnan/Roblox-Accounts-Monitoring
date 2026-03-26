#!/usr/bin/env python3
"""
Marketplace Account Listings Scraper
=====================================
Scrapes Eldorado.gg, U7Buy, and eBay for game account listings.
Outputs dashboard_data.json compatible with the monitoring dashboard.

Requirements:
    pip install playwright beautifulsoup4 lxml requests
    playwright install chromium

Usage:
    python scrape_listings.py                   # Full scrape, all games & sources
    python scrape_listings.py --games Roblox    # Single game
    python scrape_listings.py --max-pages 5     # Limit pages per source
    python scrape_listings.py --output data.json
"""

import argparse
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Try Playwright first, fall back to requests + BeautifulSoup
# ---------------------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# Shared session with connection pooling & auto-retry
_http = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=5,
    pool_maxsize=10,
    max_retries=Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]),
)
_http.mount("https://", _adapter)
_http.mount("http://", _adapter)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_OUTPUT = SCRIPT_DIR / "dashboard_data.json"
LOG_FILE = SCRIPT_DIR / "scraper.log"

ALL_GAMES = ["Roblox", "Fortnite", "Minecraft", "Steam"]

# Delays between requests (seconds) — be polite to servers
MIN_DELAY = 1.5
MAX_DELAY = 3.5

# Maximum retries per page
MAX_RETRIES = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ---------------------------------------------------------------------------
# URL configs per game per marketplace
# ---------------------------------------------------------------------------
ELDORADO_URLS = {
    "Roblox":    "https://www.eldorado.gg/roblox-accounts-for-sale/a/70-1-0",
    "Fortnite":  "https://www.eldorado.gg/fortnite-accounts-for-sale/a/16-1-0",
    "Minecraft": "https://www.eldorado.gg/minecraft-accounts/a/61-1-0",
    "Steam":     "https://www.eldorado.gg/steam-accounts/a/42-0-0",
}

U7BUY_URLS = {
    "Roblox":    "https://www.u7buy.com/roblox/roblox-accounts",
    "Fortnite":  "https://www.u7buy.com/fortnite/fortnite-accounts",
    "Minecraft": "https://www.u7buy.com/minecraft/minecraft-accounts",
    "Steam":     "https://www.u7buy.com/steam/steam-accounts",
}

U7BUY_PARAMS = {
    "Roblox":    {"spuId": "1888155406422889880", "businessId": "1820693954263351302"},
    "Fortnite":  {"spuId": "1888155406422890586", "businessId": "1820693954263351302"},
    "Minecraft": {"spuId": "1888155406422890584", "businessId": "1820693954263351302"},
    "Steam":     {"spuId": "1888155406422890226", "businessId": "1820693954263351302"},
}

EBAY_SEARCH_TERMS = {
    "Roblox":    "roblox+account",
    "Fortnite":  "fortnite+account",
    "Minecraft": "minecraft+account+java",
    "Steam":     "steam+account",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ])

log = logging.getLogger("scraper")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def polite_delay():
    """Random sleep between requests to avoid rate limiting."""
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def random_ua():
    return random.choice(USER_AGENTS)


def parse_price(text: str) -> float:
    """Extract a numeric price from text like '$12.99' or '12,99 USD'."""
    if not text:
        return 0.0
    cleaned = re.sub(r"[^\d.,]", "", text.strip())
    cleaned = cleaned.replace(",", "")
    try:
        return round(float(cleaned), 2)
    except (ValueError, TypeError):
        return 0.0


def safe_text(el, default=""):
    """Safely extract text from a BS4 element."""
    return el.get_text(strip=True) if el else default


# ============================================================================
# BROWSER MANAGER — wraps Playwright with fallback
# ============================================================================
class BrowserManager:
    """Manages a headless Playwright browser, or falls back to requests."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self.using_playwright = False

    def start(self):
        if HAS_PLAYWRIGHT:
            try:
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                self._context = self._browser.new_context(
                    user_agent=random_ua(),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )
                self._context.set_default_timeout(30_000)
                self.using_playwright = True
                log.info("Using Playwright (headless Chromium)")
            except Exception as e:
                log.warning(f"Playwright failed to start: {e}. Falling back to requests.")
                self.using_playwright = False
        else:
            log.info("Playwright not installed. Using requests + BeautifulSoup.")

    def get_page_html(self, url: str, wait_selector: str = None, scroll: bool = False) -> str:
        """Fetch a page's HTML. Uses Playwright if available, else requests."""
        for attempt in range(MAX_RETRIES):
            try:
                if self.using_playwright:
                    return self._get_pw(url, wait_selector, scroll)
                else:
                    return self._get_requests(url)
            except Exception as e:
                log.warning(f"  Attempt {attempt+1}/{MAX_RETRIES} failed for {url}: {e}")
                polite_delay()
        log.error(f"  All {MAX_RETRIES} attempts failed for {url}")
        return ""

    def _get_pw(self, url, wait_selector, scroll):
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=15_000)
                except PwTimeout:
                    log.debug(f"  Selector '{wait_selector}' not found, continuing anyway")
            if scroll:
                self._scroll_page(page)
            return page.content()
        finally:
            page.close()

    def _scroll_page(self, page):
        """Scroll down to trigger lazy-loaded content."""
        for _ in range(10):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(0.5)

    def _get_requests(self, url):
        headers = {"User-Agent": random_ua(), "Accept-Language": "en-US,en;q=0.9"}
        resp = _http.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.text

    def stop(self):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()


# ============================================================================
# ELDORADO.GG SCRAPER
# ============================================================================
class EldoradoScraper:
    """
    Scrapes Eldorado.gg listing pages.
    Eldorado renders listings server-side in a grid of offer cards.
    Pagination: appends ?page=N or uses their URL structure.
    """

    NAME = "Eldorado.gg"

    # CSS selectors (these may need updating if Eldorado changes their layout)
    LISTING_CARD = "a.offer-card, div.offer-card, [class*='OfferCard'], [class*='offer-item'], tr.offer-row"
    TITLE_SEL = "[class*='title'], [class*='name'], h3, h4, .offer-title"
    PRICE_SEL = "[class*='price'], [class*='Price'], .offer-price"
    SELLER_SEL = "[class*='seller'], [class*='Seller'], .seller-name"
    RATING_SEL = "[class*='rating'], [class*='Rating'], .seller-rating"
    NEXT_PAGE = "a[class*='next'], button[class*='next'], [aria-label='Next'], a[rel='next']"

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages  # 0 = unlimited

    def scrape_game(self, game: str) -> dict:
        base_url = ELDORADO_URLS.get(game)
        if not base_url:
            return {"total_on_site": 0, "search_url": "", "listings": []}

        log.info(f"  [{self.NAME}] Scraping {game} — {base_url}")
        all_listings = []
        total_on_site = 0
        page_num = 1

        while True:
            url = self._page_url(base_url, page_num)
            log.info(f"    Page {page_num}: {url}")

            html = self.browser.get_page_html(
                url,
                wait_selector=self.LISTING_CARD,
                scroll=True,
            )
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")

            # Try to get total count from page
            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup, game)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            # Check if there's a next page
            if self.max_pages and page_num >= self.max_pages:
                log.info(f"    Reached max pages ({self.max_pages}), stopping.")
                break

            if not self._has_next_page(soup):
                log.info(f"    No more pages available.")
                break

            page_num += 1
            polite_delay()

        return {
            "total_on_site": total_on_site or len(all_listings),
            "search_url": base_url,
            "listings": all_listings,
        }

    def _page_url(self, base_url: str, page: int) -> str:
        """Build paginated URL. Eldorado uses ?page=N query param."""
        if page == 1:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}page={page}"

    def _extract_total(self, soup: BeautifulSoup) -> int:
        """Try to find total listing count on page."""
        # Look for text like "11,544 offers" or "Showing X of Y"
        for pattern in [
            r"([\d,]+)\s*(?:offers?|listings?|results?|items?)",
            r"of\s+([\d,]+)",
        ]:
            match = re.search(pattern, soup.get_text(), re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup: BeautifulSoup, game: str) -> list:
        """Parse listing cards from page HTML."""
        listings = []

        # Try multiple selector strategies
        cards = soup.select(self.LISTING_CARD)

        # Fallback: look for any links to offer detail pages
        if not cards:
            cards = soup.select("a[href*='/oa/'], a[href*='offer'], div[data-offer]")

        for card in cards:
            try:
                listing = self._parse_card(card, game)
                if listing and listing.get("title"):
                    listings.append(listing)
            except Exception as e:
                log.debug(f"    Error parsing card: {e}")
                continue

        return listings

    def _parse_card(self, card, game: str) -> dict:
        """Extract data from a single listing card."""
        # Title
        title_el = card.select_one(self.TITLE_SEL)
        title = safe_text(title_el) or safe_text(card)
        if not title or len(title) < 3:
            return None

        # Price
        price_el = card.select_one(self.PRICE_SEL)
        price = parse_price(safe_text(price_el))

        # Seller
        seller_el = card.select_one(self.SELLER_SEL)
        seller = safe_text(seller_el)

        # Rating
        rating_el = card.select_one(self.RATING_SEL)
        rating = safe_text(rating_el)

        # URL
        url = ""
        if card.name == "a" and card.get("href"):
            href = card["href"]
            url = href if href.startswith("http") else f"https://www.eldorado.gg{href}"
        else:
            link = card.select_one("a[href]")
            if link:
                href = link["href"]
                url = href if href.startswith("http") else f"https://www.eldorado.gg{href}"

        # Delivery info
        delivery = ""
        delivery_el = card.select_one("[class*='delivery'], [class*='Delivery']")
        if delivery_el:
            delivery = safe_text(delivery_el)

        # Reviews
        reviews = ""
        reviews_el = card.select_one("[class*='review'], [class*='Review'], [class*='count']")
        if reviews_el:
            reviews = safe_text(reviews_el)

        return {
            "title": title,
            "seller": seller,
            "rating": rating,
            "reviews": reviews,
            "price": price,
            "delivery": delivery or "Instant",
            "url": url,
        }

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if pagination has a next page."""
        next_btn = soup.select_one(self.NEXT_PAGE)
        if next_btn:
            # Make sure it's not disabled
            if next_btn.get("disabled") or "disabled" in next_btn.get("class", []):
                return False
            return True
        # Also check for numbered pagination
        page_links = soup.select("a[href*='page='], button[class*='page']")
        return len(page_links) > 1


# ============================================================================
# U7BUY SCRAPER
# ============================================================================
class U7BuyScraper:
    """
    Scrapes U7Buy listing pages.
    U7Buy is a JS-heavy site; Playwright is strongly recommended.
    Falls back to attempting their internal API if requests-only.
    """

    NAME = "U7Buy"

    LISTING_CARD = "[class*='offer-item'], [class*='product-card'], [class*='OfferItem'], .offer-list-item, .goods-item"
    TITLE_SEL = "[class*='title'], [class*='name'], .goods-name, h3, h4"
    PRICE_SEL = "[class*='price'], [class*='Price'], .goods-price"
    SELLER_SEL = "[class*='seller'], [class*='shop'], .shop-name"
    RATING_SEL = "[class*='rating'], [class*='rate'], .shop-rate"
    SOLD_SEL = "[class*='sold'], [class*='sales'], .sold-num"

    # U7Buy internal API (may change — used as fallback)
    API_BASE = "https://www.u7buy.com/api/offer/list"

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def scrape_game(self, game: str) -> dict:
        base_url = U7BUY_URLS.get(game)
        if not base_url:
            return {"total_on_site": 0, "search_url": "", "listings": []}

        log.info(f"  [{self.NAME}] Scraping {game} — {base_url}")

        # Try API-based scraping first (faster, more reliable)
        listings = self._try_api_scrape(game)
        if listings:
            log.info(f"    API scrape got {len(listings)} listings")
            return {
                "total_on_site": len(listings),
                "search_url": base_url,
                "listings": listings,
            }

        # Fall back to HTML scraping
        all_listings = []
        total_on_site = 0
        page_num = 1

        while True:
            url = self._page_url(base_url, page_num)
            log.info(f"    Page {page_num}: {url}")

            html = self.browser.get_page_html(
                url,
                wait_selector=self.LISTING_CARD,
                scroll=True,
            )
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")

            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup, game)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            if self.max_pages and page_num >= self.max_pages:
                break

            if not self._has_next_page(soup):
                break

            page_num += 1
            polite_delay()

        return {
            "total_on_site": total_on_site or len(all_listings),
            "search_url": base_url,
            "listings": all_listings,
        }

    def _try_api_scrape(self, game: str) -> list:
        """Attempt to use U7Buy's internal API for faster structured data."""
        params = U7BUY_PARAMS.get(game, {})
        if not params:
            return []

        listings = []
        page = 1
        per_page = 50  # typical API page size

        while True:
            try:
                headers = {"User-Agent": random_ua(), "Accept": "application/json"}
                api_url = f"{self.API_BASE}?spuId={params['spuId']}&businessId={params['businessId']}&page={page}&pageSize={per_page}"
                resp = _http.get(api_url, headers=headers, timeout=15)

                if resp.status_code != 200:
                    log.debug(f"    API returned {resp.status_code}, falling back to HTML")
                    return []

                data = resp.json()

                # Try common API response structures
                items = (
                    data.get("data", {}).get("list", [])
                    or data.get("data", {}).get("records", [])
                    or data.get("result", {}).get("list", [])
                    or data.get("list", [])
                    or []
                )

                if not items:
                    break

                for item in items:
                    offer_id = str(item.get("offerId", item.get("id", "")))
                    title = item.get("title", item.get("name", ""))
                    price = float(item.get("price", item.get("showPrice", 0)))
                    seller = item.get("shopName", item.get("sellerName", ""))
                    rating = item.get("rate", item.get("rating", ""))
                    sold = str(item.get("soldNum", item.get("sales", "")))

                    if rating and not str(rating).endswith("%"):
                        rating = f"{rating}%"

                    url = f"https://www.u7buy.com/offer/other-detail?spuId={params['spuId']}&offerId={offer_id}&businessId={params['businessId']}&isEntrance=0"

                    listings.append({
                        "title": title,
                        "seller": seller,
                        "rating": rating,
                        "sold": sold,
                        "price": round(price, 2),
                        "delivery": "Instant",
                        "url": url,
                    })

                if len(items) < per_page:
                    break  # last page

                if self.max_pages and page >= self.max_pages:
                    break

                page += 1
                polite_delay()

            except Exception as e:
                log.debug(f"    API scrape error: {e}")
                return []

        return listings

    def _page_url(self, base_url: str, page: int) -> str:
        if page == 1:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}page={page}"

    def _extract_total(self, soup: BeautifulSoup) -> int:
        for pattern in [r"([\d,]+)\s*(?:offers?|listings?|results?|items?)", r"of\s+([\d,]+)"]:
            match = re.search(pattern, soup.get_text(), re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup: BeautifulSoup, game: str) -> list:
        listings = []
        cards = soup.select(self.LISTING_CARD)
        if not cards:
            cards = soup.select("a[href*='offer'], div[data-offer], [class*='goods']")

        for card in cards:
            try:
                listing = self._parse_card(card, game)
                if listing and listing.get("title"):
                    listings.append(listing)
            except Exception as e:
                log.debug(f"    Error parsing U7Buy card: {e}")
                continue
        return listings

    def _parse_card(self, card, game: str) -> dict:
        title_el = card.select_one(self.TITLE_SEL)
        title = safe_text(title_el) or safe_text(card)
        if not title or len(title) < 3:
            return None

        price_el = card.select_one(self.PRICE_SEL)
        price = parse_price(safe_text(price_el))

        seller_el = card.select_one(self.SELLER_SEL)
        seller = safe_text(seller_el)

        rating_el = card.select_one(self.RATING_SEL)
        rating = safe_text(rating_el)

        sold_el = card.select_one(self.SOLD_SEL)
        sold = safe_text(sold_el)

        # Build URL
        url = ""
        link = card if card.name == "a" else card.select_one("a[href]")
        if link and link.get("href"):
            href = link["href"]
            url = href if href.startswith("http") else f"https://www.u7buy.com{href}"
            # Enrich URL with required params
            if "offerId=" in url and "spuId=" not in url:
                offer_match = re.search(r"offerId=(\d+)", url)
                if offer_match:
                    p = U7BUY_PARAMS.get(game, {})
                    if p:
                        url = f"https://www.u7buy.com/offer/other-detail?spuId={p['spuId']}&offerId={offer_match.group(1)}&businessId={p['businessId']}&isEntrance=0"

        return {
            "title": title,
            "seller": seller,
            "rating": rating,
            "sold": sold,
            "price": price,
            "delivery": "Instant",
            "url": url,
        }

    def _has_next_page(self, soup):
        next_btn = soup.select_one("a[class*='next'], button[class*='next'], [aria-label='Next']")
        if next_btn and not next_btn.get("disabled"):
            return True
        return len(soup.select("a[href*='page=']")) > 1


# ============================================================================
# EBAY SCRAPER
# ============================================================================
class EbayScraper:
    """
    Scrapes eBay search results.
    eBay renders server-side, so requests + BS4 works well.
    """

    NAME = "eBay"

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def scrape_game(self, game: str) -> dict:
        search_term = EBAY_SEARCH_TERMS.get(game)
        if not search_term:
            return {"total_on_site": 0, "search_url": "", "listings": []}

        base_url = f"https://www.ebay.com/sch/i.html?_nkw={search_term}&_sop=12&LH_BIN=1"
        log.info(f"  [{self.NAME}] Scraping {game} — {base_url}")

        all_listings = []
        total_on_site = 0
        page_num = 1

        while True:
            url = self._page_url(base_url, page_num)
            log.info(f"    Page {page_num}: {url}")

            html = self.browser.get_page_html(url)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")

            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            if self.max_pages and page_num >= self.max_pages:
                break

            if not self._has_next_page(soup):
                break

            page_num += 1
            polite_delay()

        return {
            "total_on_site": total_on_site or len(all_listings),
            "search_url": f"https://www.ebay.com/sch/i.html?_nkw={search_term}",
            "listings": all_listings,
        }

    def _page_url(self, base_url: str, page: int) -> str:
        if page == 1:
            return base_url
        offset = (page - 1) * 60 + 1
        return f"{base_url}&_pgn={page}&_skc={offset}"

    def _extract_total(self, soup: BeautifulSoup) -> int:
        results_heading = soup.select_one("h1.srp-controls__count-heading, .srp-controls__count-heading")
        if results_heading:
            match = re.search(r"([\d,]+)", results_heading.get_text())
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup: BeautifulSoup) -> list:
        listings = []

        # eBay uses .s-item for search result items
        items = soup.select(".s-item")

        for item in items:
            try:
                # Skip the first "result" which is often a header/placeholder
                title_el = item.select_one(".s-item__title span, .s-item__title")
                title = safe_text(title_el)
                if not title or title.lower() in ("shop on ebay", "results matching fewer words"):
                    continue

                # Price
                price_el = item.select_one(".s-item__price")
                price_text = safe_text(price_el)
                # Handle range prices like "$5.00 to $10.00" — take the lower
                if " to " in price_text:
                    price_text = price_text.split(" to ")[0]
                price = parse_price(price_text)

                # URL
                link = item.select_one("a.s-item__link")
                url = link["href"] if link and link.get("href") else ""
                # Clean eBay tracking params
                if url and "?" in url:
                    url = url.split("?")[0]

                # Item ID from URL
                item_id = ""
                id_match = re.search(r"/itm/(\d+)", url)
                if id_match:
                    item_id = id_match.group(1)

                # Shipping
                shipping_el = item.select_one(".s-item__shipping, .s-item__freeXDays")
                shipping = safe_text(shipping_el)

                # Seller info (if visible)
                seller_el = item.select_one(".s-item__seller-info, .s-item__seller-info-text")
                seller = safe_text(seller_el)

                listings.append({
                    "title": title,
                    "price": price,
                    "itemId": item_id,
                    "url": url,
                    "shipping": shipping,
                    "seller": seller,
                })
            except Exception as e:
                log.debug(f"    Error parsing eBay item: {e}")
                continue

        return listings

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        next_btn = soup.select_one("a.pagination__next, a[aria-label='Go to next search page']")
        return next_btn is not None and not next_btn.get("disabled")


# ============================================================================
# CATEGORIZATION ENGINE (same as build_real_data.py)
# ============================================================================
def categorize_listing(title: str, platform: str) -> list:
    """Categorize a listing based on its title content."""
    title_lower = title.lower()
    categories = []

    items_keywords = [
        "robux", "limiteds", "limited", "skins", "items", "gems", "bucks", "potions",
        "pots", "candy", "blox fruit", "adopt me", "rap+", "rap ", "inventory",
        "v-bucks", "vbucks", "stacked", "og skins", "renegade", "black knight",
        "galaxy", "travis scott", "ikonik", "leviathan", "aerial assault",
        "mystery box", "korblox", "headless", "offsale", "offsales",
        "java", "bedrock", "hypixel", "cape", "optifine", "minecon",
        "cs2", "csgo", "prime", "games", "game library", "wallet",
        "vac clean", "level", "badge", "medal", "rank",
        "godhuman", "soul guitar", "draco", "gear", "fruit",
        "robux donated", "robux spent", "random roblox",
        "dlc", "edition", "r6s", "pacify", "scum", "bodycam",
        "grow a garden", "tokens", "coins",
    ]
    if any(kw in title_lower for kw in items_keywords):
        categories.append("Items / Currency")

    age_verified_keywords = [
        "age verified", "18+", "voice chat", "verified age",
        "passport", "id verified", "verification", "vc enabled",
    ]
    if any(kw in title_lower for kw in age_verified_keywords):
        categories.append("Age Verified")

    og_keywords = [
        "2006", "2007", "2008", "2009", "2010", "2011", "2012", "2013",
        "og", "old", "veteran", "3 letter", "4 letter", "4-letter",
        "namesnipe", "unique", "rare", "holy grail", "super og",
        "join date", "years old", "year old", "creation date",
        "chapter 1", "season 1", "original",
        "17-20 years", "19-21 year", "21 years", "8 year",
        "2003", "fresh", "new account",
    ]
    if any(kw in title_lower for kw in og_keywords):
        categories.append("OG / Veteran Account")

    if not categories:
        categories.append("General")

    return categories


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================
def build_dashboard_data(scraped: dict) -> dict:
    """Convert raw scraped data into dashboard-ready JSON (same format as build_real_data.py)."""
    all_listings = []
    seen_urls = set()  # deduplicate by URL
    source_stats = {}
    platform_stats = {}
    category_stats = {}
    now = datetime.now()

    for platform, sources in scraped.items():
        platform_stats[platform] = {
            "total_listings_across_sources": 0,
            "sources": {},
            "price_min": float("inf"),
            "price_max": 0,
            "price_sum": 0,
            "price_count": 0,
            "categories": {},
        }

        for source_name, source_data in sources.items():
            total = source_data.get("total_on_site", len(source_data["listings"]))
            platform_stats[platform]["total_listings_across_sources"] += total
            platform_stats[platform]["sources"][source_name] = {
                "total_on_site": total,
                "search_url": source_data["search_url"],
                "scraped_count": len(source_data["listings"]),
            }

            if source_name not in source_stats:
                source_stats[source_name] = {"total_listings": 0, "platforms": []}
            source_stats[source_name]["total_listings"] += total
            if platform not in source_stats[source_name]["platforms"]:
                source_stats[source_name]["platforms"].append(platform)

            for listing in source_data["listings"]:
                # Skip duplicates
                url = listing.get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                categories = categorize_listing(listing["title"], platform)

                enriched = {
                    "platform": platform,
                    "source": source_name,
                    "title": listing["title"],
                    "price_usd": listing.get("price", 0),
                    "url": listing.get("url", ""),
                    "seller": listing.get("seller", ""),
                    "rating": listing.get("rating", ""),
                    "delivery": listing.get("delivery", ""),
                    "sold": listing.get("sold", ""),
                    "categories": categories,
                    "scraped_at": now.isoformat(),
                }
                all_listings.append(enriched)

                price = listing.get("price", 0)
                if price > 0:
                    platform_stats[platform]["price_min"] = min(platform_stats[platform]["price_min"], price)
                    platform_stats[platform]["price_max"] = max(platform_stats[platform]["price_max"], price)
                    platform_stats[platform]["price_sum"] += price
                    platform_stats[platform]["price_count"] += 1

                for cat in categories:
                    platform_stats[platform]["categories"].setdefault(cat, 0)
                    platform_stats[platform]["categories"][cat] += 1
                    category_stats.setdefault(cat, {"count": 0, "platforms": {}})
                    category_stats[cat]["count"] += 1
                    category_stats[cat]["platforms"].setdefault(platform, 0)
                    category_stats[cat]["platforms"][platform] += 1

    # Compute averages
    for p in platform_stats:
        s = platform_stats[p]
        if s["price_count"] > 0:
            s["avg_price_usd"] = round(s["price_sum"] / s["price_count"], 2)
        else:
            s["avg_price_usd"] = 0
        if s["price_min"] == float("inf"):
            s["price_min"] = 0
        del s["price_sum"]
        del s["price_count"]

    return {
        "metadata": {
            "generated_at": now.isoformat(),
            "data_source": "Live scraping from Eldorado.gg, U7Buy, and eBay",
            "scrape_date": now.strftime("%Y-%m-%d"),
            "platforms": list(scraped.keys()),
            "sources": list(source_stats.keys()),
            "total_listings_found": sum(
                src.get("total_on_site", 0)
                for plat in scraped.values()
                for src in plat.values()
            ),
            "total_listings_scraped": len(all_listings),
            "version": "3.0.0-live",
        },
        "platform_summary": platform_stats,
        "source_summary": source_stats,
        "category_summary": category_stats,
        "listings": all_listings,
        "search_urls": {
            platform: {
                source: data["search_url"]
                for source, data in sources.items()
            }
            for platform, sources in scraped.items()
        },
    }


def git_push(output_file: Path):
    """Commit and push updated dashboard_data.json to GitHub."""
    try:
        repo_dir = SCRIPT_DIR
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Stage the updated data file
        subprocess.run(["git", "add", str(output_file)], cwd=repo_dir, check=True, capture_output=True)

        # Check if there are staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_dir, capture_output=True,
        )
        if result.returncode == 0:
            log.info("No changes to dashboard_data.json — skipping git push.")
            return

        # Commit
        msg = f"Update dashboard data — {date_str}"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=repo_dir, check=True, capture_output=True,
        )

        # Push
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=repo_dir, check=True, capture_output=True, timeout=60,
        )
        log.info(f"Pushed to GitHub: {msg}")

    except subprocess.CalledProcessError as e:
        log.error(f"Git push failed: {e.stderr.decode() if e.stderr else e}")
    except Exception as e:
        log.error(f"Git push error: {e}")


def run_scrape(games: list, max_pages: int, output_path: str, verbose: bool):
    """Main scrape orchestrator."""
    setup_logging(verbose)
    log.info("=" * 60)
    log.info(f"Scraper started at {datetime.now().isoformat()}")
    log.info(f"Games: {', '.join(games)}")
    log.info(f"Max pages per source: {'unlimited' if max_pages == 0 else max_pages}")
    log.info("=" * 60)

    browser = BrowserManager()
    browser.start()

    eldorado = EldoradoScraper(browser, max_pages)
    u7buy = U7BuyScraper(browser, max_pages)
    ebay = EbayScraper(browser, max_pages)

    scraped = {}

    for game in games:
        log.info(f"\n{'='*40}")
        log.info(f"Scraping: {game}")
        log.info(f"{'='*40}")

        scraped[game] = {}

        # Eldorado.gg
        try:
            scraped[game]["Eldorado.gg"] = eldorado.scrape_game(game)
        except Exception as e:
            log.error(f"  Eldorado.gg failed for {game}: {e}")
            scraped[game]["Eldorado.gg"] = {"total_on_site": 0, "search_url": ELDORADO_URLS.get(game, ""), "listings": []}
        polite_delay()

        # U7Buy
        try:
            scraped[game]["U7Buy"] = u7buy.scrape_game(game)
        except Exception as e:
            log.error(f"  U7Buy failed for {game}: {e}")
            scraped[game]["U7Buy"] = {"total_on_site": 0, "search_url": U7BUY_URLS.get(game, ""), "listings": []}
        polite_delay()

        # eBay
        try:
            scraped[game]["eBay"] = ebay.scrape_game(game)
        except Exception as e:
            log.error(f"  eBay failed for {game}: {e}")
            scraped[game]["eBay"] = {"total_on_site": 0, "search_url": f"https://www.ebay.com/sch/i.html?_nkw={EBAY_SEARCH_TERMS.get(game, '')}", "listings": []}
        polite_delay()

    browser.stop()

    # Build dashboard JSON
    dashboard = build_dashboard_data(scraped)

    # Save output
    output_file = Path(output_path)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)

    # Also save a timestamped backup
    backup_dir = SCRIPT_DIR / "scrape_history"
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"dashboard_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)

    # Push to GitHub so the live dashboard updates
    git_push(output_file)

    # Print summary
    log.info(f"\n{'='*60}")
    log.info("SCRAPE COMPLETE")
    log.info(f"{'='*60}")
    log.info(f"Total listings found:   {dashboard['metadata']['total_listings_found']:,}")
    log.info(f"Total listings scraped: {dashboard['metadata']['total_listings_scraped']}")
    log.info(f"Output: {output_file}")
    log.info(f"Backup: {backup_file}")
    log.info("")
    for plat, info in dashboard["platform_summary"].items():
        log.info(f"  {plat}: {info['total_listings_across_sources']:,} total | avg ${info['avg_price_usd']}")
    log.info("")
    for cat, info in dashboard["category_summary"].items():
        log.info(f"  {cat}: {info['count']} listings")

    return dashboard


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Scrape game account listings from Eldorado.gg, U7Buy, and eBay"
    )
    parser.add_argument(
        "--games", nargs="+", default=ALL_GAMES,
        choices=ALL_GAMES, help="Games to scrape (default: all)"
    )
    parser.add_argument(
        "--max-pages", type=int, default=0,
        help="Max pages per source (0 = unlimited, default: 0)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=str(DEFAULT_OUTPUT),
        help=f"Output JSON file (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()
    run_scrape(args.games, args.max_pages, args.output, args.verbose)


if __name__ == "__main__":
    main()
