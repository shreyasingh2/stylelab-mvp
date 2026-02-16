from pathlib import Path
import os
import subprocess
import sys

import streamlit as st

from components.body_analysis import default_body_profile
from components.product_catalog import load_catalog
from components.profile_builder import build_user_profile
from scoring.recommendation_engine import rank_products

st.set_page_config(page_title="Results", page_icon="🎯", layout="wide")
st.title("4) Your Recommendations")

base_dir = Path(__file__).resolve().parent.parent


def _refresh_live_catalog(project_root: Path, max_per_brand: int) -> tuple[bool, str]:
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
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)

    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode != 0:
        return False, output.strip() or f"Build failed with code {proc.returncode}"
    return True, output.strip() or "Catalog refreshed."


with st.expander("Live Catalog (Web Crawl + Claude Vision)", expanded=False):
    st.caption(
        "Pulls products from Aritzia, Princess Polly, Motel Rocks, and Reformation, then tags with Claude Vision."
    )
    max_per_brand = st.slider("Max products per brand", min_value=3, max_value=25, value=8, step=1)
    if st.button("Refresh Catalog Now", type="primary", use_container_width=True):
        with st.spinner("Crawling brand sites and tagging with Claude Vision..."):
            ok, message = _refresh_live_catalog(base_dir, max_per_brand)
        if ok:
            st.success("Live catalog refreshed.")
            if message:
                st.code(message[:6000])
            st.rerun()
        else:
            st.error("Catalog refresh failed.")
            if message:
                st.code(message[:6000])

products, products_path = load_catalog(base_dir)

body = st.session_state.get("body_profile") or default_body_profile()
instagram = st.session_state.get("instagram_profile") or {}
manual = st.session_state.get("manual_profile") or {}

user_profile = build_user_profile(body=body, instagram=instagram, manual=manual)
results = rank_products(products, user_profile, top_k=15)

st.caption(f"Catalog source: {products_path.name}")

st.subheader("Top 5 Outfits for You")
for idx, item in enumerate(results[:5], start=1):
    p = item["product"]
    s = item["scores"]

    with st.container(border=True):
        c1, c2 = st.columns([1, 2])

        with c1:
            if p.get("image_url"):
                st.image(p["image_url"], width=320)
            else:
                st.info("No image available")

        with c2:
            st.markdown(f"**{idx}. {p['name']}** ({p['brand']})")
            st.write(item["explanation"])
            if p.get("url"):
                st.markdown(f"[View item]({p['url']})")
            st.caption(
                f"Score {s['total']} | Body {s['body']} | Style {s['style']} | Context {s['context']} | Values {s['values']} | Novelty {s['novelty']}"
            )
            st.write(
                f"Vibes: {', '.join(p.get('vibes', []))} | Silhouette: {', '.join(p.get('silhouette', []))}"
            )

with st.expander("Combined user profile"):
    st.json(user_profile)
