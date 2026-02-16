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
    if not os.getenv("SERPAPI_KEY"):
        return False, "SERPAPI_KEY is not set."
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False, "ANTHROPIC_API_KEY is not set."

    cmd = [
        sys.executable,
        "scripts/build_live_catalog.py",
        "--max-per-brand",
        str(max_per_brand),
        "--out",
        "data/products_live.json",
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

c_photo1, c_photo2 = st.columns(2)
with c_photo1:
    if uploaded:
        image = Image.open(uploaded)
        st.image(image, width=280)
with c_photo2:
    if st.button("Analyze Photo", use_container_width=True):
        if uploaded:
            image = Image.open(uploaded)
            st.session_state.body_profile = analyze_body_from_image(
                uploaded.getvalue(), image.width, image.height
            )
            st.session_state._photo_status = "analyzed"
        else:
            st.session_state._photo_status = ""
            st.warning("Upload a photo first.")

if st.button("Use fallback profile", use_container_width=True):
    st.session_state.body_profile = default_body_profile()
    st.session_state._photo_status = "fallback"

if st.session_state._photo_status in {"analyzed", "fallback"} and st.session_state.get("body_profile"):
    body_profile = st.session_state["body_profile"]
    features = body_profile.get("features", {})
    with c_photo2:
        if st.session_state._photo_status == "analyzed":
            st.success("Photo analyzed.")
        else:
            st.success("Fallback profile applied.")

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

colors = st.multiselect(
    "Core colors",
    ["black", "white", "cream", "navy", "olive", "camel", "grey", "burgundy", "red", "blue", "brown", "beige"],
    default=st.session_state.manual_profile.get("colors") or None,
    placeholder="Choose your core colors...",
)

comfort_first = st.checkbox("Comfort-first", value=st.session_state.manual_profile.get("comfort_first", True))
sustainable = st.checkbox("Sustainability matters", value=st.session_state.manual_profile.get("sustainable", False))
boldness = st.slider(
    "How experimental should recommendations be?",
    min_value=0.0,
    max_value=1.0,
    value=float(st.session_state.manual_profile.get("boldness", 0.5)),
    step=0.05,
)

# Use V3 (FFIT) scoring algorithm by default
algorithm_choice = "v3"

if st.button("Save Preferences", type="primary", use_container_width=True):
    weather_to_season = {
        "cold": "winter",
        "snowy": "winter",
        "cool": "fall",
        "mild": "spring",
        "warm": "summer",
        "hot": "summer",
        "rainy": "spring",
    }

    primary_occasion = occasion_multi[0] if occasion_multi else "weekend"

    st.session_state.manual_profile = {
        "gender": gender,
        "vibes": vibes or ["minimal"],
        "silhouettes": st.session_state.manual_profile.get("silhouettes", ["relaxed"]),
        "colors": colors,
        "categories": categories,
        "location": location,
        "season": weather_to_season.get(weather, "all"),
        "weather": weather,
        "occasion": primary_occasion,
        "occasions": occasion_multi,
        "comfort_first": comfort_first,
        "sustainable": sustainable,
        "boldness": boldness,
    }
    st.success("Preferences saved.")

with st.expander("Refresh Catalog", expanded=False):
    user_vibes = st.session_state.manual_profile.get("vibes", [])
    user_gender = st.session_state.manual_profile.get("gender", "Women")
    if user_vibes:
        st.caption(f"Will search for **{user_gender.lower()}** products matching your vibes: **{', '.join(user_vibes)}**. Save preferences first to update.")
    else:
        st.caption("Save your preferences first so we can tailor the catalog to your vibes.")
    max_per_brand = st.slider("Max products per brand", min_value=3, max_value=20, value=6, step=1)
    if st.button("Refresh Catalog", type="primary", use_container_width=True):
        with st.spinner("Building your personalized catalog — this may take a minute..."):
            ok, msg = _refresh_live_catalog(base_dir, max_per_brand, vibes=user_vibes or None, gender=user_gender)
        if ok:
            st.success("Catalog refreshed with products matching your style.")
            with st.expander("Build log", expanded=False):
                st.code(msg[:5000])
        else:
            st.error("Refresh failed.")
            st.code(msg[:5000])

section_header("3) Recommendations", "Optionally add Instagram context, then generate your top outfits.")
ig_user = st.text_input("Instagram handle (optional)", placeholder="@yourhandle")
ig_text = st.text_area(
    "Paste recent captions (optional)",
    placeholder="Neutral outfit for work day\nWide-leg trousers + blazer today",
    height=100,
)

cig1, cig2 = st.columns(2)
with cig1:
    if st.button("Analyze Instagram Text", use_container_width=True):
        lines = [line.strip() for line in ig_text.splitlines() if line.strip()]
        if lines:
            profile = analyze_captions(lines)
            if ig_user:
                profile["username"] = ig_user
            st.session_state.instagram_profile = profile
            st.success("Instagram style profile added.")
        else:
            st.warning("Add at least one caption line, or skip.")
with cig2:
    if st.button("Skip Instagram", use_container_width=True):
        st.session_state.instagram_profile = {}
        st.info("Instagram skipped.")

if st.button("Get Recommendations", type="primary", use_container_width=True):
    products, products_path = load_catalog(base_dir)
    body = st.session_state.get("body_profile") or default_body_profile()
    instagram = st.session_state.get("instagram_profile") or {}
    manual = st.session_state.get("manual_profile") or {}

    # Filter by garment category if user selected any
    selected_cats = manual.get("categories", [])
    if selected_cats:
        selected_cats_lower = {c.lower() for c in selected_cats}
        products = [p for p in products if p.get("category", "").lower() in selected_cats_lower]

    user_profile = build_user_profile(body=body, instagram=instagram, manual=manual)
    results = rank_products(products, user_profile, top_k=5, algorithm=algorithm_choice)

    st.session_state._results = results
    st.session_state._catalog_name = products_path.name
    st.session_state._algorithm_choice = algorithm_choice

if st.session_state.get("_results"):
    st.subheader("Top 5 Outfits")
    st.caption(f"Catalog: {st.session_state.get('_catalog_name', 'products.json')} | Algorithm: {st.session_state.get('_algorithm_choice', 'v2').upper()}")

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
                st.markdown(f"### {idx}. {p.get('name', 'Item')} ({p.get('brand', 'Brand')})")
                st.write(item["explanation"])
                product_url = p.get("url", "")
                if product_url and "google.com/search" not in product_url:
                    st.markdown(f"[View item]({product_url})")
                if p.get("price"):
                    st.caption(f"Price: {p['price']}")
                st.caption(
                    f"Score {s['total']} | Body {s['body']} | Style {s['style']} | Context {s['context']} | Values {s['values']} | Novelty {s['novelty']}"
                )
