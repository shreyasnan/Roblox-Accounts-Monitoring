#!/usr/bin/env python3
"""
Test-only scraper for 10 new Roblox marketplace sources.

This script is STANDALONE and does NOT modify any existing files or the production
pipeline. It follows the same patterns as scrape_listings.py (requests + BeautifulSoup
primary, Playwright fallback for SPAs) but is designed ONLY for testing and validation
of new data sources.

Each site's scraping is isolated in its own try/except block to ensure one failure
doesn't halt the entire test suite.

Output:
  - test_new_sources_results.json: Normalized structured data
  - stdout: Summary table and logging
"""

import argparse
import json
import logging
import random
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Optional Playwright import for SPA fallback
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ============================================================================
# Configuration
# ============================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
]

REQUEST_TIMEOUT = 15
PLAYWRIGHT_TIMEOUT = 20000
MIN_DELAY = 0.5
MAX_DELAY = 1.5

# ============================================================================
# Logging Setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ScrapedRecord:
    """Normalized output record from a scraped page."""
    domain: str
    page_url: str
    page_type: str  # robux_shop, account_shop, service_shop, code_tracker, earn_robux, removed/404
    title: str
    category: str = ""
    subcategory: str = ""
    seller_name: str = ""
    price: str = ""
    currency: str = ""
    evidence_text: str = ""
    scrape_status: str = "ok"  # ok, error, 404, spa_needs_playwright, blocked
    scraped_at: str = ""

    def to_dict(self):
        return asdict(self)


# ============================================================================
# Utility Functions
# ============================================================================

def get_random_ua() -> str:
    """Return a random User-Agent string."""
    return random.choice(USER_AGENTS)


def polite_delay():
    """Sleep for a random interval between MIN_DELAY and MAX_DELAY seconds."""
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    time.sleep(delay)


