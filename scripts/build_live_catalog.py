from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from catalog.claude_vision import tag_product_with_claude
from catalog.web_crawler import (
    fetch_og_image,
    scrape_product_page,
    serpapi_discover_products,
    serpapi_shopping_discover,
)

BRANDS = ["Aritzia", "Princess Polly", "Motel Rocks", "Reformation", "Everlane"]

# ── Vibe-driven keyword mapping ──────────────────────────────────────
# Each vibe maps to search keywords that reflect the aesthetic.
# Validated against fashion sources (Net-a-Porter, Who What Wear, etc.)
VIBE_KEYWORDS = {
    "minimal": [
        "tailored trouser", "darted pant", "silk camisole",
        "straight-leg jeans", "crewneck knit", "white shirt",
    ],
    "polished": [
        "tailored blazer", "silk blouse", "pencil skirt",
        "tailored trousers", "cashmere sweater", "trench coat",
    ],
    "feminine": [
        "wrap dress", "floral dress", "a-line skirt",
        "puff sleeve top", "lace top", "midi skirt",
    ],
    "street": [
        "cargo pants", "oversized hoodie", "graphic tee",
        "bomber jacket", "wide-leg jeans", "puffer jacket",
    ],
    "bold": [
        "statement dress", "printed blazer", "leather pants",
        "metallic top", "wide-leg jumpsuit",
    ],
    "classic": [
        "trench coat", "button-down shirt", "straight-leg jeans",
        "cashmere sweater", "camel coat",
    ],
    "casual": [
        "relaxed jeans", "cotton tee", "linen pant",
        "denim jacket", "knit top",
    ],
    "cozy": [
        "chunky knit sweater", "cardigan", "wool coat",
        "joggers", "fleece pullover",
    ],
    "dramatic": [
        "maxi dress", "cape coat", "wide-leg jumpsuit",
        "velvet blazer", "asymmetric dress",
    ],
    "night out": [
        "mini dress", "satin top", "slip dress",
        "bodycon dress", "leather pants",
    ],
    "evening": [
        "cocktail dress", "satin blouse", "embellished top",
        "midi dress", "sequin dress",
    ],
    "workwear": [
        "tailored blazer", "trouser", "button-down shirt",
        "pencil skirt", "structured blouse",
    ],
    "elevated basics": [
        "cashmere sweater", "silk tee", "quality denim",
        "tailored jogger", "wool blazer", "poplin shirt",
    ],
    "modern": [
        "asymmetric dress", "structured top", "minimalist blazer",
        "wide-leg pant", "column dress",
    ],
    "athleisure": [
        "leggings", "sports bra", "joggers",
        "zip-up jacket", "biker shorts",
    ],
    "romantic": [
        "lace dress", "floral dress", "silk skirt",
        "puff sleeve blouse", "ruffle top",
    ],
    "preppy": [
        "polo shirt", "pleated skirt", "cable knit sweater",
        "chinos", "rugby shirt", "blazer",
    ],
    "edgy": [
        "leather jacket", "distressed jeans", "coated denim",
        "fitted turtleneck", "oversized blazer",
    ],
}

# Fallback generic keywords if no vibes are provided
FALLBACK_KEYWORDS = [
    "midi dress", "mini dress", "wrap dress",
    "silk top", "knit top", "blouse women",
    "wide leg trouser", "tailored pant", "a-line skirt",
    "blazer women", "trench coat women",
    "cardigan women", "sweater women",
    "jumpsuit women",
]


def keywords_for_vibes(vibes: list[str]) -> list[str]:
    """Build a deduplicated keyword list from selected vibes."""
    if not vibes:
        return FALLBACK_KEYWORDS

    seen = set()
    keywords = []
    for vibe in vibes:
        for kw in VIBE_KEYWORDS.get(vibe, []):
            if kw not in seen:
                seen.add(kw)
                keywords.append(kw)

    return keywords or FALLBACK_KEYWORDS


def _fallback_tags_from_name(name: str) -> dict:
    lower = name.lower()
    silhouette = []
    vibes = ["casual"]
    occasion = ["weekend"]
    structure = "soft"
    season = ["all"]
    waist = "n/a"

    if any(k in lower for k in ["dress", "midi", "maxi"]):
        silhouette.append("midi")
        vibes = ["feminine"]
        occasion = ["date", "event"]
    if any(k in lower for k in ["blazer", "tailored"]):
        silhouette.append("tailored")
        structure = "structured"
        vibes = ["polished", "minimal"]
        occasion = ["work"]
    if any(k in lower for k in ["trouser", "pant", "jeans", "chino"]):
        silhouette.append("wide-leg")
        waist = "high-rise"
    if any(k in lower for k in ["crop", "cropped"]):
        silhouette.append("cropped")
    if any(k in lower for k in ["mini"]):
        silhouette.append("mini")
    if any(k in lower for k in ["maxi"]):
        silhouette = ["maxi"]
    if any(k in lower for k in ["wrap"]):
        silhouette.append("defined waist")
    if any(k in lower for k in ["a-line", "aline"]):
        silhouette.append("a-line")
    if any(k in lower for k in ["skirt"]):
        occasion = ["work", "weekend"]
    if any(k in lower for k in ["knit", "sweater", "wool"]):
        season = ["fall", "winter"]
    if any(k in lower for k in ["linen", "cotton", "silk"]):
        season = ["spring", "summer"]

    if not silhouette:
        silhouette = ["relaxed"]

    return {
        "silhouette": list(dict.fromkeys(silhouette)),
        "waist": waist,
        "structure": structure,
        "vibes": vibes,
        "occasion": occasion,
        "colors": ["black"],
        "season": season,
    }


