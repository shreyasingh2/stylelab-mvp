from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.tag_products import (
    ModelResult,
    ValidationError,
    parse_json_from_text,
    tag_product,
    validate_and_normalize_tags,
)


class TagProductsTests(unittest.TestCase):
    def test_parse_json_from_wrapped_text(self) -> None:
        text = 'Here is output: {"silhouette":["tailored"],"waist":"defined","structure":"structured","vibes":["polished"],"occasion":["work"],"colors":["black"],"season":["all"],"confidence":0.8} Thanks.'
        parsed = parse_json_from_text(text)
        self.assertEqual(parsed["waist"], "defined")
        self.assertEqual(parsed["silhouette"], ["tailored"])

    def test_enum_validation_rejects_invalid_values(self) -> None:
        payload = {
            "silhouette": ["spacecore"],
            "waist": "defined",
            "structure": "structured",
            "vibes": ["polished"],
            "occasion": ["work"],
            "colors": ["black"],
            "season": ["all"],
            "confidence": 0.7,
        }
        with self.assertRaises(ValidationError):
            validate_and_normalize_tags(payload)

    @patch("tools.tag_products._call_repair")
    @patch("tools.tag_products._call_vision")
    def test_retry_repair_behavior(self, mock_vision, mock_repair) -> None:
        mock_vision.return_value = ModelResult(text="not json")
        mock_repair.return_value = ModelResult(
            text='{"silhouette":["tailored"],"waist":"defined","structure":"structured","vibes":["polished"],"occasion":["work"],"colors":["black"],"season":["all"],"confidence":0.88}'
        )

        product = {
            "id": "p1",
            "brand": "Aritzia",
            "name": "Relaxed Blazer",
            "image_urls": ["https://example.com/a.jpg"],
            "price_usd": 148.0,
            "product_url": "https://example.com/product",
        }

        tagged = tag_product(
            product=product,
            client=None,
            model="claude-3-5-sonnet-latest",
            prompt_text="prompt",
            examples_text="",
        )

        self.assertTrue(tagged["tagger"]["repair_used"])
        self.assertEqual(tagged["tagger"]["status"], "ok_with_repair")
        self.assertEqual(tagged["tags"]["silhouette"], ["tailored"])


if __name__ == "__main__":
    unittest.main()
