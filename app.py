from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dashboard import get_component_catalog, refresh_api_state, render_page_header


st.set_page_config(
    page_title="Digital Formulator Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

:root {
    --bg: #f4efe4;
    --bg-deep: #ebe2d2;
    --surface: rgba(255, 250, 241, 0.96);
    --surface-strong: #fffdf8;
    --surface-tint: rgba(246, 240, 230, 0.92);
    --ink: #17313e;
    --ink-soft: #274553;
    --muted: #5b7380;
    --muted-strong: #4d6470;
    --line: rgba(23, 49, 62, 0.12);
    --line-strong: rgba(23, 49, 62, 0.18);
    --accent: #0b6e69;
    --accent-strong: #075651;
    --accent-soft: rgba(11, 110, 105, 0.12);
    --signal: #b85c38;
    --signal-soft: rgba(184, 92, 56, 0.14);
    --sidebar-bg-top: #18323f;
    --sidebar-bg-bottom: #102530;
    --sidebar-text: #f2eadc;
    --sidebar-text-soft: rgba(242, 234, 220, 0.82);
    --sidebar-active-bg: rgba(255, 255, 255, 0.12);
    --shadow: 0 16px 48px rgba(23, 49, 62, 0.08);
    --shadow-soft: 0 10px 24px rgba(23, 49, 62, 0.06);
}

html, body, [class*='css']  {
    font-family: 'IBM Plex Sans', sans-serif;
    color: var(--ink);
}

body {
    color: var(--ink);
}

p, li, label, .stMarkdown, .stCaption, .stText, .stAlert {
    color: var(--ink);
}

[data-testid='stAppViewContainer'] {
    background:
        radial-gradient(circle at top right, rgba(11, 110, 105, 0.16), transparent 30%),
        radial-gradient(circle at left top, rgba(184, 92, 56, 0.12), transparent 24%),
        linear-gradient(180deg, #fbf7ef 0%, var(--bg) 60%, var(--bg-deep) 100%);
}

[data-testid='stHeader'] {
    background: rgba(244, 239, 228, 0.78);
    backdrop-filter: blur(10px);
}

[data-testid='stToolbar'] {
    right: 1rem;
}

[data-testid='stSidebar'] {
    background: linear-gradient(180deg, var(--sidebar-bg-top) 0%, var(--sidebar-bg-bottom) 100%);
    border-right: 1px solid rgba(255,255,255,0.08);
}

[data-testid='stSidebar'] * {
    color: var(--sidebar-text);
}

[data-testid='stSidebar'] p,
[data-testid='stSidebar'] li,
[data-testid='stSidebar'] label,
[data-testid='stSidebar'] span,
[data-testid='stSidebar'] div,
[data-testid='stSidebar'] a,
[data-testid='stSidebar'] button {
    color: var(--sidebar-text) !important;
}

[data-testid='stSidebarNav'] {
    padding-top: 0.25rem;
}

[data-testid='stSidebarNav'] a {
    background: transparent;
    border-radius: 14px;
    margin-bottom: 0.22rem;
}

[data-testid='stSidebarNav'] a:hover {
    background: rgba(255,255,255,0.08);
}

[data-testid='stSidebarNav'] a[aria-current='page'] {
    background: var(--sidebar-active-bg);
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.10);
}

[data-testid='stSidebarNav'] a[aria-current='page']:hover {
    background: rgba(255,255,255,0.16);
}

[data-testid='stSidebarNav'] a[data-testid='stSidebarNavLink'] span {
    color: var(--sidebar-text) !important;
}

[data-testid='stSidebarNav'] a[data-testid='stSidebarNavLink'] p,
[data-testid='stSidebarNav'] a[data-testid='stSidebarNavLink'] div,
[data-testid='stSidebarNav'] a[data-testid='stSidebarNavLink'] svg {
    color: var(--sidebar-text) !important;
    fill: var(--sidebar-text);
}

[data-testid='stSidebarNav'] a:not([aria-current='page']) [data-testid='stSidebarNavLink'] p,
[data-testid='stSidebarNav'] a:not([aria-current='page']) [data-testid='stSidebarNavLink'] span {
    color: var(--sidebar-text-soft) !important;
}

[data-testid='stSidebarNav'] a[aria-current='page'] [data-testid='stSidebarNavLink'] p,
[data-testid='stSidebarNav'] a[aria-current='page'] [data-testid='stSidebarNavLink'] span,
[data-testid='stSidebarNav'] a[aria-current='page'] [data-testid='stSidebarNavLink'] div,
[data-testid='stSidebarNav'] a[aria-current='page'] [data-testid='stSidebarNavLink'] svg {
    color: var(--sidebar-text) !important;
    fill: var(--sidebar-text);
    font-weight: 700;
}

.sidebar-brand {
    background: linear-gradient(145deg, rgba(255,255,255,0.10), rgba(255,255,255,0.04));
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 18px;
    padding: 1rem 1rem 0.95rem 1rem;
    margin: 0.4rem 0 1rem 0;
}

.sidebar-brand .eyebrow {
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.16em;
    opacity: 0.72;
    color: var(--sidebar-text-soft);
}

.sidebar-brand .title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.2rem;
    font-weight: 700;
    margin-top: 0.4rem;
    color: var(--sidebar-text);
}

