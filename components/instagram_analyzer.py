from __future__ import annotations

from collections import Counter
from typing import Dict, List

VIBE_KEYWORDS = {
    "minimal": ["minimal", "neutral", "clean", "tailored"],
    "street": ["street", "oversized", "cargo", "sneaker"],
    "feminine": ["dress", "soft", "silk", "romantic"],
    "bold": ["statement", "bold", "sequins", "color"],
    "polished": ["blazer", "work", "structured", "office"],
}

SILHOUETTE_KEYWORDS = {
    "wide-leg": ["wide leg", "trouser"],
    "fitted": ["fitted", "contour", "bodycon"],
    "relaxed": ["relaxed", "oversized"],
    "midi": ["midi"],
    "tailored": ["tailored", "blazer"],
}

COLOR_KEYWORDS = [
    "black",
    "white",
    "cream",
    "navy",
    "olive",
    "grey",
    "camel",
    "burgundy",
    "red",
]


def analyze_captions(captions: List[str]) -> Dict:
    text = " ".join(captions).lower()
    vibe_counts = Counter()
    silhouette_counts = Counter()
    colors = []

    for vibe, words in VIBE_KEYWORDS.items():
        for w in words:
            if w in text:
                vibe_counts[vibe] += 1

    for shape, words in SILHOUETTE_KEYWORDS.items():
        for w in words:
            if w in text:
                silhouette_counts[shape] += 1

    for color in COLOR_KEYWORDS:
        if color in text:
            colors.append(color)

    top_vibes = [v for v, _ in vibe_counts.most_common(3)] or ["minimal"]
    top_silhouettes = [s for s, _ in silhouette_counts.most_common(3)] or ["tailored"]
    top_colors = list(dict.fromkeys(colors))[:4] or ["black", "cream"]

    return {
        "source": "instagram_text_prototype",
        "vibes": top_vibes,
        "silhouettes": top_silhouettes,
        "colors": top_colors,
        "confidence": min(0.9, 0.4 + len(captions) * 0.02),
    }
