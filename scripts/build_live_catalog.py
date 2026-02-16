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
        "tailored trouser", "silk camisole", "column dress",
        "straight-leg jeans", "crewneck knit", "white button-down shirt",
    ],
    "polished": [
        "tailored blazer", "silk blouse", "pencil skirt",
        "tailored trousers", "midi dress", "cashmere sweater",
    ],
    "feminine": [
        "wrap dress", "floral midi dress", "a-line skirt",
        "puff sleeve top", "lace top", "midi skirt",
    ],
    "street": [
        "cargo pants", "oversized hoodie", "graphic tee",
        "bomber jacket", "wide-leg jeans", "mini skirt",
    ],
    "bold": [
        "statement dress", "printed blazer", "leather pants",
        "metallic top", "wide-leg jumpsuit", "sequin mini dress",
    ],
    "classic": [
        "button-down shirt", "straight-leg jeans", "midi dress",
        "cashmere sweater", "a-line skirt", "tailored trouser",
    ],
    "casual": [
        "relaxed jeans", "cotton tee", "linen pant",
        "denim jacket", "knit top", "t-shirt dress",
    ],
    "cozy": [
        "chunky knit sweater", "cardigan", "knit dress",
        "joggers", "fleece pullover", "wide-leg knit pant",
    ],
    "dramatic": [
        "maxi dress", "wide-leg jumpsuit", "velvet blazer",
        "asymmetric dress", "statement skirt", "draped top",
    ],
    "night out": [
        "mini dress", "satin top", "slip dress",
        "bodycon dress", "leather pants", "sequin top",
    ],
    "evening": [
        "cocktail dress", "satin blouse", "embellished top",
        "midi dress", "sequin dress", "wide-leg trouser",
    ],
    "workwear": [
        "tailored blazer", "trouser", "button-down shirt",
        "pencil skirt", "structured blouse", "sheath dress",
    ],
    "elevated basics": [
        "cashmere sweater", "silk tee", "quality denim",
        "tailored jogger", "poplin shirt", "knit midi dress",
    ],
    "modern": [
        "asymmetric dress", "structured top", "wide-leg pant",
        "column dress", "minimal jumpsuit", "draped skirt",
    ],
    "athleisure": [
        "leggings", "sports bra", "joggers",
        "zip-up jacket", "biker shorts", "knit tank",
    ],
    "romantic": [
        "lace dress", "floral midi dress", "silk skirt",
        "puff sleeve blouse", "ruffle top", "wrap dress",
    ],
    "preppy": [
        "polo shirt", "pleated skirt", "cable knit sweater",
        "chinos", "rugby shirt", "shirt dress",
    ],
    "edgy": [
        "leather jacket", "distressed jeans", "coated denim",
        "fitted turtleneck", "mini skirt", "bodysuit",
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
    """Build a deduplicated keyword list from selected vibes.

    Keywords are interleaved across vibes so that if we hit the API limit
    early, we still get diversity across aesthetics rather than exhausting
    one vibe's keywords first.
    """
    if not vibes:
        return FALLBACK_KEYWORDS

    # Gather per-vibe keyword lists
    per_vibe = [VIBE_KEYWORDS.get(v, []) for v in vibes]
    if not any(per_vibe):
        return FALLBACK_KEYWORDS

    # Interleave: round-robin across vibes for maximum diversity
    seen: set[str] = set()
    keywords: list[str] = []
    max_len = max(len(kws) for kws in per_vibe)
    for i in range(max_len):
        for kws in per_vibe:
            if i < len(kws) and kws[i] not in seen:
                seen.add(kws[i])
                keywords.append(kws[i])

    return keywords or FALLBACK_KEYWORDS


# Category keywords used to ensure catalog diversity.  When the vibe
# keywords alone don't produce enough variety, we append targeted
# category searches (e.g., "Aritzia dress classic").
CATEGORY_DIVERSITY_TERMS = ["dress", "top", "pants", "skirt", "jumpsuit"]


def _infer_category(name: str) -> str:
    """Infer garment category from product name."""
    lower = name.lower()
    if any(k in lower for k in ["dress", "gown"]):
        return "dress"
    if any(k in lower for k in ["coat", "jacket", "puffer", "anorak", "parka", "bomber"]):
        return "outerwear"
    if any(k in lower for k in ["trouser", "pant", "jeans", "chino", "jogger", "legging", "short"]):
        return "bottom"
    if any(k in lower for k in ["skirt"]):
        return "skirt"
    if any(k in lower for k in ["jumpsuit", "romper"]):
        return "jumpsuit"
    if any(k in lower for k in ["sweater", "cardigan", "knit", "pullover", "fleece"]):
        return "knitwear"
    if any(k in lower for k in ["top", "blouse", "shirt", "tee", "camisole", "tank", "bodysuit"]):
        return "top"
    # Blazers are borderline — treat as outerwear
    if "blazer" in lower:
        return "outerwear"
    return ""


def _fallback_tags_from_name(name: str) -> dict:
    lower = name.lower()
    silhouette = []
    vibes = ["casual"]
    occasion = ["weekend"]
    structure = "soft"
    season = ["all"]
    waist = "n/a"
    category = _infer_category(name)

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
        "category": category,
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

    # Infer category from name if Claude Vision didn't provide one
    cat = tags.get("category", "") or _infer_category(c.name)

    row = {
        "name": c.name,
        "brand": c.brand,
        "url": c.url,
        "image_url": image_url,
        "category": cat,
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


def _balance_by_category(
    rows: list[dict],
    max_per_category: int = 3,
    max_total: int = 8,
) -> list[dict]:
    """Select a diverse subset from a flat list of tagged product rows.

    Ensures no single garment category dominates by capping each category
    at ``max_per_category`` items.  Products from under-represented
    categories are preferred.  Returns up to ``max_total`` products.
    """
    from collections import defaultdict

    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        cat = row.get("category", "") or "other"
        buckets[cat].append(row)

    # Round-robin across categories for maximum diversity
    selected: list[dict] = []
    cat_counts: dict[str, int] = defaultdict(int)

    # Priority order: dresses/tops/bottoms first, outerwear last
    priority_order = ["dress", "top", "bottom", "skirt", "jumpsuit", "knitwear", "outerwear", "other"]
    ordered_cats = [c for c in priority_order if c in buckets]
    # Add any categories not in priority list
    ordered_cats += [c for c in buckets if c not in ordered_cats]

    round_idx = 0
    while len(selected) < max_total:
        added_any = False
        for cat in ordered_cats:
            if cat_counts[cat] >= max_per_category:
                continue
            if round_idx < len(buckets[cat]):
                selected.append(buckets[cat][round_idx])
                cat_counts[cat] += 1
                added_any = True
                if len(selected) >= max_total:
                    break
        round_idx += 1
        if not added_any:
            break

    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Build StyleLab live product catalog")
    parser.add_argument("--max-per-brand", type=int, default=8)
    parser.add_argument("--max-per-category", type=int, default=3,
                        help="Max products per garment category per brand (for diversity)")
    parser.add_argument("--out", default="data/products_live.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-vision", action="store_true",
                        help="Skip Claude Vision tagging, use keyword fallback only")
    parser.add_argument("--vibes", nargs="*", default=None,
                        help="Vibes to drive keyword selection (e.g. --vibes minimal polished)")
    parser.add_argument("--gender", default="women", choices=["women", "men", "unisex"],
                        help="Gender to filter search results (default: women)")
    args = parser.parse_args()

    keywords = keywords_for_vibes(args.vibes)

    # Prepend gender to every keyword for targeted results
    # e.g. "midi dress" → "women midi dress"
    gender_prefix = args.gender if args.gender != "unisex" else ""
    if gender_prefix:
        keywords = [f"{gender_prefix} {kw}" for kw in keywords]

    print(f"Gender: {args.gender}")
    print(f"Selected vibes: {args.vibes or '(none — using fallback)'}")
    print(f"Search keywords ({len(keywords)}): {', '.join(keywords)}")

    products = []
    pid = 1

    for brand in BRANDS:
        print(f"\n{'='*50}")
        print(f"Discovering products for {brand}...")
        print(f"{'='*50}")

        # ── Phase 1: Fetch from vibe keywords ────────────────────────
        # Request MORE than max_per_brand so we have room to balance
        fetch_limit = args.max_per_brand * 3

        try:
            candidates = serpapi_shopping_discover(
                brand=brand,
                keywords=keywords,
                max_results=fetch_limit,
            )
            discovery_method = "shopping"
        except Exception as exc:
            print(f"  Shopping API failed ({exc}), falling back to organic search...")
            candidates = serpapi_discover_products(
                brand=brand,
                keywords=keywords,
                max_results=fetch_limit,
            )
            discovery_method = "organic"

        print(f"Found {len(candidates)} products via {discovery_method} search")

        # ── Phase 2: If results look category-heavy, add diversity searches ──
        # Quick check: if >60% of candidates have similar names (all coats, etc.)
        # inject targeted category searches
        name_cats = [_infer_category(c.name) for c in candidates]
        from collections import Counter
        cat_dist = Counter(name_cats)
        dominant = cat_dist.most_common(1)
        if dominant and dominant[0][1] > len(candidates) * 0.6 and len(candidates) > 3:
            dominant_cat = dominant[0][0]
            print(f"  ⚠ Catalog skewed toward '{dominant_cat}' ({dominant[0][1]}/{len(candidates)})")
            print(f"  → Adding diversity searches...")
            diversity_kws = [
                t for t in CATEGORY_DIVERSITY_TERMS
                if t.lower() != dominant_cat.lower()
            ]
            # Build diversity queries from the user's vibes + gender
            vibe_label = " ".join(args.vibes[:2]) if args.vibes else ""
            gender_label = args.gender if args.gender != "unisex" else ""
            prefix = f"{gender_label} {vibe_label}".strip() or "women"
            extra_keywords = [f"{prefix} {t}" for t in diversity_kws]
            try:
                extra = serpapi_shopping_discover(
                    brand=brand,
                    keywords=extra_keywords,
                    max_results=fetch_limit // 2,
                )
                # Deduplicate against existing candidates
                existing_names = {c.name.lower().strip() for c in candidates}
                for c in extra:
                    if c.name.lower().strip() not in existing_names:
                        candidates.append(c)
                        existing_names.add(c.name.lower().strip())
                print(f"  + Added {len(extra)} diversity candidates")
            except Exception as exc:
                print(f"  Diversity search failed: {exc}")

        # ── Phase 3: Tag and build rows ──────────────────────────────
        brand_rows = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futures = [
                ex.submit(_build_row_for_candidate, c, not args.skip_vision)
                for c in candidates
            ]
            for fut in concurrent.futures.as_completed(futures):
                row = fut.result()
                if row:
                    brand_rows.append(row)

        # ── Phase 4: Balance by category ─────────────────────────────
        balanced = _balance_by_category(
            brand_rows,
            max_per_category=args.max_per_category,
            max_total=args.max_per_brand,
        )

        # Log category distribution
        bal_cats = Counter(r.get("category", "other") for r in balanced)
        print(f"  Selected {len(balanced)} products: {dict(bal_cats)}")

        for row in balanced:
            row["id"] = f"live_{pid:04d}"
            pid += 1
            products.append(row)
            print(f"  + [{row['tag_source']}] {row['brand']} | {row['name']} [{row.get('category','')}]")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(products, indent=2))

    # Summary
    vision_count = sum(1 for p in products if p["tag_source"] == "vision")
    fallback_count = sum(1 for p in products if "fallback" in p["tag_source"])
    total_cats = Counter(p.get("category", "other") for p in products)
    print(f"\n{'='*50}")
    print(f"Wrote {len(products)} products -> {out_path}")
    print(f"  Vision-tagged: {vision_count}")
    print(f"  Fallback-tagged: {fallback_count}")
    print(f"  Category distribution: {dict(total_cats)}")
    if fallback_count > 0 and not args.skip_vision:
        print(f"  ⚠ {fallback_count} products used fallback tags (check API credits)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
