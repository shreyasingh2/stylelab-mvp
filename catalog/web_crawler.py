from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _request_with_backoff(url: str, params: dict, max_retries: int = 3, timeout: int = 25):
    """HTTP GET with exponential backoff for rate limits and transient errors."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                wait = 2 ** attempt + 0.5
                logger.warning("Rate limited (429), retrying in %.1fs (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.ConnectionError as exc:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning("Connection error, retrying in %ds: %s", wait, exc)
                time.sleep(wait)
            else:
                raise
    # Final attempt after all retries exhausted
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp


@dataclass
class CrawlCandidate:
    brand: str
    name: str
    url: str
    image_url: str
    price: Optional[str] = None
    extracted_price: Optional[float] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    snippet: Optional[str] = None
    product_text: Optional[str] = None  # scraped from product page


# ── Brand config ──────────────────────────────────────────────────────
BRAND_DOMAINS = {
    "aritzia": "aritzia.com",
    "princess polly": "princesspolly.com",
    "motel rocks": "motelrocks.com",
    "reformation": "thereformation.com",
    "everlane": "everlane.com",
}

# Source names Google Shopping uses for each brand (case-insensitive match)
_BRAND_SOURCES = {
    "aritzia": ["aritzia"],
    "princess polly": ["princess polly"],
    "motel rocks": ["motel rocks", "motelrocks"],
    "reformation": ["reformation"],
    "everlane": ["everlane"],
}

# ── URL filtering (kept for organic search fallback) ──────────────────
_COLLECTION_PATTERNS = re.compile(
    r"/(collections|categories|category|sale|shop|search|blog|about|faq|help"
    r"|returns|contact|gift-cards|loyalty|rewards|size-guide|sustainability"
    r"|stores|careers|press|terms|privacy|sitemap)"
    r"(/|$|\?)",
    re.IGNORECASE,
)

_PRODUCT_URL_PATTERNS = {
    "aritzia.com": re.compile(r"/product/[^/]+/\d+", re.IGNORECASE),
    "princesspolly.com": re.compile(r"/products/[^/]+", re.IGNORECASE),
    "motelrocks.com": re.compile(r"/products/[^/]+", re.IGNORECASE),
    "thereformation.com": re.compile(r"/products/[^/]+", re.IGNORECASE),
    "everlane.com": re.compile(r"/products/[^/]+", re.IGNORECASE),
}


def _is_product_url(url: str) -> bool:
    """Return True if the URL looks like an individual product page."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    path = parsed.path

    if _COLLECTION_PATTERNS.search(path):
        return False

    for brand_domain, pattern in _PRODUCT_URL_PATTERNS.items():
        if brand_domain in domain:
            return bool(pattern.search(path))

    segments = [s for s in path.strip("/").split("/") if s]
    if len(segments) < 2:
        return False

    return True


def _clean_product_name(title: str, brand: str) -> str:
    """Strip common brand prefixes/suffixes from search result titles."""
    for sep in [" | ", " - ", " – ", " — ", " : "]:
        if sep in title:
            parts = title.split(sep)
            cleaned = [
                p.strip() for p in parts
                if brand.lower() not in p.lower()
                and not p.strip().lower().startswith("shop ")
                and not p.strip().lower().startswith("buy ")
            ]
            if cleaned:
                title = cleaned[0]
                break

    return title.strip()


def _domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def _matches_brand_source(source: str, brand: str) -> bool:
    """Check if a Google Shopping source matches our target brand."""
    source_lower = source.lower()
    brand_sources = _BRAND_SOURCES.get(brand.lower(), [brand.lower()])
    return any(bs in source_lower for bs in brand_sources)


# ── Product page text extraction ──────────────────────────────────────

def scrape_product_page(url: str) -> Dict[str, str]:
    """Visit a product page and extract useful text: description, material,
    fit notes, and the og:image. Returns a dict with keys:
    og_image, description, material, fit_notes."""
    result = {"og_image": "", "description": "", "material": "", "fit_notes": ""}

    try:
        resp = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Failed to fetch product page %s: %s", url, e)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # og:image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        result["og_image"] = og["content"].strip()

    # og:description as fallback product description
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        result["description"] = og_desc["content"].strip()

    # Look for product description in common selectors
    desc_selectors = [
        '[class*="product-description"]',
        '[class*="product-details"]',
        '[class*="pdp-description"]',
        '[class*="product-info"]',
        '[data-testid*="description"]',
        '[itemprop="description"]',
    ]
    for selector in desc_selectors:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            text = el.get_text(" ", strip=True)
            if len(text) > len(result["description"]):
                result["description"] = text[:1000]
            break

    # Look for material/composition info
    material_selectors = [
        '[class*="material"]',
        '[class*="composition"]',
        '[class*="fabric"]',
        '[class*="care-details"]',
    ]
    for selector in material_selectors:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            result["material"] = el.get_text(" ", strip=True)[:500]
            break

    # Look for fit notes
    fit_selectors = [
        '[class*="fit-note"]',
        '[class*="size-fit"]',
        '[class*="model-info"]',
        '[class*="fit-guide"]',
    ]
    for selector in fit_selectors:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            result["fit_notes"] = el.get_text(" ", strip=True)[:500]
            break

    return result


