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
    max_retries=Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], redirect=5),
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
MIN_DELAY = 0.5
MAX_DELAY = 1.5

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

PLAYERAUCTIONS_URLS = {
    "Roblox":    "https://www.playerauctions.com/roblox-account/",
    "Fortnite":  "https://www.playerauctions.com/fortnite-account/",
    "Minecraft": "https://www.playerauctions.com/minecraft-account/",
    "Steam":     "https://www.playerauctions.com/steam-account/",
}

Z2U_URLS = {
    "Roblox":    "https://www.z2u.com/rbl/accounts-5-2941",
    "Fortnite":  "https://www.z2u.com/fortnite/accounts-5-20",
    "Minecraft": "https://www.z2u.com/minecraft/accounts-5-44",
    "Steam":     "https://www.z2u.com/steam/accounts-5-3271",
}

G2G_URLS = {
    "Roblox": "https://www.g2g.com/categories/rbl-account",
}

PLAYHUB_URLS = {
    "Roblox": "https://playhub.com/roblox/accounts",
}

ZEUSX_URLS = {
    "Roblox": "https://zeusx.com/game/roblox-in-game-items-for-sale/23/accounts",
}

EBAY_AGE_VERIFIED_SEARCH_TERMS = {
    "Roblox": "roblox+account+age+verified",
}

