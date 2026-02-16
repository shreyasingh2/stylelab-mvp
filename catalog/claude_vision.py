from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from anthropic import Anthropic

from config import (
    TAG_SCHEMA,
    SILHOUETTES_SET,
    WAIST_SET,
    STRUCTURE_SET,
    VIBES_SET,
    OCCASIONS_SET,
    COLORS_SET,
    SEASONS_SET,
)

# ── Prompt + few-shot paths (relative to project root) ─────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROMPT_V2 = _PROJECT_ROOT / "prompts" / "tag_product_vision_v2.txt"
_EXAMPLES_V2 = _PROJECT_ROOT / "prompts" / "tag_product_vision_examples_v2.jsonl"

# ── Legacy inline prompt (v1 fallback) ─────────────────────────────────
_PROMPT_V1_TEMPLATE = """
You are tagging a fashion product for a recommendation engine.
Product name: {name}
Brand: {brand}

Return strict JSON only with keys:
- silhouette (array)
- waist (string)
- structure (string)
- vibes (array)
- occasion (array)
- colors (array)
- season (array)

Use only values from this schema:
{schema}

If uncertain, choose conservative tags and keep arrays short.
""".strip()


def _download_image_b64(image_url: str) -> tuple[str, str]:
    """Download an image and return (base64_data, media_type)."""
    r = requests.get(image_url, timeout=25)
    r.raise_for_status()
    content_type = r.headers.get("Content-Type", "").lower()

    # Detect actual media type from Content-Type header
    if "png" in content_type:
        media_type = "image/png"
    elif "webp" in content_type:
        media_type = "image/webp"
    elif "gif" in content_type:
        media_type = "image/gif"
    elif "jpeg" in content_type or "jpg" in content_type:
        media_type = "image/jpeg"
    elif content_type.startswith("image/"):
        media_type = content_type.split(";")[0].strip()
    else:
        # Fallback: detect from URL extension
        url_lower = image_url.lower()
        if ".png" in url_lower:
            media_type = "image/png"
        elif ".webp" in url_lower:
            media_type = "image/webp"
        elif ".gif" in url_lower:
            media_type = "image/gif"
        else:
            media_type = "image/jpeg"  # safe default

    return base64.b64encode(r.content).decode("utf-8"), media_type


def _load_prompt_v2(name: str, brand: str, product_text: Optional[str] = None) -> str:
    """Load PAE-style system prompt. Allowed values are already inline in the
    prompt file. Appends product context and optional scraped text."""
    base_prompt = _PROMPT_V2.read_text(encoding="utf-8").strip()

    context = (
        f"{base_prompt}\n\n---\n\n"
        f"Product name: {name}\n"
        f"Brand: {brand}"
    )

    # If we have scraped product text, include it as additional context
    # PAE dual-extraction: image + text → fused attributes
    if product_text and product_text.strip():
        context += (
            f"\n\nProduct page text (use to supplement visual observations):\n"
            f"{product_text.strip()[:800]}"
        )

    return context


def _load_few_shot_examples() -> List[Dict[str, Any]]:
    """Load few-shot examples from JSONL → list of user/assistant message pairs.
    PAE finding: clean JSON output only (no reasoning) improves F1."""
    if not _EXAMPLES_V2.exists():
        return []

    examples = []
    for line in _EXAMPLES_V2.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        ex = json.loads(line)
        inp = ex["input"]
        out = ex["output"]

        user_text = (
            f"Generate silhouette, waist, structure, vibes, occasion, colors, "
            f"season, and confidence attributes from the below product.\n"
            f"Product name: {inp['name']}\n"
            f"Brand: {inp['brand']}"
        )

        # Clean JSON only — no reasoning (PAE Prompt 2 style)
        assistant_text = json.dumps(out, indent=2)

        examples.append({"role": "user", "content": user_text})
        examples.append({"role": "assistant", "content": assistant_text})

    return examples


