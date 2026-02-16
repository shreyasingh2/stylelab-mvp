import streamlit as st

from components.instagram_analyzer import analyze_captions

st.set_page_config(page_title="Instagram (Optional)", page_icon="📱", layout="wide")
st.title("3) Instagram (Optional)")
st.caption("You can skip this step. Manual style inputs are enough to get recommendations.")

if st.button("Skip Instagram and continue", use_container_width=True):
    st.session_state.instagram_profile = {}
    st.switch_page("pages/4_Results.py")

st.divider()

username = st.text_input("Instagram handle (optional)", placeholder="@yourhandle")
caption_block = st.text_area(
    "Paste recent caption snippets (one per line)",
    placeholder="Neutral outfit for work day\nWide-leg trousers + blazer today\nMinimal all-black dinner look",
    height=180,
)

if st.button("Analyze style from captions"):
    lines = [line.strip() for line in caption_block.splitlines() if line.strip()]
    if not lines:
        st.warning("Add at least one caption line, or skip this step.")
    else:
        profile = analyze_captions(lines)
        if username:
            profile["username"] = username
        st.session_state.instagram_profile = profile
        st.success("Instagram style profile generated.")
        st.json(profile)

col1, col2 = st.columns(2)
with col1:
    if st.button("Continue to Your Style", use_container_width=True):
        st.switch_page("pages/3_Your_Style.py")
with col2:
    if st.button("Continue to Results", use_container_width=True):
        st.switch_page("pages/4_Results.py")
