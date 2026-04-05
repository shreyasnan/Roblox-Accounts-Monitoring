#!/usr/bin/env python3
"""
Test Scraper for New Roblox Account Marketplaces
=================================================
Scrapes G2G, PlayHub, and ZeusX for Roblox account listings.
Standalone test script — does NOT modify existing production files.

Requirements:
    pip install playwright beautifulsoup4 lxml requests

Usage:
    python test_new_marketplaces.py                # Full scrape
    python test_new_marketplaces.py --dry-run      # Preview without requests
    python test_new_marketplaces.py --output data.json
"""

import argparse
import json
import logging
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Try Playwright first, fall back to requests + BeautifulSoup
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
DEFAULT_OUTPUT = SCRIPT_DIR / "test_new_marketplaces_results.json"

# Delays between requests (seconds) — be polite to servers
MIN_DELAY = 0.5
MAX_DELAY = 1.5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# New marketplace URLs
MARKETPLACE_URLS = {
    "g2g": {
        "domain": "g2g.com",
        "url": "https://www.g2g.com/categories/rbl-account",
        "pages": 2,
    },
    "playhub": {
        "domain": "playhub.com",
        "url": "https://playhub.com/roblox/accounts",
        "pages": 2,
    },
    "zeusx": {
        "domain": "zeusx.com",
        "url": "https://zeusx.com/game/roblox-in-game-items-for-sale/23/accounts",
        "pages": 2,
    },
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, handlers=[
        logging.StreamHandler(sys.stdout),
    ])

log = logging.getLogger("test_scraper")


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
                    },
                )
                self.using_playwright = True
                log.info("Playwright browser started.")
            except Exception as e:
                log.warning(f"Playwright init failed ({e}), falling back to requests.")
                self._cleanup()
        else:
            log.info("Playwright not installed, using requests + BeautifulSoup.")

    def fetch(self, url: str) -> str:
        """Fetch HTML from URL using Playwright or requests."""
        if self.using_playwright:
            try:
                page = self._context.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                html = page.content()
                page.close()
                return html
            except Exception as e:
                log.warning(f"Playwright fetch failed for {url}: {e}, falling back to requests.")
                return self._fetch_requests(url)
        else:
            return self._fetch_requests(url)

    def _fetch_requests(self, url: str) -> str:
        """Fetch HTML using requests library."""
        headers = {"User-Agent": random_ua()}
        try:
            resp = _http.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            log.error(f"requests fetch failed for {url}: {e}")
            return ""

    def _cleanup(self):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def close(self):
        self._cleanup()


# ============================================================================
# SCRAPERS FOR EACH MARKETPLACE
# ============================================================================

def scrape_g2g(browser: BrowserManager, base_url: str, max_pages: int = 2) -> list:
    """Scrape G2G.com Roblox account listings."""
    results = []
    log.info(f"Scraping G2G ({base_url})...")

    for page_num in range(1, max_pages + 1):
        page_url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
        log.debug(f"  Page {page_num}: {page_url}")

        try:
            html = browser.fetch(page_url)
            if not html:
                log.warning(f"  No HTML returned for page {page_num}")
                break

            soup = BeautifulSoup(html, "lxml")
            cards = soup.find_all("div", class_="full-height column g-card-no-deco")

            if not cards:
                log.info(f"  No cards found on page {page_num}, stopping pagination.")
                break

            for card in cards:
                try:
                    # Title text
                    title_el = card.find("a", href=re.compile(r"/offer/"))
                    title = safe_text(title_el, "Unknown Title")

                    # Price
                    price_text = safe_text(card.find("span", class_="price"))
                    price = parse_price(price_text)

                    # Seller info (appears after listing)
                    seller_text = safe_text(card)
                    seller_name = extract_g2g_seller(seller_text)

                    record = {
                        "domain": "g2g.com",
                        "page_url": page_url,
                        "page_type": "roblox_accounts",
                        "title": title,
                        "category": "Roblox",
                        "subcategory": "Account",
                        "seller_name": seller_name,
                        "seller_rating": None,
                        "price_usd": price,
                        "currency": "USD",
                        "delivery_type": "Instant",
                        "evidence_text": f"Title: {title} | Price: {price_text} | Seller: {seller_name}",
                        "scrape_status": "ok",
                        "scraped_at": datetime.utcnow().isoformat() + "Z",
                    }
                    results.append(record)
                except Exception as e:
                    log.error(f"  Error parsing card on page {page_num}: {e}")
                    continue

            polite_delay()

        except Exception as e:
            log.error(f"  Error scraping page {page_num}: {e}")
            continue

    log.info(f"  G2G: scraped {len(results)} listings")
    return results


