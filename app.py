from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dashboard import get_component_catalog, refresh_api_state, render_page_header, render_top_nav


st.set_page_config(
    page_title="Digital Formulator",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {
    /* ── CMAC / Strathclyde Brand Palette ───────────────────────── */
    --cmac-navy:        #002850;
    --cmac-blue:        #0071CE;
    --cmac-blue-dark:   #005A9E;
    --cmac-blue-mid:    #D0E8F8;
    --cmac-blue-light:  #EBF5FF;

    --bg:               #FFFFFF;
    --bg-deep:          #F4F8FC;
    --surface:          #FFFFFF;
    --surface-tint:     #F5F8FC;

    --ink:              #0C1E2E;
    --ink-soft:         #1A3A5C;
    --muted:            #4A6A8A;
    --muted-light:      #7A9BBB;

    --line:             rgba(0, 56, 101, 0.13);
    --line-strong:      rgba(0, 56, 101, 0.22);

    --accent:           #0071CE;
    --accent-strong:    #005A9E;
    --accent-soft:      rgba(0, 113, 206, 0.10);
    --accent-hover:     rgba(0, 113, 206, 0.18);

    --success:          #1B7A3E;
    --success-soft:     rgba(27, 122, 62, 0.10);
    --warning-color:    #9A6B00;
    --warning-soft:     rgba(154, 107, 0, 0.10);

    --shadow-sm:        0 1px 4px rgba(0, 40, 90, 0.07);
    --shadow:           0 2px 12px rgba(0, 40, 90, 0.09);
    --shadow-md:        0 4px 24px rgba(0, 40, 90, 0.12);
    --shadow-lg:        0 8px 40px rgba(0, 40, 90, 0.14);

    --radius-sm:        6px;
    --radius:           10px;
    --radius-lg:        16px;
    --radius-xl:        22px;
    --radius-pill:      999px;
}

/* ── Base ─────────────────────────────────────────────────────────── */
html, body, [class*='css'] {
    font-family: 'Inter', sans-serif;
    color: var(--ink);
}
body { color: var(--ink); }
p, li, label, .stMarkdown, .stCaption, .stText, .stAlert { color: var(--ink); }

[data-testid='stAppViewContainer'] {
    background: #FFFFFF;
    min-height: 100vh;
}

/* Hide default Streamlit header bar */
[data-testid='stHeader'] { display: none !important; }
[data-testid='stToolbar'] { display: none !important; }

/* ── Sidebar: hide entirely (replaced by top nav) ─────────────────── */
[data-testid='stSidebar'],
[data-testid='stSidebarCollapsedControl'],
section[data-testid='stSidebarContent'],
[data-testid='collapsedControl'] {
    display: none !important;
}
.main .block-container {
    max-width: 1440px;
    padding-top: 0 !important;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
    padding-bottom: 3rem;
}

/* Containers on white page get a light tint */
[data-testid='stVerticalBlockBorderWrapper'] > div > div {
    border-radius: var(--radius-lg) !important;
}

/* Streamlit bordered containers */
[data-testid='stVerticalBlockBorderWrapper'] {
    background: var(--surface-tint) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ── Top Navigation Bar ───────────────────────────────────────────── */
.topnav-brand {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--cmac-navy);
    letter-spacing: 0.01em;
    padding: 0.5rem 0;
    white-space: nowrap;
}
.topnav-divider {
    height: 1px;
    background: var(--line);
    margin: 0.5rem 0 1.5rem 0;
}
/* Style all page_link elements in the top nav row */
[data-testid='stPageLink'] a,
[data-testid='stPageLink-NavLink'] {
    display: block !important;
    text-align: center !important;
    background: transparent !important;
    border: 1px solid var(--line) !important;
    border-radius: var(--radius) !important;
    padding: 0.4rem 0.5rem !important;
    color: var(--ink-soft) !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
    text-decoration: none !important;
    transition: all 0.15s ease !important;
    white-space: nowrap !important;
}
[data-testid='stPageLink'] a:hover,
[data-testid='stPageLink-NavLink']:hover {
    background: var(--accent-soft) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
[data-testid='stPageLink-NavLink'][aria-current='page'],
[data-testid='stPageLink'] a[aria-current='page'] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
}

/* ── Page Header ─────────────────────────────────────────────────── */
.page-shell { margin-bottom: 1.25rem; }
.page-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
    background: var(--surface);
    border: 1px solid var(--line-strong);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius-xl);
    padding: 1.3rem 1.6rem;
    box-shadow: var(--shadow-md);
}
.page-kicker {
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.68rem;
    color: var(--accent);
    font-weight: 600;
    margin-bottom: 0.4rem;
}
.ph-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.75rem;
    line-height: 1.1;
    color: var(--ink);
    font-weight: 700;
}
.ph-sub {
    font-size: 0.92rem;
    color: var(--muted);
    line-height: 1.6;
    max-width: 72rem;
    margin-top: 0.4rem;
}
.page-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.4rem 0.75rem;
    border-radius: var(--radius-pill);
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 700;
    font-size: 0.78rem;
    border: 1px solid rgba(0, 113, 206, 0.2);
    white-space: nowrap;
}

