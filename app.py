"""
Digital Formulator Dashboard — Landing Page

Checks API health, shows available excipients / objectives / constraints,
and provides navigation hints for the three simulation tools.
"""

import os

import streamlit as st

from utils.api_client import health_check, get_options, component_label

# ── Page config ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Digital Formulator",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    if ok:
        try:
            st.session_state["api_options"] = get_options()
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

if not ok:
    _configured_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    st.warning(f"Configured `API_BASE_URL`: **{_configured_url}**")

    with st.expander("🔧 Troubleshooting — Docker networking", expanded=True):
        st.markdown(
            f"""
The dashboard tried to reach:
```
{_configured_url}/digital_formulator/options
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
            "Description":       _CON_DESC.get(c, "—"),
            "Default":           "✓" if c in def_map else "",
            "Default Threshold": def_map.get(c, "—"),
        }
        for c in constraints
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

with tab_def:
    curr = opts.get("current_defaults", {})
    if curr:
        import json
        st.code(json.dumps(curr, indent=2), language="json")
    else:
        st.info("No defaults data available.")

# ── Navigation cards ──────────────────────────────────────────────────────
st.divider()
st.subheader("Available Tools")

c1, c2, c3 = st.columns(3)
with c1:
    st.info(
        "**🔬 Single Run**\n\n"
        "Simulate granular and compacted tablet properties (density, flowability, "
        "tensile strength, porosity) for any formulation at a fixed compaction pressure.  \n\n"
        "_Use the sidebar to navigate there._"
    )
with c2:
    st.info(
        "**📈 Multiple Run**\n\n"
        "Generate a full compressibility and tensile-strength profile across a "
        "compaction-pressure range.  Fits Kawakita (porosity) and Duckworth (tensile) "
        "empirical models and plots 95 % confidence bands.  \n\n"
        "_Use the sidebar to navigate there._"
    )
with c3:
    st.info(
        "**🚀 Digital Formulator**\n\n"
        "Run NSGA-II (multi-objective) or mixed-variable GA (single-objective) to find "
        "Pareto-optimal tablet formulations satisfying user-defined constraints.  \n\n"
        "_Use the sidebar to navigate there._"
    )
