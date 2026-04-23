"""
CMAC Digital Formulator — navigation controller & home page.

app.py is the single Streamlit entry point.  It:
  1. Sets global page config and CSS (applied to every page).
  2. Renders a branded sidebar header.
  3. Defines the home page as an inline function.
  4. Registers all pages via st.navigation() so the sidebar nav
     shows proper names instead of raw filenames.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from utils.api_client import health_check, get_options, component_label, _FALLBACK_OPTIONS

# ── Global page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="CMAC Digital Formulator",
    page_icon="\U0001f48a",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS (applies to every page through the navigation controller) ──
st.markdown("""
<style>
/* ── Sidebar brand strip ──────────────────────────────────────────── */
.cmac-brand {
    background: linear-gradient(135deg, #003865 0%, #1a4f8a 100%);
    padding: 1rem 1.2rem .9rem 1.2rem;
    border-bottom: 2px solid rgba(79,142,197,.4);
    margin: -.5rem -1rem 1rem -1rem;
}
.cmac-brand .bt { font-size:1.05rem; font-weight:800; color:#fff; letter-spacing:.02em; line-height:1.2; }
.cmac-brand .bs { font-size:.7rem; color:rgba(255,255,255,.55); margin-top:.25rem; letter-spacing:.06em; text-transform:uppercase; }

/* ── Metric cards ─────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(79,142,197,.07);
    border: 1px solid rgba(79,142,197,.22);
    border-radius: 10px;
    padding: 14px 18px !important;
}

/* ── Caption labels ───────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] > p {
    text-transform: uppercase;
    letter-spacing: .08em;
    font-size: .68rem !important;
    font-weight: 700;
    color: rgba(232,240,250,.4) !important;
}

/* ── Page header banner ───────────────────────────────────────────── */
.page-header { padding: 1.2rem 0 .8rem 0; border-bottom: 2px solid rgba(79,142,197,.3); margin-bottom: 1.5rem; }
.page-header .ph-title { font-size: 1.55rem; font-weight: 700; color: #e8f0fa; line-height: 1.2; }
.page-header .ph-sub   { font-size: .88rem; color: rgba(232,240,250,.5); margin-top: .3rem; line-height: 1.5; }

/* ── Tool cards ───────────────────────────────────────────────────── */
[data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] > div[data-testid="stMarkdownContainer"] h4 {
    margin-bottom: .25rem;
}

/* ── Hide sidebar collapse toggle (nav is always visible) ─────────── */
[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Branded sidebar header ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div class="cmac-brand">
  <div class="bt">\U0001f48a Digital Formulator</div>
  <div class="bs">CMAC &nbsp;·&nbsp; University of Strathclyde</div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# Home page
# ════════════════════════════════════════════════════════════════════════════

def _home() -> None:

    # ── API health check (once per session) ──────────────────────────────
    def _check():
        ok, msg = health_check()
        st.session_state.update({"api_ok": ok, "api_msg": msg, "options_degraded": False})
        if ok:
            try:
                raw = get_options()
                st.session_state["options_degraded"] = raw is _FALLBACK_OPTIONS
                st.session_state["api_options"] = raw
            except Exception as exc:
                st.session_state.update({"api_ok": False, "api_msg": str(exc), "api_options": {}})

    if "api_ok" not in st.session_state:
        _check()

    ok      = st.session_state.get("api_ok",  False)
    msg     = st.session_state.get("api_msg", "Not yet checked")
    opts    = st.session_state.get("api_options", {})
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000")

    # ── Hero strip ───────────────────────────────────────────────────────
    hero_l, hero_r = st.columns([5, 2])
    with hero_l:
        st.markdown("""
<div style="padding:1.4rem 0 .8rem 0;">
  <div style="font-size:2.1rem;font-weight:800;color:#e8f0fa;letter-spacing:-.02em;line-height:1.15;">
    CMAC Digital Formulator
  </div>
  <div style="font-size:.92rem;color:rgba(232,240,250,.5);margin-top:.4rem;line-height:1.6;">
    In-silico tablet formulation prediction &amp; optimisation
    &nbsp;&#183;&nbsp; Physics-informed machine learning
    &nbsp;&#183;&nbsp; University of Strathclyde / CMAC
  </div>
</div>""", unsafe_allow_html=True)
    with hero_r:
        st.markdown("<div style=\'height:.7rem\'></div>", unsafe_allow_html=True)
        if ok:
            st.success("API Online", icon="\u2705")
            st.caption(api_url)
        else:
            st.error("API Offline", icon="\u274c")
            st.caption(api_url)
        if st.button("\u27f3\u2002Refresh", use_container_width=True, key="home_refresh"):
            for k in ("api_ok", "api_msg", "api_options", "options_degraded"):
                st.session_state.pop(k, None)
            st.rerun()

    st.divider()

    # ── API offline: troubleshooting ─────────────────────────────────────
    if not ok:
        with st.container(border=True):
            st.error(f"Cannot reach the API backend.  Last error: **{msg}**")
            st.markdown(f"**Endpoint tried:** `{api_url}/openapi.json`")
            st.divider()
            st.markdown("#### Troubleshooting")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Linux — same machine**")
                st.code(
                    "docker run --network=host \\\n"
                    "  -e API_BASE_URL=http://localhost:8000 \\\n"
                    "  mosalehian/digital-formulator-dashboard:latest",
                    language="bash",
                )
            with c2:
                st.markdown("**Docker Desktop (Win / macOS)**")
                st.code(
                    "docker run -p 8501:8501 \\\n"
                    "  -e API_BASE_URL=http://host.docker.internal:8000 \\\n"
                    "  mosalehian/digital-formulator-dashboard:latest",
                    language="bash",
                )
            with c3:
                st.markdown("**Remote server**")
                st.code(
                    "docker run -p 8501:8501 \\\n"
                    "  -e API_BASE_URL=http://<server-ip>:8000 \\\n"
                    "  mosalehian/digital-formulator-dashboard:latest",
                    language="bash",
                )
        st.stop()

    # ── Degraded options warning ─────────────────────────────────────────
    if st.session_state.get("options_degraded"):
        st.warning(
            "\u26a0\ufe0f  `/digital_formulator/options` returned HTTP 500.  "
            "Using built-in defaults \u2014 all simulation tools remain fully functional.",
            icon="\u26a0\ufe0f",
        )

    # ── Metrics ──────────────────────────────────────────────────────────
    n_exc = len(opts.get("available_excipients", []))
    n_api = len(opts.get("available_apis", []))
    n_obj = len(opts.get("available_objectives", []))
    n_con = len(opts.get("available_constraints", []))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Excipients in Library",     n_exc)
    m2.metric("Active Ingredients (APIs)", n_api)
    m3.metric("Optimisation Objectives",   n_obj)
    m4.metric("Constraint Types",          n_con)

    st.divider()

    # ── Tool cards ───────────────────────────────────────────────────────
    st.markdown("### Simulation & Optimisation Tools")
    t1, t2, t3, t4, t5 = st.columns(5)
    _cards = [
        (t1, "\U0001f52c", "Single Run",
         "Predict all granular and tablet properties at a **single** compaction pressure.",
         "Density \u00b7 FFC \u00b7 Porosity \u00b7 Tensile"),
        (t2, "\U0001f4c8", "Multiple Run",
         "Full compressibility **profile** across a CP range via Kawakita & Duckworth models.",
         "Kawakita \u00b7 Duckworth \u00b7 CP profile"),
        (t3, "\U0001f680", "Digital Formulator",
         "Multi-objective **genetic algorithm** (NSGA-II) to optimise formulation composition.",
         "Pareto front \u00b7 NSGA-II \u00b7 GA"),
        (t4, "\u2697\ufe0f", "Formulation Comparison",
         "Build and simulate up to **5 formulations** and compare them side-by-side.",
         "Radar \u00b7 PSD/AR overlay \u00b7 Table"),
        (t5, "\U0001f4d0", "Sensitivity Analysis",
         "Sweep one parameter while holding others fixed to map the **design space**.",
         "Fraction sweep \u00b7 CP sweep"),
    ]
    for col, icon, title, desc, tags in _cards:
        with col:
            with st.container(border=True):
                st.markdown(f"#### {icon} {title}")
                st.markdown(desc)
                st.caption(tags)

    st.divider()

    # ── Reference Data Explorer ──────────────────────────────────────────
    st.markdown("### Reference Data")
    st.caption("Select a category to explore available scientific reference data")

    _EXPLORE = [
        "\u2014 select a category \u2014",
        "\U0001f4e6  Excipient & API Library",
        "\U0001f3af  Optimisation Objectives",
        "\U0001f512  Constraints",
        "\u2699\ufe0f  Model Defaults",
    ]
    ex_col, _ = st.columns([3, 5])
    choice = ex_col.selectbox("Category", _EXPLORE, label_visibility="collapsed", key="home_explorer")

    if choice == "\U0001f4e6  Excipient & API Library":
        all_comps = opts.get("available_apis", []) + opts.get("available_excipients", [])
        rows = [
            {
                "ID":   c,
                "Name": component_label(c),
                "Role": "Active Ingredient (API)" if c in opts.get("available_apis", []) else "Excipient",
            }
            for c in all_comps
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif choice == "\U0001f3af  Optimisation Objectives":
        _OBJ = {
            "maximise_tensile":       ("Maximise tensile strength",          "Maximise mean tablet tensile strength (MPa); stored as its negation internally for pymoo minimisation."),
            "minimise_tablet_weight": ("Minimise API fraction",              "Minimises API w/w fraction, driving toward minimum viable drug loading."),
            "maximise_porosity":      ("Maximise porosity",                  "Maximises tablet porosity \u2014 useful when rapid disintegration is desired."),
            "maximise_ffc":           ("Maximise flow function coefficient", "Maximises FFC for improved powder flowability through hoppers and feeders."),
            "minimise_eaoif":         ("Minimise angle of internal friction","Minimises EAOIF \u2014 lower values indicate better free-flow behaviour."),
        }
        objectives = opts.get("available_objectives", [])
        defaults   = opts.get("current_defaults", {}).get("objectives", [])
        rows = [
            {
                "Key":         o,
                "Objective":   _OBJ.get(o, (o, ""))[0],
                "Description": _OBJ.get(o, (o, ""))[1],
                "Default":     "\u2713" if o in defaults else "",
            }
            for o in objectives
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif choice == "\U0001f512  Constraints":
        _CON = {
            "tensile_strength_min":   ("Tensile (mean\u2212std) \u2265 threshold", "Robustness: tensile strength must exceed threshold (MPa) at 1\u03c3 below mean."),
            "tensile_mean_min":       ("Mean tensile \u2265 threshold",        "Mean tensile strength must exceed threshold (MPa)."),
            "ffc_min":                ("FFC \u2265 threshold",                 "Flow function coefficient must exceed threshold."),
            "eaoif_max":              ("EAOIF \u2264 threshold",               "Effective angle of internal friction must not exceed threshold (\u00b0). Recommended max: 41\u00b0."),
            "porosity_min":           ("Porosity \u2265 threshold",            "Mean tablet porosity must exceed threshold."),
            "porosity_minus_std_min": ("Porosity (mean\u2212std) \u2265 threshold", "Robustness: porosity mean minus std must exceed threshold."),
        }
        constraints = opts.get("available_constraints", [])
        defs_list   = opts.get("current_defaults", {}).get("constraints", [])
        def_map     = {d["name"]: d["threshold"] for d in defs_list}
        rows = [
            {
                "Key":               c,
                "Condition":         _CON.get(c, (c, ""))[0],
                "Description":       _CON.get(c, (c, ""))[1],
                "Default":           "\u2713" if c in def_map else "",
                "Default Threshold": def_map.get(c, "\u2014"),
            }
            for c in constraints
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif choice == "\u2699\ufe0f  Model Defaults":
        curr = opts.get("current_defaults", {})
        if curr:
            lc, rc = st.columns(2)
            with lc:
                with st.container(border=True):
                    st.caption("Optimisation objectives")
                    for o in curr.get("objectives", []):
                        st.markdown(f"\u2022 `{o}`")
                with st.container(border=True):
                    st.caption("Constraints")
                    crows = [{"Constraint": c["name"], "Threshold": c["threshold"]}
                             for c in curr.get("constraints", [])]
                    if crows:
                        st.dataframe(pd.DataFrame(crows), use_container_width=True, hide_index=True)
            with rc:
                with st.container(border=True):
                    st.caption("Solver settings")
                    for k in ("pop_size", "n_iters", "n_threads", "cp_bounds",
                              "disintegrant_id", "disintegrant_fraction",
                              "lubricant_id", "lubricant_fraction"):
                        if k in curr:
                            st.markdown(f"**{k}:** `{curr[k]}`")
                with st.container(border=True):
                    st.caption("Default candidate excipients")
                    exc_opts = curr.get("excipient_options", [])
                    st.markdown(", ".join(f"`{e}`" for e in exc_opts) if exc_opts else "_none_")
        else:
            st.info("No defaults data available.")


# ── Navigation ────────────────────────────────────────────────────────────
_pg = st.navigation(
    {
        "Home": [
            st.Page(_home, title="Home", icon="\U0001f3e0", default=True),
        ],
        "Simulation": [
            st.Page("pages/1_Single_Run.py",  title="Single Run",   icon="\U0001f52c"),
            st.Page("pages/2_Multiple_Run.py", title="Multiple Run", icon="\U0001f4c8"),
        ],
        "Optimisation & Analysis": [
            st.Page("pages/3_Digital_Formulator.py",     title="Digital Formulator",     icon="\U0001f680"),
            st.Page("pages/4_Formulation_Comparison.py", title="Formulation Comparison", icon="\u2697\ufe0f"),
            st.Page("pages/5_Sensitivity_Analysis.py",   title="Sensitivity Analysis",   icon="\U0001f4d0"),
        ],
    }
)
_pg.run()
