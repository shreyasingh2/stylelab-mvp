from __future__ import annotations

import argparse
import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from anthropic import Anthropic

REQUIRED_TAG_KEYS = [
    "silhouette",
    "waist",
    "structure",
    "vibes",
    "occasion",
    "colors",
    "season",
    "confidence",
]

TAG_ENUMS = {
    "silhouette": {
        "wide-leg",
        "tailored",
        "fitted",
        "relaxed",
        "midi",
        "cropped",
        "longline",
        "defined waist",
        "fluid",
        "mini",
        "maxi",
        "straight",
        "a-line",
        "column",
        "boxy",
        "draped",
    },
    "waist": {"high-rise", "mid-rise", "low-rise", "defined", "n/a"},
    "structure": {"structured", "soft"},
    "vibes": {
        "minimal",
        "polished",
        "feminine",
        "street",
        "bold",
        "classic",
        "casual",
        "cozy",
        "dramatic",
        "night out",
        "evening",
        "workwear",
        "elevated basics",
        "modern",
        "athleisure",
        "romantic",
        "preppy",
        "edgy",
    },
    "occasion": {
        "work",
        "weekend",
        "date",
        "event",
        "travel",
        "party",
        "dinner",
        "vacation",
        "city",
    },
    "season": {"winter", "spring", "summer", "fall", "all"},
}


class ParseError(ValueError):
    pass


class ValidationError(ValueError):
    pass


@dataclass
class ModelResult:
    text: str
    request_id: Optional[str] = None


def _extract_text_response(message: Any) -> str:
    text = "".join(
        block.text for block in message.content if getattr(block, "type", "") == "text"
    ).strip()
    if not text:
        raise ParseError("Model returned empty text response.")
    return text


