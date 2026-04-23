"""
Digital Formulator Dashboard — Home Page
"""

import os

import streamlit as st

from utils.api_client import health_check, get_options, component_label, _FALLBACK_OPTIONS

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Digital Formulator",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Metric card borders */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 14px 18px !important;
}
/* Uppercase caption labels */
[data-testid="stCaptionContainer"] > p {
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-size: 0.69rem !important;
    font-weight: 600;
    color: rgba(255,255,255,0.4) !important;
}
/* Hide default hamburger / sidebar toggle */
[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── API health check (runs once per session or on refresh) ────────────────
def _check_api():
    ok, msg = health_check()
    st.session_state["api_ok"]  = ok
    st.session_state["api_msg"] = msg
    st.session_state["options_degraded"] = False
    if ok:
        try:
            opts_raw = get_options()
            if opts_raw is _FALLBACK_OPTIONS:
                st.session_state["options_degraded"] = True
            st.session_state["api_options"] = opts_raw
        except Exception as e:
            st.session_state["api_ok"]  = False
            st.session_state["api_msg"] = f"Options fetch failed: {e}"
            st.session_state["api_options"] = {}

if "api_ok" not in st.session_state:
    _check_api()

ok   = st.session_state.get("api_ok",  False)
msg  = st.session_state.get("api_msg", "Not yet checked")
opts = st.session_state.get("api_options", {})

# ── Header ────────────────────────────────────────────────────────────────
title_col, status_col = st.columns([6, 2])

with title_col:
    st.markdown("# 💊 Digital Formulator")
    st.markdown(
        "AI-powered in-silico tablet formulation · "
        "Physics-informed ML models · University of Strathclyde"
    )

with status_col:
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    if ok:
        st.success(f"● API Connected")
        st.caption(api_url)
    else:
        st.error(f"● API Unavailable")
        st.caption(api_url)
    if st.button("⟳ Refresh status", use_container_width=True, key="btn_refresh"):
        for k in ["api_ok", "api_msg", "api_options", "options_degraded"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── API unavailable: full troubleshoot panel ──────────────────────────────
if not ok:
    _configured_url = api_url
    st.divider()
    with st.container(border=True):
        st.error(f"Cannot reach the API backend.  Last error: **{msg}**")
        st.markdown(f"**Configured endpoint:** `{_configured_url}/openapi.json`")
        st.divider()
        st.markdown("#### Troubleshooting checklist")

        t1, t2, t3 = st.columns(3)
        with t1:
            st.markdown("**Same machine · Linux Docker**")
            st.code(
                "docker run --network=host \\\n"
                "  -e API_BASE_URL=http://localhost:8000 \\\n"
                "  mosalehian/digital-formulator-dashboard:latest",
                language="bash",
            )
        with t2:
            st.markdown("**Same machine · Docker Desktop (Win / macOS)**")
            st.code(
                "docker run -p 8501:8501 \\\n"
                "  -e API_BASE_URL=http://host.docker.internal:8000 \\\n"
                "  mosalehian/digital-formulator-dashboard:latest",
                language="bash",
            )
        with t3:
            st.markdown("**Remote server**")
            st.code(
                "docker run -p 8501:8501 \\\n"
                "  -e API_BASE_URL=http://<server-ip>:8000 \\\n"
                "  mosalehian/digital-formulator-dashboard:latest",
                language="bash",
            )
    st.stop()

# ── Degraded endpoint warning ─────────────────────────────────────────────
if st.session_state.get("options_degraded"):
    st.warning(
        "⚠️  `/digital_formulator/options` returned HTTP 500.  "
        "Simulation endpoints are working — the Digital Formulator page uses built-in defaults.",
        icon="⚠️",
    )

st.divider()

# ── System metrics ────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Excipients in Library",    len(opts.get("available_excipients", [])))
m2.metric("Optimisation Objectives",  len(opts.get("available_objectives", [])))
m3.metric("Constraint Types",         len(opts.get("available_constraints", [])))
m4.metric("Backend API Version",      "20260306")

st.divider()

# ── Tool cards ────────────────────────────────────────────────────────────
st.subheader("Available Tools")
tc1, tc2, tc3, tc4, tc5 = st.columns(5)

with tc1:
    with st.container(border=True):
        st.markdown("#### 🔬 Single Run")
        st.markdown(
            "Predict all granular and tablet properties at a **single** "
            "compaction pressure."
        )
        st.caption("Density · FFC · Porosity · Tensile")

with tc2:
    with st.container(border=True):
        st.markdown("#### 📈 Multiple Run")
        st.markdown(
            "Generate a full compressibility **profile** across a "
            "compaction-pressure range."
        )
        st.caption("Kawakita · Duckworth · 95 % bands")

with tc3:
    with st.container(border=True):
        st.markdown("#### 🚀 Digital Formulator")
        st.markdown(
            "Multi-objective **genetic algorithm** (NSGA-II) to optimise "
            "formulation composition."
        )
        st.caption("Pareto front · GA · NSGA-II")

with tc4:
    with st.container(border=True):
        st.markdown("#### ⚗️ Comparison")
        st.markdown(
            "Build and simulate up to **5 formulations** and compare them "
            "side-by-side."
        )
        st.caption("Radar · Overlay PSD/AR · Table")

with tc5:
    with st.container(border=True):
        st.markdown("#### 📐 Sensitivity")
        st.markdown(
            "Sweep one parameter while holding all others fixed to map "
            "the **design space**."
        )
        st.caption("Fraction sweep · CP sweep")

st.divider()

# ── Reference Data Explorer ───────────────────────────────────────────────
st.subheader("Reference Data Explorer")
st.markdown(
    "Select a category below to explore the scientific reference data "
    "available in this deployment."
)

_EXPLORE_OPTS = [
    "— choose a category —",
    "📦  Excipient Library",
    "🎯  Optimisation Objectives",
    "🔒  Constraint Reference",
    "⚙️  Model Defaults",
]

explore_col, _ = st.columns([3, 5])
with explore_col:
    explore_choice = st.selectbox(
        "Reference data category",
        options=_EXPLORE_OPTS,
        label_visibility="collapsed",
        key="explore_choice",
    )

if explore_choice == "📦  Excipient Library":
    excipients = opts.get("available_excipients", [])
    if excipients:
        rows = [{"ID": e, "Full Name": component_label(e)} for e in excipients]
        import pandas as pd
        df_exc = pd.DataFrame(rows)
        st.dataframe(df_exc, use_container_width=True, hide_index=True)
    else:
        st.info("No excipient data available.")

elif explore_choice == "🎯  Optimisation Objectives":
    _OBJ_DESC = {
        "maximise_tensile":       ("Maximise tensile strength",          "The optimiser maximises mean tablet tensile strength (MPa). Stored as its negation for pymoo."),
        "minimise_tablet_weight": ("Minimise API fraction",              "Minimises API w/w fraction, driving the tablet toward the lowest possible drug loading."),
        "maximise_porosity":      ("Maximise porosity",                  "Maximises tablet porosity — useful when rapid disintegration is desired."),
        "maximise_ffc":           ("Maximise flow function coefficient", "Maximises FFC for better powder flowability."),
        "minimise_eaoif":         ("Minimise eff. angle of int. friction","Minimises EAOIF for improved flow through hoppers."),
    }
    objectives = opts.get("available_objectives", [])
    defaults   = opts.get("current_defaults", {}).get("objectives", [])
    rows = []
    for o in objectives:
        short, desc = _OBJ_DESC.get(o, (o, ""))
        rows.append({
            "Key":         o,
            "Description": short,
            "Detail":      desc,
            "Default":     "✓" if o in defaults else "",
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif explore_choice == "🔒  Constraint Reference":
    _CON_DESC = {
        "tensile_strength_min":   ("Tensile ≥ threshold",             "Mean − std tensile strength must exceed threshold (MPa)."),
        "tensile_mean_min":       ("Mean tensile ≥ threshold",         "Mean tensile strength must exceed threshold (MPa)."),
        "ffc_min":                ("FFC ≥ threshold",                  "Flow function coefficient must exceed threshold."),
        "eaoif_max":              ("EAOIF ≤ threshold",                "Effective angle of internal friction must not exceed threshold (°)."),
        "porosity_min":           ("Porosity ≥ threshold",             "Mean tablet porosity must exceed threshold."),
        "porosity_minus_std_min": ("Porosity − std ≥ threshold",       "Robustness constraint: porosity mean minus std must exceed threshold."),
    }
    constraints = opts.get("available_constraints", [])
    defs_list   = opts.get("current_defaults", {}).get("constraints", [])
    def_map     = {d["name"]: d["threshold"] for d in defs_list}
    rows = []
    for c in constraints:
        short, detail = _CON_DESC.get(c, (c, ""))
        rows.append({
            "Key":               c,
            "Condition":         short,
            "Detail":            detail,
            "Default":           "✓" if c in def_map else "",
            "Default Threshold": def_map.get(c, "—"),
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif explore_choice == "⚙️  Model Defaults":
    curr = opts.get("current_defaults", {})
    if curr:
        import json
        left_col, right_col = st.columns(2)
        with left_col:
            with st.container(border=True):
                st.caption("Optimisation Objectives (default)")
                for o in curr.get("objectives", []):
                    st.markdown(f"• `{o}`")
            with st.container(border=True):
                st.caption("Constraints (default)")
                import pandas as pd
                con_rows = [{"Constraint": c["name"], "Threshold": c["threshold"]}
                            for c in curr.get("constraints", [])]
                if con_rows:
                    st.dataframe(pd.DataFrame(con_rows), use_container_width=True, hide_index=True)
        with right_col:
            with st.container(border=True):
                st.caption("Solver Defaults")
                solver_keys = ["pop_size", "n_iters", "n_threads", "cp_bounds",
                               "disintegrant_id", "disintegrant_fraction",
                               "lubricant_id", "lubricant_fraction"]
                for k in solver_keys:
                    if k in curr:
                        st.markdown(f"**{k}:** `{curr[k]}`")
            with st.container(border=True):
                st.caption("Candidate Excipients (default search space)")
                exc_opts = curr.get("excipient_options", [])
                st.markdown(", ".join(f"`{e}`" for e in exc_opts) if exc_opts else "_none_")
    else:
        st.info("No defaults data available.")


# ── Header ───────────────────────────────────────────────────────────────
st.title("💊 Digital Formulator Dashboard")
st.markdown(
    "AI-powered in-silico tablet formulation platform built on a physics-informed "
    "system of machine-learning models.  \n"
    "Select a tool from the sidebar to get started."
)
st.divider()

# ── API Status ───────────────────────────────────────────────────────────
status_col, refresh_col = st.columns([9, 1])
with refresh_col:
    do_refresh = st.button("⟳ Refresh", use_container_width=True)

if "api_ok" not in st.session_state or do_refresh:
    ok, msg = health_check()
    st.session_state["api_ok"] = ok
    st.session_state["api_msg"] = msg
    st.session_state["options_degraded"] = False
    if ok:
        try:
            opts_raw = get_options()
            # Detect if we fell back to hardcoded defaults (server /options returned 5xx)
            if opts_raw is _FALLBACK_OPTIONS:
                st.session_state["options_degraded"] = True
            st.session_state["api_options"] = opts_raw
        except Exception as e:
            st.session_state["api_options"] = {}
            st.session_state["api_ok"] = False
            st.session_state["api_msg"] = f"Options fetch failed: {e}"

ok  = st.session_state.get("api_ok", False)
msg = st.session_state.get("api_msg", "Not yet checked")

with status_col:
    if ok:
        api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        st.success(f"✅  API Connected  ·  {api_url}")
    else:
        st.error(f"❌  API Unavailable — {msg}")

if ok and st.session_state.get("options_degraded"):
    st.warning(
        "⚠️  The `/digital_formulator/options` endpoint returned a server error (HTTP 500).  "
        "Simulation endpoints are working — using built-in defaults for the Digital Formulator page."
    )

if not ok:
    _configured_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    st.warning(f"Configured `API_BASE_URL`: **{_configured_url}**")

    with st.expander("🔧 Troubleshooting — Docker networking", expanded=True):
        st.markdown(
            f"""
The dashboard tried to reach:
```
{_configured_url}/openapi.json
```

**Pick the scenario that matches your setup:**

| Scenario | Correct `API_BASE_URL` / Docker flag |
|----------|--------------------------------------|
| API and dashboard on the **same Linux machine** (Docker bridge) | Run with `--network=host`; keep `API_BASE_URL=http://localhost:8000` |
| API and dashboard on the **same machine — Docker Desktop** (Windows / macOS) | `API_BASE_URL=http://host.docker.internal:8000` |
| API on a **different machine / remote server** | `API_BASE_URL=http://<remote-ip>:8000` and ensure port 8000 is open in the server firewall |

**Same-machine fix (Linux):**
```bash
docker run --network=host \\
  -e API_BASE_URL=http://localhost:8000 \\
  mosalehian/digital-formulator-dashboard:latest
```
*(with `--network=host` the `-p` flag is not needed — the dashboard binds directly to host port 8501)*

**Same-machine fix (Docker Desktop — Windows / macOS):**
```bash
docker run -p 8501:8501 \\
  -e API_BASE_URL=http://host.docker.internal:8000 \\
  mosalehian/digital-formulator-dashboard:latest
```

**Remote-machine fix:**
```bash
docker run -p 8501:8501 \\
  -e API_BASE_URL=http://130.159.77.49:8000 \\
  mosalehian/digital-formulator-dashboard:latest
```
*(Ensure port 8000 accepts inbound connections on the API server's firewall / security group.)*
"""
        )
    st.stop()

# ── Overview metrics ─────────────────────────────────────────────────────
opts = st.session_state.get("api_options", {})

c1, c2, c3, c4 = st.columns(4)
c1.metric("Available Excipients",    len(opts.get("available_excipients", [])))
c2.metric("Optimisation Objectives", len(opts.get("available_objectives", [])))
c3.metric("Constraint Types",        len(opts.get("available_constraints", [])))
c4.metric("API Version",             "20260306")

st.divider()

# ── Reference tables ─────────────────────────────────────────────────────
tab_exc, tab_obj, tab_con, tab_def = st.tabs(
    ["Excipients", "Objectives", "Constraints", "Current Defaults"]
)

with tab_exc:
    excipients = opts.get("available_excipients", [])
    if excipients:
        rows = [
            {"ID": e, "Display Name": component_label(e)}
            for e in excipients
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No excipient data returned from API.")

with tab_obj:
    objectives = opts.get("available_objectives", [])
    defaults   = opts.get("current_defaults", {}).get("objectives", [])
    _OBJ_DESC = {
        "maximise_tensile":       "Maximise mean tablet tensile strength (MPa)",
        "minimise_tablet_weight": "Minimise API fraction → lighter tablet (closer to target drug loading)",
        "maximise_porosity":      "Maximise tablet porosity",
        "maximise_ffc":           "Maximise flow function coefficient",
        "minimise_eaoif":         "Minimise effective angle of internal friction",
    }
    rows = [
        {
            "Key":         o,
            "Description": _OBJ_DESC.get(o, "—"),
            "Default":     "✓" if o in defaults else "",
        }
        for o in objectives
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

with tab_con:
    constraints = opts.get("available_constraints", [])
    defs_list   = opts.get("current_defaults", {}).get("constraints", [])
    def_map     = {d["name"]: d["threshold"] for d in defs_list}
    _CON_DESC = {
        "tensile_strength_min":   "Min tensile strength (mean – std) in MPa",
        "tensile_mean_min":       "Min mean tensile strength in MPa",
        "ffc_min":                "Min flow function coefficient",
        "eaoif_max":              "Max effective angle of internal friction (°)",
        "porosity_min":           "Min mean porosity",
        "porosity_minus_std_min": "Min (porosity mean – std) — robustness constraint",
    }
    rows = [
        {
            "Key":               c,
            "Condition":         "≥ threshold" if "min" in c else "≤ threshold",
            "Detail":            _CON_DESC.get(c, "—"),
            "Default":           "✓" if c in def_map else "",
            "Default Threshold": def_map.get(c, "—"),
        }
        for c in constraints
    ]
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)