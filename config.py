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
    "vacation", "city", "night out",
]

COLORS = [
    "black", "white", "cream", "navy", "olive", "camel", "grey", "burgundy",
    "red", "blue", "brown", "beige",
]

SEASONS = ["winter", "spring", "summer", "fall", "all"]

GARMENT_CATEGORIES = [
    "dress", "top", "bottom", "outerwear", "jumpsuit", "skirt", "knitwear",
]
GARMENT_CATEGORIES_SET = set(GARMENT_CATEGORIES)

GENDERS = ["women", "men", "unisex"]

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
    "category": GARMENT_CATEGORIES,
}

# ── Category-occasion affinity ──────────────────────────────────────
# How appropriate each garment category is for each occasion (0-1).
# Used as a multiplier in context scoring to penalize mismatches like
# "outerwear for a night out".
CATEGORY_OCCASION_AFFINITY = {
    "dress":     {"party": 1.0, "night out": 1.0, "date": 1.0, "dinner": 0.95,
                  "event": 1.0, "work": 0.70, "weekend": 0.75, "city": 0.80,
                  "travel": 0.50, "vacation": 0.85, "casual": 0.60},
    "top":       {"party": 0.85, "night out": 0.85, "date": 0.80, "dinner": 0.80,
                  "event": 0.75, "work": 0.90, "weekend": 0.90, "city": 0.85,
                  "travel": 0.85, "vacation": 0.85, "casual": 0.95},
    "bottom":    {"party": 0.70, "night out": 0.70, "date": 0.75, "dinner": 0.80,
                  "event": 0.65, "work": 0.95, "weekend": 0.90, "city": 0.85,
                  "travel": 0.90, "vacation": 0.80, "casual": 0.95},
    "outerwear": {"party": 0.30, "night out": 0.25, "date": 0.45, "dinner": 0.40,
                  "event": 0.40, "work": 0.80, "weekend": 0.85, "city": 0.90,
                  "travel": 0.95, "vacation": 0.50, "casual": 0.80},
    "jumpsuit":  {"party": 0.90, "night out": 0.85, "date": 0.85, "dinner": 0.85,
                  "event": 0.90, "work": 0.70, "weekend": 0.75, "city": 0.80,
                  "travel": 0.65, "vacation": 0.80, "casual": 0.60},
    "skirt":     {"party": 0.80, "night out": 0.80, "date": 0.85, "dinner": 0.85,
                  "event": 0.80, "work": 0.90, "weekend": 0.70, "city": 0.80,
                  "travel": 0.55, "vacation": 0.70, "casual": 0.60},
    "knitwear":  {"party": 0.30, "night out": 0.25, "date": 0.55, "dinner": 0.55,
                  "event": 0.35, "work": 0.80, "weekend": 0.95, "city": 0.80,
                  "travel": 0.80, "vacation": 0.50, "casual": 0.95},
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
