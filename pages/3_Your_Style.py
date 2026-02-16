import streamlit as st

from components.ui_theme import apply_theme

st.set_page_config(page_title="Your Style", page_icon="✨", layout="wide")
apply_theme()

st.title("2) Your Style")
st.caption("These questions map directly to your recommendation score.")

st.markdown(
    """
    <div class="hero-wrap" style="text-align:left;">
      <div class="pill">Style Profile</div>
      <div class="hero-sub" style="margin-left:0;max-width:none;">
        We score recommendations by Body Harmony (35%), Style Match (30%), Context (20%), Values (10%), and Novelty (5%).
        Your answers below feed those exact factors.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("A) Your Vibe (Style Match)")
vibes = st.multiselect(
    "Pick 2-4 vibes you actually wear most",
    [
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
    ],
    default=["minimal", "polished"],
)

silhouettes = st.multiselect(
    "Silhouettes you feel best in",
    [
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
    ],
    default=["tailored", "wide-leg"],
)

colors = st.multiselect(
    "Core color palette",
    [
        "black",
        "white",
        "cream",
        "navy",
        "olive",
        "camel",
        "grey",
        "burgundy",
        "red",
        "blue",
        "brown",
        "beige",
    ],
    default=["black", "cream", "navy"],
)

st.subheader("B) Your Context (Context Score)")
col1, col2, col3 = st.columns(3)
with col1:
    location = st.text_input("Location", value="NYC")
with col2:
    season = st.selectbox("Current season", ["winter", "spring", "summer", "fall", "all"])
with col3:
    occasion = st.selectbox(
        "Main occasion right now",
        ["work", "weekend", "date", "event", "travel", "party", "dinner", "vacation", "city"],
    )

st.subheader("C) Your Values (Values Score)")
comfort_first = st.checkbox("Comfort-first", value=True)
sustainable = st.checkbox("Sustainability matters", value=False)
boldness = st.slider(
    "How experimental do you want recommendations to be?",
    min_value=0.0,
    max_value=1.0,
    value=0.5,
    step=0.05,
)

col_save, col_next = st.columns(2)
with col_save:
    if st.button("Save style profile", type="primary", use_container_width=True):
        st.session_state.manual_profile = {
            "vibes": vibes,
            "silhouettes": silhouettes,
            "colors": colors,
            "location": location,
            "season": season,
            "occasion": occasion,
            "comfort_first": comfort_first,
            "sustainable": sustainable,
            "boldness": boldness,
        }
        st.success("Style profile saved.")

with col_next:
    if st.button("See Results", use_container_width=True):
        st.switch_page("pages/4_Results.py")