def extract_g2g_seller(text: str) -> str:
    """Extract seller name from G2G card text (e.g., 'SellerName Level 171')."""
    lines = text.split("\n")
    for line in lines:
        if "Level" in line:
            return line.strip()
    return "Unknown"


def scrape_playhub(browser: BrowserManager, base_url: str, max_pages: int = 2) -> list:
    """Scrape PlayHub.com Roblox account listings."""
    results = []
    log.info(f"Scraping PlayHub ({base_url})...")

    for page_num in range(1, max_pages + 1):
        # PlayHub likely uses page parameter or scroll-based loading
        page_url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
        log.debug(f"  Page {page_num}: {page_url}")

        try:
            html = browser.fetch(page_url)
            if not html:
                log.warning(f"  No HTML returned for page {page_num}")
                break

            soup = BeautifulSoup(html, "lxml")

            # Look for seller cards (exact selectors may vary)
            cards = soup.find_all("div", class_=re.compile(r"product|listing|card", re.I))
            if not cards:
                log.info(f"  No cards found on page {page_num}, stopping pagination.")
                break

            for card in cards:
                try:
                    # Pattern: stock_count \n seller_name \n rating(review_count) \n title
                    card_text = safe_text(card)
                    lines = [l.strip() for l in card_text.split("\n") if l.strip()]

                    if len(lines) < 3:
                        continue

                    # Infer structure from available data
                    seller_name = extract_playhub_seller(lines)
                    title = extract_playhub_title(lines)
                    rating = extract_playhub_rating(lines)
                    price = extract_playhub_price(card_text)

                    record = {
                        "domain": "playhub.com",
                        "page_url": page_url,
                        "page_type": "roblox_accounts",
                        "title": title,
                        "category": "Roblox",
                        "subcategory": "Account",
                        "seller_name": seller_name,
                        "seller_rating": rating,
                        "price_usd": price,
                        "currency": "USD",
                        "delivery_type": "Auto",
                        "evidence_text": f"Title: {title} | Seller: {seller_name} | Rating: {rating}",
                        "scrape_status": "ok",
                        "scraped_at": datetime.utcnow().isoformat() + "Z",
                    }
                    results.append(record)
                except Exception as e:
                    log.error(f"  Error parsing card on page {page_num}: {e}")
                    continue

            polite_delay()

        except Exception as e:
            log.error(f"  Error scraping page {page_num}: {e}")
            continue

    log.info(f"  PlayHub: scraped {len(results)} listings")
    return results


def extract_playhub_seller(lines: list) -> str:
    """Extract seller name from PlayHub card lines."""
    # Typically first or second line
    for line in lines[:3]:
        if line and not line.startswith("$") and not "(" in line:
            return line
    return "Unknown"


def extract_playhub_title(lines: list) -> str:
    """Extract title from PlayHub card lines."""
    # Usually longest line or contains game info
    for line in lines:
        if len(line) > 20 and not "$" in line and not "(" in line:
            return line
    return " | ".join(lines[:2]) if len(lines) > 1 else lines[0]


def extract_playhub_rating(lines: list) -> str:
    """Extract rating from PlayHub card (e.g., '5 (37)')."""
    for line in lines:
        if "(" in line and ")" in line:
            return line
    return None


def extract_playhub_price(text: str) -> float:
    """Extract price from PlayHub card text."""
    match = re.search(r"\$[\d.,]+", text)
    if match:
        return parse_price(match.group())
    return 0.0