ELDORADO_AGE_VERIFIED_URLS = {
    "Roblox": "https://www.eldorado.gg/roblox-accounts-for-sale/a/70-1-0?search=age+verified",
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
def polite_delay(extra: float = 0):
    """Random sleep between requests to avoid rate limiting."""
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY) + extra)


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

    def __init__(self, force_requests: bool = False):
        self._pw = None
        self._browser = None
        self._context = None
        self.using_playwright = False
        self._force_requests = force_requests

    def start(self):
        if self._force_requests:
            log.info("Fast mode: using requests + BeautifulSoup (Playwright skipped).")
            return
        if HAS_PLAYWRIGHT:
            try:
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--no-sandbox",
                    ],
                )
                self._context = self._browser.new_context(
                    user_agent=random_ua(),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    java_script_enabled=True,
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                    },
                )
                # Remove webdriver flag to appear more like a real browser
                self._context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """)
                self._context.set_default_timeout(30_000)
                self.using_playwright = True
                log.info("Using Playwright (headless Chromium)")
            except Exception as e:
                log.warning(f"Playwright failed to start: {e}. Falling back to requests.")
                self.using_playwright = False
        else:
            log.info("Playwright not installed. Using requests + BeautifulSoup.")

    def get_page_html(self, url: str, wait_selector: str = None, scroll: bool = False) -> str:
        """Fetch a page's HTML. Uses Playwright if available, else requests.
        For eBay: tries requests first (server-rendered), falls back to Playwright."""
        use_requests_first = "ebay.com" in url
        for attempt in range(MAX_RETRIES):
            try:
                if use_requests_first:
                    # eBay is server-rendered; requests is faster and avoids bot detection
                    html = self._get_requests(url)
                    if html and len(html) > 5000:  # got a real page, not an error/CAPTCHA
                        return html
                    if html == "":
                        log.debug(f"  requests got CAPTCHA or empty for eBay, trying Playwright")
                    else:
                        log.debug(f"  requests got short response ({len(html) if html else 0} bytes) for eBay, trying Playwright")
                if self.using_playwright:
                    html = self._get_pw(url, wait_selector, scroll)
                    # Check Playwright result for CAPTCHA too
                    if html and ("splashui/challenge" in html or "captcha" in html.lower()[:2000]):
                        log.warning(f"  eBay CAPTCHA detected in Playwright response for {url[:80]}")
                        polite_delay(extra=3)  # longer delay before retry
                        continue
                    return html
                else:
                    return self._get_requests(url)
            except Exception as e:
                log.warning(f"  Attempt {attempt+1}/{MAX_RETRIES} failed for {url}: {e}")
                use_requests_first = False  # don't retry requests for eBay, switch to Playwright
                polite_delay()
        log.error(f"  All {MAX_RETRIES} attempts failed for {url}")
        return ""

    def _get_pw(self, url, wait_selector, scroll):
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # Check for CAPTCHA/challenge redirect
            current_url = page.url
            if "challenge" in current_url or "splashui" in current_url:
                log.warning(f"  Playwright: CAPTCHA redirect detected ({current_url[:80]})")
                return ""
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=25_000)
                except PwTimeout:
                    # Selector not found — log page state for debugging
                    title = page.title()
                    li_count = len(page.query_selector_all("li"))
                    body_text = page.inner_text("body")[:300] if page.query_selector("body") else ""
                    log.warning(f"  Selector '{wait_selector}' not found after 25s. "
                                f"Title: '{title}', <li> count: {li_count}, URL: {page.url[:80]}")
                    log.debug(f"  Page body preview: {body_text[:200]}")
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
        headers = {
            "User-Agent": random_ua(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        }
        # Add Referer header for eBay to reduce CAPTCHA triggers
        if "ebay.com" in url:
            headers["Referer"] = "https://www.ebay.com/"
            headers["Sec-Fetch-Site"] = "same-origin"
        resp = _http.get(url, headers=headers, timeout=20, allow_redirects=True)
        # Detect CAPTCHA / challenge page redirects
        if resp.url and ("challenge" in resp.url or "splashui" in resp.url):
            log.warning(f"  eBay CAPTCHA detected (redirected to {resp.url[:80]})")
            return ""
        resp.raise_for_status()
        text = resp.text
        # Secondary check: detect CAPTCHA in page content
        if "splashui/challenge" in text or "captcha" in text.lower()[:2000]:
            log.warning(f"  eBay CAPTCHA detected in page content for {url[:80]}")
            return ""
        return text

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
    LISTING_CARD = "a[href*='/oa/'], a.offer-card, div.offer-card, [class*='OfferCard'], [class*='offer-item'], eld-acc-offer-item"
    TITLE_SEL = ".offer-title, [class*='title'], [class*='name'], h3, h4"
    PRICE_SEL = "eld-offer-price, eld-offer-price strong, [class*='price'], [class*='Price'], .offer-price"
    SELLER_SEL = ".username, [class*='seller'], [class*='Seller'], .seller-name"
    RATING_SEL = "[class*='rating'], [class*='Rating'], .seller-rating"
    NEXT_PAGE = "a[class*='next'], button[class*='next'], [aria-label='Next'], a[rel='next']"

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages  # 0 = unlimited

    def scrape_game(self, game: str, base_url: str = None) -> dict:
        if base_url is None:
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

            if not self._has_next_page(soup, page_num, len(listings)):
                log.info(f"    No more pages available.")
                break

            page_num += 1
            polite_delay()

        return {
            "total_on_site": total_on_site or len(all_listings),
            "search_url": base_url,
            "listings": all_listings,
        }

    # Maximum pages to scrape from Eldorado to avoid excessive requests
    MAX_ELDORADO_PAGES = 10

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

    def _has_next_page(self, soup: BeautifulSoup, page_num: int, found_count: int) -> bool:
        """Check if there's likely a next page.
        Eldorado uses JS-rendered pagination that CSS selectors may not detect,
        so we also use heuristics: if we got a full page of results, there's
        probably more."""
        # Hard cap to avoid runaway scraping
        if page_num >= self.MAX_ELDORADO_PAGES:
            log.info(f"    Reached Eldorado page cap ({self.MAX_ELDORADO_PAGES}), stopping.")
            return False

        # CSS selector check (may work if Eldorado renders server-side)
        next_btn = soup.select_one(self.NEXT_PAGE)
        if next_btn:
            if next_btn.get("disabled") or "disabled" in next_btn.get("class", []):
                return False
            return True

        # Check for numbered pagination links
        page_links = soup.select("a[href*='page='], button[class*='page']")
        if len(page_links) > 1:
            return True

        # Heuristic: if we got 20+ listings on this page, there are likely more pages.
        # Eldorado typically shows 24-48 listings per page.
        if found_count >= 20:
            return True

        return False


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

    # Keywords that indicate a listing is NOT an actual game account
    JUNK_KEYWORDS = [
        "gift card", "giftcard", "robux card", "v-bucks card", "vbucks card",
        "toy", "figure", "figurine", "plush", "stuffed", "action figure",
        "t-shirt", "tshirt", "shirt", "hoodie", "hat", "cap", "clothing",
        "phone case", "case for", "sticker", "decal", "poster", "wall art",
        "book", "guide", "manual", "strategy guide", "handbook",
        "lego", "board game", "card game", "trading card", "pin",
        "mug", "cup", "keychain", "lanyard", "backpack", "bag",
        "mouse pad", "mousepad", "controller skin", "vinyl",
        "birthday", "party supplies", "invitation", "cake topper",
        "costume", "cosplay", "mask", "wig",
        "coloring book", "notebook", "journal", "diary",
        "blanket", "pillow", "bedding", "curtain",
        "watch", "bracelet", "necklace", "jewelry",
        "funko", "pop!", "blind bag", "mystery box toy",
        "dvd", "blu-ray", "soundtrack", "cd",
    ]

    # Keywords that indicate a listing IS likely an actual account sale
    ACCOUNT_KEYWORDS = [
        "account", "acc ", "acct", "login", "email access", "full access",
        "stacked", "og ", "join date", "creation date",
        "age verified", "age verification", "voice chat", "voice enabled", "voice verified",
        "vc enabled", "vc account", "13+", "18+", "email verified",
        "prime", "game library", "steam level", "csgo", "cs2",
        "cape", "hypixel",
    ]

    # Keywords that indicate in-game items/currency (NOT accounts)
    INGAME_ITEM_KEYWORDS = [
        # Roblox in-game items & currency
        "robux", "donation", "pls donate", "donate game",
        "blox fruit", "blox fruits", "fruit ", "dough", "leopard", "kitsune",
        "murder mystery", "mm2", "godly", "chroma",
        "adopt me", "neon ", "mega neon", "fly ride",
        "grow a garden", "seed", "seeds",
        "tower defense", "units",
        "blade ball", "bladeball", "tokens",
        "pet simulator", "huge ", "titanic ",
        "brookhaven", "royale high item", "halo ",
        "da hood", "cash ", "jailbreak",
        "in-game", "in game item", "game item",
        "virtual item", "digital item",
        # Generic in-game signals
        "sword", "weapon", "armor", "pet ", "pets ",
        "coins", "gold ", "gems ", "diamonds ",
        "boost", "gamepass", "game pass",
    ]

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def _is_relevant_listing(self, title: str) -> bool:
        """Filter out non-account listings (merch, gift cards, toys, in-game items, etc.)."""
        title_lower = title.lower()

        # Reject if it matches junk keywords (merch, toys, etc.)
        if any(kw in title_lower for kw in self.JUNK_KEYWORDS):
            return False

        # Reject if it's clearly an in-game item/currency sale, UNLESS
        # the title also contains "account" (e.g. "blox fruits stacked account")
        has_account_kw = any(kw in title_lower for kw in self.ACCOUNT_KEYWORDS)
        has_ingame_kw = any(kw in title_lower for kw in self.INGAME_ITEM_KEYWORDS)

        if has_ingame_kw and not has_account_kw:
            return False

        # Accept if it has account keywords
        if has_account_kw:
            return True

        # For ambiguous titles with neither signal, reject — conservative
        # approach means we only count things we're confident are accounts
        return False

    def scrape_game(self, game: str, search_term: str = None) -> dict:
        if search_term is None:
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

            html = self.browser.get_page_html(
                url,
                wait_selector="li.s-card, .s-item, .srp-results",
                scroll=True,
            )
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

        # Use filtered count rather than eBay's raw total, since the raw total
        # includes irrelevant results (merch, gift cards, toys, etc.)
        filtered_total = len(all_listings)
        if total_on_site and filtered_total:
            # Estimate true account count: scale the site total by the
            # ratio of relevant listings we found on the pages we scraped
            pages_scraped_raw = page_num * 60  # approximate items seen before filtering
            relevance_ratio = filtered_total / max(pages_scraped_raw, filtered_total)
            estimated_total = max(filtered_total, int(total_on_site * relevance_ratio))
        else:
            estimated_total = filtered_total

        log.info(f"    eBay {game}: {filtered_total} relevant listings scraped "
                 f"(raw site total: {total_on_site}, estimated relevant: {estimated_total})")

        return {
            "total_on_site": estimated_total,
            "search_url": f"https://www.ebay.com/sch/i.html?_nkw={search_term}",
            "listings": all_listings,
        }

    def _page_url(self, base_url: str, page: int) -> str:
        if page == 1:
            return base_url
        offset = (page - 1) * 60 + 1
        return f"{base_url}&_pgn={page}&_skc={offset}"

    def _extract_total(self, soup: BeautifulSoup) -> int:
        # New eBay: plain h1/h2 with "X results for ..."
        for heading in soup.select("h1, h2"):
            match = re.search(r"([\d,]+)\s*(?:results?|items?)", heading.get_text(), re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        # Legacy selector
        results_heading = soup.select_one("h1.srp-controls__count-heading, .srp-controls__count-heading")
        if results_heading:
            match = re.search(r"([\d,]+)", results_heading.get_text())
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup: BeautifulSoup) -> list:
        listings = []

        # New eBay (2025+): li.s-card  |  Legacy: li.s-item
        items = soup.select("li.s-card")
        if items:
            return self._parse_new_cards(items)

        # Fallback to legacy .s-item selectors
        items = soup.select(".s-item")
        for item in items:
            try:
                title_el = item.select_one(".s-item__title span, .s-item__title")
                title = safe_text(title_el)
                if not title or title.lower() in ("shop on ebay", "results matching fewer words"):
                    continue
                if not self._is_relevant_listing(title):
                    log.debug(f"    Skipping irrelevant eBay listing: {title[:50]}")
                    continue

                price_el = item.select_one(".s-item__price")
                price_text = safe_text(price_el)
                if " to " in price_text:
                    price_text = price_text.split(" to ")[0]
                price = parse_price(price_text)

                link = item.select_one("a.s-item__link")
                url = link["href"] if link and link.get("href") else ""
                if url and "?" in url:
                    url = url.split("?")[0]

                item_id = ""
                id_match = re.search(r"/itm/(\d+)", url)
                if id_match:
                    item_id = id_match.group(1)

                shipping_el = item.select_one(".s-item__shipping, .s-item__freeXDays")
                shipping = safe_text(shipping_el)

                seller_el = item.select_one(".s-item__seller-info, .s-item__seller-info-text")
                seller = safe_text(seller_el)

                listings.append({
                    "title": title, "price": price, "itemId": item_id,
                    "url": url, "shipping": shipping, "seller": seller,
                })
            except Exception as e:
                log.debug(f"    Error parsing eBay item: {e}")
                continue
        return listings

    def _parse_new_cards(self, cards) -> list:
        """Parse eBay's new (2025+) s-card layout."""
        listings = []
        for card in cards:
            try:
                # Title — use .s-card__title (link's direct text is empty)
                title_el = card.select_one(".s-card__title, a.s-card__link span")
                title = safe_text(title_el)
                # Keep link element for URL extraction
                title_link = card.select_one("a.s-card__link")
                if not title or title.lower() in ("shop on ebay", "results matching fewer words"):
                    continue
                if not self._is_relevant_listing(title):
                    log.debug(f"    Skipping irrelevant eBay listing: {title[:50]}")
                    continue

                # Price — dedicated .s-card__price element
                price_el = card.select_one(".s-card__price")
                price_text = safe_text(price_el)
                if " to " in price_text:
                    price_text = price_text.split(" to ")[0]
                price = parse_price(price_text)

                # URL
                url = ""
                if title_link and title_link.get("href"):
                    url = title_link["href"]
                    if url and "?" in url:
                        url = url.split("?")[0]

                # Item ID from URL
                item_id = ""
                id_match = re.search(r"/itm/(\d+)", url)
                if id_match:
                    item_id = id_match.group(1)

                # Shipping — look in attribute rows
                shipping = ""
                for row in card.select(".s-card__attribute-row"):
                    text = safe_text(row).lower()
                    if "delivery" in text or "shipping" in text or "free" in text:
                        shipping = safe_text(row)
                        break

                # Seller — in secondary attributes, e.g. "hpmarket 98.2% positive (3K)"
                seller = ""
                secondary = card.select_one(".su-card-container__attributes__secondary")
                if secondary:
                    for row in secondary.select(".s-card__attribute-row"):
                        text = safe_text(row)
                        if "positive" in text.lower() or "%" in text:
                            # Extract seller name (before the percentage)
                            parts = re.split(r"\s+\d", text, maxsplit=1)
                            seller = parts[0].strip() if parts else text
                            break

                listings.append({
                    "title": title, "price": price, "itemId": item_id,
                    "url": url, "shipping": shipping, "seller": seller,
                })
            except Exception as e:
                log.debug(f"    Error parsing eBay s-card: {e}")
                continue
        return listings

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        # New eBay + legacy selectors
        next_btn = soup.select_one(
            "a[aria-label*='next' i], a[aria-label*='Next'], "
            "a.pagination__next, a[aria-label='Go to next search page']"
        )
        return next_btn is not None and not next_btn.get("disabled")