.sidebar-brand .copy {
    font-size: 0.86rem;
    line-height: 1.45;
    opacity: 0.82;
    margin-top: 0.45rem;
    color: var(--sidebar-text);
}

.page-shell {
    margin-bottom: 1rem;
}

.page-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
    background: linear-gradient(135deg, rgba(255,252,247,0.98), rgba(247,239,226,0.94));
    border: 1px solid var(--line-strong);
    border-radius: 24px;
    padding: 1.4rem 1.5rem;
    box-shadow: var(--shadow);
}

.page-kicker {
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 0.72rem;
    color: var(--muted);
    margin-bottom: 0.5rem;
}

.ph-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem;
    line-height: 1.05;
    color: var(--ink);
}

.ph-sub {
    font-size: 0.98rem;
    color: var(--muted);
    line-height: 1.55;
    max-width: 70rem;
    margin-top: 0.45rem;
}

.page-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.5rem 0.75rem;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 700;
    white-space: nowrap;
}

.empty-state {
    text-align: center;
    padding: 3.25rem 1rem;
    background: var(--surface);
    border: 1px dashed var(--line-strong);
    border-radius: 22px;
}

.empty-icon {
    font-size: 2.8rem;
}

.empty-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem;
    margin-top: 0.5rem;
}

.empty-copy {
    color: var(--muted);
    margin-top: 0.35rem;
}

.hero-grid {
    display: grid;
    grid-template-columns: 1.6fr 1fr;
    gap: 1rem;
    margin-top: 0.35rem;
}

.hero-panel,
.insight-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 22px;
    box-shadow: var(--shadow);
}

.hero-panel {
    padding: 1.4rem 1.5rem;
}

.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.2rem;
    line-height: 1.02;
    max-width: 20ch;
}

.hero-copy {
    color: var(--muted);
    line-height: 1.6;
    margin-top: 0.8rem;
}

.hero-points {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
}

.hero-point {
    padding: 0.9rem 1rem;
    border-radius: 18px;
    background: rgba(255,255,255,0.64);
    border: 1px solid rgba(23, 49, 62, 0.08);
}

.hero-point strong {
    display: block;
    font-size: 0.9rem;
}

.hero-point span {
    display: block;
    margin-top: 0.25rem;
    color: var(--muted);
    font-size: 0.82rem;
}

.insight-card {
    padding: 1.2rem;
}

.insight-card h4 {
    font-family: 'Space Grotesk', sans-serif;
    margin: 0;
    font-size: 1.02rem;
}

.insight-card p {
    color: var(--muted);
    line-height: 1.55;
    margin: 0.55rem 0 0 0;
}

.tool-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 1rem;
    min-height: 11.5rem;
    box-shadow: var(--shadow-soft);
}

.tool-card .tool-kicker {
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.68rem;
    font-weight: 700;
}

.tool-card h4 {
    font-family: 'Space Grotesk', sans-serif;
    margin: 0.35rem 0;
    font-size: 1rem;
}

.tool-card p {
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.5;
}

.tool-card .tool-foot {
    display: inline-flex;
    margin-top: 0.8rem;
    padding: 0.35rem 0.6rem;
    background: var(--signal-soft);
    color: var(--signal);
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
}

[data-testid='stMetric'] {
    background: var(--surface) !important;
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 1rem 1.1rem !important;
    box-shadow: var(--shadow);
}

[data-testid='stMetricLabel'] {
    color: var(--muted) !important;
}

[data-testid='stMetricValue'] {
    color: var(--ink) !important;
}

[data-testid='stMarkdownContainer'],
[data-testid='stText'],
[data-testid='stCaptionContainer'],
[data-testid='stElementContainer'],
[data-testid='stNotificationContentInfo'],
[data-testid='stNotificationContentWarning'],
[data-testid='stNotificationContentError'],
[data-testid='stNotificationContentSuccess'] {
    color: var(--ink);
}

[data-testid='stMarkdownContainer'] p,
[data-testid='stMarkdownContainer'] li,
[data-testid='stMarkdownContainer'] span,
[data-testid='stMarkdownContainer'] div,
[data-testid='stCaptionContainer'] p {
    color: inherit;
}

[data-testid='stDataFrame'], [data-testid='stTable'] {
    background: var(--surface);
    border-radius: 20px;
}

