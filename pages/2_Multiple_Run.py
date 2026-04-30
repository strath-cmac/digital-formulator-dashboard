from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import multiple_run
from utils.dashboard import (
    component_select_maps,
    derived_metrics,
    format_component_option,
    normalise_formulation_frame,
    refresh_api_state,
    render_empty_state,
    render_page_header,
    render_smart_formulation_editor,
    summarise_formulation,
)
from utils.plotting import compressibility_figure, formulation_bar, formulation_pie, tensile_figure


api_state = refresh_api_state()
if not api_state["ok"]:
    st.error(api_state["msg"])
    st.stop()

contract = api_state["contract"]
options = api_state["options"]

if "/multiple_run" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /multiple_run endpoint.")
    st.stop()

_, label_to_id = component_select_maps(options)
if not label_to_id:
    st.error("No material components were returned by the API.")
    st.stop()

default_cp_bounds = options.get("current_defaults", {}).get("cp_bounds", [70.0, 250.0])
cp_default_low  = float(default_cp_bounds[0]) if len(default_cp_bounds) == 2 else 70.0
cp_default_high = float(default_cp_bounds[1]) if len(default_cp_bounds) == 2 else 250.0

render_page_header(
    "Compressibility Profile Analysis",
    "Predict tablet porosity and tensile-strength profiles across a compaction-pressure range. "
    "The platform fits the Kawakita\u2013Lud\u017ee compressibility model and the Duckworth "
    "tensile\u2013porosity relationship to characterise the full compactibility window of your blend.",
)

config_col, result_col = st.columns([1.15, 1.6], gap="large")

with config_col:
    form_df, form_valid = render_smart_formulation_editor(options, key_prefix="mr")

    with st.container(border=True):
        st.markdown("<p class='form-section-title'>Compaction-Pressure Sweep</p>", unsafe_allow_html=True)
        cp_min, cp_max = st.slider(
            "Compaction-pressure range (MPa)",
            min_value=30.0,
            max_value=450.0,
            value=(min(max(cp_default_low, 30.0), 430.0), min(max(cp_default_high, 50.0), 450.0)),
            step=5.0,
        )
        n_runs = st.slider("Number of profile points", min_value=3, max_value=20, value=7, step=1)
        if cp_min >= cp_max:
            st.error("The lower pressure must be smaller than the upper pressure.")

    run_disabled = not form_valid or cp_min >= cp_max
    run_clicked = st.button(
        "▶  Run Empirical Profile",
        type="primary",
        use_container_width=True,
        disabled=run_disabled,
    )

if run_clicked:
    try:
        payload = normalise_formulation_frame(form_df, label_to_id)
        result = multiple_run(
            titles=payload.titles,
            components=payload.components,
            fractions=payload.fractions,
            cp_range=(cp_min, cp_max),
            n_runs=n_runs,
        )
        st.session_state["mr_result"] = result
        st.session_state["mr_payload"] = {
            "components": payload.components,
            "fractions": payload.fractions,
            "summary": summarise_formulation(payload, options),
            "cp_min": cp_min,
            "cp_max": cp_max,
            "n_runs": n_runs,
        }
    except Exception as exc:
        st.error(f"Profile simulation failed: {exc}")

result = st.session_state.get("mr_result")
payload_info = st.session_state.get("mr_payload", {})

with result_col:
    if result is None:
        render_empty_state(
            "📈",
            "No profile yet",
            "Configure a formulation on the left and run the empirical profile endpoint.",
        )
        st.stop()

    results_df = pd.DataFrame(result.get("results_df", []))
    metrics    = derived_metrics(result)
    kawakita   = result.get("kawakita_params", {})
    duckworth  = result.get("duckworth_params", {})

    st.caption(f"**Formulation:** {payload_info.get('summary', '')}")
    st.caption(
        f"**Pressure range:** {payload_info.get('cp_min', cp_min):.0f} – "
        f"{payload_info.get('cp_max', cp_max):.0f} MPa · "
        f"{payload_info.get('n_runs', n_runs)} evaluations"
    )

    # ── Empirical model parameters ──────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Initial porosity (a₀)",
        f"{float(kawakita.get('init_por', 0.0)):.4f}",
        help="Kawakita–Luděe a parameter: porosity of the loosely packed bed before compression",
    )
    k2.metric(
        "Kawakita B",
        f"{float(kawakita.get('B', 0.0)):.5f}",
        help="Kawakita–Luděe B parameter: reciprocal of the mean yield pressure; higher B = more compressible blend",
    )
    k3.metric(
        "Duckworth t̂",
        f"{float(duckworth.get('t_hat', 0.0)):.4f} MPa",
        help="Duckworth characteristic tensile strength: tensile strength at zero porosity",
    )
    k4.metric(
        "Duckworth kB",
        f"{float(duckworth.get('kb', 0.0)):.5f}",
        help="Duckworth compressibility factor: rate of tensile strength gain with decreasing porosity",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    tab_profiles, tab_snapshot, tab_formulation, tab_raw = st.tabs(
        ["Profiles", "Blend snapshot", "Formulation", "Raw output"]
    )

    with tab_profiles:
        left, right = st.columns(2, gap="medium")
        with left:
            st.plotly_chart(compressibility_figure(results_df), use_container_width=True)
            st.caption("Porosity response across compaction pressure.")
        with right:
            st.plotly_chart(tensile_figure(results_df), use_container_width=True)
            st.caption("Tensile strength profile via the Duckworth relation.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)

    with tab_snapshot:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("FFC",           f"{result['ffc']:.3f}")
        s2.metric("Flow class",    metrics["flow_class"])
        s3.metric("Porosity (at lower CP)", f"{result['porosity_mean']:.4f}")
        s4.metric("Tensile (at lower CP)",  f"{result['tensile_mean']:.3f} MPa")
        st.info(
            f"**Blend snapshot at the lower pressure bound ({payload_info.get('cp_min', cp_min):.0f} MPa):** "
            f"Carr\u2019s index {metrics['carrs_index']:.2f}\u202f%, "
            f"Hausner ratio {metrics['hausner_ratio']:.3f}, "
            f"EAOIF {result['effective_angle_of_internal_friction']:.2f}\u00b0. "
            "These bulk-flow properties are pressure-independent and represent the uncompacted blend."
        )
        if result["effective_angle_of_internal_friction"] > 41.0:
            st.warning("EAOIF exceeds 41\u00b0 — this blend may exhibit poor hopper discharge. Consider adding a glidant or switching the filler grade.")

    with tab_formulation:
        chart_labels = [
            format_component_option(cid, options) for cid in payload_info.get("components", [])
        ]
        chart_left, chart_right = st.columns(2, gap="medium")
        with chart_left:
            st.plotly_chart(
                formulation_pie(chart_labels, payload_info.get("fractions", [])),
                use_container_width=True,
            )
        with chart_right:
            st.plotly_chart(
                formulation_bar(chart_labels, payload_info.get("fractions", [])),
                use_container_width=True,
            )

    with tab_raw:
        st.download_button(
            "⬇  Download JSON",
            data=json.dumps(result, indent=2).encode("utf-8"),
            file_name="multiple_run_result.json",
            mime="application/json",
        )
        st.json(result)
