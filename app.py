from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from PIL import Image

from components.body_analysis import analyze_body_from_image, default_body_profile
from components.product_catalog import load_catalog
from components.profile_builder import build_user_profile
from components.instagram_analyzer import analyze_captions
from components.ui_theme import apply_theme, hero_block, section_header, top_nav, render_stepper
from scoring.recommendation_engine import rank_products

st.set_page_config(page_title="StyleLab MVP", page_icon="✨", layout="wide")
apply_theme()
st.markdown(
    """
    <style>
      [data-testid="stSidebarNav"] { display: none !important; }
      section[data-testid="stSidebar"] { display: none !important; }
      [data-testid="collapsedControl"] { display: none !important; }
      header[data-testid="stHeader"] { display: none !important; }
      [data-testid="stToolbar"] { display: none !important; }
      [data-testid="stDecoration"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

for key, default in {
    "body_profile": {},
    "instagram_profile": {},
    "manual_profile": {},
    "_results": [],
    "_catalog_name": "",
    "_algorithm_choice": "v3",
    "_photo_status": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

base_dir = Path(__file__).resolve().parent


def _refresh_live_catalog(
    project_root: Path,
    max_per_brand: int,
    vibes: list[str] | None = None,
    gender: str = "Women",
) -> tuple[bool, str]:
    """Blocking catalog refresh (used by Force Refresh button)."""
    if not os.getenv("SERPAPI_KEY"):
        return False, "SERPAPI_KEY is not set."
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False, "ANTHROPIC_API_KEY is not set."
    cmd = [
        sys.executable,
        str(project_root / "scripts" / "build_live_catalog.py"),
        "--max-per-brand",
        str(max_per_brand),
        "--out",
        str(project_root / "data" / "products_live.json"),
        "--gender",
        gender.lower(),
    ]
    if vibes:
        cmd += ["--vibes"] + vibes
    proc = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True, check=False)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode != 0:
        return False, output.strip() or f"Build failed with code {proc.returncode}"
    return True, output.strip() or "Catalog refreshed."


top_nav()

photo_done = bool(st.session_state.body_profile)
prefs_done = bool(st.session_state.manual_profile.get("vibes")) and bool(
    st.session_state.manual_profile.get("occasion")
)
results_done = bool(st.session_state._results)

render_stepper(photo_done, prefs_done, results_done)
hero_block()

section_header("1) Share Your Photo", "Upload a full-body photo so we can analyze your proportions.")
uploaded = st.file_uploader("Drop your photo here", type=["jpg", "jpeg", "png"])

# Auto-analyze when a new photo is uploaded
if uploaded:
    # Track which file we've already analyzed to avoid re-running on every rerun
    upload_id = f"{uploaded.name}_{uploaded.size}"
    if st.session_state.get("_last_upload_id") != upload_id:
        image = Image.open(uploaded)
        try:
            st.session_state.body_profile = analyze_body_from_image(
                uploaded.getvalue(), image.width, image.height
            )
            st.session_state._photo_status = "analyzed"
        except Exception:
            st.session_state.body_profile = default_body_profile()
            st.session_state._photo_status = "fallback"
        st.session_state["_last_upload_id"] = upload_id

c_photo1, c_photo2 = st.columns(2)
with c_photo1:
    if uploaded:
        image = Image.open(uploaded)
        st.image(image, width=280)
    if st.button("Use default profile instead", use_container_width=True):
        st.session_state.body_profile = default_body_profile()
        st.session_state._photo_status = "fallback"
        st.session_state["_last_upload_id"] = None
        st.rerun()

with c_photo2:
    if st.session_state._photo_status in {"analyzed", "fallback"} and st.session_state.get("body_profile"):
        body_profile = st.session_state["body_profile"]
        features = body_profile.get("features", {})
        if st.session_state._photo_status == "analyzed":
            st.success("Photo analyzed.")
        else:
            st.success("Default profile applied.")

        bullets = [
            f"- Proportion signal: **{body_profile.get('proportion_signal', 'n/a').title()}**",
            f"- Line harmony: **{body_profile.get('line_harmony', 'n/a').title()}**",
            f"- Shoulder/Hip balance: **{body_profile.get('shoulder_hip_balance', 'n/a').replace('_', ' ').title()}**",
            f"- Torso/Leg ratio: **{float(body_profile.get('torso_leg_ratio', 0.0)):.3f}**",
            f"- Confidence: **{float(body_profile.get('confidence', 0.0)):.3f}**",
        ]
        if features:
            bullets.extend(
                [
                    f"- Body aspect ratio: **{float(features.get('body_aspect_ratio', 0.0)):.3f}**",
                    f"- Shoulder/Hip ratio: **{float(features.get('shoulder_hip_ratio', 0.0)):.3f}**",
                    f"- Joint softness: **{float(features.get('joint_softness', 0.0)):.3f}**",
                ]
            )
        st.markdown("\n".join(bullets))

        if uploaded and st.button("Re-analyze photo"):
            image = Image.open(uploaded)
            try:
                st.session_state.body_profile = analyze_body_from_image(
                    uploaded.getvalue(), image.width, image.height
                )
                st.session_state._photo_status = "analyzed"
            except Exception:
                st.session_state.body_profile = default_body_profile()
                st.session_state._photo_status = "fallback"
            st.rerun()

section_header("2) Your Style Preferences", "Pick your vibe, occasion, weather, and core colors.")

gender_options = ["Women", "Men", "Unisex"]
default_gender = st.session_state.manual_profile.get("gender", "Women")
if default_gender not in gender_options:
    default_gender = "Women"
gender = st.selectbox("Shopping for", gender_options, index=gender_options.index(default_gender))

vibe_options = [
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
]

vibes = st.multiselect(
    "What's your vibe? (select multiple)",
    vibe_options,
    default=st.session_state.manual_profile.get("vibes") or None,
    placeholder="Choose your style vibes...",
)

occasion_options = ["work", "weekend", "date", "night out", "event", "travel", "party", "dinner", "vacation", "city"]
occasion_multi = st.multiselect(
    "What do you dress for? (select multiple)",
    occasion_options,
    default=st.session_state.manual_profile.get("occasions") or None,
    placeholder="Choose occasions...",
)

col_a, col_b = st.columns(2)
with col_a:
    weather_options = ["cold", "cool", "mild", "warm", "hot", "rainy", "snowy"]
    default_weather = st.session_state.manual_profile.get("weather", "cool")
    if default_weather not in weather_options:
        default_weather = "cool"
    weather = st.selectbox("Weather", weather_options, index=weather_options.index(default_weather))
with col_b:
    location_options = ["Urban City", "Suburban", "Coastal", "Tropical", "Cold Climate", "Mediterranean"]
    default_loc = st.session_state.manual_profile.get("location", "Urban City")
    if default_loc not in location_options:
        default_loc = "Urban City"
    location = st.selectbox("Where do you live?", location_options, index=location_options.index(default_loc))

category_options = ["dress", "top", "bottom", "outerwear", "jumpsuit", "skirt", "knitwear"]
categories = st.multiselect(
    "What are you looking for? (optional — leave blank for all)",
    category_options,
    default=st.session_state.manual_profile.get("categories") or None,
    placeholder="e.g. dress, top, pants...",
)

brand_options = ["Reformation", "Aritzia", "Motel Rocks", "Princess Polly"]
preferred_brands = st.multiselect(
    "Preferred brands (optional — leave blank for all)",
    brand_options,
    default=st.session_state.manual_profile.get("preferred_brands") or None,
    placeholder="e.g. Reformation, Aritzia...",
)

colors = st.multiselect(
    "Core colors",
    ["black", "white", "cream", "navy", "olive", "camel", "grey", "burgundy", "red", "blue", "brown", "beige"],
    default=st.session_state.manual_profile.get("colors") or None,
    placeholder="Choose your core colors...",
)

boldness = 0.5  # Fixed default — no longer exposed in UI

# Use V3 (FFIT) scoring algorithm by default
algorithm_choice = "v3"

# Weather → season mapping (used when saving preferences)
_WEATHER_TO_SEASON = {
    "cold": "winter", "snowy": "winter", "cool": "fall",
    "mild": "spring", "warm": "summer", "hot": "summer", "rainy": "spring",
}

with st.expander("Refresh Catalog", expanded=False):
    st.caption(
        "Fetch fresh products from Google Shopping and tag them with AI. "
        "Requires SERPAPI_KEY and ANTHROPIC_API_KEY in your .env file."
    )
    if st.button("Refresh Catalog", use_container_width=True):
        user_vibes = vibes or ["minimal", "polished", "feminine", "casual", "classic"]
        with st.spinner("Refreshing catalog — this may take a minute..."):
            ok, msg = _refresh_live_catalog(base_dir, 3, vibes=user_vibes, gender=gender)
        if ok:
            st.success("Catalog refreshed.")
            with st.expander("Build log", expanded=False):
                st.code(msg[:5000])
        else:
            st.error("Refresh failed.")
            st.code(msg[:5000])

section_header("3) Recommendations", "Generate your top outfit picks.")

ig_handle = st.text_input("Instagram handle (optional)", placeholder="@yourhandle")

if st.button("Get Recommendations", type="primary", use_container_width=True):
    # If user provided an Instagram handle, store it
    if ig_handle:
        st.session_state.instagram_profile = {"username": ig_handle}
    # Auto-save preferences from current widget values
    primary_occ = occasion_multi[0] if occasion_multi else "weekend"
    st.session_state.manual_profile = {
        "gender": gender,
        "vibes": vibes or ["minimal"],
        "silhouettes": st.session_state.manual_profile.get("silhouettes", ["relaxed"]),
        "colors": colors,
        "categories": categories,
        "preferred_brands": preferred_brands,
        "location": location,
        "season": _WEATHER_TO_SEASON.get(weather, "all"),
        "weather": weather,
        "occasion": primary_occ,
        "occasions": occasion_multi,
        "boldness": boldness,
    }

    manual = st.session_state.manual_profile
    products, products_path = load_catalog(base_dir)
    body = st.session_state.get("body_profile") or default_body_profile()
    instagram = st.session_state.get("instagram_profile") or {}

    # Filter by garment category if user selected any
    selected_cats = manual.get("categories", [])
    if selected_cats:
        selected_cats_lower = {c.lower() for c in selected_cats}
        products = [p for p in products if p.get("category", "").lower() in selected_cats_lower]

    # Filter by preferred brands if user selected any
    sel_brands = manual.get("preferred_brands", [])
    if sel_brands:
        sel_brands_lower = {b.lower() for b in sel_brands}
        products = [p for p in products if p.get("brand", "").lower() in sel_brands_lower]

    user_profile = build_user_profile(body=body, instagram=instagram, manual=manual)
    results = rank_products(products, user_profile, top_k=5, algorithm=algorithm_choice)

    st.session_state._results = results
    st.session_state._catalog_name = products_path.name
    st.session_state._algorithm_choice = algorithm_choice

if st.session_state.get("_results"):
    st.subheader("Your Top Picks")

    for idx, item in enumerate(st.session_state._results, start=1):
        p = item["product"]
        s = item["scores"]
        with st.container(border=True):
            left, right = st.columns([1, 2])
            with left:
                if p.get("image_url"):
                    st.image(p["image_url"], width=320)
                else:
                    st.info("No image available")
            with right:
                st.markdown(f"### {idx}. {p.get('name', 'Item')}")
                st.caption(p.get("brand", ""))
                st.write(item["explanation"])
                product_url = p.get("url", "")
                if product_url and "google.com/search" not in product_url:
                    st.markdown(f"[View item]({product_url})")
                if p.get("price"):
                    st.caption(f"💰 {p['price']}")
                with st.expander("Score breakdown", expanded=False):
                    st.caption(
                        f"Total {s['total']} · Body {s['body']} · Style {s['style']} "
                        f"· Context {s['context']} · Values {s['values']} · Novelty {s['novelty']}"
                    )