[data-testid='stDataFrame'] * ,
[data-testid='stTable'] * {
    color: var(--ink) !important;
}

[data-testid='stTabs'] [data-baseweb='tab-list'] {
    gap: 0.25rem;
}

[data-testid='stTabs'] [data-baseweb='tab'] {
    background: rgba(255,255,255,0.55);
    border-radius: 999px;
    border: 1px solid rgba(23,49,62,0.08);
    height: 2.4rem;
    padding: 0 1rem;
    color: var(--ink-soft);
}

[data-testid='stTabs'] [aria-selected='true'] {
    background: var(--accent-soft) !important;
    color: var(--accent) !important;
}

[data-testid='stTabs'] [data-baseweb='tab-highlight'] {
    background: transparent !important;
}

[data-baseweb='input'],
[data-baseweb='select'] > div,
textarea,
[data-baseweb='textarea'] {
    background: var(--surface-strong) !important;
    color: var(--ink) !important;
    border-color: var(--line-strong) !important;
    border-radius: 16px !important;
}

input, textarea {
    color: var(--ink) !important;
    -webkit-text-fill-color: var(--ink) !important;
}

input::placeholder,
textarea::placeholder {
    color: var(--muted) !important;
    -webkit-text-fill-color: var(--muted) !important;
}

[data-baseweb='select'] input {
    color: var(--ink) !important;
}

[data-baseweb='tag'] {
    background: var(--accent-soft) !important;
    border-radius: 999px !important;
    border: 1px solid rgba(11, 110, 105, 0.14) !important;
}

[data-baseweb='tag'] span {
    color: var(--accent-strong) !important;
}

label, .st-bq, .st-bs, .st-bt, .st-bu {
    color: var(--ink) !important;
}

[data-testid='stNumberInput'] button,
[data-testid='stDateInput'] button,
[data-testid='stSelectbox'] button,
[data-testid='baseButton-secondary'],
[data-testid='baseButton-headerNoPadding'] {
    color: var(--ink) !important;
}

.stButton > button,
[data-testid='stDownloadButton'] > button {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
    color: #f7f4ee !important;
    border: 0;
    border-radius: 14px;
    padding: 0.62rem 1rem;
    font-weight: 700;
    box-shadow: 0 10px 22px rgba(11, 110, 105, 0.18);
}