/* ── Empty State ──────────────────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 3.5rem 1rem;
    background: var(--surface-tint);
    border: 1px dashed var(--line-strong);
    border-radius: var(--radius-xl);
}
.empty-icon  { font-size: 2.5rem; }
.empty-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem;
    font-weight: 600;
    margin-top: 0.5rem;
    color: var(--ink-soft);
}
.empty-copy  { color: var(--muted); margin-top: 0.3rem; font-size: 0.88rem; }

/* ── Hero Cards (home page) ───────────────────────────────────────── */
.hero-panel {
    background: var(--surface);
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-xl);
    padding: 1.6rem;
    box-shadow: var(--shadow-md);
}
.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.85rem;
    line-height: 1.1;
    color: var(--ink);
    font-weight: 700;
    max-width: 22ch;
}
.hero-copy {
    color: var(--muted);
    line-height: 1.65;
    margin-top: 0.8rem;
    font-size: 0.95rem;
}
.hero-points {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-top: 1.1rem;
}
.hero-point {
    padding: 0.85rem 1rem;
    border-radius: var(--radius-lg);
    background: var(--cmac-blue-light);
    border: 1px solid var(--cmac-blue-mid);
}
.hero-point strong {
    display: block;
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--cmac-navy);
}
.hero-point span {
    display: block;
    margin-top: 0.2rem;
    color: var(--muted);
    font-size: 0.80rem;
}

/* ── Tool Cards ───────────────────────────────────────────────────── */
.tool-card {
    background: var(--surface);
    border: 1px solid var(--line-strong);
    border-top: 3px solid var(--accent);
    border-radius: var(--radius-lg);
    padding: 1rem 1.1rem;
    min-height: 12rem;
    box-shadow: var(--shadow);
    transition: box-shadow 0.2s ease;
}
.tool-card:hover { box-shadow: var(--shadow-md); }
.tool-card .tool-kicker {
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.66rem;
    font-weight: 700;
}
.tool-card h4 {
    font-family: 'Space Grotesk', sans-serif;
    margin: 0.3rem 0 0.4rem 0;
    font-size: 0.97rem;
    color: var(--ink);
}
.tool-card p {
    color: var(--muted);
    font-size: 0.85rem;
    line-height: 1.5;
    margin: 0;
}
.tool-card .tool-foot {
    display: inline-flex;
    margin-top: 0.75rem;
    padding: 0.28rem 0.6rem;
    background: var(--accent-soft);
    color: var(--accent);
    border-radius: var(--radius-pill);
    font-size: 0.72rem;
    font-weight: 700;
    border: 1px solid rgba(0,113,206,0.15);
}

