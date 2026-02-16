from __future__ import annotations

from typing import Dict, List


# ── Vibe → silhouette inference ──────────────────────────────────────
# When the user hasn't explicitly picked silhouettes, we infer likely
# silhouette preferences from their selected vibes. Each vibe maps to
# the silhouettes most commonly associated with that aesthetic.
VIBE_SILHOUETTE_MAP: Dict[str, List[str]] = {
    "minimal": ["tailored", "straight", "column"],
    "polished": ["tailored", "fitted", "defined waist"],
    "feminine": ["a-line", "midi", "defined waist", "fluid"],
    "street": ["wide-leg", "boxy", "relaxed"],
    "bold": ["wide-leg", "maxi", "fitted"],
    "classic": ["tailored", "straight", "a-line"],
    "casual": ["relaxed", "straight", "wide-leg"],
    "cozy": ["relaxed", "boxy", "longline"],
    "dramatic": ["maxi", "wide-leg", "draped", "column"],
    "night out": ["mini", "fitted", "defined waist"],
    "evening": ["midi", "maxi", "fitted", "column"],
    "workwear": ["tailored", "straight", "midi"],
    "elevated basics": ["tailored", "straight", "relaxed"],
    "modern": ["column", "wide-leg", "draped", "boxy"],
    "athleisure": ["fitted", "straight", "cropped"],
    "romantic": ["midi", "fluid", "a-line", "draped"],
    "preppy": ["tailored", "a-line", "midi", "straight"],
    "edgy": ["fitted", "straight", "cropped", "boxy"],
}


def _infer_silhouettes_from_vibes(vibes: List[str]) -> List[str]:
    """Derive likely silhouette preferences from the user's vibe selections.
    Returns a deduplicated list capped at 5 items."""
    seen = set()
    silhouettes = []
    for vibe in vibes:
        for sil in VIBE_SILHOUETTE_MAP.get(vibe, []):
            if sil not in seen:
                seen.add(sil)
                silhouettes.append(sil)
    return silhouettes[:5] or ["relaxed"]


def build_user_profile(body: Dict, instagram: Dict, manual: Dict) -> Dict:
    # Merge silhouettes from Instagram + manual input
    explicit_silhouettes = sorted(
        set((instagram.get("silhouettes") or []) + (manual.get("silhouettes") or []))
    )[:5]

    # Merge vibes from Instagram + manual
    vibes = sorted(
        set((instagram.get("vibes") or []) + (manual.get("vibes") or []))
    )[:5]

    # If no explicit silhouettes, infer from vibes
    if not explicit_silhouettes or explicit_silhouettes == ["relaxed"]:
        silhouettes = _infer_silhouettes_from_vibes(vibes)
    else:
        silhouettes = explicit_silhouettes

    style = {
        "vibes": vibes,
        "silhouettes": silhouettes,
        "colors": sorted(
            set((instagram.get("colors") or []) + (manual.get("colors") or []))
        )[:6],
    }

    context = {
        "location": manual.get("location", "Unknown"),
        "season": manual.get("season", "all"),
        "occasion": manual.get("occasion", "weekend"),
    }

    values = {
        "comfort_first": manual.get("comfort_first", True),
        "sustainable": manual.get("sustainable", False),
        "boldness": manual.get("boldness", 0.5),
    }

    return {
        "body": body,
        "style": style,
        "context": context,
        "values": values,
    }
