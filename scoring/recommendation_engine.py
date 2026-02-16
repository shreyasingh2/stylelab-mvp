"""Recommendation engine: scores and ranks products against a user profile.

Combines four scoring dimensions — body harmony, style match, context fit,
and values alignment — into a single total score. Supports three algorithm
versions (v1, v2, v3) with different weight distributions and body scorers.

Scoring weights are defined in config.py (single source of truth).
"""
from __future__ import annotations

from typing import Dict, List

from config import WEIGHTS_V1, WEIGHTS_V2, WEIGHTS_V3
from scoring.body_harmony import score_body_harmony, score_body_harmony_v2, score_body_harmony_v3
from scoring.context_values import score_context, score_values
from scoring.style_match import score_style_match


def _novelty_score_v1(product: Dict, style: Dict, core_avg: float) -> float:
    user_vibes = {v.lower() for v in style.get("vibes", [])}
    item_vibes = {v.lower() for v in product.get("vibes", [])}

    if not user_vibes or not item_vibes:
        return 0.5

    # FIX: use user_vibes as denominator — measures how much of
    # the user's taste this product covers (recall-based novelty)
    overlap = len(user_vibes.intersection(item_vibes)) / max(len(user_vibes), 1)
    base = 0.35 + 0.55 * (1.0 - overlap)

    if core_avg < 0.45:
        return min(base, 0.4)
    return min(1.0, max(0.0, base))


def _novelty_score_v2(product: Dict, style: Dict, core_avg: float) -> float:
    """Band novelty so moderate exploration is rewarded, extremes are penalized."""
    user_vibes = {v.lower() for v in style.get("vibes", [])}
    item_vibes = {v.lower() for v in product.get("vibes", [])}

    if not user_vibes or not item_vibes:
        return 0.5

    # FIX: use user_vibes as denominator (recall-based)
    overlap = len(user_vibes.intersection(item_vibes)) / max(len(user_vibes), 1)
    distance = 1.0 - overlap

    # Peak novelty near moderate distance (~0.45)
    novelty = 1.0 - abs(distance - 0.45) / 0.45
    novelty = max(0.0, min(1.0, novelty))

    if core_avg < 0.45:
        novelty *= 0.6

    return novelty


def _style_score_v2(product: Dict, style: Dict) -> float:
    base = score_style_match(product, style)

    # Light synonym boost for sparse tagging.
    item_s = {s.lower() for s in product.get("silhouette", [])}
    user_s = {s.lower() for s in style.get("silhouettes", [])}
    synonym_pairs = [
        ({"tailored", "structured"}, 0.05),
        ({"fluid", "draped"}, 0.05),
        ({"relaxed", "boxy"}, 0.04),
    ]

    boost = 0.0
    for pair, w in synonym_pairs:
        if item_s.intersection(pair) and user_s.intersection(pair):
            boost += w

    return min(1.0, base + boost)


def score_product(product: Dict, user_profile: Dict, algorithm: str = "v1") -> Dict:
    body = user_profile.get("body", {})
    style = user_profile.get("style", {})
    context = user_profile.get("context", {})
    values = user_profile.get("values", {})

    algo = (algorithm or "v1").lower()

    if algo == "v3":
        body_s = score_body_harmony_v3(product, body)
        style_s = _style_score_v2(product, style)  # reuse synonym-aware style
    elif algo == "v2":
        body_s = score_body_harmony_v2(product, body)
        style_s = _style_score_v2(product, style)
    else:
        body_s = score_body_harmony(product, body)
        style_s = score_style_match(product, style)

    context_s = score_context(product, context)
    values_s = score_values(product, values)

    core_avg = (body_s + style_s + context_s) / 3.0

    if algo == "v3":
        # V3: point-based, no separate novelty weight (absorbed into style weight)
        novelty_s = _novelty_score_v2(product, style, core_avg)
        core_total = (
            WEIGHTS_V3["body"] * body_s
            + WEIGHTS_V3["style"] * style_s
            + WEIGHTS_V3["context"] * context_s
            + WEIGHTS_V3["values"] * values_s
        )
        # Novelty is a small tie-breaker, not a scored dimension
        total = 0.97 * core_total + 0.03 * novelty_s
    elif algo == "v2":
        novelty_s = _novelty_score_v2(product, style, core_avg)
        core_total = (
            WEIGHTS_V2["body"] * body_s
            + WEIGHTS_V2["style"] * style_s
            + WEIGHTS_V2["context"] * context_s
            + WEIGHTS_V2["values"] * values_s
        )
        total = 0.95 * core_total + 0.05 * novelty_s
    else:
        novelty_s = _novelty_score_v1(product, style, core_avg)
        total = (
            WEIGHTS_V1["body"] * body_s
            + WEIGHTS_V1["style"] * style_s
            + WEIGHTS_V1["context"] * context_s
            + WEIGHTS_V1["values"] * values_s
            + WEIGHTS_V1["novelty"] * novelty_s
        )

    explanation = build_explanation(product, user_profile, body_s, style_s, context_s)

    return {
        "product": product,
        "scores": {
            "body": round(body_s, 3),
            "style": round(style_s, 3),
            "context": round(context_s, 3),
            "values": round(values_s, 3),
            "novelty": round(novelty_s, 3),
            "total": round(total, 3),
            "algorithm": algo,
        },
        "explanation": explanation,
    }


def rank_products(
    products: List[Dict],
    user_profile: Dict,
    top_k: int = 15,
    algorithm: str = "v1",
) -> List[Dict]:
    scored = [score_product(p, user_profile, algorithm=algorithm) for p in products]
    scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return scored[:top_k]


def build_explanation(
    product: Dict,
    user_profile: Dict,
    body_score: float,
    style_score: float,
    context_score: float,
) -> str:
    body_signal = user_profile.get("body", {}).get("proportion_signal", "balanced")
    occasion = user_profile.get("context", {}).get("occasion", "daily life")
    vibes = ", ".join(user_profile.get("style", {}).get("vibes", [])[:2]) or "your style"

    tone = "works beautifully with" if body_score >= 0.7 else "can still work with"
    style_phrase = "strongly reflects" if style_score >= 0.55 else "gently expands"
    context_phrase = "fits naturally into" if context_score >= 0.55 else "can be a flexible option for"

    return (
        f"This {product['name'].lower()} {tone} your {body_signal} proportions, "
        f"{style_phrase} your {vibes} aesthetic, and {context_phrase} your {occasion} context."
    )