def _build_row_for_candidate(c, use_vision: bool) -> dict | None:
    # ── Scrape product page for higher-res image + product text ──────
    product_text = ""
    image_url = c.image_url  # Shopping API thumbnail as default

    if c.url:
        try:
            page_data = scrape_product_page(c.url)
            # Prefer og:image over Shopping thumbnail (higher resolution)
            if page_data.get("og_image"):
                image_url = page_data["og_image"]

            # Build product text from scraped fields for PAE dual-extraction
            text_parts = []
            if page_data.get("description"):
                text_parts.append(page_data["description"])
            if page_data.get("material"):
                text_parts.append(f"Material: {page_data['material']}")
            if page_data.get("fit_notes"):
                text_parts.append(f"Fit: {page_data['fit_notes']}")
            product_text = " | ".join(text_parts)
        except Exception as exc:
            print(f"  page scrape failed for {c.name}: {exc}")

    # Fallback: try legacy og:image fetch if we still have no good image
    if not image_url and c.url:
        image_url = fetch_og_image(c.url)

    if not image_url:
        return None

    # ── Tag with Claude Vision (image + product text) ────────────────
    if use_vision:
        try:
            tags = tag_product_with_claude(
                c.name, c.brand, image_url,
                product_text=product_text or None,
            )
            tagged_mode = "vision"
        except Exception as exc:
            print(f"  vision failed for {c.name}: {exc}")
            tags = _fallback_tags_from_name(c.name)
            tagged_mode = "fallback"
    else:
        tags = _fallback_tags_from_name(c.name)
        tagged_mode = "fallback_no_vision"

    row = {
        "name": c.name,
        "brand": c.brand,
        "url": c.url,
        "image_url": image_url,
        "silhouette": tags.get("silhouette", []),
        "waist": tags.get("waist", "n/a"),
        "structure": tags.get("structure", "soft"),
        "vibes": tags.get("vibes", []),
        "occasion": tags.get("occasion", []),
        "colors": tags.get("colors", []),
        "season": tags.get("season", ["all"]),
        "tag_source": tagged_mode,
        "confidence": tags.get("confidence", None),
    }

    # Include Shopping API metadata when available
    if c.price:
        row["price"] = c.price
    if c.extracted_price is not None:
        row["extracted_price"] = c.extracted_price
    if c.rating is not None:
        row["rating"] = c.rating
    if c.reviews is not None:
        row["reviews"] = c.reviews

    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Build StyleLab live product catalog")
    parser.add_argument("--max-per-brand", type=int, default=8)
    parser.add_argument("--out", default="data/products_live.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-vision", action="store_true",
                        help="Skip Claude Vision tagging, use keyword fallback only")
    parser.add_argument("--vibes", nargs="*", default=None,
                        help="Vibes to drive keyword selection (e.g. --vibes minimal polished)")
    args = parser.parse_args()

    keywords = keywords_for_vibes(args.vibes)
    print(f"Selected vibes: {args.vibes or '(none — using fallback)'}")
    print(f"Search keywords ({len(keywords)}): {', '.join(keywords)}")

    products = []
    pid = 1

    for brand in BRANDS:
        print(f"\n{'='*50}")
        print(f"Discovering products for {brand}...")
        print(f"{'='*50}")

        # Primary: Google Shopping API (structured product data)
        try:
            candidates = serpapi_shopping_discover(
                brand=brand,
                keywords=keywords,
                max_results=args.max_per_brand,
            )
            discovery_method = "shopping"
        except Exception as exc:
            print(f"  Shopping API failed ({exc}), falling back to organic search...")
            candidates = serpapi_discover_products(
                brand=brand,
                keywords=keywords,
                max_results=args.max_per_brand,
            )
            discovery_method = "organic"

        print(f"Found {len(candidates)} products via {discovery_method} search")

        brand_candidates = candidates[: args.max_per_brand]
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futures = [
                ex.submit(_build_row_for_candidate, c, not args.skip_vision)
                for c in brand_candidates
            ]
            for fut in concurrent.futures.as_completed(futures):
                row = fut.result()
                if not row:
                    continue
                row["id"] = f"live_{pid:04d}"
                pid += 1
                products.append(row)
                print(f"  + [{row['tag_source']}] {row['brand']} | {row['name']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(products, indent=2))

    # Summary
    vision_count = sum(1 for p in products if p["tag_source"] == "vision")
    fallback_count = sum(1 for p in products if "fallback" in p["tag_source"])
    print(f"\n{'='*50}")
    print(f"Wrote {len(products)} products -> {out_path}")
    print(f"  Vision-tagged: {vision_count}")
    print(f"  Fallback-tagged: {fallback_count}")
    if fallback_count > 0 and not args.skip_vision:
        print(f"  ⚠ {fallback_count} products used fallback tags (check API credits)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