# ============================================================================
# PLAYERAUCTIONS SCRAPER
# ============================================================================
class PlayerAuctionsScraper:
    """
    Scrapes PlayerAuctions.com listing pages.
    PlayerAuctions is one of the largest game account marketplaces.
    Uses Playwright for JS-heavy rendering, falls back to requests.
    """

    NAME = "PlayerAuctions"

    LISTING_CARD = ".product-card, .offer-card, [class*='ListingCard'], [class*='listing-item'], .product-list-item, tr.product-row, .pa-product"
    TITLE_SEL = ".product-name, [class*='title'], [class*='name'], h3, h4, a[class*='product']"
    PRICE_SEL = "[class*='price'], [class*='Price'], .product-price, .offer-price"
    SELLER_SEL = "[class*='seller'], [class*='Seller'], .seller-name, .shop-name"
    NEXT_PAGE = "a[class*='next'], button[class*='next'], [aria-label='Next'], a[rel='next'], .pagination a:last-child"

    MAX_PA_PAGES = 10

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def scrape_game(self, game: str) -> dict:
        base_url = PLAYERAUCTIONS_URLS.get(game)
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

            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup, game)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            effective_max = self.max_pages if self.max_pages else self.MAX_PA_PAGES
            if page_num >= effective_max:
                log.info(f"    Reached max pages ({effective_max}), stopping.")
                break

            if not self._has_next_page(soup, page_num, len(listings)):
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
        if page == 1:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}page={page}"

    def _extract_total(self, soup: BeautifulSoup) -> int:
        for pattern in [
            r"([\d,]+)\s*(?:offers?|listings?|results?|items?|accounts?)",
            r"of\s+([\d,]+)",
            r"showing.*?of\s+([\d,]+)",
        ]:
            match = re.search(pattern, soup.get_text(), re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup: BeautifulSoup, game: str) -> list:
        listings = []
        cards = soup.select(self.LISTING_CARD)
        if not cards:
            # Fallback: look for any links to offer/product pages
            cards = soup.select("a[href*='/offer/'], a[href*='roblox-account'], div[data-offer], tr[data-id]")

        for card in cards:
            try:
                listing = self._parse_card(card, game)
                if listing and listing.get("title"):
                    listings.append(listing)
            except Exception as e:
                log.debug(f"    Error parsing PlayerAuctions card: {e}")
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

        url = ""
        if card.name == "a" and card.get("href"):
            href = card["href"]
            url = href if href.startswith("http") else f"https://www.playerauctions.com{href}"
        else:
            link = card.select_one("a[href]")
            if link:
                href = link["href"]
                url = href if href.startswith("http") else f"https://www.playerauctions.com{href}"

        delivery = ""
        delivery_el = card.select_one("[class*='delivery'], [class*='Delivery'], [class*='time']")
        if delivery_el:
            delivery = safe_text(delivery_el)

        return {
            "title": title,
            "seller": seller,
            "rating": "",
            "reviews": "",
            "price": price,
            "delivery": delivery or "Varies",
            "url": url,
        }

    def _has_next_page(self, soup: BeautifulSoup, page_num: int, found_count: int) -> bool:
        if page_num >= self.MAX_PA_PAGES:
            return False
        next_btn = soup.select_one(self.NEXT_PAGE)
        if next_btn:
            if next_btn.get("disabled") or "disabled" in next_btn.get("class", []):
                return False
            return True
        page_links = soup.select("a[href*='page='], .pagination a")
        if len(page_links) > 1:
            return True
        # Heuristic: if we got many listings, there are likely more
        if found_count >= 15:
            return True
        return False


