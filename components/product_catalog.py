"""Product catalog: loads, validates, and normalizes products for the scoring engine.

Supports two catalog sources:
- data/products.json — static fallback catalog (hand-curated Aritzia products)
- data/products_live.json — dynamically built catalog from web crawling + Claude Vision

The normalizer flattens nested tag structures and ensures all scoring fields
exist with sensible defaults, so the scoring engine never hits missing keys.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from config import SILHOUETTES_SET, WAIST_SET, STRUCTURE_SET, VIBES_SET, OCCASIONS_SET, SEASONS_SET

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = {"name", "brand"}


def _validate_product(product: Dict, index: int) -> List[str]:
    """Validate a product against the canonical schema. Returns list of warnings."""
    warnings = []
    name = product.get("name", f"product[{index}]")

    for field in _REQUIRED_FIELDS:
        if not product.get(field):
            warnings.append(f"{name}: missing required field '{field}'")

    # Validate enum fields against canonical sets
    for sil in product.get("silhouette", []):
        if sil.lower() not in SILHOUETTES_SET:
            warnings.append(f"{name}: unknown silhouette '{sil}'")

    waist = product.get("waist", "n/a")
    if isinstance(waist, str) and waist.lower() not in WAIST_SET:
        warnings.append(f"{name}: unknown waist '{waist}'")

    structure = product.get("structure", "soft")
    if isinstance(structure, str) and structure.lower() not in STRUCTURE_SET:
        warnings.append(f"{name}: unknown structure '{structure}'")

    for vibe in product.get("vibes", []):
        if vibe.lower() not in VIBES_SET:
            warnings.append(f"{name}: unknown vibe '{vibe}'")

    for occ in product.get("occasion", []):
        if occ.lower() not in OCCASIONS_SET:
            warnings.append(f"{name}: unknown occasion '{occ}'")

    for season in product.get("season", []):
        if season.lower() not in SEASONS_SET:
            warnings.append(f"{name}: unknown season '{season}'")

    return warnings


def normalize_product_for_scoring(product: Dict) -> Dict:
    out = dict(product)
    tags = product.get("tags") or {}

    # New tagging pipeline format -> flatten for scoring engine compatibility.
    if isinstance(tags, dict) and tags:
        out["silhouette"] = tags.get("silhouette", product.get("silhouette", []))
        out["waist"] = tags.get("waist", product.get("waist", "n/a"))
        out["structure"] = tags.get("structure", product.get("structure", "soft"))
        out["vibes"] = tags.get("vibes", product.get("vibes", []))
        out["occasion"] = tags.get("occasion", product.get("occasion", []))
        out["colors"] = tags.get("colors", product.get("colors", []))
        out["season"] = tags.get("season", product.get("season", ["all"]))

    # Image/url compatibility across schemas.
    if not out.get("image_url"):
        image_urls = out.get("image_urls")
        if isinstance(image_urls, list) and image_urls:
            out["image_url"] = image_urls[0]
    if not out.get("url") and out.get("product_url"):
        out["url"] = out["product_url"]

    # Ensure scoring fields exist even for partially-tagged entries.
    out.setdefault("silhouette", [])
    out.setdefault("waist", "n/a")
    out.setdefault("structure", "soft")
    out.setdefault("vibes", [])
    out.setdefault("occasion", [])
    out.setdefault("colors", [])
    out.setdefault("season", ["all"])

    return out


def load_catalog(base_dir: Path) -> Tuple[List[Dict], Path]:
    live_products_path = base_dir / "data" / "products_live.json"
    default_products_path = base_dir / "data" / "products.json"

    chosen_path = default_products_path
    products: List[Dict] = []

    if live_products_path.exists():
        live_products = json.loads(live_products_path.read_text())
        if live_products:
            products = live_products
            chosen_path = live_products_path

    if not products:
        products = json.loads(default_products_path.read_text())
        chosen_path = default_products_path

    normalized = [normalize_product_for_scoring(p) for p in products]

    # Validate all products and log warnings (non-blocking)
    all_warnings = []
    for i, product in enumerate(normalized):
        all_warnings.extend(_validate_product(product, i))
    if all_warnings:
        logger.warning("Product catalog validation found %d issues:", len(all_warnings))
        for w in all_warnings[:20]:  # cap log output
            logger.warning("  - %s", w)

    return normalized, chosen_path
