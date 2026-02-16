# StyleLab MVP

Streamlit app for personalized outfit recommendations based on body harmony, personal style, context, and values.

## Running the app

```bash
cd "/Users/shreyasingh/Projects/StyleLab/stylelab-mvp"
source .venv_local/bin/activate
streamlit run app.py
```

If the venv doesn't exist yet, create it first:

```bash
python3 -m venv .venv_local
source .venv_local/bin/activate
pip install -r requirements.txt
```

## Environment variables

The app loads from `.env` via `python-dotenv`. Make sure `.env` exists with the following keys set:

- `ANTHROPIC_API_KEY` — used for Claude Vision body analysis and product tagging
- `SERPAPI_KEY` — used for Google Shopping product discovery

## Building the product catalog

The catalog is built from user-selected vibes. From the app UI, click "Refresh Catalog" in the expander. Or run manually:

```bash
source .venv_local/bin/activate
python scripts/build_live_catalog.py --vibes minimal polished --max-per-brand 8
```

Tag raw products with Claude Vision (legacy):

```bash
python tools/tag_products.py --input data/products_raw.json --output data/products.json
```

## Tests

```bash
source .venv_local/bin/activate
python -m pytest tests/
```

## Architecture overview

The app follows a three-stage pipeline: **Discover** products, **Score** them against a user profile, and **Rank** the results.

### Data flow

```
User selects vibes/preferences
        |
        v
  [Catalog Builder]  scripts/build_live_catalog.py
    1. Vibes -> search keywords  (VIBE_KEYWORDS mapping)
    2. SerpAPI Google Shopping    (catalog/web_crawler.py)
    3. Claude Vision tagging     (catalog/claude_vision.py)
    4. Output -> data/products_live.json
        |
        v
  [Profile Builder]  components/profile_builder.py
    Merges body analysis + Instagram + manual preferences
    Infers silhouettes from vibes when not explicitly set
        |
        v
  [Scoring Engine]   scoring/recommendation_engine.py
    For each product:
      Body harmony   (35%) — silhouette/waist/structure vs body shape
      Style match    (35%) — vibe/silhouette/color overlap (recall-weighted)
      Context fit    (20%) — season + occasion affinity
      Values         (10%) — comfort, boldness, sustainability
    Novelty used as tie-breaker (3%)
        |
        v
  [Ranked Results]   Top 5 shown with explanations
```

### Project structure

```
app.py                          — Single-page Streamlit entrypoint (3-step flow)
config.py                       — Single source of truth: all enums, weights, defaults

components/
  body_analysis.py              — MediaPipe pose estimation -> body proportions
  profile_builder.py            — Merges inputs into unified user profile
  product_catalog.py            — Loads, validates, normalizes product catalogs
  instagram_analyzer.py         — Keyword-based caption analysis (prototype)
  ui_theme.py                   — Custom Streamlit CSS theme + UI components

scoring/
  recommendation_engine.py      — Orchestrates scoring, ranking, explanation generation
  body_harmony.py               — V1 (rules), V2 (continuous), V3 (FFIT point-based)
  style_match.py                — Asymmetric overlap for vibes/silhouettes/colors
  context_values.py             — Season neighbors, occasion affinity matrix, values

catalog/
  web_crawler.py                — SerpAPI Shopping + organic search, page scraping
  claude_vision.py              — Claude Vision product attribute extraction (PAE-inspired)

scripts/
  build_live_catalog.py         — CLI to discover + tag products (vibe-driven keywords)

prompts/
  tag_product_vision_v2.txt     — Claude Vision system prompt with attribute definitions
  tag_product_vision_examples_v2.jsonl — Few-shot examples for consistent tagging

data/
  products.json                 — Static fallback catalog (30 Aritzia items)
  products_live.json            — Dynamically built catalog (from web crawl + vision)

tests/
  test_scoring.py               — Scoring engine unit tests
  test_tag_products.py          — Product tagging tests

pages/                          — Legacy multi-page screens (no longer used, kept for reference)
```

### Scoring algorithms

All three versions are available via the UI dropdown. V3 is recommended.

- **V1**: Original rule-based body scoring with discrete proportion signals. Includes novelty as a scored dimension (5% weight).
- **V2**: Continuous body ratios with FFIT-style reasoning. Synonym-aware style matching. Novelty as small bonus (5%).
- **V3** (recommended): Point-based body scoring from Zong (2022) FFIT thesis. Lookup matrices map body shape x garment attribute -> 1-5 score. Novelty is only a tie-breaker (3%). Weights: body=0.35, style=0.35, context=0.20, values=0.10.

### Key design decisions

- **config.py as single source of truth**: All tag enums, scoring weights, and constants live in one place. Every module imports from config rather than defining its own lists.
- **Asymmetric overlap for style matching**: Products are judged by how much of the user's taste they satisfy (recall), not penalized for having extra tags. Recall denominator is capped at 3 so users who select many vibes aren't penalized.
- **Vibe-to-silhouette inference**: When users haven't explicitly picked silhouettes, we infer them from vibes (e.g., "minimal" -> tailored, straight, column). This keeps the UI simple while still using silhouette data in scoring.
- **PAE-inspired Claude Vision tagging**: Uses findings from the Product Attribute Extraction paper — temperature 0.2, clean JSON output (no reasoning), few-shot examples, post-extraction validation against config enums, and dual extraction (image + scraped product text).
