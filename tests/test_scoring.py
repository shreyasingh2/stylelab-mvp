"""Unit tests for scoring modules: body_harmony, style_match, context_values, recommendation_engine."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from scoring.body_harmony import (
    score_body_harmony,
    score_body_harmony_v2,
    score_body_harmony_v3,
    _classify_body_shape,
)
from scoring.style_match import score_style_match, _asymmetric_overlap
from scoring.context_values import score_context, score_values
from scoring.recommendation_engine import score_product, rank_products


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def inverted_triangle_body():
    """Shoulder-dominant elongated body (user's actual MediaPipe data)."""
    return {
        "proportion_signal": "elongated",
        "line_harmony": "fluid",
        "shoulder_hip_balance": "shoulder_dominant",
        "torso_leg_ratio": 0.599,
        "confidence": 0.890,
        "features": {
            "body_aspect_ratio": 3.719,
            "shoulder_hip_ratio": 1.400,
            "torso_leg_ratio": 0.599,
            "joint_softness": 0.786,
        },
    }


@pytest.fixture
def triangle_body():
    """Hip-dominant compact body."""
    return {
        "proportion_signal": "compact",
        "line_harmony": "clean",
        "shoulder_hip_balance": "hip_dominant",
        "torso_leg_ratio": 0.72,
        "confidence": 0.85,
        "features": {
            "body_aspect_ratio": 2.6,
            "shoulder_hip_ratio": 0.82,
            "torso_leg_ratio": 0.72,
            "joint_softness": 0.4,
        },
    }


@pytest.fixture
def wide_leg_trouser():
    return {
        "name": "Effortless Wide-Leg Trouser",
        "brand": "Aritzia",
        "silhouette": ["wide-leg", "tailored"],
        "waist": "high-rise",
        "structure": "structured",
        "vibes": ["minimal", "polished"],
        "occasion": ["work", "dinner"],
        "colors": ["black", "charcoal"],
        "season": ["fall", "winter", "spring"],
    }


@pytest.fixture
def boxy_tee():
    return {
        "name": "Boxy Tee",
        "brand": "Aritzia",
        "silhouette": ["boxy", "cropped"],
        "waist": "n/a",
        "structure": "soft",
        "vibes": ["casual", "street"],
        "occasion": ["weekend", "casual"],
        "colors": ["white"],
        "season": ["summer", "spring"],
    }


@pytest.fixture
def user_style():
    return {
        "vibes": ["minimal", "polished", "elevated basics"],
        "silhouettes": ["tailored", "wide-leg", "fluid"],
        "colors": ["black", "white", "navy", "camel"],
    }


@pytest.fixture
def user_context():
    return {"season": "winter", "occasion": "work"}


@pytest.fixture
def user_values():
    return {"boldness": 0.35}


@pytest.fixture
def full_profile(inverted_triangle_body, user_style, user_context, user_values):
    return {
        "body": inverted_triangle_body,
        "style": user_style,
        "context": user_context,
        "values": user_values,
    }


# ══════════════════════════════════════════════════════════════════════
# FFIT body shape classification
# ══════════════════════════════════════════════════════════════════════

class TestClassifyBodyShape:
    def test_inverted_triangle(self):
        assert _classify_body_shape(1.4, 3.7) == "inverted_triangle"

    def test_triangle(self):
        assert _classify_body_shape(0.82, 2.6) == "triangle"

    def test_hourglass(self):
        assert _classify_body_shape(1.0, 2.8) == "hourglass"

    def test_rectangle(self):
        assert _classify_body_shape(1.0, 3.5) == "rectangle"

    def test_boundary_low(self):
        """Exactly 0.90 should be balanced, not triangle."""
        shape = _classify_body_shape(0.90, 3.0)
        assert shape in ("hourglass", "rectangle")

    def test_boundary_high(self):
        """Exactly 1.10 should be balanced, not inverted_triangle."""
        shape = _classify_body_shape(1.10, 3.0)
        assert shape in ("hourglass", "rectangle")


# ══════════════════════════════════════════════════════════════════════
# Body harmony scoring
# ══════════════════════════════════════════════════════════════════════

class TestBodyHarmonyV1:
    def test_good_match_scores_high(self, inverted_triangle_body, wide_leg_trouser):
        score = score_body_harmony(wide_leg_trouser, inverted_triangle_body)
        assert score >= 0.55, f"Wide-leg should score well for elongated body, got {score}"

    def test_bad_match_scores_low(self, inverted_triangle_body, boxy_tee):
        score = score_body_harmony(boxy_tee, inverted_triangle_body)
        # Boxy + cropped on elongated shoulder-dominant should be penalized
        assert score < 0.55, f"Boxy+cropped should score low for elongated, got {score}"

    def test_output_range(self, inverted_triangle_body, wide_leg_trouser):
        score = score_body_harmony(wide_leg_trouser, inverted_triangle_body)
        assert 0.0 <= score <= 1.0


class TestBodyHarmonyV3:
    def test_good_match_inverted_triangle(self, inverted_triangle_body, wide_leg_trouser):
        score = score_body_harmony_v3(wide_leg_trouser, inverted_triangle_body)
        # Wide-leg(5) + high-rise(5) + structured(3) = 13/15 ≈ 0.87
        assert score >= 0.75, f"Expected high score for wide-leg on inv.tri, got {score}"

    def test_bad_match_inverted_triangle(self, inverted_triangle_body, boxy_tee):
        score = score_body_harmony_v3(boxy_tee, inverted_triangle_body)
        # boxy(2) or cropped(2) + n/a(2) + soft(5) → best sil = 2, so 9/15 ≈ 0.60
        assert score < 0.70, f"Boxy+cropped should score lower for inv.tri, got {score}"

    def test_triangle_prefers_a_line(self, triangle_body):
        a_line_dress = {
            "silhouette": ["a-line", "defined waist"],
            "waist": "defined",
            "structure": "soft",
        }
        straight_dress = {
            "silhouette": ["straight", "column"],
            "waist": "n/a",
            "structure": "structured",
        }
        score_aline = score_body_harmony_v3(a_line_dress, triangle_body)
        score_straight = score_body_harmony_v3(straight_dress, triangle_body)
        assert score_aline > score_straight, (
            f"Triangle body should prefer A-line ({score_aline}) over straight ({score_straight})"
        )

    def test_confidence_gate_attenuates(self, inverted_triangle_body, wide_leg_trouser):
        """Low confidence should reduce score."""
        low_conf_body = dict(inverted_triangle_body)
        low_conf_body["confidence"] = 0.2
        high_conf_body = dict(inverted_triangle_body)
        high_conf_body["confidence"] = 0.95

        low = score_body_harmony_v3(wide_leg_trouser, low_conf_body)
        high = score_body_harmony_v3(wide_leg_trouser, high_conf_body)
        assert high > low, f"Higher confidence should yield higher score: {high} vs {low}"


# ══════════════════════════════════════════════════════════════════════
# Style match scoring
# ══════════════════════════════════════════════════════════════════════

class TestAsymmetricOverlap:
    def test_perfect_overlap(self):
        assert _asymmetric_overlap({"a", "b"}, {"a", "b"}) == 1.0

    def test_no_overlap(self):
        assert _asymmetric_overlap({"a"}, {"b"}) == 0.0

    def test_partial_recall(self):
        # user has {a,b}, product has {a,c} → recall=1/2, precision=1/2
        score = _asymmetric_overlap({"a", "c"}, {"a", "b"})
        expected = 0.65 * 0.5 + 0.35 * 0.5
        assert abs(score - expected) < 0.01

    def test_empty_user_tags_returns_neutral(self):
        assert _asymmetric_overlap({"a"}, set()) == 0.45

    def test_empty_product_tags_returns_neutral(self):
        assert _asymmetric_overlap(set(), {"a"}) == 0.45


class TestStyleMatch:
    def test_matching_vibes(self, wide_leg_trouser, user_style):
        score = score_style_match(wide_leg_trouser, user_style)
        assert score >= 0.5, f"Matching vibes should score well, got {score}"

    def test_no_overlap_vibes(self, user_style):
        product = {"vibes": ["goth", "punk"], "silhouette": ["mini"], "colors": ["red"]}
        score = score_style_match(product, user_style)
        assert score < 0.3, f"No overlap should score low, got {score}"


# ══════════════════════════════════════════════════════════════════════
# Context scoring
# ══════════════════════════════════════════════════════════════════════

class TestContextScoring:
    def test_matching_season_and_occasion(self, wide_leg_trouser, user_context):
        score = score_context(wide_leg_trouser, user_context)
        # winter product + work occasion → should be high
        assert score >= 0.8, f"Matching season+occasion should be high, got {score}"

    def test_wrong_season(self, user_context):
        summer_product = {"season": ["summer"], "occasion": ["work"]}
        score = score_context(summer_product, user_context)
        # winter user, summer product → season penalty
        assert score < 0.8, f"Wrong season should lower score, got {score}"

    def test_cross_occasion_affinity(self, user_context):
        dinner_product = {"season": ["winter"], "occasion": ["dinner"]}
        casual_product = {"season": ["winter"], "occasion": ["casual"]}
        dinner_score = score_context(dinner_product, user_context)
        casual_score = score_context(casual_product, user_context)
        # work→dinner should have higher affinity than work→casual
        assert dinner_score > casual_score, (
            f"Work→dinner ({dinner_score}) should beat work→casual ({casual_score})"
        )


# ══════════════════════════════════════════════════════════════════════
# Values scoring
# ══════════════════════════════════════════════════════════════════════

class TestValuesScoring:
    def test_output_range(self, user_values):
        product = {"vibes": ["bold", "dramatic"], "structure": "structured"}
        score = score_values(product, user_values)
        assert 0.0 <= score <= 1.0


# ══════════════════════════════════════════════════════════════════════
# Recommendation engine integration
# ══════════════════════════════════════════════════════════════════════

class TestRecommendationEngine:
    def test_score_product_returns_all_keys(self, wide_leg_trouser, full_profile):
        result = score_product(wide_leg_trouser, full_profile, algorithm="v3")
        assert "scores" in result
        for key in ("body", "style", "context", "values", "novelty", "total", "algorithm"):
            assert key in result["scores"], f"Missing key: {key}"

    def test_v3_total_in_range(self, wide_leg_trouser, full_profile):
        result = score_product(wide_leg_trouser, full_profile, algorithm="v3")
        assert 0.0 <= result["scores"]["total"] <= 1.0

    def test_all_algorithms_produce_scores(self, wide_leg_trouser, full_profile):
        for algo in ["v1", "v2", "v3"]:
            result = score_product(wide_leg_trouser, full_profile, algorithm=algo)
            assert result["scores"]["total"] > 0, f"Algorithm {algo} returned 0"
            assert result["scores"]["algorithm"] == algo

    def test_rank_products_ordering(self, full_profile):
        products = [
            {
                "name": "Good Match", "brand": "A",
                "silhouette": ["wide-leg", "fluid"], "waist": "high-rise",
                "structure": "soft", "vibes": ["minimal", "polished"],
                "occasion": ["work"], "colors": ["black"], "season": ["winter"],
            },
            {
                "name": "Bad Match", "brand": "B",
                "silhouette": ["boxy", "cropped"], "waist": "n/a",
                "structure": "soft", "vibes": ["street", "bold"],
                "occasion": ["party"], "colors": ["red"], "season": ["summer"],
            },
        ]
        ranked = rank_products(products, full_profile, top_k=2, algorithm="v3")
        assert ranked[0]["product"]["name"] == "Good Match"
        assert ranked[0]["scores"]["total"] > ranked[1]["scores"]["total"]

    def test_explanation_not_empty(self, wide_leg_trouser, full_profile):
        result = score_product(wide_leg_trouser, full_profile)
        assert len(result["explanation"]) > 20
