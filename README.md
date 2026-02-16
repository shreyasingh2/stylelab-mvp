# StyleLab MVP

A Streamlit MVP for personalized outfit recommendations based on body harmony, personal style, context, and values.

## Run locally

```bash
cd "/Users/shreyasingh/Projects/StyleLab/stylelab-mvp"
python3 -m venv .venv_local
source .venv_local/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

## Claude Vision product tagging pipeline

Input schema (`data/products_raw.json`):
- `id`, `brand`, `name`, `image_urls`, `price_usd`, `product_url`

Required files:
- `prompts/tag_product_vision_v1.txt`
- Optional: `prompts/tag_product_vision_examples_v1.jsonl`

Run:

```bash
cd "/Users/shreyasingh/Projects/StyleLab/stylelab-mvp"
source .venv_local/bin/activate
export ANTHROPIC_API_KEY="..."
python tools/tag_products.py --input data/products_raw.json --output data/products.json
```

This writes `data/products.json` with:
- `tags` (schema from prompt)
- `tag_confidence`
- `tagger` metadata (`model`, `timestamp_utc`, `repair_used`, `status`, etc.)

## App integration

The Results page now supports both formats:
- legacy flattened product fields
- new `tags` object from `tools/tag_products.py`

It auto-normalizes tagged products for scoring and displays `image_url` (or first `image_urls` item).

## Tests

```bash
cd "/Users/shreyasingh/Projects/StyleLab/stylelab-mvp"
source .venv_local/bin/activate
python -m unittest tests/test_tag_products.py
```