# ============================================================================
# Z2U SCRAPER
# ============================================================================
class Z2UScraper:
    """
    Scrapes Z2U.com listing pages.
    Z2U is a global gaming marketplace with significant Roblox account inventory.
    """

    NAME = "Z2U"

    LISTING_CARD = ".goods-item, .offer-item, [class*='product-card'], [class*='ProductCard'], [class*='listing-card']"
    TITLE_SEL = "[class*='title'], [class*='name'], .goods-name, h3, h4, a[class*='name']"
    PRICE_SEL = "[class*='price'], [class*='Price'], .goods-price"
    SELLER_SEL = "[class*='seller'], [class*='shop'], .shop-name, [class*='store']"
    NEXT_PAGE = "a[class*='next'], button[class*='next'], [aria-label='Next'], a.page-next, .pagination-next"

    MAX_Z2U_PAGES = 10

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def scrape_game(self, game: str) -> dict:
        base_url = Z2U_URLS.get(game)
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

            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup, game)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            effective_max = self.max_pages if self.max_pages else self.MAX_Z2U_PAGES
            if page_num >= effective_max:
                log.info(f"    Reached max pages ({effective_max}), stopping.")
                break

            if not self._has_next_page(soup, page_num, len(listings)):
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
        if page == 1:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}page={page}"

    def _extract_total(self, soup: BeautifulSoup) -> int:
        for pattern in [
            r"([\d,]+)\s*(?:offers?|listings?|results?|items?|products?)",
            r"of\s+([\d,]+)",
        ]:
            match = re.search(pattern, soup.get_text(), re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup: BeautifulSoup, game: str) -> list:
        listings = []
        cards = soup.select(self.LISTING_CARD)
        if not cards:
            cards = soup.select("a[href*='/offer/'], div[data-id], .product-list-item")

        for card in cards:
            try:
                listing = self._parse_card(card, game)
                if listing and listing.get("title"):
                    listings.append(listing)
            except Exception as e:
                log.debug(f"    Error parsing Z2U card: {e}")
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

        url = ""
        if card.name == "a" and card.get("href"):
            href = card["href"]
            url = href if href.startswith("http") else f"https://www.z2u.com{href}"
        else:
            link = card.select_one("a[href]")
            if link:
                href = link["href"]
                url = href if href.startswith("http") else f"https://www.z2u.com{href}"

        delivery = ""
        delivery_el = card.select_one("[class*='delivery'], [class*='Delivery']")
        if delivery_el:
            delivery = safe_text(delivery_el)

        return {
            "title": title,
            "seller": seller,
            "rating": "",
            "reviews": "",
            "price": price,
            "delivery": delivery or "Varies",
            "url": url,
        }

    def _has_next_page(self, soup: BeautifulSoup, page_num: int, found_count: int) -> bool:
        if page_num >= self.MAX_Z2U_PAGES:
            return False
        next_btn = soup.select_one(self.NEXT_PAGE)
        if next_btn:
            if next_btn.get("disabled") or "disabled" in next_btn.get("class", []):
                return False
            return True
        page_links = soup.select("a[href*='page='], .pagination a")
        if len(page_links) > 1:
            return True
        if found_count >= 15:
            return True
        return False


