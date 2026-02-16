# StyleLab Scoring Algorithm Reference

**Body Ratios, Algorithm Architecture, and Tag Impact Analysis**

*February 2026*

---

## 1. Input Pipeline — MediaPipe Body Analysis

**File:** `components/body_analysis.py`

Four body ratios extracted from MediaPipe:

- **body_aspect_ratio** (line 68-71): `height_proxy / max(shoulder_width, hip_width)`, clipped [2.20, 4.50]
- **torso_leg_ratio** (line 74-76): `torso_len / leg_len`, clipped [0.40, 0.85]
- **shoulder_hip_ratio** (line 78-79): `shoulder_width / hip_width`, clipped [0.70, 1.40]
- **joint_softness** (line 81-106): `0.6 * angle_openness + 0.4 * line_softness`, clipped [0, 1]

### Signal Derivation Thresholds

| Ratio | Threshold | Signal |
|-------|-----------|--------|
| body_aspect_ratio | >= 3.4 | elongated |
| body_aspect_ratio | <= 2.75 | compact |
| body_aspect_ratio | else | balanced |
| shoulder_hip_ratio | >= 1.08 | shoulder_dominant |
| shoulder_hip_ratio | <= 0.92 | hip_dominant |
| shoulder_hip_ratio | else | balanced |
| joint_softness | >= 0.66 | fluid |
| joint_softness | <= 0.45 | structured |
| joint_softness | else | clean |

**Confidence:** `0.65 * visibility_mean + 0.35 * gate_score`

---

## 2. V1 — Rule-Based Scoring

**File:** `scoring/body_harmony.py`, function `score_body_harmony` (line 14)

Base score: **0.45**. Applies bonuses/penalties from discrete body signals.

### V1 Scoring Rules

| Condition | Silhouette Match | Adjustment |
|-----------|-----------------|------------|
| Elongated body | wide-leg, longline, tailored, maxi, column | +0.18 |
| Elongated body | cropped, mini | -0.14 |
| Compact body | cropped, defined waist, a-line, mini | +0.18 |
| Compact body | longline, maxi, column | -0.14 |
| Balanced body | any | +0.10 |
| Torso/leg > 0.7 | high-rise waist | +0.10 |
| Torso/leg > 0.7 | low-rise waist | -0.08 |
| Torso/leg < 0.55 | longline, maxi, straight | +0.10 |
| Shoulder dominant | fluid, defined waist, a-line, wide-leg | +0.10 |
| Shoulder dominant | boxy + structured | -0.10 |
| Hip dominant | tailored, structured, boxy | +0.10 |
| Hip dominant | a-line, wide-leg (no tailored) | -0.08 |
| Fluid body line | fluid/draped OR soft structure | +0.14 |
| Structured body line | structured structure | +0.14 |
| Mismatch: fluid body + structured product | — | -0.06 |
| Mismatch: structured body + soft product | — | -0.06 |

**V1 Weights:** body 0.35, style 0.30, context 0.20, values 0.10, novelty 0.05

---

## 3. V2 — Continuous Ratio Blending

**File:** `scoring/body_harmony.py`, function `score_body_harmony_v2` (line 80)

### V2 Sub-Score Weights

| Sub-Score | Weight | Input Ratio | Base Score |
|-----------|--------|-------------|------------|
| Vertical proportion | 30% | body_aspect_ratio | 0.65 / 0.78 |
| Shape balance | 30% | shoulder_hip_ratio | 0.62 / 0.80 |
| Rise fit | 20% | torso_leg_ratio | 0.62 |
| Line harmony | 20% | joint_softness | 0.62 / 0.78 |

**Formula:** `raw = 0.30*vertical + 0.30*balance + 0.20*rise_fit + 0.20*line`

**Gate:** `gated = raw * (0.85 + 0.15 * confidence)`

**Synonym boosts:** tailored/structured +0.05, fluid/draped +0.05, relaxed/boxy +0.04

**V2 Weights:** body 0.40, style 0.32, context 0.20, values 0.08. Novelty 5%.

---

## 4. V3 — FFIT Point-Based Lookup

**File:** `scoring/body_harmony.py`, function `score_body_harmony_v3` (line 292)