/* ── Metric Cards ─────────────────────────────────────────────────── */
[data-testid='stMetric'] {
    background: var(--surface) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: var(--radius-lg) !important;
    padding: 1.1rem 1.3rem !important;
    box-shadow: var(--shadow) !important;
}
[data-testid='stMetricLabel']  { color: var(--muted) !important; font-size: 0.80rem !important; }
[data-testid='stMetricValue']  { color: var(--ink) !important; font-weight: 700 !important; }
[data-testid='stMetricDelta']  { font-size: 0.80rem !important; }

/* ── Text / Markdown ──────────────────────────────────────────────── */
[data-testid='stMarkdownContainer'],
[data-testid='stText'],
[data-testid='stCaptionContainer'],
[data-testid='stElementContainer'],
[data-testid='stNotificationContentInfo'],
[data-testid='stNotificationContentWarning'],
[data-testid='stNotificationContentError'],
[data-testid='stNotificationContentSuccess'] { color: var(--ink); }

[data-testid='stMarkdownContainer'] p,
[data-testid='stMarkdownContainer'] li,
[data-testid='stMarkdownContainer'] span,
[data-testid='stCaptionContainer'] p { color: inherit; }

/* ── Tables / DataFrames ──────────────────────────────────────────── */
[data-testid='stDataFrame'], [data-testid='stTable'] {
    background: var(--surface);
    border-radius: var(--radius-lg);
    border: 1px solid var(--line);
    overflow: hidden;
}
[data-testid='stDataFrame'] *, [data-testid='stTable'] * { color: var(--ink) !important; }
[data-testid='stDataEditor'] { border-radius: var(--radius-lg); overflow: hidden; }
[data-testid='stDataEditor'] * { color: var(--ink) !important; }

/* ── Tabs ─────────────────────────────────────────────────────────── */
[data-testid='stTabs'] [data-baseweb='tab-list'] {
    gap: 0.2rem;
    background: var(--surface-tint);
    border-radius: var(--radius-pill);
    padding: 0.2rem;
    border: 1px solid var(--line);
    width: fit-content;
}
[data-testid='stTabs'] [data-baseweb='tab'] {
    background: transparent;
    border-radius: var(--radius-pill);
    border: none;
    padding: 0.4rem 1rem;
    color: var(--muted);
    font-size: 0.86rem;
    font-weight: 500;
    white-space: nowrap;
}
[data-testid='stTabs'] [aria-selected='true'] {
    background: var(--accent) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
}
[data-testid='stTabs'] [data-baseweb='tab-highlight'] { display: none !important; }
[data-testid='stTabs'] [data-baseweb='tab-border']    { display: none !important; }

/* ── Inputs ───────────────────────────────────────────────────────── */
[data-baseweb='input'],
[data-baseweb='select'] > div,
textarea,
[data-baseweb='textarea'] {
    background: var(--surface) !important;
    color: var(--ink) !important;
    border-color: var(--line-strong) !important;
    border-radius: var(--radius) !important;
}
input, textarea {
    color: var(--ink) !important;
    -webkit-text-fill-color: var(--ink) !important;
}
input::placeholder, textarea::placeholder {
    color: var(--muted) !important;
    -webkit-text-fill-color: var(--muted) !important;
}
[data-baseweb='select'] input { color: var(--ink) !important; }
[data-baseweb='tag'] {
    background: var(--accent-soft) !important;
    border-radius: var(--radius-pill) !important;
    border: 1px solid rgba(0, 113, 206, 0.18) !important;
}
[data-baseweb='tag'] span { color: var(--accent-strong) !important; }

/* ── Labels ───────────────────────────────────────────────────────── */
label, .st-bq, .st-bs, .st-bt, .st-bu { color: var(--ink) !important; }
[data-testid='stCheckbox'] label,
[data-testid='stRadio'] label,
[data-testid='stToggle'] label,
[data-testid='stSlider'] label,
[data-testid='stMultiSelect'] label,
[data-testid='stSelectbox'] label,
[data-testid='stTextInput'] label,
[data-testid='stNumberInput'] label,
[data-testid='stTextArea'] label { color: var(--ink) !important; font-weight: 600; font-size: 0.85rem; }

