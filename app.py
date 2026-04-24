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

    --bg:               #EEF4FB;
    --bg-deep:          #E0EAF5;
    --surface:          #FFFFFF;
    --surface-tint:     #F5F9FF;

    --ink:              #0C1E2E;
    --ink-soft:         #1A3A5C;
    --muted:            #4A6A8A;
    --muted-light:      #7A9BBB;

    --line:             rgba(0, 56, 101, 0.10);
    --line-strong:      rgba(0, 56, 101, 0.18);

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
    background: linear-gradient(160deg, var(--bg) 0%, #e8f0f9 50%, var(--bg-deep) 100%);
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
    border: 1px solid var(--line);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius-xl);
    padding: 1.3rem 1.6rem;
    box-shadow: var(--shadow);
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
    border: 1px solid var(--line);
    border-radius: var(--radius-xl);
    padding: 1.6rem;
    box-shadow: var(--shadow);
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
    border: 1px solid var(--line);
    border-top: 3px solid var(--accent);
    border-radius: var(--radius-lg);
    padding: 1rem 1.1rem;
    min-height: 12rem;
    box-shadow: var(--shadow-sm);
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
    border: 1px solid var(--line) !important;
    border-radius: var(--radius-lg) !important;
    padding: 1.1rem 1.3rem !important;
    box-shadow: var(--shadow-sm) !important;
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
        "Blend & Tablet Property Prediction",
        "DM² System-of-Models — simulate blend flowability, tablet porosity, tensile strength, and compressibility profiles, or run in-silico formulation optimisation and design-space sensitivity analysis.",
        badge=contract.get("version", "API offline"),
    )

    hero_left, hero_right = st.columns([1.8, 1.1], gap="large")
    with hero_left:
        st.markdown(
            """
<div class='hero-panel'>
  <div class='hero-title'>Predictive modelling &amp; simulation for pharmaceutical formulation.</div>
  <div class='hero-copy'>
    Connect to the DM² backend to access physics-informed and data-driven models for direct-compression tablet development. All results are driven live from the API — no hardcoded data.
  </div>
  <div class='hero-points'>
    <div class='hero-point'><strong>Single-point simulation</strong><span>Blend &amp; tablet properties at one compaction pressure.</span></div>
    <div class='hero-point'><strong>Empirical profiles</strong><span>Kawakita and Duckworth analysis across a pressure range.</span></div>
    <div class='hero-point'><strong>Optimisation &amp; sensitivity</strong><span>Solver-driven formulation search and design-space mapping.</span></div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with hero_right:
        with st.container(border=True):
            st.caption("Backend connection")
            if api_state["ok"]:
                st.success(api_state["msg"])
                st.write(contract.get("base_url", "Unknown base URL"))
            else:
                st.error(api_state["msg"])
            if st.button("Refresh API discovery", use_container_width=True):
                refresh_api_state(force_refresh=True)
                st.rerun()

        with st.container(border=True):
            st.caption("Live contract")
            st.write(contract.get("title", "Digital Formulator API"))
            st.write(f"{len(contract.get('paths', []))} documented paths")
            if options.get("options_degraded"):
                st.warning("Options endpoint returned degraded metadata. Simulation endpoints may still work.")

    if not api_state["ok"]:
        st.info(
            "The backend Dockerfile and entrypoint in the sibling DM2-System-of-Models project expose port 8080. "
            "If you are running the API locally, use an API base URL ending in 8080 unless your deployment remaps the port."
        )
        st.stop()

    catalog = get_component_catalog(options)
    paths = contract.get("path_map", {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("API paths", len(contract.get("paths", [])))
    m2.metric("Materials", len(catalog))
    m3.metric("Objectives", len(options.get("available_objectives", [])))
    m4.metric("Constraints", len(options.get("available_constraints", [])))

    st.markdown("### Study modes")
    tool_cols = st.columns(5, gap="medium")
    tool_cards = [
        ("Simulation", "Single Run", "Predict blend and tablet properties at one compaction pressure using the shared backend endpoint.", "/single_run"),
        ("Simulation", "Multiple Run", "Fit compressibility and tensile profiles over a compaction-pressure range using the empirical profile endpoint.", "/multiple_run"),
        ("Optimisation", "Digital Formulator", "Configure objectives, constraints, and search space, then run in-silico formulation optimisation.", "/digital_formulator"),
        ("Comparison", "Formulation Comparison", "Run several candidate blends through the same single-run model and compare responses side by side.", "/single_run"),
        ("Analysis", "Sensitivity Analysis", "Sweep one fraction or compaction pressure and observe design-space trends.", "/single_run"),
    ]
    for col, (kicker, title, copy, endpoint) in zip(tool_cols, tool_cards):
        status = "Live" if endpoint in paths else "Not published"
        with col:
            st.markdown(
                f"""
<div class='tool-card'>
  <div class='tool-kicker'>{kicker}</div>
  <h4>{title}</h4>
  <p>{copy}</p>
  <div class='tool-foot'>{status}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("### API surface &amp; reference data")
    tab_materials, tab_endpoints, tab_defaults = st.tabs(["Materials", "Endpoints", "Optimisation defaults"])

    with tab_materials:
        if catalog.empty:
            st.info("The options endpoint did not return material metadata.")
        else:
            role_counts = catalog.groupby("Role").size().reset_index(name="Count")
            left, right = st.columns([1, 2.5], gap="large")
            with left:
                st.dataframe(role_counts, use_container_width=True, hide_index=True)
            with right:
                st.dataframe(catalog, use_container_width=True, hide_index=True)

    with tab_endpoints:
        endpoint_rows = []
        for path, methods in paths.items():
            for method_name, info in methods.items():
                endpoint_rows.append({"Method": method_name.upper(), "Path": path, "Summary": info.get("summary", "")})
        endpoint_df = (
            pd.DataFrame(endpoint_rows).sort_values(["Path", "Method"])
            if endpoint_rows
            else pd.DataFrame()
        )
        st.dataframe(endpoint_df, use_container_width=True, hide_index=True)

    with tab_defaults:
        defaults = options.get("current_defaults", {})
        if defaults:
            left, right = st.columns(2, gap="large")
            with left:
                st.dataframe(
                    pd.DataFrame([{"Setting": k, "Value": str(v)} for k, v in defaults.items() if k != "constraints"]),
                    use_container_width=True,
                    hide_index=True,
                )
            with right:
                constraint_defaults = defaults.get("constraints", [])
                if constraint_defaults:
                    st.dataframe(pd.DataFrame(constraint_defaults), use_container_width=True, hide_index=True)
        else:
            st.info("No optimisation defaults were returned by the backend.")


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