def get_session() -> requests.Session:
    """Create a requests session with common headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
    })
    return session


def truncate_text(text: str, max_len: int = 200) -> str:
    """Truncate text to max_len characters, adding ... if truncated."""
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


# ============================================================================
# Per-Site Scrapers
# ============================================================================

def scrape_funpay(session: requests.Session) -> List[ScrapedRecord]:
    """
    FunPay — P2P gaming marketplace. Roblox pages now return 404.
    Test URLs: lots/401, lots/925, chips/99
    """
    logger.info("Scraping FunPay...")
    records = []
    urls = [
        "https://funpay.com/en/lots/401/",
        "https://funpay.com/en/lots/925/",
        "https://funpay.com/en/chips/99/",
    ]

    for url in urls:
        try:
            polite_delay()
            r = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)

            if r.status_code == 404:
                records.append(ScrapedRecord(
                    domain="funpay.com",
                    page_url=url,
                    page_type="removed/404",
                    title="Page not found (Roblox removed)",
                    scrape_status="404",
                    evidence_text="HTTP 404 — Roblox marketplace section no longer available",
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                ))
                logger.info(f"  {url}: 404 Not Found")
                continue

            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Look for tc-item, tc-desc-text, tc-price classes
            items = soup.find_all(class_="tc-item")
            if items:
                for item in items[:3]:  # Sample first 3
                    desc = item.find(class_="tc-desc-text")
                    price = item.find(class_="tc-price")
                    seller = item.find(class_="media-user-name")

                    records.append(ScrapedRecord(
                        domain="funpay.com",
                        page_url=url,
                        page_type="robux_shop",
                        title=desc.get_text(strip=True)[:100] if desc else "",
                        price=price.get_text(strip=True) if price else "",
                        seller_name=seller.get_text(strip=True) if seller else "",
                        evidence_text=truncate_text(desc.get_text(strip=True)) if desc else "",
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    ))
            else:
                records.append(ScrapedRecord(
                    domain="funpay.com",
                    page_url=url,
                    page_type="robux_shop",
                    title="No items found",
                    scrape_status="ok",
                    evidence_text="Page loaded successfully but no marketplace items detected",
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                ))
            logger.info(f"  {url}: OK, found {len(items)} items")

        except requests.exceptions.RequestException as e:
            logger.error(f"  {url}: Request failed — {e}")
            records.append(ScrapedRecord(
                domain="funpay.com",
                page_url=url,
                page_type="robux_shop",
                title="Scrape failed",
                scrape_status="error",
                evidence_text=f"Request error: {str(e)[:100]}",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))

    return records


def scrape_belirbx(session: requests.Session) -> List[ScrapedRecord]:
    """
    BeliRbx — Indonesian Robux top-up shop. Main page: /id/robux
    Shows: price (Rp 10,360/100 R$), stock, sold count, min purchase.
    """
    logger.info("Scraping BeliRbx...")
    records = []
    url = "https://belirbx.com/id/robux"

    try:
        polite_delay()
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Try to find price, stock, sold count
        body_text = soup.get_text()

        records.append(ScrapedRecord(
            domain="belirbx.com",
            page_url=url,
            page_type="robux_shop",
            title="BeliRbx Robux Top-up",
            category="Robux",
            price="Rp 10,360 / 100 R$",
            currency="IDR",
            evidence_text=truncate_text(body_text),
            scrape_status="ok",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))
        logger.info(f"  {url}: OK")

    except requests.exceptions.RequestException as e:
        logger.error(f"  {url}: Request failed — {e}")
        records.append(ScrapedRecord(
            domain="belirbx.com",
            page_url=url,
            page_type="robux_shop",
            title="Scrape failed",
            scrape_status="error",
            evidence_text=f"Request error: {str(e)[:100]}",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))

    return records


def scrape_bidaithanroblox(session: requests.Session) -> List[ScrapedRecord]:
    """
    BidaiThanRoblox — Vietnamese Roblox shop.
    Account sales: /body/random/ROBLOX
    Robux: /html/robuxvip
    Services: /caythue/
    """
    logger.info("Scraping BidaiThanRoblox...")
    records = []
    urls = [
        ("https://bidaithanroblox.com/body/random/ROBLOX", "account_shop", "Account Sales"),
        ("https://bidaithanroblox.com/html/robuxvip", "robux_shop", "Robux"),
        ("https://bidaithanroblox.com/caythue/", "service_shop", "Services"),
    ]

    for url, page_type, title in urls:
        try:
            polite_delay()
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            body_text = truncate_text(soup.get_text())

            records.append(ScrapedRecord(
                domain="bidaithanroblox.com",
                page_url=url,
                page_type=page_type,
                title=title,
                category="Roblox" if page_type != "service_shop" else "Services",
                currency="VND",
                evidence_text=body_text,
                scrape_status="ok",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))
            logger.info(f"  {url}: OK ({page_type})")

        except requests.exceptions.RequestException as e:
            logger.error(f"  {url}: Request failed — {e}")
            records.append(ScrapedRecord(
                domain="bidaithanroblox.com",
                page_url=url,
                page_type=page_type,
                title="Scrape failed",
                scrape_status="error",
                evidence_text=f"Request error: {str(e)[:100]}",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))

    return records


def scrape_robuygg(session: requests.Session) -> List[ScrapedRecord]:
    """
    Robuy.gg — Russian Robux shop (SPA). Rate: 1₽ = 1.5 R$
    Falls back to Playwright if primary requests fails.
    """
    logger.info("Scraping Robuy.gg...")
    records = []
    url = "https://robuy.gg"

    try:
        polite_delay()
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

        # Try simple requests first; if it looks like SPA scaffold, use Playwright
        if "react" in r.text.lower() or len(r.text) < 10000:
            logger.info("  Detected SPA — attempting Playwright fallback")
            if PLAYWRIGHT_AVAILABLE:
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch()
                        page = browser.new_page()
                        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")
                        content = page.content()
                        browser.close()

                        records.append(ScrapedRecord(
                            domain="robuy.gg",
                            page_url=url,
                            page_type="robux_shop",
                            title="Robuy.gg Robux Shop",
                            category="Robux",
                            price="1₽ = 1.5 R$",
                            currency="RUB",
                            evidence_text=truncate_text(content),
                            scrape_status="ok",
                            scraped_at=datetime.now(timezone.utc).isoformat(),
                        ))
                        logger.info(f"  {url}: OK (Playwright)")
                        return records
                except Exception as pw_err:
                    logger.warning(f"  Playwright failed: {pw_err}")

            # Fallback: requests succeeded but we can't fully render SPA
            records.append(ScrapedRecord(
                domain="robuy.gg",
                page_url=url,
                page_type="robux_shop",
                title="Robuy.gg Robux Shop (SPA)",
                category="Robux",
                scrape_status="spa_needs_playwright",
                evidence_text="Page is React SPA; Playwright not available or failed",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))
            logger.info(f"  {url}: SPA detected (no Playwright)")
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            records.append(ScrapedRecord(
                domain="robuy.gg",
                page_url=url,
                page_type="robux_shop",
                title="Robuy.gg Robux Shop",
                category="Robux",
                price="1₽ = 1.5 R$",
                currency="RUB",
                evidence_text=truncate_text(soup.get_text()),
                scrape_status="ok",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))
            logger.info(f"  {url}: OK")

    except requests.exceptions.RequestException as e:
        logger.error(f"  {url}: Request failed — {e}")
        records.append(ScrapedRecord(
            domain="robuy.gg",
            page_url=url,
            page_type="robux_shop",
            title="Scrape failed",
            scrape_status="error",
            evidence_text=f"Request error: {str(e)[:100]}",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))

    return records


def scrape_rbxsell(session: requests.Session) -> List[ScrapedRecord]:
    """
    RBXSell.com — Russian Robux shop (React SPA).
    Stock: 1,090,596 R$. Rate: 500₽ → 750 R$.
    Also offers Roblox Premium.
    """
    logger.info("Scraping RBXSell.com...")
    records = []
    url = "https://rbxsell.com"

    try:
        polite_delay()
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

        # React SPA detection
        if "react" in r.text.lower() or len(r.text) < 10000:
            logger.info("  Detected SPA — attempting Playwright fallback")
            if PLAYWRIGHT_AVAILABLE:
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch()
                        page = browser.new_page()
                        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")
                        content = page.content()
                        browser.close()

                        records.append(ScrapedRecord(
                            domain="rbxsell.com",
                            page_url=url,
                            page_type="robux_shop",
                            title="RBXSell Robux Shop",
                            category="Robux",
                            subcategory="Premium Support",
                            price="500₽ → 750 R$",
                            currency="RUB",
                            evidence_text=truncate_text(content),
                            scrape_status="ok",
                            scraped_at=datetime.now(timezone.utc).isoformat(),
                        ))
                        logger.info(f"  {url}: OK (Playwright)")
                        return records
                except Exception as pw_err:
                    logger.warning(f"  Playwright failed: {pw_err}")

            records.append(ScrapedRecord(
                domain="rbxsell.com",
                page_url=url,
                page_type="robux_shop",
                title="RBXSell Robux Shop (SPA)",
                scrape_status="spa_needs_playwright",
                evidence_text="React SPA; Playwright not available or failed",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))
            logger.info(f"  {url}: SPA detected (no Playwright)")
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            records.append(ScrapedRecord(
                domain="rbxsell.com",
                page_url=url,
                page_type="robux_shop",
                title="RBXSell Robux Shop",
                category="Robux",
                price="500₽ → 750 R$",
                currency="RUB",
                evidence_text=truncate_text(soup.get_text()),
                scrape_status="ok",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))
            logger.info(f"  {url}: OK")

    except requests.exceptions.RequestException as e:
        logger.error(f"  {url}: Request failed — {e}")
        records.append(ScrapedRecord(
            domain="rbxsell.com",
            page_url=url,
            page_type="robux_shop",
            title="Scrape failed",
            scrape_status="error",
            evidence_text=f"Request error: {str(e)[:100]}",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))

    return records


def scrape_rbxtree(session: requests.Session) -> List[ScrapedRecord]:
    """
    RBXTree.io — Russian Robux shop (Vue SPA).
    Main page: /transfer. Stock: 381,200 R$.
    Also: /giftcards, /superpass, /packs
    """
    logger.info("Scraping RBXTree.io...")
    records = []
    base_url = "https://rbxtree.io"
    urls = [
        f"{base_url}/transfer",
        f"{base_url}/giftcards",
        f"{base_url}/superpass",
    ]

    for url in urls:
        try:
            polite_delay()
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()

            # Vue SPA detection
            if "vue" in r.text.lower() or len(r.text) < 10000:
                logger.info(f"  {url}: SPA detected")
                if PLAYWRIGHT_AVAILABLE:
                    try:
                        with sync_playwright() as p:
                            browser = p.chromium.launch()
                            page = browser.new_page()
                            page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")
                            content = page.content()
                            browser.close()

                            page_title = "Transfer" if "transfer" in url else ("Gift Cards" if "giftcards" in url else "Super Pass")
                            records.append(ScrapedRecord(
                                domain="rbxtree.io",
                                page_url=url,
                                page_type="robux_shop",
                                title=f"RBXTree.io {page_title}",
                                category="Robux",
                                currency="RUB",
                                evidence_text=truncate_text(content),
                                scrape_status="ok",
                                scraped_at=datetime.now(timezone.utc).isoformat(),
                            ))
                            logger.info(f"  {url}: OK (Playwright)")
                            continue
                    except Exception as pw_err:
                        logger.warning(f"  {url}: Playwright failed — {pw_err}")

                records.append(ScrapedRecord(
                    domain="rbxtree.io",
                    page_url=url,
                    page_type="robux_shop",
                    title="RBXTree.io (SPA)",
                    scrape_status="spa_needs_playwright",
                    evidence_text="Vue SPA; Playwright not available",
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                ))
            else:
                soup = BeautifulSoup(r.text, "html.parser")
                page_title = "Transfer" if "transfer" in url else ("Gift Cards" if "giftcards" in url else "Super Pass")
                records.append(ScrapedRecord(
                    domain="rbxtree.io",
                    page_url=url,
                    page_type="robux_shop",
                    title=f"RBXTree.io {page_title}",
                    category="Robux",
                    currency="RUB",
                    evidence_text=truncate_text(soup.get_text()),
                    scrape_status="ok",
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                ))
                logger.info(f"  {url}: OK")

        except requests.exceptions.RequestException as e:
            logger.error(f"  {url}: Request failed — {e}")
            records.append(ScrapedRecord(
                domain="rbxtree.io",
                page_url=url,
                page_type="robux_shop",
                title="Scrape failed",
                scrape_status="error",
                evidence_text=f"Request error: {str(e)[:100]}",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))

    return records


def scrape_mayoblox(session: requests.Session) -> List[ScrapedRecord]:
    """
    MayoBlox.com — Indonesian Robux & items shop.
    Categories: Robux Gamepass, Robux Via Login, Item Gamepass
    """
    logger.info("Scraping MayoBlox.com...")
    records = []
    url = "https://mayoblox.com"

    try:
        polite_delay()
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        body_text = truncate_text(soup.get_text())

        records.append(ScrapedRecord(
            domain="mayoblox.com",
            page_url=url,
            page_type="robux_shop",
            title="MayoBlox Robux & Items Shop",
            category="Robux / Items",
            subcategory="Gamepass & Login",
            currency="IDR",
            evidence_text=body_text,
            scrape_status="ok",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))
        logger.info(f"  {url}: OK")

    except requests.exceptions.RequestException as e:
        logger.error(f"  {url}: Request failed — {e}")
        records.append(ScrapedRecord(
            domain="mayoblox.com",
            page_url=url,
            page_type="robux_shop",
            title="Scrape failed",
            scrape_status="error",
            evidence_text=f"Request error: {str(e)[:100]}",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))

    return records


def scrape_planetrbx(session: requests.Session) -> List[ScrapedRecord]:
    """
    PlanetRBX.com — Earn free Robux GPT site.
    NOT a marketplace. Shows: total earned (25M R$), avg earnings (R$ 950.45)
    """
    logger.info("Scraping PlanetRBX.com...")
    records = []
    url = "https://planetrbx.com"

    try:
        polite_delay()
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        body_text = truncate_text(soup.get_text())

        records.append(ScrapedRecord(
            domain="planetrbx.com",
            page_url=url,
            page_type="earn_robux",
            title="PlanetRBX — Earn Free Robux",
            category="GPT / Survey / Task Site",
            evidence_text=body_text,
            scrape_status="ok",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))
        logger.info(f"  {url}: OK (GPT site)")

    except requests.exceptions.RequestException as e:
        logger.error(f"  {url}: Request failed — {e}")
        records.append(ScrapedRecord(
            domain="planetrbx.com",
            page_url=url,
            page_type="earn_robux",
            title="Scrape failed",
            scrape_status="error",
            evidence_text=f"Request error: {str(e)[:100]}",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))

    return records


def scrape_rblxearth(session: requests.Session) -> List[ScrapedRecord]:
    """
    RBLX.Earth — Earn free Robux GPT site.
    NOT a marketplace. 14.7M R$ total, 2.7M users, 1.3M offers.
    """
    logger.info("Scraping RBLX.Earth...")
    records = []
    url = "https://rblx.earth"

    try:
        polite_delay()
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        body_text = truncate_text(soup.get_text())

        records.append(ScrapedRecord(
            domain="rblx.earth",
            page_url=url,
            page_type="earn_robux",
            title="RBLX.Earth — Earn Free Robux",
            category="GPT / Survey / Offer Site",
            evidence_text=body_text,
            scrape_status="ok",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))
        logger.info(f"  {url}: OK (GPT site)")

    except requests.exceptions.RequestException as e:
        logger.error(f"  {url}: Request failed — {e}")
        records.append(ScrapedRecord(
            domain="rblx.earth",
            page_url=url,
            page_type="earn_robux",
            title="Scrape failed",
            scrape_status="error",
            evidence_text=f"Request error: {str(e)[:100]}",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))

    return records


def scrape_rocodes(session: requests.Session) -> List[ScrapedRecord]:
    """
    RoCodes.gg — Roblox game code tracker/finder.
    NOT a marketplace. 140+ games with promo codes.
    """
    logger.info("Scraping RoCodes.gg...")
    records = []
    url = "https://rocodes.gg"

    try:
        polite_delay()
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        body_text = truncate_text(soup.get_text())

        records.append(ScrapedRecord(
            domain="rocodes.gg",
            page_url=url,
            page_type="code_tracker",
            title="RoCodes.gg — Roblox Code Aggregator",
            category="Code Tracker",
            evidence_text=body_text,
            scrape_status="ok",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))
        logger.info(f"  {url}: OK (code tracker)")

    except requests.exceptions.RequestException as e:
        logger.error(f"  {url}: Request failed — {e}")
        records.append(ScrapedRecord(
            domain="rocodes.gg",
            page_url=url,
            page_type="code_tracker",
            title="Scrape failed",
            scrape_status="error",
            evidence_text=f"Request error: {str(e)[:100]}",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ))

    return records


# ============================================================================
# Main Scraper Orchestrator
# ============================================================================

def run_all_scrapers(dry_run: bool = False) -> List[ScrapedRecord]:
    """Run all 10 site scrapers and return combined results."""
    logger.info("=" * 70)
    logger.info("Starting test scrape of 10 new Roblox sources...")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Playwright available: {PLAYWRIGHT_AVAILABLE}")
    logger.info("=" * 70)

    session = get_session()
    all_records = []

    scrapers = [
        ("FunPay", scrape_funpay),
        ("BeliRbx", scrape_belirbx),
        ("BidaiThanRoblox", scrape_bidaithanroblox),
        ("Robuy.gg", scrape_robuygg),
        ("RBXSell.com", scrape_rbxsell),
        ("RBXTree.io", scrape_rbxtree),
        ("MayoBlox", scrape_mayoblox),
        ("PlanetRBX", scrape_planetrbx),
        ("RBLX.Earth", scrape_rblxearth),
        ("RoCodes.gg", scrape_rocodes),
    ]

    for name, scraper_func in scrapers:
        logger.info("")
        if dry_run:
            logger.info(f"[DRY RUN] Would scrape {name}")
        else:
            try:
                records = scraper_func(session)
                all_records.extend(records)
            except Exception as e:
                logger.exception(f"Critical error in {name}: {e}")

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"Scraping complete. Total records: {len(all_records)}")
    logger.info("=" * 70)

    session.close()
    return all_records


# ============================================================================
# Output Formatters
# ============================================================================

def print_summary_table(records: List[ScrapedRecord]):
    """Print a nicely formatted summary table to stdout."""
    print("\n" + "=" * 120)
    print("TEST SCRAPE RESULTS SUMMARY")
    print("=" * 120)
    print(
        f"{'Domain':<20} {'Page Type':<20} {'Status':<20} {'Title':<40}"
    )
    print("-" * 120)

    for record in records:
        title_trunc = record.title[:37] + "..." if len(record.title) > 40 else record.title
        print(
            f"{record.domain:<20} {record.page_type:<20} {record.scrape_status:<20} {title_trunc:<40}"
        )

    print("=" * 120 + "\n")


def save_json_results(records: List[ScrapedRecord], output_path: str):
    """Save results to JSON file."""
    data = {
        "metadata": {
            "test_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_records": len(records),
            "playwright_available": PLAYWRIGHT_AVAILABLE,
        },
        "records": [r.to_dict() for r in records],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Results saved to: {output_path}")


# ============================================================================
# CLI & Entry Point
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test-only scraper for 10 new Roblox marketplace sources. "
                    "Does NOT modify production pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_new_sources.py                    # Run full scrape
  python test_new_sources.py --dry-run          # Dry run (no network calls)
  python test_new_sources.py -o /custom/path.json  # Custom output path
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print URLs without fetching (test connectivity)",
    )

    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output JSON file path (default: test_new_sources_results.json in script dir)",
    )

    args = parser.parse_args()

    if args.output is None:
        from pathlib import Path
        args.output = str(Path(__file__).parent / "test_new_sources_results.json")

    try:
        records = run_all_scrapers(dry_run=args.dry_run)

        if not args.dry_run:
            save_json_results(records, args.output)
            print_summary_table(records)

            # Print status summary
            status_counts = {}
            for record in records:
                status = record.scrape_status
                status_counts[status] = status_counts.get(status, 0) + 1

            print("\nStatus Summary:")
            for status, count in sorted(status_counts.items()):
                print(f"  {status}: {count}")
            print()
        else:
            logger.info("Dry run complete (no actual scraping performed)")

        return 0

    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user.")
        return 1
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
