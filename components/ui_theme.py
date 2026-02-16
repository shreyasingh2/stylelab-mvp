from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Cormorant+Garamond:wght@500;600;700&display=swap');

          :root {
            --bg: #f8f5f1;
            --surface: #fffdfa;
            --surface-2: #ffffff;
            --text: #1d1a18;
            --muted: #6f6760;
            --line: #e8dfd5;
            --accent: #d4553c;
            --accent-dark: #ba432d;
          }

          .stApp {
            background:
              radial-gradient(circle at 0% 40%, rgba(224, 216, 205, 0.22) 0, rgba(248,245,241,0) 38%),
              radial-gradient(circle at 95% 20%, rgba(226, 215, 202, 0.22) 0, rgba(248,245,241,0) 34%),
              var(--bg);
            color: var(--text);
            font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          }

          .block-container {
            max-width: 860px;
            padding-top: 1.0rem;
            padding-bottom: 2rem;
          }

          h1, h2, h3 {
            color: var(--text) !important;
            letter-spacing: -0.01em;
          }

          [data-testid="stMarkdownContainer"] p,
          [data-testid="stMarkdownContainer"] li,
          [data-testid="stMarkdownContainer"] span,
          [data-testid="stMetricValue"],
          [data-testid="stMetricLabel"],
          label,
          small,
          .stCaption {
            color: var(--text) !important;
          }

          .top-nav {
            border-bottom: 1px solid var(--line);
            padding: 0.45rem 0;
            margin-bottom: 0.9rem;
          }

          .brand-mark {
            font-family: 'Cormorant Garamond', Georgia, serif;
            font-size: 1.45rem;
            font-weight: 700;
          }

          .stepper {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.4rem;
            margin: 0.2rem 0 1rem 0;
            align-items: center;
          }

          .step {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.24rem;
            color: var(--muted);
            font-size: 0.72rem;
          }

          .step .dot {
            width: 26px;
            height: 26px;
            border-radius: 999px;
            border: 1px solid var(--line);
            background: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.74rem;
            color: #7d746c;
          }

          .step.active .dot,
          .step.done .dot {
            background: var(--accent);
            color: #fff;
            border-color: transparent;
          }

          .hero-wrap {
            text-align: center;
            border: 1px solid var(--line);
            background: linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,251,246,0.75));
            border-radius: 20px;
            padding: 1.8rem 1.1rem;
            margin-bottom: 1rem;
          }

          .display-serif {
            font-family: 'Cormorant Garamond', Georgia, serif;
            font-size: 3.3rem;
            line-height: 0.98;
            letter-spacing: -0.02em;
            margin: 0;
            color: var(--text);
          }

          .hero-sub {
            color: var(--muted) !important;
            max-width: 640px;
            margin: 0.5rem auto 0 auto;
            line-height: 1.42;
            font-size: 1rem;
          }

          .pill {
            display: inline-block;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 0.2rem 0.68rem;
            color: #7f746b;
            background: #fff;
            font-size: 0.78rem;
            margin-bottom: 0.7rem;
          }

          .section-card {
            border: 1px solid var(--line);
            border-radius: 14px;
            background: rgba(255,255,255,0.86);
            padding: 0.8rem 0.95rem;
            margin: 0.9rem 0 0.45rem 0;
          }

          .section-title {
            color: var(--text);
            font-weight: 600;
            font-size: 1.01rem;
          }

          .section-hint {
            color: var(--muted) !important;
            font-size: 0.89rem;
            margin-top: 0.12rem;
          }

          .stButton > button {
            border-radius: 10px;
            border: 1px solid var(--line);
            padding: 0.5rem 0.95rem;
            font-weight: 600;
            background: #fff;
            color: var(--text);
          }

          .stButton > button[kind="primary"] {
            background: var(--accent);
            color: white;
            border-color: transparent;
          }

          .stButton > button[kind="primary"]:hover {
            background: var(--accent-dark);
          }

          [data-testid="stTextInput"] input,
          [data-testid="stTextArea"] textarea,
          [data-baseweb="select"] > div,
          [data-testid="stMultiSelect"] > div,
          [data-testid="stNumberInput"] input {
            background-color: var(--surface-2) !important;
            color: var(--text) !important;
            border: 1px solid var(--line) !important;
          }

          [data-testid="stFileUploader"] section,
          [data-testid="stFileUploaderDropzone"] {
            background: rgba(255, 255, 255, 0.94) !important;
            border: 1px dashed var(--line) !important;
          }

          [data-testid="stFileUploaderDropzone"] * {
            color: var(--text) !important;
          }

          [data-testid="stFileUploaderDropzone"] small,
          [data-testid="stFileUploaderDropzoneInstructions"] {
            color: var(--muted) !important;
          }

          [data-testid="stFileUploaderDropzone"] button {
            background: var(--accent) !important;
            color: #ffffff !important;
            border: 0 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
          }

          [data-testid="stFileUploaderDropzone"] button:hover {
            background: var(--accent-dark) !important;
            color: #ffffff !important;
          }

          [data-testid="stExpander"] {
            border-radius: 12px;
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.86);
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def top_nav() -> None:
    st.markdown(
        """
        <div class="top-nav">
          <div class="brand-mark">StyleLab</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stepper(photo_done: bool, prefs_done: bool, results_done: bool) -> None:
    states = [
        ("Your Photo", photo_done),
        ("Preferences", prefs_done),
        ("Recommendations", results_done),
    ]

    # Active is first incomplete step
    active_idx = 0
    for i, (_, done) in enumerate(states):
        if not done:
            active_idx = i
            break
    else:
        active_idx = len(states) - 1

    bits = ["<div class='stepper'>"]
    for i, (label, done) in enumerate(states):
        cls = "done" if done else ("active" if i == active_idx else "")
        marker = "✓" if done else str(i + 1)
        bits.append(
            f"<div class='step {cls}'><div class='dot'>{marker}</div><div>{label}</div></div>"
        )
    bits.append("</div>")
    st.markdown("".join(bits), unsafe_allow_html=True)


def hero_block() -> None:
    st.markdown(
        """
        <div class="hero-wrap">
          <div class="pill">AI-powered personal styling</div>
          <div class="display-serif">Clothing that feels like <span style="color:#d4553c;">you</span></div>
          <div class="hero-sub">StyleLab understands your proportions and preferences to recommend outfits that harmonize with your life.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, hint: str) -> None:
    st.markdown(
        f"""
        <div class="section-card">
          <div class="section-title">{title}</div>
          <div class="section-hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
