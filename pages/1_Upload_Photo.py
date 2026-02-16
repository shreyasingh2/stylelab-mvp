import streamlit as st
from PIL import Image

from components.body_analysis import analyze_body_from_image, default_body_profile

st.set_page_config(page_title="Upload Photo", page_icon="📸", layout="wide")
st.title("1) Upload Photo")
st.caption("We use your photo to infer proportion signals, never to label or judge.")

uploaded = st.file_uploader("Upload a full-body photo", type=["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Uploaded image", width=320)
    body_profile = analyze_body_from_image(uploaded.getvalue(), image.width, image.height)
    st.session_state.body_profile = body_profile
    st.success("Body harmony signals extracted.")
    st.json(body_profile)
else:
    if st.button("Use fallback profile for now"):
        st.session_state.body_profile = default_body_profile()
        st.info("Fallback body profile saved.")

if st.button("Continue to Instagram"):
    st.switch_page("pages/2_Connect_Instagram.py")