def _validate_tags(result: Dict[str, Any]) -> Dict[str, Any]:
    """Post-extraction schema validation. Filters out any values not in
    the allowed enum sets from config.py. PAE uses catalog matching for this;
    we do it inline since our schema is fixed."""

    # Filter array fields — keep only values in the allowed set
    if "silhouette" in result:
        result["silhouette"] = [s for s in result["silhouette"] if s in SILHOUETTES_SET]
        if not result["silhouette"]:
            result["silhouette"] = ["relaxed"]

    if "vibes" in result:
        result["vibes"] = [v for v in result["vibes"] if v in VIBES_SET]
        if not result["vibes"]:
            result["vibes"] = ["casual"]

    if "occasion" in result:
        result["occasion"] = [o for o in result["occasion"] if o in OCCASIONS_SET]
        if not result["occasion"]:
            result["occasion"] = ["weekend"]

    if "colors" in result:
        result["colors"] = [c for c in result["colors"] if c in COLORS_SET]
        if not result["colors"]:
            result["colors"] = ["black"]

    if "season" in result:
        result["season"] = [s for s in result["season"] if s in SEASONS_SET]
        if not result["season"]:
            result["season"] = ["all"]

    # Validate single-value fields
    if result.get("waist") not in WAIST_SET:
        result["waist"] = "n/a"

    if result.get("structure") not in STRUCTURE_SET:
        result["structure"] = "soft"

    # Clamp confidence
    try:
        conf = float(result.get("confidence", 0.7))
        result["confidence"] = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        result["confidence"] = 0.7

    return result


def tag_product_with_claude(
    name: str,
    brand: str,
    image_url: str,
    *,
    prompt_version: str = "v2",
    product_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Tag a product image using Claude Vision with PAE-inspired prompting.

    Key PAE learnings applied:
    - Prompt 2 format: explicit attribute listing with constrained values (96.8% F1)
    - Temperature 0.2: optimal per PAE Table VI
    - Clean output: no reasoning in few-shot examples (Prompt 3 verbose hurts)
    - Post-extraction validation: filter to allowed enum values
    - Dual extraction: image + product page text fused (PAE Section III)
    - Correct media type detection (not hardcoded JPEG)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for vision tagging.")

    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    client = Anthropic(api_key=api_key)
    image_b64, media_type = _download_image_b64(image_url)

    # ── Build messages based on prompt version ─────────────────────────
    if prompt_version == "v2" and _PROMPT_V2.exists():
        system_prompt = _load_prompt_v2(name, brand, product_text=product_text)
        few_shot = _load_few_shot_examples()

        # Final user message: image + PAE-style generation instruction
        final_user = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"Generate silhouette, waist, structure, vibes, occasion, "
                        f"colors, season, and confidence attributes from the above "
                        f"product image.\n"
                        f"Product name: {name}\n"
                        f"Brand: {brand}\n\n"
                        f"Return JSON only."
                    ),
                },
            ],
        }

        messages = few_shot + [final_user]

        msg = client.messages.create(
            model=model,
            max_tokens=500,
            temperature=0.2,  # PAE Table VI: 0.2 optimal
            system=system_prompt,
            messages=messages,
        )
    else:
        # ── V1 fallback: inline prompt, no few-shot ───────────────────
        prompt = _PROMPT_V1_TEMPLATE.format(
            name=name, brand=brand, schema=json.dumps(TAG_SCHEMA)
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        msg = client.messages.create(
            model=model,
            max_tokens=400,
            temperature=0.2,
            messages=messages,
        )

    # ── Parse response ─────────────────────────────────────────────────
    text = "".join(
        block.text for block in msg.content if getattr(block, "type", "") == "text"
    ).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Claude did not return JSON. Output: {text[:250]}")

    result = json.loads(text[start : end + 1])

    # Strip any reasoning field the model might add
    result.pop("reasoning", None)

    # PAE-inspired: validate all extracted values against schema
    result = _validate_tags(result)

    return result