def scrape_zeusx(browser: BrowserManager, base_url: str, max_pages: int = 2) -> list:
    """Scrape ZeusX.com Roblox account listings."""
    results = []
    log.info(f"Scraping ZeusX ({base_url})...")

    for page_num in range(1, max_pages + 1):
        page_url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
        log.debug(f"  Page {page_num}: {page_url}")

        try:
            html = browser.fetch(page_url)
            if not html:
                log.warning(f"  No HTML returned for page {page_num}")
                break

            soup = BeautifulSoup(html, "lxml")

            # Look for seller cards
            cards = soup.find_all("div", class_=re.compile(r"product|listing|card", re.I))
            if not cards:
                log.info(f"  No cards found on page {page_num}, stopping pagination.")
                break

            for card in cards:
                try:
                    card_text = safe_text(card)
                    lines = [l.strip() for l in card_text.split("\n") if l.strip()]

                    if len(lines) < 3:
                        continue

                    # Pattern: title \n price \n seller_name \n rating
                    title = extract_zeusx_title(lines)
                    seller_name = extract_zeusx_seller(lines)
                    rating = extract_zeusx_rating(lines)
                    price = extract_zeusx_price(card_text)

                    record = {
                        "domain": "zeusx.com",
                        "page_url": page_url,
                        "page_type": "roblox_accounts",
                        "title": title,
                        "category": "Roblox",
                        "subcategory": "Account",
                        "seller_name": seller_name,
                        "seller_rating": rating,
                        "price_usd": price,
                        "currency": "USD",
                        "delivery_type": "Auto",
                        "evidence_text": f"Title: {title} | Seller: {seller_name} | Rating: {rating}",
                        "scrape_status": "ok",
                        "scraped_at": datetime.utcnow().isoformat() + "Z",
                    }
                    results.append(record)
                except Exception as e:
                    log.error(f"  Error parsing card on page {page_num}: {e}")
                    continue

            polite_delay()

        except Exception as e:
            log.error(f"  Error scraping page {page_num}: {e}")
            continue

    log.info(f"  ZeusX: scraped {len(results)} listings")
    return results


def extract_zeusx_title(lines: list) -> str:
    """Extract title from ZeusX card lines."""
    for line in lines:
        if len(line) > 15 and not "$" in line and not "(" in line:
            return line
    return " | ".join(lines[:2]) if len(lines) > 1 else lines[0]


def extract_zeusx_seller(lines: list) -> str:
    """Extract seller name from ZeusX card (before rating)."""
    for i, line in enumerate(lines):
        if "(" in line and ")" in line:
            # Seller is usually before rating
            if i > 0:
                return lines[i - 1]
    return lines[-1] if lines else "Unknown"


def extract_zeusx_rating(lines: list) -> str:
    """Extract rating from ZeusX card (e.g., '5.0 (1.59K)')."""
    for line in lines:
        if "(" in line and ")" in line and ("." in line or re.search(r"\d+\.?\d*", line)):
            return line
    return None


def extract_zeusx_price(text: str) -> float:
    """Extract price from ZeusX card text."""
    match = re.search(r"\$[\d.,]+", text)
    if match:
        return parse_price(match.group())
    return 0.0


# ============================================================================
# MAIN SCRIPT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test scraper for new Roblox account marketplaces (G2G, PlayHub, ZeusX)"
    )
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help=f"Output JSON file (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--max-pages", type=int, default=2,
                        help="Max pages per marketplace (default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without making requests")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose logging")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    log.info("=" * 70)
    log.info("Test Scraper for New Roblox Account Marketplaces")
    log.info("=" * 70)

    if args.dry_run:
        log.info("DRY-RUN MODE: Preview URLs without scraping")
        for name, cfg in MARKETPLACE_URLS.items():
            log.info(f"  {name.upper()}: {cfg['url']} ({cfg['pages']} pages)")
        log.info("Run without --dry-run to scrape.")
        return

    # Initialize browser
    browser = BrowserManager(force_requests=True)  # Use requests for faster testing
    browser.start()

    all_results = []

    try:
        # Scrape each marketplace
        for name, cfg in MARKETPLACE_URLS.items():
            if name == "g2g":
                results = scrape_g2g(browser, cfg["url"], cfg["pages"])
            elif name == "playhub":
                results = scrape_playhub(browser, cfg["url"], cfg["pages"])
            elif name == "zeusx":
                results = scrape_zeusx(browser, cfg["url"], cfg["pages"])
            else:
                continue

            all_results.extend(results)

    finally:
        browser.close()

    # Save results to JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    log.info(f"Results saved to: {output_path}")

    # Print summary table
    print("\n" + "=" * 70)
    print("SCRAPE SUMMARY")
    print("=" * 70)
    print(f"Total records scraped: {len(all_results)}")
    print(f"Output file: {output_path}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 70)

    # Domain breakdown
    by_domain = {}
    for rec in all_results:
        domain = rec.get("domain", "unknown")
        by_domain[domain] = by_domain.get(domain, 0) + 1

    print("\nBy Domain:")
    for domain, count in sorted(by_domain.items()):
        print(f"  {domain:20} {count:5} listings")

    print("\nFields per record:")
    if all_results:
        for key in sorted(all_results[0].keys()):
            print(f"  - {key}")

    print()


if __name__ == "__main__":
    main()
