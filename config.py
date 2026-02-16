"""Centralized configuration for StyleLab MVP.

Single source of truth for all tag enums, scoring options, and shared constants.
Every module that needs vibe/silhouette/occasion/etc. lists should import from here.
"""
from __future__ import annotations

# ── Tag enums (canonical set) ──────────────────────────────────────────
# Used by: Claude Vision tagging, product catalog validation, Streamlit UI,
# Instagram analyzer, scoring engine.

SILHOUETTES = [
    "wide-leg", "tailored", "fitted", "relaxed", "midi", "cropped", "longline",
    "defined waist", "fluid", "mini", "maxi", "straight", "a-line", "column",
    "boxy", "draped",
]

WAIST_OPTIONS = ["high-rise", "mid-rise", "low-rise", "defined", "n/a"]

STRUCTURE_OPTIONS = ["structured", "soft"]

VIBES = [
    "minimal", "polished", "feminine", "street", "bold", "classic", "casual",
    "cozy", "dramatic", "night out", "evening", "workwear", "elevated basics",
    "modern", "athleisure", "romantic", "preppy", "edgy",
]

OCCASIONS = [
    "work", "weekend", "date", "event", "travel", "party", "dinner",
    "vacation", "city",
]

COLORS = [
    "black", "white", "cream", "navy", "olive", "camel", "grey", "burgundy",
    "red", "blue", "brown", "beige",
]

SEASONS = ["winter", "spring", "summer", "fall", "all"]

# Sets for fast lookup (used by validation and scoring)
SILHOUETTES_SET = set(SILHOUETTES)
WAIST_SET = set(WAIST_OPTIONS)
STRUCTURE_SET = set(STRUCTURE_OPTIONS)
VIBES_SET = set(VIBES)
OCCASIONS_SET = set(OCCASIONS)
COLORS_SET = set(COLORS)
SEASONS_SET = set(SEASONS)

# Dict format for Claude Vision prompt and tag_products validation
TAG_SCHEMA = {
    "silhouette": SILHOUETTES,
    "waist": WAIST_OPTIONS,
    "structure": STRUCTURE_OPTIONS,
    "vibes": VIBES,
    "occasion": OCCASIONS,
    "colors": COLORS,
    "season": SEASONS,
}

# ── Body analysis enums ────────────────────────────────────────────────

PROPORTION_SIGNALS = ["elongated", "compact", "balanced"]
LINE_HARMONY_OPTIONS = ["clean", "fluid", "structured"]
SHOULDER_HIP_BALANCE_OPTIONS = ["shoulder_dominant", "hip_dominant", "balanced"]

# FFIT body shapes (from Zong 2022 thesis)
FFIT_BODY_SHAPES = ["hourglass", "triangle", "inverted_triangle", "rectangle", "oval"]

# ── Scoring weights ────────────────────────────────────────────────────

WEIGHTS_V1 = {"body": 0.35, "style": 0.30, "context": 0.20, "values": 0.10, "novelty": 0.05}
WEIGHTS_V2 = {"body": 0.40, "style": 0.32, "context": 0.20, "values": 0.08}
WEIGHTS_V3 = {"body": 0.35, "style": 0.35, "context": 0.20, "values": 0.10}

# ── UI defaults ────────────────────────────────────────────────────────

DEFAULT_VIBES = ["minimal", "polished"]
DEFAULT_SILHOUETTES = ["tailored", "wide-leg"]
DEFAULT_COLORS = ["black", "cream", "navy"]
DEFAULT_SEASON = "winter"
DEFAULT_OCCASION = "work"

# ── Season neighbors (for context scoring) ─────────────────────────────

SEASON_NEIGHBORS = {
    "winter": {"winter", "fall"},
    "fall": {"fall", "winter", "spring"},
    "spring": {"spring", "fall", "summer"},
    "summer": {"summer", "spring"},
    "all": {"all", "winter", "fall", "spring", "summer"},
}
