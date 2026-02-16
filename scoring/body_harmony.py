"""Body harmony scoring: evaluates how well a garment's silhouette fits a body shape.

Three algorithm versions:
- V1: Rule-based with proportion signal, torso/leg ratio, shoulder/hip balance.
- V2: Continuous ratios (FFIT-style) blending vertical, balance, rise, and line.
- V3: Point-based lookup matrices from Zong (2022) FFIT thesis — recommended.

Body data comes from MediaPipe pose estimation (see components/body_analysis.py).
"""
from __future__ import annotations

from typing import Dict


def _has_any(values: set[str], targets: set[str]) -> bool:
    return bool(values.intersection(targets))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_body_harmony(product: Dict, body: Dict) -> float:
    """V1 body harmony scorer — improved with wider penalty range and
    explicit contradiction penalties so bad fits actually score low."""
    silhouette = {s.lower() for s in product.get("silhouette", [])}
    structure = str(product.get("structure", "")).lower()
    waist = str(product.get("waist", "")).lower()

    signal = body.get("proportion_signal", "balanced")
    line_harmony = body.get("line_harmony", "clean")
    shoulder_hip_balance = body.get("shoulder_hip_balance", "balanced")
    torso_leg_ratio = float(body.get("torso_leg_ratio", 0.65))

    score = 0.45  # lowered base from 0.5 → 0.45 for wider range

    # ── Proportion signal ──
    if signal == "elongated":
        if _has_any(silhouette, {"wide-leg", "longline", "tailored", "maxi", "column"}):
            score += 0.18
        if _has_any(silhouette, {"cropped", "mini"}):
            score -= 0.14  # stronger penalty (was -0.08)
        if _has_any(silhouette, {"boxy"}) and not _has_any(silhouette, {"longline", "tailored"}):
            score -= 0.06  # boxy without length breaks elongated line
    elif signal == "compact":
        if _has_any(silhouette, {"cropped", "defined waist", "a-line", "mini"}):
            score += 0.18
        if _has_any(silhouette, {"longline", "maxi", "column"}):
            score -= 0.14  # stronger penalty (was -0.08)
    else:  # balanced
        score += 0.10

    # ── Torso/leg ratio ──
    if torso_leg_ratio > 0.7 and "high-rise" in waist:
        score += 0.10
    elif torso_leg_ratio > 0.7 and waist in {"low-rise"}:
        score -= 0.08  # NEW: low-rise on long-torso shortens legs visually
    if torso_leg_ratio < 0.55 and _has_any(silhouette, {"longline", "maxi", "straight"}):
        score += 0.10

    # ── Shoulder/hip balance ──
    if shoulder_hip_balance == "shoulder_dominant":
        if _has_any(silhouette, {"fluid", "defined waist", "a-line", "wide-leg"}):
            score += 0.10  # softens/balances broad shoulders
        if _has_any(silhouette, {"boxy", "structured"}) and structure == "structured":
            score -= 0.10  # NEW: adds bulk to already-wide shoulders
    elif shoulder_hip_balance == "hip_dominant":
        if _has_any(silhouette, {"tailored", "structured", "boxy"}):
            score += 0.10  # adds structure to upper body
        if _has_any(silhouette, {"a-line", "wide-leg"}) and not _has_any(silhouette, {"tailored"}):
            score -= 0.08  # NEW: flares below amplify hip width

    # ── Line harmony ──
    if line_harmony == "clean" and (_has_any(silhouette, {"tailored", "clean"}) or structure == "structured"):
        score += 0.14
    elif line_harmony == "fluid" and (_has_any(silhouette, {"fluid", "draped", "flowy"}) or structure == "soft"):
        score += 0.14
    elif line_harmony == "structured" and structure == "structured":
        score += 0.14
    # NEW: harmony contradictions
    elif line_harmony == "fluid" and structure == "structured" and not _has_any(silhouette, {"fluid", "draped"}):
        score -= 0.06  # stiff structure on fluid body
    elif line_harmony == "structured" and structure == "soft" and not _has_any(silhouette, {"tailored"}):
        score -= 0.06  # too soft for structured body

    return _clamp01(score)