/* ── Buttons ──────────────────────────────────────────────────────── */
.stButton > button,
[data-testid='stDownloadButton'] > button {
    background: var(--accent);
    color: #ffffff !important;
    border: none;
    border-radius: var(--radius);
    padding: 0.55rem 1rem;
    font-weight: 600;
    font-size: 0.88rem;
    box-shadow: 0 3px 12px rgba(0, 113, 206, 0.22);
    transition: all 0.18s ease;
}
.stButton > button:hover,
[data-testid='stDownloadButton'] > button:hover {
    background: var(--accent-strong);
    box-shadow: 0 5px 18px rgba(0, 113, 206, 0.32);
    transform: translateY(-1px);
}
[data-testid='stNumberInput'] button,
[data-testid='stDateInput'] button,
[data-testid='stSelectbox'] button,
[data-testid='baseButton-secondary'],
[data-testid='baseButton-headerNoPadding'] { color: var(--ink) !important; }

/* ── Containers / Expanders ───────────────────────────────────────── */
[data-testid='stExpander'] {
    background: var(--surface);
    border: 1px solid var(--line) !important;
    border-radius: var(--radius-lg) !important;
}
[data-testid='stAlert'] {
    border-radius: var(--radius-lg);
    border: 1px solid var(--line);
}
[data-testid='stAlert'] * { color: var(--ink) !important; }

/* ── Form Section Labels ──────────────────────────────────────────── */
.form-section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--ink-soft);
    margin: 0 0 0.25rem 0;
}

