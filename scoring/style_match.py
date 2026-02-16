"""Style matching: scores how well a product's aesthetic tags align with user preferences.

Uses asymmetric (recall-weighted) overlap so products are judged by how much
of the user's taste they satisfy, not penalized for having extra tags.
"""
from __future__ import annotations

from typing import Dict, Iterable


def _overlap_score(left: Iterable[str], right: Iterable[str], neutral: float = 0.45) -> float:
    """Jaccard overlap — kept for backward compatibility with v1 algorithm."""
    l, r = {x.lower() for x in left}, {x.lower() for x in right}
    if not l or not r:
        return neutral
    return len(l.intersection(r)) / len(l.union(r))


def _asymmetric_overlap(
    product_tags: Iterable[str],
    user_tags: Iterable[str],
    neutral: float = 0.45,
) -> float:
    """Recall-weighted overlap: what fraction of the *user's* preferences does
    this product satisfy?  Blended with a precision term so products with
    wildly irrelevant extra tags are lightly penalized.

    Formula: 0.65 * recall + 0.35 * precision
    - recall  = |intersection| / min(|user_tags|, 3)   (capped so selecting
      more vibes doesn't penalize matches — a product matching 2 of 5 user
      vibes should score similarly to matching 2 of 3)
    - precision = |intersection| / |product_tags| (relevance of product tags)
    """
    p = {x.lower() for x in product_tags}
    u = {x.lower() for x in user_tags}
    if not u or not p:
        return neutral
    common = len(u.intersection(p))
    # Cap recall denominator at 3 so users who select many tags aren't penalized
    recall = common / min(len(u), 3)
    recall = min(recall, 1.0)  # clamp after cap
    precision = common / len(p)
    return 0.65 * recall + 0.35 * precision


def score_style_match(product: Dict, style: Dict) -> float:
    vibe_score = _asymmetric_overlap(
        product.get("vibes", []), style.get("vibes", []), neutral=0.5
    )
    silhouette_score = _asymmetric_overlap(
        product.get("silhouette", []), style.get("silhouettes", []), neutral=0.45
    )
    color_score = _asymmetric_overlap(
        product.get("colors", []), style.get("colors", []), neutral=0.4
    )

    return min(1.0, 0.45 * vibe_score + 0.35 * silhouette_score + 0.20 * color_score)