def score_body_harmony_v2(product: Dict, body: Dict) -> float:
    """
    V2 body harmony scorer.

    Paper-inspired direction:
    - Uses continuous body ratios (FFIT-style ratio reasoning) instead of pure discrete rules.
    - Adds shape-balance component from shoulder/hip relationship.
    - Blends proportion, balance, rise fit, and line harmony.
    """
    silhouette = {s.lower() for s in product.get("silhouette", [])}
    structure = str(product.get("structure", "soft")).lower()
    waist = str(product.get("waist", "n/a")).lower()

    features = body.get("features", {})
    body_aspect = float(features.get("body_aspect_ratio", 3.0))
    shoulder_hip_ratio = float(features.get("shoulder_hip_ratio", 1.0))
    torso_leg_ratio = float(body.get("torso_leg_ratio", features.get("torso_leg_ratio", 0.65)))
    joint_softness = float(features.get("joint_softness", 0.55))

    # 1) Vertical proportion compatibility
    if body_aspect >= 3.4:  # elongated
        vertical = 0.65
        if _has_any(silhouette, {"wide-leg", "longline", "maxi", "tailored"}):
            vertical += 0.25
        if _has_any(silhouette, {"cropped", "mini"}):
            vertical -= 0.15
    elif body_aspect <= 2.75:  # compact
        vertical = 0.65
        if _has_any(silhouette, {"cropped", "defined waist", "a-line", "mini"}):
            vertical += 0.22
        if _has_any(silhouette, {"maxi", "longline"}):
            vertical -= 0.14
    else:
        vertical = 0.78

    # 2) Shape-balance compatibility (FFIT-like shoulder/hip emphasis)
    # >1 means shoulder-dominant, <1 hip-dominant.
    if shoulder_hip_ratio > 1.08:
        balance = 0.62
        if _has_any(silhouette, {"fluid", "defined waist", "a-line"}):
            balance += 0.25
        if _has_any(silhouette, {"boxy", "structured"}) and structure == "structured":
            balance -= 0.10
    elif shoulder_hip_ratio < 0.92:
        balance = 0.62
        if _has_any(silhouette, {"tailored", "structured", "boxy", "straight"}):
            balance += 0.25
        if _has_any(silhouette, {"a-line", "wide-leg"}):
            balance -= 0.07
    else:
        balance = 0.80

    # 3) Rise / torso-leg compatibility
    rise_fit = 0.62
    if torso_leg_ratio > 0.70 and waist in {"high-rise", "defined"}:
        rise_fit += 0.25
    if torso_leg_ratio < 0.55 and _has_any(silhouette, {"longline", "maxi", "straight"}):
        rise_fit += 0.18

    # 4) Line harmony compatibility
    if joint_softness >= 0.66:
        line = 0.62 + (0.24 if (structure == "soft" or _has_any(silhouette, {"fluid", "draped"})) else 0.0)
    elif joint_softness <= 0.45:
        line = 0.62 + (0.24 if (structure == "structured" or _has_any(silhouette, {"tailored", "boxy"})) else 0.0)
    else:
        line = 0.78

    # 5) Confidence gate from extractor reliability
    conf = float(body.get("confidence", 0.65))

    # Weighted blend (continuous, less brittle)
    raw = 0.30 * vertical + 0.30 * balance + 0.20 * rise_fit + 0.20 * line
    gated = raw * (0.85 + 0.15 * _clamp01(conf))

    return _clamp01(gated)


# ═══════════════════════════════════════════════════════════════════════
# V3: Point-based body scorer — Zong (2022) FFIT methodology
# ═══════════════════════════════════════════════════════════════════════
# Maps MediaPipe ratios → FFIT body shape, then accumulates points from
# lookup matrices for each product attribute. Normalizes raw/max → [0,1].
# Directly aligned with the Zong paper scoring and StyleLab scoring sheet.

