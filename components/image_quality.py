from __future__ import annotations

from io import BytesIO
from functools import lru_cache

import requests
from PIL import Image


@lru_cache(maxsize=512)
def is_low_color_or_low_res_image(url: str) -> bool:
    """
    Returns True when image appears unsuitable for product display:
    - too small
    - likely grayscale/low-color
    """
    if not url:
        return True

    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception:
        return True

    w, h = img.size
    if w < 380 or h < 380:
        return True

    # Downsample for fast colorfulness check
    img = img.resize((128, 128))
    px = list(img.getdata())

    n = len(px)
    if n == 0:
        return True

    # Mean channel spread; grayscale images have very low spread.
    spread_sum = 0.0
    for r, g, b in px:
        spread_sum += max(r, g, b) - min(r, g, b)
    mean_spread = spread_sum / n

    # Conservative threshold: keep normal product photos, drop mostly monochrome.
    return mean_spread < 14.0