/* ── Role Badges (Smart Formulation Builder) ──────────────────────── */
.role-pill {
    display: inline-block;
    padding: 0.22rem 0.65rem;
    border-radius: var(--radius-pill);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0.55rem;
}
.role-api      { background: var(--accent-soft); color: var(--accent); border: 1px solid rgba(0,113,206,0.20); }
.role-disint   { background: rgba(27,122,62,0.10); color: #1B7A3E; border: 1px solid rgba(27,122,62,0.20); }
.role-lubricant{ background: rgba(154,107,0,0.10); color: #9A6B00; border: 1px solid rgba(154,107,0,0.20); }
.role-filler   { background: rgba(74,106,138,0.10); color: #4A6A8A; border: 1px solid rgba(74,106,138,0.20); }

/* ── Code ─────────────────────────────────────────────────────────── */
[data-testid='stMarkdownContainer'] code {
    background: var(--cmac-blue-light);
    color: var(--accent-strong);
    border-radius: 4px;
    padding: 0.1rem 0.35rem;
}

/* ── Responsive ───────────────────────────────────────────────────── */
@media (max-width: 960px) {
    .hero-points { grid-template-columns: 1fr; }
    .page-header { flex-direction: column; }
}
</style>
""",
    unsafe_allow_html=True,
)


def _home() -> None:
    api_state = refresh_api_state()
    contract = api_state.get("contract", {})
    options = api_state.get("options", {})

    render_page_header(
        "Digital Formulator",
        "An in-silico platform for direct-compression tablet development — predict powder blend "
        "characterisation, tablet mechanical performance, and compressibility profiles, or run "
        "physics-informed optimisation to identify candidate formulations meeting your target "
        "product profile.",
    )

    hero_left, hero_right = st.columns([2.2, 0.9], gap="large")
    with hero_left:
        st.markdown(
            """
<div class='hero-panel'>
  <div class='hero-title'>Predictive modelling for pharmaceutical formulation scientists.</div>
  <div class='hero-copy'>
    The Digital Formulator integrates data-driven and physics-informed models trained on powder
    characterisation and compaction datasets. From a formulation composition and compaction
    pressure, the platform predicts blend flowability (FFC, EAOIF, Carr&#8217;s index), particle
    size and shape distributions, tablet porosity, tensile strength, and empirical compressibility
    parameters (Kawakita&#8211;Lud&#273;e, Duckworth) — all without a single laboratory experiment.
  </div>
  <div class='hero-points'>
    <div class='hero-point'>
      <strong>Blend characterisation</strong>
      <span>Flowability (FFC), bulk &amp; tapped density, EAOIF, and particle morphology from composition alone.</span>
    </div>
    <div class='hero-point'>
      <strong>Tablet performance</strong>
      <span>Porosity and tensile strength profiles across a compaction-pressure range via the Duckworth model.</span>
    </div>
    <div class='hero-point'>
      <strong>Formulation optimisation</strong>
      <span>Genetic-algorithm search over composition and pressure space to meet user-defined feasibility constraints.</span>
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with hero_right:
        with st.container(border=True):
            if api_state["ok"]:
                st.success("Backend connected")
                base_url = contract.get("base_url", "")
                if base_url:
                    st.caption(f"**Endpoint:** `{base_url}`")
                version = contract.get("version", "")
                if version:
                    st.caption(f"**Version:** {version}")
            else:
                st.error("Backend unavailable")
                st.caption(
                    "Start the DM² backend (port 8080) or set `API_BASE_URL` in your environment."
                )
            if st.button("Reconnect", use_container_width=True):
                refresh_api_state(force_refresh=True)
                st.rerun()

        if options.get("options_degraded"):
            st.warning("Backend returned partial metadata. Simulation pages remain functional.")

    if not api_state["ok"]:
        st.info(
            "The backend exposes its API on port 8080 by default. "
            "Set the `API_BASE_URL` environment variable to the base URL of your deployment."
        )
        st.stop()

    catalog = get_component_catalog(options)

    # ── Tool navigation cards ───────────────────────────────────────────
    st.markdown(
        "<div style='margin:1.5rem 0 0.75rem 0; font-family:\"Space Grotesk\",sans-serif;"
        " font-size:1.05rem; font-weight:700; color:var(--ink);'>What would you like to do?</div>",
        unsafe_allow_html=True,
    )
    paths = contract.get("path_map", {})
    tool_cols = st.columns(5, gap="medium")
    tool_cards = [
        (
            "Blend & Tablet Assessment",
            "Single-Point Prediction",
            "Choose a formulation composition and compaction pressure to receive a full prediction: "
            "FFC, EAOIF, densities, particle size & shape distributions, tablet porosity and "
            "tensile strength.",
            "/single_run",
            "pages/1_Single_Run.py",
        ),
        (
            "Compressibility Profiling",
            "Pressure–Range Analysis",
            "Predict porosity and tensile-strength profiles across a compaction-pressure range. "
            "Extracts Kawakita&#8211;Lud&#273;e and Duckworth empirical parameters for the blend.",
            "/multiple_run",
            "pages/2_Multiple_Run.py",
        ),
        (
            "Formulation Optimisation",
            "Digital Formulator",
            "Define objectives (maximise FFC, tensile strength, porosity) and feasibility "
            "constraints, then search the formulation design space using a genetic algorithm "
            "to identify optimal candidate blends.",
            "/digital_formulator",
            "pages/3_Digital_Formulator.py",
        ),
        (
            "Candidate Screening",
            "Formulation Comparison",
            "Run up to five candidate formulations through the same prediction model at specified "
            "compaction pressures and compare all blend and tablet properties side by side with "
            "radar and overlay charts.",
            "/single_run",
            "pages/4_Formulation_Comparison.py",
        ),
        (
            "Design-Space Mapping",
            "Sensitivity Analysis",
            "Sweep one input variable — a component fraction or compaction pressure — across a "
            "defined range and trace how each key performance indicator (FFC, tensile strength, "
            "porosity) responds.",
            "/single_run",
            "pages/5_Sensitivity_Analysis.py",
        ),
    ]
    for col, (kicker, title, copy, endpoint, page_file) in zip(tool_cols, tool_cards):
        live = endpoint in paths
        foot = "Available" if live else "Backend unavailable"
        with col:
            st.markdown(
                f"""
<div class='tool-card'>
  <div class='tool-kicker'>{kicker}</div>
  <h4>{title}</h4>
  <p>{copy}</p>
  <div class='tool-foot'>{foot}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    # ── Materials summary ───────────────────────────────────────────────
    if not catalog.empty:
        st.markdown(
            "<div style='margin:1.5rem 0 0.5rem 0; font-family:\"Space Grotesk\",sans-serif;"
            " font-size:1.05rem; font-weight:700; color:var(--ink);'>Available materials</div>",
            unsafe_allow_html=True,
        )
        api_mat   = catalog[catalog["Role"] == "API"]
        filler_mat = catalog[catalog["Role"].isin(["Candidate filler", "Material"])]
        fixed_mat  = catalog[catalog["Role"].isin(["Default disintegrant", "Default lubricant"])]

        mc1, mc2, mc3 = st.columns(3, gap="medium")
        with mc1:
            with st.container(border=True):
                st.markdown(
                    "<p class='form-section-title'>Active Pharmaceutical Ingredients</p>",
                    unsafe_allow_html=True,
                )
                if api_mat.empty:
                    st.caption("None configured")
                else:
                    for _, row in api_mat.iterrows():
                        st.markdown(
                            f"<span class='role-pill role-api'>{row['Label']}</span>",
                            unsafe_allow_html=True,
                        )
        with mc2:
            with st.container(border=True):
                st.markdown(
                    "<p class='form-section-title'>Filler Excipients</p>",
                    unsafe_allow_html=True,
                )
                if filler_mat.empty:
                    st.caption("None configured")
                else:
                    for _, row in filler_mat.head(12).iterrows():
                        st.markdown(
                            f"<span class='role-pill role-filler'>{row['Label']}</span>",
                            unsafe_allow_html=True,
                        )
        with mc3:
            with st.container(border=True):
                st.markdown(
                    "<p class='form-section-title'>Fixed Functional Excipients</p>",
                    unsafe_allow_html=True,
                )
                if fixed_mat.empty:
                    st.caption("None configured")
                else:
                    for _, row in fixed_mat.iterrows():
                        role_css = "role-disint" if "disint" in row["Role"].lower() else "role-lubricant"
                        st.markdown(
                            f"<span class='role-pill {role_css}'>{row['Label']} — {row['Role']}</span>",
                            unsafe_allow_html=True,
                        )

        with st.expander("Full material catalogue", expanded=False):
            st.dataframe(catalog, use_container_width=True, hide_index=True)


_pg_home   = st.Page(_home, title="Home", icon="🏠", default=True)
_pg_sr     = st.Page("pages/1_Single_Run.py", title="Single Run", icon="🔬")
_pg_mr     = st.Page("pages/2_Multiple_Run.py", title="Multiple Run", icon="📈")
_pg_df     = st.Page("pages/3_Digital_Formulator.py", title="Digital Formulator", icon="🧬")
_pg_cmp    = st.Page("pages/4_Formulation_Comparison.py", title="Comparison", icon="⚗️")
_pg_sa     = st.Page("pages/5_Sensitivity_Analysis.py", title="Sensitivity", icon="📐")

navigation = st.navigation(
    {
        "Home": [_pg_home],
        "Simulation": [_pg_sr, _pg_mr],
        "Optimisation and analysis": [_pg_df, _pg_cmp, _pg_sa],
    },
    position="hidden",
)

render_top_nav({
    "home":              _pg_home,
    "single_run":        _pg_sr,
    "multiple_run":      _pg_mr,
    "digital_formulator": _pg_df,
    "comparison":        _pg_cmp,
    "sensitivity":       _pg_sa,
})
navigation.run()