.stButton > button:hover,
[data-testid='stDownloadButton'] > button:hover {
    background: linear-gradient(135deg, #0d7d77 0%, #08615c 100%);
}

[data-testid='stForm'] {
    background: rgba(255, 250, 241, 0.7);
    border-radius: 22px;
}

[data-testid='stAlert'] {
    border-radius: 18px;
    border: 1px solid var(--line);
}

[data-testid='stAlert'] * {
    color: var(--ink) !important;
}

[data-testid='stExpander'] {
    background: rgba(255, 250, 241, 0.52);
    border: 1px solid var(--line);
    border-radius: 18px;
}

[data-testid='stCheckbox'] label,
[data-testid='stRadio'] label,
[data-testid='stToggle'] label,
[data-testid='stSlider'] label,
[data-testid='stMultiSelect'] label,
[data-testid='stSelectbox'] label,
[data-testid='stTextInput'] label,
[data-testid='stNumberInput'] label,
[data-testid='stTextArea'] label {
    color: var(--ink) !important;
    font-weight: 600;
}

[data-testid='stDataEditor'] {
    border-radius: 18px;
    overflow: hidden;
}

[data-testid='stDataEditor'] * {
    color: var(--ink) !important;
}

[data-testid='stMarkdownContainer'] code {
    background: rgba(23,49,62,0.06);
    color: var(--ink);
}

@media (max-width: 980px) {
    .hero-grid {
        grid-template-columns: 1fr;
    }
    .hero-points {
        grid-template-columns: 1fr;
    }
    .page-header {
        flex-direction: column;
    }
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
        "Blend and tablet property prediction",
        "Use the DM2 System-of-Models backend to simulate blend flowability, tablet porosity, tensile strength, compressibility profiles, optimisation studies, and parameter sweeps from one connected workspace.",
        badge=contract.get("version", "API offline"),
    )

    hero_left, hero_right = st.columns([1.8, 1.1], gap="large")
    with hero_left:
        st.markdown(
            """
<div class='hero-panel'>
  <div class='hero-title'>Model-led formulation analysis without local dashboard hardcoding.</div>
  <div class='hero-copy'>
    The dashboard now reads its live contract from the FastAPI backend, aligns its forms to the published optimisation options, and keeps the scientific outputs focused on what the backend actually returns.
  </div>
  <div class='hero-points'>
    <div class='hero-point'><strong>Single-point simulation</strong><span>Blend and tablet properties at one compaction pressure.</span></div>
    <div class='hero-point'><strong>Empirical profiles</strong><span>Kawakita and Duckworth analysis across a pressure range.</span></div>
    <div class='hero-point'><strong>Optimisation and sensitivity</strong><span>Solver-driven formulation search and design-space mapping.</span></div>
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
            "The backend Dockerfile and entrypoint in the sibling DM2-System-of-Models project expose port 8080. If you are running the API locally, prefer an API base URL ending in 8080 unless your deployment explicitly remaps the port."
        )
        st.stop()

    catalog = get_component_catalog(options)
    materials_count = len(catalog)
    paths = contract.get("path_map", {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("API paths", len(contract.get("paths", [])))
    m2.metric("Materials exposed", materials_count)
    m3.metric("Objectives", len(options.get("available_objectives", [])))
    m4.metric("Constraints", len(options.get("available_constraints", [])))

    st.markdown("### Study modes")
    tool_cols = st.columns(5, gap="medium")
    tool_cards = [
        ("Simulation", "Single Run", "Predict granular and tablet properties at one compaction pressure using the shared single-run backend endpoint.", "/single_run"),
        ("Simulation", "Multiple Run", "Fit compressibility and tensile profiles over a compaction-pressure range using the empirical profile endpoint.", "/multiple_run"),
        ("Optimisation", "Digital Formulator", "Query backend objectives, constraints, and defaults, then run formulation optimisation with the published solver settings.", "/digital_formulator"),
        ("Comparison", "Formulation Comparison", "Run several candidate blends through the same single-run model and compare responses side by side.", "/single_run"),
        ("Analysis", "Sensitivity Analysis", "Sweep one fraction or compaction pressure and observe design-space trends in flowability and tablet properties.", "/single_run"),
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

    st.markdown("### API surface and reference data")
    tab_materials, tab_endpoints, tab_defaults = st.tabs(["Materials", "Endpoints", "Optimisation defaults"])

    with tab_materials:
        if catalog.empty:
            st.info("The options endpoint did not return material metadata.")
        else:
            role_counts = catalog.groupby("Role").size().reset_index(name="Count")
            left, right = st.columns([1, 2], gap="large")
            with left:
                st.dataframe(role_counts, use_container_width=True, hide_index=True)
            with right:
                st.dataframe(catalog, use_container_width=True, hide_index=True)

    with tab_endpoints:
        endpoint_rows = []
        for path, methods in paths.items():
            for method_name, info in methods.items():
                endpoint_rows.append(
                    {
                        "Method": method_name.upper(),
                        "Path": path,
                        "Summary": info.get("summary", ""),
                    }
                )
        endpoint_df = pd.DataFrame(endpoint_rows).sort_values(["Path", "Method"]) if endpoint_rows else pd.DataFrame()
        st.dataframe(endpoint_df, use_container_width=True, hide_index=True)

    with tab_defaults:
        defaults = options.get("current_defaults", {})
        if defaults:
            left, right = st.columns(2, gap="large")
            with left:
                st.dataframe(
                    pd.DataFrame(
                        [{"Setting": key, "Value": str(value)} for key, value in defaults.items() if key != "constraints"]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            with right:
                constraint_defaults = defaults.get("constraints", [])
                if constraint_defaults:
                    st.dataframe(pd.DataFrame(constraint_defaults), use_container_width=True, hide_index=True)
        else:
            st.info("No optimisation defaults were returned by the backend.")


with st.sidebar:
    st.markdown(
        """
<div class='sidebar-brand'>
  <div class='eyebrow'>University of Strathclyde · CMAC</div>
  <div class='title'>Digital Formulator</div>
  <div class='copy'>A Streamlit front end for the DM2 System-of-Models API, oriented around scientific analysis of blends, compaction, and tablet performance.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    sidebar_state = refresh_api_state()
    if sidebar_state["ok"]:
        st.caption("Connected backend")
        st.write(sidebar_state["contract"].get("base_url", "Unavailable"))
    else:
        st.caption("Backend status")
        st.write("Offline")


navigation = st.navigation(
    {
        "Home": [
            st.Page(_home, title="Home", icon="🏠", default=True),
        ],
        "Simulation": [
            st.Page("pages/1_Single_Run.py", title="Single Run", icon="🔬"),
            st.Page("pages/2_Multiple_Run.py", title="Multiple Run", icon="📈"),
        ],
        "Optimisation and analysis": [
            st.Page("pages/3_Digital_Formulator.py", title="Digital Formulator", icon="🧭"),
            st.Page("pages/4_Formulation_Comparison.py", title="Comparison", icon="⚗️"),
            st.Page("pages/5_Sensitivity_Analysis.py", title="Sensitivity", icon="📐"),
        ],
    }
)
navigation.run()