# ── Google Shopping API (primary) ─────────────────────────────────────

def serpapi_shopping_discover(
    brand: str,
    keywords: List[str],
    max_results: int = 25,
) -> List[CrawlCandidate]:
    """Discover products using SerpAPI's Google Shopping engine.
    Returns structured product data with images, prices, and descriptions."""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SERPAPI_KEY is required to crawl products.")

    rows: List[CrawlCandidate] = []
    seen_titles: set = set()

    for term in keywords:
        if len(rows) >= max_results:
            break

        query = f"{brand} {term}"
        params = {
            "engine": "google_shopping",
            "q": query,
            "num": min(max(max_results - len(rows), 1), 20),
            "api_key": api_key,
        }

        resp = _request_with_backoff("https://serpapi.com/search.json", params=params)
        data = resp.json()

        shopping_results = data.get("shopping_results", [])
        for item in shopping_results:
            title = item.get("title", "")
            source = item.get("source", "")
            thumbnail = item.get("thumbnail", "")

            if not title or not thumbnail:
                continue

            # Filter to results from the target brand
            if not _matches_brand_source(source, brand):
                continue

            # Deduplicate by normalized title
            title_key = title.lower().strip()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            clean_name = _clean_product_name(title, brand)

            # Prefer the direct retailer link over Google's redirect
            product_link = item.get("link", "") or item.get("product_link", "")

            rows.append(CrawlCandidate(
                brand=brand,
                name=clean_name,
                url=product_link,
                image_url=thumbnail,
                price=item.get("price"),
                extracted_price=item.get("extracted_price"),
                rating=item.get("rating"),
                reviews=item.get("reviews"),
                snippet=item.get("snippet", ""),
            ))

            if len(rows) >= max_results:
                break

    return rows


# ── Organic search fallback ───────────────────────────────────────────

def serpapi_discover_products(
    brand: str,
    keywords: List[str],
    max_results: int = 25,
) -> List[CrawlCandidate]:
    """Fallback: discover products via organic Google search.
    Use serpapi_shopping_discover() as the primary method."""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SERPAPI_KEY is required to crawl products.")

    brand_domain = BRAND_DOMAINS.get(brand.lower())
    if not brand_domain:
        raise ValueError(f"Unsupported brand: {brand}")

    rows: List[CrawlCandidate] = []
    seen = set()
    skipped_collection = 0

    for term in keywords:
        if len(rows) >= max_results:
            break
        query = f"site:{brand_domain} {term}"
        per_query = min(max(max_results - len(rows), 1), 10)
        params = {
            "engine": "google",
            "q": query,
            "num": per_query,
            "api_key": api_key,
        }
        resp = _request_with_backoff("https://serpapi.com/search.json", params=params)
        data = resp.json()

        organic = data.get("organic_results", [])
        for row in organic:
            url = row.get("link") or ""
            title = row.get("title") or ""
            image_url = row.get("thumbnail") or ""
            if not url or not title:
                continue
            if brand_domain not in _domain_of(url):
                continue

            if not _is_product_url(url):
                skipped_collection += 1
                continue

            key = (url, image_url)
            if key in seen:
                continue
            seen.add(key)

            clean_name = _clean_product_name(title, brand)
            rows.append(CrawlCandidate(
                brand=brand,
                name=clean_name,
                url=url,
                image_url=image_url,
            ))
            if len(rows) >= max_results:
                break

    if skipped_collection:
        logger.info("Skipped %d collection/category pages for %s", skipped_collection, brand)

    return rows


# ── Legacy helper (still used if Shopping image is too small) ─────────

def fetch_og_image(url: str) -> str:
    """Fetch og:image from a product page URL."""
    try:
        html = requests.get(url, timeout=20).text
    except Exception:
        return ""

    marker = 'property="og:image" content="'
    pos = html.find(marker)
    if pos == -1:
        marker = "property='og:image' content='"
        pos = html.find(marker)
        if pos == -1:
            return ""

    start = pos + len(marker)
    end = html.find('"' if '"' in marker else "'", start)
    if end == -1:
        return ""
    return html[start:end].strip()
