# StyleLab Ranking Algorithm (Cofounder Brief)

## Objective
Rank clothing items so recommendations fit the user's body signals, style preferences, real-life context, and values, while allowing small style expansion.

## Final Score
`Final Score = 0.35*Body + 0.30*Style + 0.20*Context + 0.10*Values + 0.05*Novelty`

Source: `scoring/recommendation_engine.py`

## Component Definitions

### 1) Body Harmony (35%)
Uses MediaPipe-derived user signals:
- `proportion_signal`
- `torso_leg_ratio`
- `shoulder_hip_balance`
- `line_harmony`

Compares against product attributes:
- `silhouette`
- `waist`
- `structure`

Logic is rule-based with positive/negative adjustments and clamp to `[0,1]`.

Source: `scoring/body_harmony.py`

### 2) Style Match (30%)
Compares overlap between user and product tags:
- `vibes`
- `silhouettes`
- `colors`

Uses weighted overlap and neutral defaults when user profile is sparse.

Source: `scoring/style_match.py`

### 3) Context Fit (20%)
Scores:
- Season compatibility (including adjacent-season partial credit)
- Occasion compatibility (including partial cross-occasion credit)

Not binary; graded to avoid brittle ranking.

Source: `scoring/context_values.py`

### 4) Values Fit (10%)
Aligns product with preferences:
- `comfort_first`
- `sustainable`
- `boldness`

Uses product vibes and structure to adjust score.

Source: `scoring/context_values.py`

### 5) Novelty (5%)
Encourages gentle expansion from existing style.
- Higher when item vibes are less overlapping with user vibes
- Capped when core fit (Body+Style+Context avg) is weak

Source: `scoring/recommendation_engine.py`

## Ranking Pipeline
1. Load product catalog (prefer `data/products_live.json` if non-empty, else `data/products.json`)
2. Normalize product schema for scoring compatibility
3. Build user profile from body + manual + optional Instagram inputs
4. Score each product using the 5-component formula
5. Sort descending by total score
6. Return top N recommendations

Sources:
- `components/product_catalog.py`
- `components/profile_builder.py`
- `scoring/recommendation_engine.py`

## Body Feature Extraction Pipeline
MediaPipe extracts geometric features:
- `body_aspect_ratio`
- `torso_leg_ratio`
- `shoulder_hip_ratio`
- `joint_softness`

These are mapped to scoring signals:
- `proportion_signal`
- `shoulder_hip_balance`
- `line_harmony`
- `confidence`

Source: `components/body_analysis.py`

## Product Tagging Pipeline (Claude Vision)
Inputs per product:
- `id`, `brand`, `name`, `image_urls` (up to 3 used), `price_usd`, `product_url`

Process:
1. Send images + product context to Claude Vision
2. Parse JSON response
3. Validate keys + enum values
4. If invalid, one repair retry using prior model output
5. Store `tags`, `tag_confidence`, and `tagger` metadata

Command:
`python tools/tag_products.py --input data/products_raw.json --output data/products.json`

Source: `tools/tag_products.py`

## Practical Notes
- Instagram input is optional; manual profile alone is sufficient.
- Live crawl/tag data can be slow; use smaller batch sizes for quick iteration.
- If live catalog is empty, app falls back to local catalog.