# ============================================================================
# G2G SCRAPER
# ============================================================================
class G2GScraper:
    """
    Scrapes G2G.com listing pages.
    G2G renders offer cards with seller info and pricing.
    """

    NAME = "G2G"

    LISTING_CARD = "div.full-height.column.g-card-no-deco, [class*='OfferCard'], [class*='offer-card'], div[class*='product-card']"
    TITLE_SEL = "a[href*='/offer/'], [class*='title'], h3, h4"
    PRICE_SEL = "span.price, [class*='price'], [class*='Price']"
    SELLER_SEL = "[class*='seller'], [class*='Seller'], .seller-name"
    NEXT_PAGE = "a[class*='next'], button[class*='next'], [aria-label='Next']"

    MAX_G2G_PAGES = 5

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def scrape_game(self, game: str) -> dict:
        base_url = G2G_URLS.get(game)
        if not base_url:
            return {"total_on_site": 0, "search_url": "", "listings": []}

        log.info(f"  [{self.NAME}] Scraping {game} — {base_url}")
        all_listings = []
        total_on_site = 0
        page_num = 1

        while True:
            url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
            log.info(f"    Page {page_num}: {url}")

            html = self.browser.get_page_html(url, wait_selector=self.LISTING_CARD, scroll=True)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")

            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup, game, url)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            if self.max_pages and page_num >= self.max_pages:
                break
            if page_num >= self.MAX_G2G_PAGES:
                break

            page_num += 1
            polite_delay()

        return {
            "total_on_site": total_on_site or len(all_listings),
            "search_url": base_url,
            "listings": all_listings,
        }

    def _extract_total(self, soup):
        """Try to find total listing count on G2G."""
        for el in soup.select("[class*='total'], [class*='count'], [class*='result']"):
            text = safe_text(el)
            m = re.search(r"([\d,]+)\s*(?:offer|listing|result|item)", text, re.I)
            if m:
                return int(m.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup, game, page_url):
        listings = []
        cards = soup.select(self.LISTING_CARD)
        if not cards:
            # Fallback: look for offer links
            cards = soup.find_all("a", href=re.compile(r"/offer/"))
            cards = [c.parent for c in cards if c.parent]

        for card in cards:
            try:
                title_el = card.select_one(self.TITLE_SEL) or card.find("a", href=re.compile(r"/offer/"))
                title = safe_text(title_el, "").strip()
                if not title or len(title) < 3:
                    continue

                price_el = card.select_one(self.PRICE_SEL)
                price = parse_price(safe_text(price_el))

                url = ""
                link = card.find("a", href=re.compile(r"/offer/"))
                if link and link.get("href"):
                    href = link["href"]
                    url = href if href.startswith("http") else f"https://www.g2g.com{href}"

                # Extract seller from card text
                card_text = safe_text(card)
                seller = self._extract_seller(card_text)

                listings.append({
                    "title": title,
                    "price": price,
                    "seller": seller,
                    "rating": "",
                    "delivery": "Instant",
                    "url": url,
                })
            except Exception as e:
                log.debug(f"    G2G card parse error: {e}")
                continue

        return listings

    def _extract_seller(self, text):
        """Extract seller from G2G card text (pattern: 'SellerName\\nLevel NNN')."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "Level" in line and i > 0:
                return lines[i - 1] if lines[i - 1] else line
            if re.match(r"Level\s+\d+", line) and i > 0:
                return lines[i - 1]
        return ""


# ============================================================================
# PLAYHUB SCRAPER
# ============================================================================
class PlayHubScraper:
    """
    Scrapes PlayHub.com listing pages.
    PlayHub uses product/listing cards with seller info.
    """

    NAME = "PlayHub"

    LISTING_CARD = "div[class*='product'], div[class*='listing'], div[class*='card'], div[class*='offer']"
    NEXT_PAGE = "a[class*='next'], button[class*='next']"

    MAX_PLAYHUB_PAGES = 5

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def scrape_game(self, game: str) -> dict:
        base_url = PLAYHUB_URLS.get(game)
        if not base_url:
            return {"total_on_site": 0, "search_url": "", "listings": []}

        log.info(f"  [{self.NAME}] Scraping {game} — {base_url}")
        all_listings = []
        total_on_site = 0
        page_num = 1

        while True:
            url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
            log.info(f"    Page {page_num}: {url}")

            html = self.browser.get_page_html(url, wait_selector=self.LISTING_CARD, scroll=True)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")

            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup, game, url)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            if self.max_pages and page_num >= self.max_pages:
                break
            if page_num >= self.MAX_PLAYHUB_PAGES:
                break

            page_num += 1
            polite_delay()

        return {
            "total_on_site": total_on_site or len(all_listings),
            "search_url": base_url,
            "listings": all_listings,
        }

    def _extract_total(self, soup):
        for el in soup.select("[class*='total'], [class*='count'], [class*='result']"):
            text = safe_text(el)
            m = re.search(r"([\d,]+)\s*(?:offer|listing|result|item)", text, re.I)
            if m:
                return int(m.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup, game, page_url):
        listings = []
        cards = soup.select(self.LISTING_CARD)

        for card in cards:
            try:
                card_text = safe_text(card)
                lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                if len(lines) < 3:
                    continue

                title = self._extract_title(lines)
                if not title or len(title) < 3:
                    continue

                price = self._extract_price(card_text)
                seller = self._extract_seller(lines)
                rating = self._extract_rating(lines)

                url = ""
                link = card.find("a", href=True)
                if link:
                    href = link["href"]
                    url = href if href.startswith("http") else f"https://playhub.com{href}"

                listings.append({
                    "title": title,
                    "price": price,
                    "seller": seller,
                    "rating": rating,
                    "delivery": "Auto",
                    "url": url,
                })
            except Exception as e:
                log.debug(f"    PlayHub card parse error: {e}")
                continue

        return listings

    def _extract_title(self, lines):
        for line in lines:
            if len(line) > 20 and "$" not in line and "(" not in line:
                return line
        return " | ".join(lines[:2]) if len(lines) > 1 else (lines[0] if lines else "")

    def _extract_price(self, text):
        match = re.search(r"\$[\d.,]+", text)
        return parse_price(match.group()) if match else 0.0

    def _extract_seller(self, lines):
        for line in lines[:3]:
            if line and not line.startswith("$") and "(" not in line and len(line) < 30:
                return line
        return ""

    def _extract_rating(self, lines):
        for line in lines:
            if "(" in line and ")" in line:
                return line
        return ""


# ============================================================================
# ZEUSX SCRAPER
# ============================================================================
class ZeusXScraper:
    """
    Scrapes ZeusX.com listing pages.
    ZeusX uses product cards with title, price, seller, and rating.
    """

    NAME = "ZeusX"

    LISTING_CARD = "div[class*='product'], div[class*='listing'], div[class*='card'], div[class*='offer']"
    NEXT_PAGE = "a[class*='next'], button[class*='next']"

    MAX_ZEUSX_PAGES = 5

    def __init__(self, browser: BrowserManager, max_pages: int = 0):
        self.browser = browser
        self.max_pages = max_pages

    def scrape_game(self, game: str) -> dict:
        base_url = ZEUSX_URLS.get(game)
        if not base_url:
            return {"total_on_site": 0, "search_url": "", "listings": []}

        log.info(f"  [{self.NAME}] Scraping {game} — {base_url}")
        all_listings = []
        total_on_site = 0
        page_num = 1

        while True:
            url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
            log.info(f"    Page {page_num}: {url}")

            html = self.browser.get_page_html(url, wait_selector=self.LISTING_CARD, scroll=True)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")

            if page_num == 1:
                total_on_site = self._extract_total(soup)

            listings = self._parse_listings(soup, game, url)
            if not listings:
                log.info(f"    No listings found on page {page_num}, stopping.")
                break

            all_listings.extend(listings)
            log.info(f"    Found {len(listings)} listings (total so far: {len(all_listings)})")

            if self.max_pages and page_num >= self.max_pages:
                break
            if page_num >= self.MAX_ZEUSX_PAGES:
                break

            page_num += 1
            polite_delay()

        return {
            "total_on_site": total_on_site or len(all_listings),
            "search_url": base_url,
            "listings": all_listings,
        }

    def _extract_total(self, soup):
        for el in soup.select("[class*='total'], [class*='count'], [class*='result']"):
            text = safe_text(el)
            m = re.search(r"([\d,]+)\s*(?:offer|listing|result|item)", text, re.I)
            if m:
                return int(m.group(1).replace(",", ""))
        return 0

    def _parse_listings(self, soup, game, page_url):
        listings = []
        cards = soup.select(self.LISTING_CARD)

        for card in cards:
            try:
                card_text = safe_text(card)
                lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                if len(lines) < 3:
                    continue

                title = self._extract_title(lines)
                if not title or len(title) < 3:
                    continue

                price = self._extract_price(card_text)
                seller = self._extract_seller(lines)
                rating = self._extract_rating(lines)

                url = ""
                link = card.find("a", href=True)
                if link:
                    href = link["href"]
                    url = href if href.startswith("http") else f"https://zeusx.com{href}"

                listings.append({
                    "title": title,
                    "price": price,
                    "seller": seller,
                    "rating": rating,
                    "delivery": "Auto",
                    "url": url,
                })
            except Exception as e:
                log.debug(f"    ZeusX card parse error: {e}")
                continue

        return listings

    def _extract_title(self, lines):
        for line in lines:
            if len(line) > 15 and "$" not in line and "(" not in line:
                return line
        return " | ".join(lines[:2]) if len(lines) > 1 else (lines[0] if lines else "")

    def _extract_price(self, text):
        match = re.search(r"\$[\d.,]+", text)
        return parse_price(match.group()) if match else 0.0

    def _extract_seller(self, lines):
        for i, line in enumerate(lines):
            if "(" in line and ")" in line and i > 0:
                return lines[i - 1]
        return ""

    def _extract_rating(self, lines):
        for line in lines:
            if "(" in line and ")" in line and re.search(r"\d+\.?\d*", line):
                return line
        return ""


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
        # explicit age/id verification
        "age verified", "age verification", "verified age", "age gate", "age check",
        "id verified", "id verification", "gov id", "government id", "passport verified",
        # voice chat (requires age verification on Roblox)
        "voice chat", "voice enabled", "voice verified", "vc enabled", "vc account",
        "with vc", "has vc",
        # age signals common in listing titles
        "18+", "18 years", "over 18", "13+", "over 13",
        # other account-specific verification signals
        "phone verified", "adult verified",
    ]
    age_verified_disqualifiers = [
        "email verification", "payment verification", "verification service",
        "passport to",  # in-game item/quest reference, not an age-verified account
    ]
    if (any(kw in title_lower for kw in age_verified_keywords)
            and not any(dq in title_lower for dq in age_verified_disqualifiers)):
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
            total_on_site = source_data.get("total_on_site", len(source_data["listings"]))
            scraped_count = len(source_data["listings"])
            platform_stats[platform]["total_listings_across_sources"] += scraped_count
            platform_stats[platform]["sources"][source_name] = {
                "total_on_site": total_on_site,
                "scraped_count": scraped_count,
                "search_url": source_data["search_url"],
            }

            if source_name not in source_stats:
                source_stats[source_name] = {"total_listings": 0, "total_on_site": 0, "platforms": []}
            source_stats[source_name]["total_listings"] += scraped_count
            source_stats[source_name]["total_on_site"] += total_on_site
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

    total_on_site_all = sum(
        src.get("total_on_site", 0)
        for plat in scraped.values()
        for src in plat.values()
    )

    return {
        "metadata": {
            "generated_at": now.isoformat(),
            "data_source": "Live scraping from Eldorado.gg, U7Buy, PlayerAuctions, Z2U, eBay, G2G, PlayHub, ZeusX",
            "scrape_date": now.strftime("%Y-%m-%d"),
            "platforms": list(scraped.keys()),
            "sources": list(source_stats.keys()),
            "total_listings_scraped": len(all_listings),
            "total_on_site": total_on_site_all,
            "version": "3.1.0-live",
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


def _compute_proportional_pages(total_budget: int, output_path: str) -> dict:
    """Compute per-source page budgets proportional to marketplace size.

    Uses total_on_site counts from the *previous* scrape run stored in
    ``output_path`` (dashboard_data.json).  If no prior data exists, returns
    an empty dict so the caller can fall back to a flat default.

    Returns a dict like ``{"Eldorado.gg": 12, "eBay": 1, ...}`` where values
    are the number of pages to scrape for that source (summed across all
    platforms).  Every source gets at least 1 page.
    """
    prior = Path(output_path)
    if not prior.exists():
        return {}

    try:
        with open(prior, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
    except Exception:
        return {}

    # Aggregate total_on_site per source across all platforms
    source_totals: dict[str, int] = {}
    for _platform, pinfo in prev_data.get("platform_summary", {}).items():
        for src_name, sinfo in pinfo.get("sources", {}).items():
            source_totals[src_name] = source_totals.get(src_name, 0) + sinfo.get("total_on_site", 0)

    if not source_totals:
        return {}

    grand_total = sum(source_totals.values()) or 1
    allocations: dict[str, int] = {}
    for src, total in source_totals.items():
        # Proportional share, minimum 1 page
        share = max(1, round(total / grand_total * total_budget))
        allocations[src] = share

    return allocations


def run_scrape(games: list, max_pages: int, output_path: str, verbose: bool, fast: bool = False):
    """Main scrape orchestrator."""
    setup_logging(verbose)
    log.info("=" * 60)
    log.info(f"Scraper started at {datetime.now().isoformat()}")
    log.info(f"Games: {', '.join(games)}")
    log.info(f"Fast mode: {'ON' if fast else 'OFF'}")
    log.info("=" * 60)

    # --- Proportional page allocation ---
    # total_budget = max_pages * number_of_sources (legacy flat behaviour)
    # We redistribute that total so larger marketplaces get more pages.
    ALL_SOURCES = ["Eldorado.gg", "U7Buy", "eBay", "PlayerAuctions", "Z2U", "G2G", "PlayHub", "ZeusX"]
    total_budget = max_pages * len(ALL_SOURCES)  # e.g. 3 * 8 = 24 pages total
    proportional = _compute_proportional_pages(total_budget, output_path)

    if proportional:
        log.info("Using proportional page allocation (based on prior marketplace sizes):")
        for src, pages in sorted(proportional.items(), key=lambda x: -x[1]):
            log.info(f"  {src}: {pages} pages")
    else:
        log.info(f"No prior data found — using flat {max_pages} pages per source")

    def pages_for(source_name: str) -> int:
        return proportional.get(source_name, max_pages)

    browser = BrowserManager(force_requests=fast)
    browser.start()

    eldorado = EldoradoScraper(browser, pages_for("Eldorado.gg"))
    u7buy = U7BuyScraper(browser, pages_for("U7Buy"))
    ebay = EbayScraper(browser, pages_for("eBay"))
    playerauctions = PlayerAuctionsScraper(browser, pages_for("PlayerAuctions"))
    z2u = Z2UScraper(browser, pages_for("Z2U"))
    g2g = G2GScraper(browser, pages_for("G2G"))
    playhub = PlayHubScraper(browser, pages_for("PlayHub"))
    zeusx = ZeusXScraper(browser, pages_for("ZeusX"))

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

        # Eldorado.gg supplementary age-verified search (Roblox only, 2 targeted pages)
        if game in ELDORADO_AGE_VERIFIED_URLS:
            try:
                eldorado_av = EldoradoScraper(browser, max_pages=2)
                av_result = eldorado_av.scrape_game(game, base_url=ELDORADO_AGE_VERIFIED_URLS[game])
                seen_urls = {l["url"] for l in scraped[game]["Eldorado.gg"]["listings"]}
                new_listings = [l for l in av_result["listings"] if l["url"] not in seen_urls]
                scraped[game]["Eldorado.gg"]["listings"].extend(new_listings)
                log.info(f"  [Eldorado age-verified] Added {len(new_listings)} new listings for {game}")
            except Exception as e:
                log.warning(f"  Eldorado age-verified supplementary search failed for {game}: {e}")
            polite_delay()

        # U7Buy
        try:
            scraped[game]["U7Buy"] = u7buy.scrape_game(game)
        except Exception as e:
            log.error(f"  U7Buy failed for {game}: {e}")
            scraped[game]["U7Buy"] = {"total_on_site": 0, "search_url": U7BUY_URLS.get(game, ""), "listings": []}
        polite_delay()

        # PlayerAuctions
        try:
            scraped[game]["PlayerAuctions"] = playerauctions.scrape_game(game)
        except Exception as e:
            log.error(f"  PlayerAuctions failed for {game}: {e}")
            scraped[game]["PlayerAuctions"] = {"total_on_site": 0, "search_url": PLAYERAUCTIONS_URLS.get(game, ""), "listings": []}
        polite_delay()

        # Z2U
        try:
            scraped[game]["Z2U"] = z2u.scrape_game(game)
        except Exception as e:
            log.error(f"  Z2U failed for {game}: {e}")
            scraped[game]["Z2U"] = {"total_on_site": 0, "search_url": Z2U_URLS.get(game, ""), "listings": []}
        polite_delay()

        # eBay — use longer delay between game searches to reduce CAPTCHA triggers
        try:
            scraped[game]["eBay"] = ebay.scrape_game(game)
        except Exception as e:
            log.error(f"  eBay failed for {game}: {e}")
            scraped[game]["eBay"] = {"total_on_site": 0, "search_url": f"https://www.ebay.com/sch/i.html?_nkw={EBAY_SEARCH_TERMS.get(game, '')}", "listings": []}
        polite_delay(extra=1)  # extra delay for eBay to avoid CAPTCHA

        # eBay supplementary age-verified search (Roblox only, 1 targeted page)
        if game in EBAY_AGE_VERIFIED_SEARCH_TERMS:
            try:
                ebay_av = EbayScraper(browser, max_pages=1)
                av_result = ebay_av.scrape_game(game, search_term=EBAY_AGE_VERIFIED_SEARCH_TERMS[game])
                seen_urls = {l["url"] for l in scraped[game]["eBay"]["listings"]}
                new_listings = [l for l in av_result["listings"] if l["url"] not in seen_urls]
                scraped[game]["eBay"]["listings"].extend(new_listings)
                log.info(f"  [eBay age-verified] Added {len(new_listings)} new listings for {game}")
            except Exception as e:
                log.warning(f"  eBay age-verified supplementary search failed for {game}: {e}")
            polite_delay(extra=1)

        # G2G (Roblox only for now)
        if game in G2G_URLS:
            try:
                scraped[game]["G2G"] = g2g.scrape_game(game)
            except Exception as e:
                log.error(f"  G2G failed for {game}: {e}")
                scraped[game]["G2G"] = {"total_on_site": 0, "search_url": G2G_URLS.get(game, ""), "listings": []}
            polite_delay()

        # PlayHub (Roblox only for now)
        if game in PLAYHUB_URLS:
            try:
                scraped[game]["PlayHub"] = playhub.scrape_game(game)
            except Exception as e:
                log.error(f"  PlayHub failed for {game}: {e}")
                scraped[game]["PlayHub"] = {"total_on_site": 0, "search_url": PLAYHUB_URLS.get(game, ""), "listings": []}
            polite_delay()

        # ZeusX (Roblox only for now)
        if game in ZEUSX_URLS:
            try:
                scraped[game]["ZeusX"] = zeusx.scrape_game(game)
            except Exception as e:
                log.error(f"  ZeusX failed for {game}: {e}")
                scraped[game]["ZeusX"] = {"total_on_site": 0, "search_url": ZEUSX_URLS.get(game, ""), "listings": []}
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

    # Save to SQLite database for historical analysis
    try:
        from db import get_connection, init_db, insert_scrape_run
        db_conn = get_connection()
        init_db(db_conn)
        run_id = insert_scrape_run(db_conn, dashboard)
        db_conn.close()
        log.info(f"Saved to SQLite database (run_id={run_id})")
    except Exception as e:
        log.warning(f"Failed to save to SQLite: {e}")

    # Push to GitHub so the live dashboard updates
    git_push(output_file)

    # Print summary
    log.info(f"\n{'='*60}")
    log.info("SCRAPE COMPLETE")
    log.info(f"{'='*60}")
    log.info(f"Total listings scraped: {dashboard['metadata']['total_listings_scraped']}")
    log.info(f"Total on-site (reported by marketplaces): {dashboard['metadata']['total_on_site']:,}")
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
        "--max-pages", type=int, default=3,
        help="Max pages per source (0 = unlimited, default: 3)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=str(DEFAULT_OUTPUT),
        help=f"Output JSON file (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--fast", action="store_true",
        help="Fast mode: skip Playwright, use requests only (much faster)"
    )

    args = parser.parse_args()
    run_scrape(args.games, args.max_pages, args.output, args.verbose, args.fast)


if __name__ == "__main__":
    main()