def parse_json_from_text(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ParseError("No JSON object found in model output.")
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Invalid JSON in model output: {exc}") from exc


def _as_list_of_strings(value: Any, key: str) -> List[str]:
    if not isinstance(value, list):
        raise ValidationError(f"{key} must be a list.")
    cleaned: List[str] = []
    for x in value:
        if not isinstance(x, str):
            raise ValidationError(f"{key} must contain only strings.")
        cleaned.append(x.strip().lower())
    return [c for c in cleaned if c]


def validate_and_normalize_tags(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = [k for k in REQUIRED_TAG_KEYS if k not in payload]
    if missing:
        raise ValidationError(f"Missing required keys: {missing}")

    out: Dict[str, Any] = {}

    out["silhouette"] = _as_list_of_strings(payload["silhouette"], "silhouette")
    out["vibes"] = _as_list_of_strings(payload["vibes"], "vibes")
    out["occasion"] = _as_list_of_strings(payload["occasion"], "occasion")
    out["colors"] = _as_list_of_strings(payload["colors"], "colors")
    out["season"] = _as_list_of_strings(payload["season"], "season")

    waist = str(payload["waist"]).strip().lower()
    structure = str(payload["structure"]).strip().lower()
    confidence = float(payload["confidence"])

    out["waist"] = waist
    out["structure"] = structure
    out["confidence"] = max(0.0, min(1.0, confidence))

    for key, allowed in TAG_ENUMS.items():
        value = out[key]
        if isinstance(value, list):
            invalid = [v for v in value if v not in allowed and key != "colors"]
            if invalid:
                raise ValidationError(f"Invalid enum values for {key}: {invalid}")
        else:
            if value not in allowed:
                raise ValidationError(f"Invalid enum value for {key}: {value}")

    if not out["silhouette"]:
        raise ValidationError("silhouette cannot be empty.")
    if not out["vibes"]:
        raise ValidationError("vibes cannot be empty.")
    if not out["occasion"]:
        raise ValidationError("occasion cannot be empty.")
    if not out["season"]:
        raise ValidationError("season cannot be empty.")

    return out


def _download_image_as_base64(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        if not content_type.startswith("image/"):
            return None
        return base64.b64encode(resp.content).decode("utf-8")
    except Exception:
        return None


def _normalize_image_urls(product: Dict[str, Any]) -> List[str]:
    urls = product.get("image_urls", [])
    if isinstance(urls, str):
        urls = [urls]
    if not isinstance(urls, list):
        return []
    cleaned = []
    for u in urls:
        if isinstance(u, str) and u.strip().startswith("http"):
            cleaned.append(u.strip())
    return cleaned[:3]


def _load_examples_text(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    lines = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        lines.append(raw)
    if not lines:
        return ""
    return "\nExamples (JSONL):\n" + "\n".join(lines)


def _fallback_tags() -> Dict[str, Any]:
    return {
        "silhouette": ["relaxed"],
        "waist": "n/a",
        "structure": "soft",
        "vibes": ["casual"],
        "occasion": ["weekend"],
        "colors": ["black"],
        "season": ["all"],
        "confidence": 0.25,
    }


def _call_vision(
    client: Anthropic,
    model: str,
    prompt_text: str,
    product: Dict[str, Any],
    examples_text: str,
    image_urls: List[str],
) -> ModelResult:
    content: List[Dict[str, Any]] = []

    for url in image_urls[:3]:
        image_b64 = _download_image_as_base64(url)
        if not image_b64:
            continue
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_b64,
                },
            }
        )

    context = (
        f"Brand: {product.get('brand', '')}\n"
        f"Name: {product.get('name', '')}\n"
        f"Product URL: {product.get('product_url', '')}\n"
        f"Price USD: {product.get('price_usd', '')}\n"
        f"Image URLs used: {image_urls[:3]}\n"
    )

    content.append(
        {
            "type": "text",
            "text": prompt_text + "\n\n" + context + examples_text,
        }
    )

    msg = client.messages.create(
        model=model,
        max_tokens=700,
        temperature=0.0,
        messages=[{"role": "user", "content": content}],
    )
    return ModelResult(text=_extract_text_response(msg), request_id=getattr(msg, "id", None))


def _call_repair(
    client: Anthropic,
    model: str,
    previous_output: str,
    validation_error: str,
) -> ModelResult:
    repair_prompt = (
        "Your previous response was invalid. Return JSON only, no prose, no markdown. "
        "Match the required schema and enum values exactly.\n"
        f"Validation/parse error: {validation_error}\n\n"
        "Previous output:\n"
        f"{previous_output}"
    )
    msg = client.messages.create(
        model=model,
        max_tokens=700,
        temperature=0.0,
        messages=[{"role": "user", "content": [{"type": "text", "text": repair_prompt}]}],
    )
    return ModelResult(text=_extract_text_response(msg), request_id=getattr(msg, "id", None))


def tag_product(
    product: Dict[str, Any],
    client: Anthropic,
    model: str,
    prompt_text: str,
    examples_text: str,
) -> Dict[str, Any]:
    image_urls = _normalize_image_urls(product)
    vision_res = _call_vision(client, model, prompt_text, product, examples_text, image_urls)

    repair_used = False
    repaired_successfully = False
    last_error = ""
    raw_text = vision_res.text

    try:
        parsed = parse_json_from_text(raw_text)
        tags = validate_and_normalize_tags(parsed)
    except (ParseError, ValidationError) as exc:
        repair_used = True
        last_error = str(exc)
        repair_res = _call_repair(client, model, raw_text, last_error)
        raw_text = repair_res.text
        try:
            parsed = parse_json_from_text(raw_text)
            tags = validate_and_normalize_tags(parsed)
            repaired_successfully = True
            last_error = ""
        except (ParseError, ValidationError) as second_exc:
            tags = _fallback_tags()
            last_error = f"repair_failed: {second_exc}"

    enriched = dict(product)
    enriched["tags"] = {
        "silhouette": tags["silhouette"],
        "waist": tags["waist"],
        "structure": tags["structure"],
        "vibes": tags["vibes"],
        "occasion": tags["occasion"],
        "colors": tags["colors"],
        "season": tags["season"],
    }
    enriched["tag_confidence"] = tags["confidence"]
    enriched["tagger"] = {
        "provider": "anthropic",
        "model": model,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "image_count": min(3, len(image_urls)),
        "repair_used": repair_used,
        "status": (
            "ok_with_repair"
            if repaired_successfully
            else ("ok" if not last_error else "fallback")
        ),
        "error": last_error,
    }
    return enriched


def run_pipeline(
    input_path: Path,
    output_path: Path,
    prompt_path: Path,
    examples_path: Optional[Path],
    model: str,
    client: Optional[Anthropic] = None,
) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    products = json.loads(input_path.read_text())
    if not isinstance(products, list):
        raise ValueError("Input must be a JSON list of products.")

    prompt_text = prompt_path.read_text()
    examples_text = _load_examples_text(examples_path)

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if client is None:
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY is required.")
        client = Anthropic(api_key=anthropic_key)

    out: List[Dict[str, Any]] = []
    for product in products:
        out.append(tag_product(product, client, model, prompt_text, examples_text))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Tag products with Claude Vision.")
    parser.add_argument("--input", default="data/products_raw.json")
    parser.add_argument("--output", default="data/products.json")
    parser.add_argument("--prompt", default="prompts/tag_product_vision_v1.txt")
    parser.add_argument(
        "--examples",
        default="prompts/tag_product_vision_examples_v1.jsonl",
        help="Optional JSONL examples file",
    )
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"))
    args = parser.parse_args()

    examples_path = Path(args.examples)
    if not examples_path.exists():
        examples_path = None

    run_pipeline(
        input_path=Path(args.input),
        output_path=Path(args.output),
        prompt_path=Path(args.prompt),
        examples_path=examples_path,
        model=args.model,
    )


if __name__ == "__main__":
    main()
