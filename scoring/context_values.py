"""Context and values scoring: evaluates season/occasion fit and user value alignment.

Context scoring uses a season-neighbor graph (from config.py) and an occasion
affinity matrix to measure how well a product fits the user's lifestyle context.

Values scoring checks comfort, boldness, and sustainability preferences.
"""
from __future__ import annotations

from typing import Dict

from config import SEASON_NEIGHBORS, CATEGORY_OCCASION_AFFINITY
_OCCASION_AFFINITY: Dict[str, Dict[str, float]] = {
    "work":      {"work": 1.0, "dinner": 0.55, "event": 0.60, "city": 0.65,
                  "date": 0.40, "weekend": 0.30, "casual": 0.25},
    "dinner":    {"dinner": 1.0, "date": 0.85, "event": 0.75, "work": 0.50,
                  "party": 0.60, "city": 0.55, "weekend": 0.30, "night out": 0.70},
    "date":      {"date": 1.0, "dinner": 0.85, "event": 0.70, "party": 0.65,
                  "city": 0.50, "work": 0.35, "weekend": 0.35, "night out": 0.60},
    "weekend":   {"weekend": 1.0, "casual": 0.90, "travel": 0.80, "city": 0.55,
                  "vacation": 0.70, "work": 0.25, "dinner": 0.30},
    "travel":    {"travel": 1.0, "weekend": 0.80, "casual": 0.75, "vacation": 0.85,
                  "city": 0.60, "work": 0.25, "dinner": 0.30},
    "event":     {"event": 1.0, "dinner": 0.75, "date": 0.65, "party": 0.80,
                  "work": 0.50, "city": 0.55, "weekend": 0.25, "night out": 0.75},
    "party":     {"party": 1.0, "event": 0.80, "date": 0.70, "dinner": 0.65,
                  "night out": 0.90, "city": 0.45, "weekend": 0.25},
    "night out": {"night out": 1.0, "party": 0.90, "event": 0.75, "date": 0.70,
                  "dinner": 0.65, "city": 0.40, "weekend": 0.15, "work": 0.10,
                  "travel": 0.10, "casual": 0.15},
    "casual":    {"casual": 1.0, "weekend": 0.90, "travel": 0.75, "vacation": 0.70,
                  "city": 0.50, "work": 0.20, "dinner": 0.20},
    "city":      {"city": 1.0, "work": 0.60, "dinner": 0.55, "weekend": 0.55,
                  "event": 0.55, "travel": 0.55, "casual": 0.45},
    "vacation":  {"vacation": 1.0, "travel": 0.85, "weekend": 0.70, "casual": 0.70,
                  "city": 0.45, "work": 0.15, "dinner": 0.30},
}
_OCCASION_DEFAULT = 0.20


def _occasion_affinity(user_occasion: str, product_occasions: set[str]) -> float:
    """Best-match affinity between the user's occasion and all product occasion tags."""
    if not product_occasions:
        return 0.45
    row = _OCCASION_AFFINITY.get(user_occasion, {})
    return max(row.get(po, _OCCASION_DEFAULT) for po in product_occasions)


def _category_occasion_fit(category: str, occasion: str) -> float:
    """How appropriate is this garment category for the user's occasion?
    Returns a multiplier between 0.3 and 1.0 — applied to the final
    context score so outerwear is penalized for 'night out', etc."""
    if not category:
        return 0.85  # unknown category → slight neutral penalty
    row = CATEGORY_OCCASION_AFFINITY.get(category.lower(), {})
    return row.get(occasion.lower(), 0.65)


def score_context(product: Dict, context: Dict) -> float:
    season = context.get("season", "all").lower()
    occasion = context.get("occasion", "weekend").lower()

    p_seasons = {s.lower() for s in product.get("season", [])}
    p_occasions = {o.lower() for o in product.get("occasion", [])}

    # ── Season scoring ──
    if not p_seasons:
        season_score = 0.45
    elif "all" in p_seasons:
        season_score = 1.0
    elif season in p_seasons:
        season_score = 1.0
    elif p_seasons.intersection(SEASON_NEIGHBORS.get(season, {season})):
        season_score = 0.65
    else:
        season_score = 0.2

    # ── Occasion scoring (affinity matrix) ──
    occasion_score = _occasion_affinity(occasion, p_occasions)

    # ── Category-occasion fit (new: penalizes wrong garment types) ──
    category = str(product.get("category", "")).lower()
    category_fit = _category_occasion_fit(category, occasion)

    base = 0.55 * season_score + 0.45 * occasion_score
    # Apply category fit as a multiplier so outerwear gets penalized for night out
    return min(1.0, base * category_fit)


def score_values(product: Dict, values: Dict) -> float:
    score = 0.5  # lowered base from 0.6 → 0.5 for better discrimination
    vibes = {v.lower() for v in product.get("vibes", [])}
    structure = str(product.get("structure", "")).lower()

    # ── Comfort ──
    comfort_first = values.get("comfort_first", False)
    if comfort_first and (
        "cozy" in vibes or "casual" in vibes or structure == "soft"
    ):
        score += 0.22
    elif comfort_first and (
        structure == "structured" and not vibes.intersection({"cozy", "casual", "comfort"})
    ):
        score -= 0.12  # penalty: user wants comfort but product is stiff

    # ── Boldness ──
    boldness = float(values.get("boldness", 0.5))
    bold_vibes = vibes.intersection({"bold", "night out", "dramatic", "sharp"})
    quiet_vibes = vibes.intersection({"minimal", "classic", "subtle", "elevated basics"})

    if boldness > 0.65:
        if bold_vibes:
            score += 0.22
        elif quiet_vibes and not bold_vibes:
            score -= 0.10  # penalty: user wants bold but product is subdued
    elif boldness < 0.35:
        if quiet_vibes:
            score += 0.22
        elif bold_vibes and not quiet_vibes:
            score -= 0.10  # penalty: user wants subtle but product is loud

    # ── Sustainability ──
    if values.get("sustainable"):
        score += 0.06

    return max(0.0, min(1.0, score))