### FFIT Classification

| Condition | Body Shape |
|-----------|-----------|
| shoulder_hip < 0.90 | triangle |
| shoulder_hip > 1.10 | inverted_triangle |
| 0.90-1.10 AND aspect >= 3.2 | rectangle |
| 0.90-1.10 AND aspect < 3.2 | hourglass |

### Silhouette Scoring Matrix

| Silhouette | Hourglass | Triangle | Inv. Tri | Rectangle | Oval |
|------------|-----------|----------|----------|-----------|------|
| defined waist | 5 | 5 | 5 | 5 | 5 |
| a-line | 4 | 5 | 5 | 5 | 5 |
| straight | 5 | 2 | 3 | 3 | 2 |
| wide-leg | 4 | 3 | 5 | 4 | 4 |
| tailored | 5 | 3 | 3 | 4 | 3 |
| fitted | 5 | 2 | 3 | 3 | 2 |
| boxy | 2 | 3 | 2 | 3 | 3 |
| fluid | 4 | 4 | 5 | 3 | 4 |
| longline | 4 | 3 | 4 | 4 | 3 |
| cropped | 3 | 4 | 2 | 4 | 2 |
| mini | 3 | 4 | 2 | 4 | 2 |

### Waist Scoring Matrix

| Waist Type | Hourglass | Triangle | Inv. Tri | Rectangle | Oval |
|------------|-----------|----------|----------|-----------|------|
| high-rise | 5 | 5 | 5 | 5 | 5 |
| defined | 5 | 5 | 5 | 5 | 5 |
| mid-rise | 4 | 3 | 4 | 3 | 3 |
| low-rise | 2 | 1 | 2 | 2 | 1 |
| n/a | 2 | 2 | 2 | 2 | 2 |

### Structure Scoring Matrix

| Structure | Hourglass | Triangle | Inv. Tri | Rectangle | Oval |
|-----------|-----------|----------|----------|-----------|------|
| structured | 5 | 3 | 3 | 3 | 2 |
| soft | 3 | 4 | 5 | 3 | 4 |

**Normalization:** `raw / 15`. **Gate:** `* (0.85 + 0.15 * conf)`

V3 uses `max()` across silhouette tags. "defined waist" = 5/5 for ALL shapes.

**V3 Weights:** body 0.35, style 0.35, context 0.20, values 0.10. Novelty 3% tiebreaker.

---

## 5. Shared Scoring Dimensions

**Style Match:** `0.45*vibe + 0.35*silhouette + 0.20*color`. Asymmetric overlap (`0.65*recall + 0.35*precision`).

**Context:** `0.55*season + 0.45*occasion`. Season neighbors + 10x10 occasion affinity matrix.

**Values:** base 0.5. Comfort +0.22/-0.12, Boldness +0.22/-0.10, Sustainability +0.06.

---

## 6. Tag Impact Tiers

| Tier | Tags | Max Score Swing | Used By |
|------|------|----------------|---------|
| Tier 1 (Critical) | silhouette, structure, waist | up to 0.24 pts | V1, V2, V3 body harmony |
| Tier 2 (Important) | vibes, occasion | up to 0.15 pts | style match, context, values |
| Tier 3 (Supporting) | colors, season | up to 0.08 pts | style match, context |

V3 demonstrates highest tag sensitivity due to point-based matrix lookup. Tier 1 tags can swing final scores by up to 0.24 points when silhouette mismatches body shape classification. This explains why silhouette selection is critical in the recommendation pipeline.

---

## 7. Research Validation

- **PAE (2024):** 92.5% F1 for LLM attribute extraction
- **Stitch Fix:** collaborative filtering + mixed-effects
- **Trunk Club:** matrix factorization with WARP loss
- **Zong (2022):** FFIT body shapes from Cornell thesis
- **Golden Ratio:** 1:1.618 proportional splits
- **Goldilocks Principle (PLOS ONE 2014):** moderate color coordination

---

## 8. Architecture Decisions

One universal prompt (v2) serves all algorithms. Products tagged once, scored many times.

**Open decisions:** hem_position field, oval body shape path, human review workflow.