# FFIT body shape classification from MediaPipe ratios
def _classify_body_shape(shoulder_hip_ratio: float, body_aspect: float) -> str:
    """Map MediaPipe measurements to FFIT body shape categories.
    Uses shoulder-to-hip ratio as primary discriminator (from Zong/Excel sheet):
      < 0.90  → triangle (hip-dominant)
      0.90–1.10 → hourglass or rectangle (balanced)
      > 1.10  → inverted_triangle (shoulder-dominant)
    Body aspect ratio helps disambiguate hourglass vs rectangle:
      hourglass tends to have more defined waist (aspect > 3.0 with balanced ratio)
    """
    if shoulder_hip_ratio < 0.90:
        return "triangle"
    elif shoulder_hip_ratio > 1.10:
        return "inverted_triangle"
    else:
        # balanced ratio — approximate hourglass vs rectangle
        # (without waist measurement we use body_aspect as proxy)
        if body_aspect >= 3.2:
            return "rectangle"  # elongated + balanced ≈ rectangle
        else:
            return "hourglass"  # moderate + balanced ≈ hourglass


# ── Scoring matrices (1-5 scale) from Zong paper + StyleLab Excel sheet ──
# Each dict maps body_shape → score for that attribute value.

# Silhouette attribute scores per body shape
_SILHOUETTE_SCORES: Dict[str, Dict[str, int]] = {
    "a-line": {
        "hourglass": 4, "triangle": 5, "inverted_triangle": 5,
        "rectangle": 5, "oval": 5,
    },
    "straight": {  # H-line / column
        "hourglass": 5, "triangle": 2, "inverted_triangle": 3,
        "rectangle": 3, "oval": 2,
    },
    "column": {  # alias for H-line
        "hourglass": 5, "triangle": 2, "inverted_triangle": 3,
        "rectangle": 3, "oval": 2,
    },
    "wide-leg": {  # flares below — similar to A-line lower body
        "hourglass": 4, "triangle": 3, "inverted_triangle": 5,
        "rectangle": 4, "oval": 4,
    },
    "tailored": {  # structured fit close to H-line
        "hourglass": 5, "triangle": 3, "inverted_triangle": 3,
        "rectangle": 4, "oval": 3,
    },
    "fitted": {  # body-skimming
        "hourglass": 5, "triangle": 2, "inverted_triangle": 3,
        "rectangle": 3, "oval": 2,
    },
    "boxy": {  # oversized rectangular
        "hourglass": 2, "triangle": 3, "inverted_triangle": 2,
        "rectangle": 3, "oval": 3,
    },
    "fluid": {  # draped, flowy
        "hourglass": 4, "triangle": 4, "inverted_triangle": 5,
        "rectangle": 3, "oval": 4,
    },
    "draped": {  # alias
        "hourglass": 4, "triangle": 4, "inverted_triangle": 5,
        "rectangle": 3, "oval": 4,
    },
    "longline": {  # elongated silhouette
        "hourglass": 4, "triangle": 3, "inverted_triangle": 4,
        "rectangle": 4, "oval": 3,
    },
    "maxi": {
        "hourglass": 3, "triangle": 3, "inverted_triangle": 4,
        "rectangle": 3, "oval": 3,
    },
    "cropped": {
        "hourglass": 3, "triangle": 4, "inverted_triangle": 2,
        "rectangle": 4, "oval": 2,
    },
    "mini": {
        "hourglass": 3, "triangle": 4, "inverted_triangle": 2,
        "rectangle": 4, "oval": 2,
    },
    "defined waist": {
        "hourglass": 5, "triangle": 5, "inverted_triangle": 5,
        "rectangle": 5, "oval": 5,
    },
}

# Waistline scores per body shape
_WAIST_SCORES: Dict[str, Dict[str, int]] = {
    "high-rise": {  # ≈ natural waist — universally recommended
        "hourglass": 5, "triangle": 5, "inverted_triangle": 5,
        "rectangle": 5, "oval": 5,
    },
    "defined": {  # natural/defined waist
        "hourglass": 5, "triangle": 5, "inverted_triangle": 5,
        "rectangle": 5, "oval": 5,
    },
    "mid-rise": {
        "hourglass": 4, "triangle": 3, "inverted_triangle": 4,
        "rectangle": 3, "oval": 3,
    },
    "low-rise": {  # ≈ drop waist — generally unflattering
        "hourglass": 2, "triangle": 1, "inverted_triangle": 2,
        "rectangle": 2, "oval": 1,
    },
    "n/a": {  # no defined waistline
        "hourglass": 2, "triangle": 2, "inverted_triangle": 2,
        "rectangle": 2, "oval": 2,
    },
}

# Structure/fit scores per body shape (from extended attributes)
_STRUCTURE_SCORES: Dict[str, Dict[str, int]] = {
    "structured": {  # tailored/fitted construction
        "hourglass": 5, "triangle": 3, "inverted_triangle": 3,
        "rectangle": 3, "oval": 2,
    },
    "soft": {  # fluid/jersey/draped construction
        "hourglass": 3, "triangle": 4, "inverted_triangle": 5,
        "rectangle": 3, "oval": 4,
    },
}

_MAX_SILHOUETTE_SCORE = 5
_MAX_WAIST_SCORE = 5
_MAX_STRUCTURE_SCORE = 5
_DEFAULT_SCORE = 3  # neutral fallback


def score_body_harmony_v3(product: Dict, body: Dict) -> float:
    """
    V3 body harmony scorer — point-based, Zong (2022) FFIT methodology.

    1. Classifies body shape from MediaPipe ratios using FFIT thresholds.
    2. Looks up per-attribute scores (1-5) from scoring matrices.
    3. Sums points, normalizes by max possible → [0, 1].
    4. Applies confidence gate from body extraction reliability.

    Aligned with: StyleLab_Scoring_Sheet.xlsx, Zong Cornell thesis,
    and user's handwritten point-accumulation approach.
    """
    silhouette_tags = {s.lower() for s in product.get("silhouette", [])}
    structure = str(product.get("structure", "")).lower()
    waist = str(product.get("waist", "n/a")).lower()

    features = body.get("features", {})
    body_aspect = float(features.get("body_aspect_ratio", 3.0))
    shoulder_hip_ratio = float(features.get("shoulder_hip_ratio", 1.0))
    conf = float(body.get("confidence", 0.65))

    # ── Step 1: Classify FFIT body shape ──
    shape = _classify_body_shape(shoulder_hip_ratio, body_aspect)

    # ── Step 2: Silhouette points (best match across all silhouette tags) ──
    if silhouette_tags:
        sil_points = []
        for tag in silhouette_tags:
            tag_scores = _SILHOUETTE_SCORES.get(tag)
            if tag_scores:
                sil_points.append(tag_scores.get(shape, _DEFAULT_SCORE))
        sil_score = max(sil_points) if sil_points else _DEFAULT_SCORE
    else:
        sil_score = _DEFAULT_SCORE

    # ── Step 3: Waistline points ──
    waist_lookup = _WAIST_SCORES.get(waist, _WAIST_SCORES.get("n/a", {}))
    waist_score = waist_lookup.get(shape, _DEFAULT_SCORE)

    # ── Step 4: Structure points ──
    struct_lookup = _STRUCTURE_SCORES.get(structure, {})
    struct_score = struct_lookup.get(shape, _DEFAULT_SCORE)

    # ── Step 5: Aggregate — raw / max (user's normalization approach) ──
    raw = sil_score + waist_score + struct_score
    max_possible = _MAX_SILHOUETTE_SCORE + _MAX_WAIST_SCORE + _MAX_STRUCTURE_SCORE  # 15

    normalized = raw / max_possible  # → [0, 1]

    # ── Step 6: Confidence gate (slight attenuation when body data is unreliable) ──
    gated = normalized * (0.85 + 0.15 * _clamp01(conf))

    return _clamp01(gated)
