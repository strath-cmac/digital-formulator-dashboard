from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import multiple_run
from utils.dashboard import (
    build_default_formulation,
    component_select_maps,
    derived_metrics,
    format_component_option,
    normalise_formulation_frame,
    refresh_api_state,
    render_empty_state,
    render_page_header,
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

display_options, label_to_id = component_select_maps(options)
if not display_options:
    st.error("No material components were returned by the API.")
    st.stop()

if "mr_form_df" not in st.session_state:
    st.session_state["mr_form_df"] = build_default_formulation(options)

default_cp_bounds = options.get("current_defaults", {}).get("cp_bounds", [70.0, 250.0])
cp_default_low = float(default_cp_bounds[0]) if len(default_cp_bounds) == 2 else 70.0
cp_default_high = float(default_cp_bounds[1]) if len(default_cp_bounds) == 2 else 250.0

render_page_header(
    "Multiple-run profile analysis",
    "Predict porosity and tensile-strength profiles across a compaction-pressure range and inspect the empirical Kawakita and Duckworth parameters returned by the backend.",
    badge="/multiple_run",
)

config_col, result_col = st.columns([1.1, 1.5], gap="large")

with config_col:
    top_left, top_right = st.columns([2, 1])
    with top_left:
        st.caption("Formulation builder")
    with top_right:
        if st.button("Reset defaults", use_container_width=True):
            st.session_state["mr_form_df"] = build_default_formulation(options)
            st.session_state.pop("mr_result", None)
            st.rerun()

    edited_df = st.data_editor(
        st.session_state["mr_form_df"],
        key="mr_editor",
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Component": st.column_config.SelectboxColumn("Component", options=display_options, required=True, width="large"),
            "Fraction": st.column_config.NumberColumn("Fraction (w/w)", min_value=0.0001, max_value=1.0, step=0.005, format="%.4f", width="small"),
        },
    )
    st.session_state["mr_form_df"] = edited_df

    valid_df = edited_df.dropna(subset=["Component", "Fraction"])
    total_fraction = float(pd.to_numeric(valid_df["Fraction"], errors="coerce").fillna(0).sum())
    if abs(total_fraction - 1.0) < 0.01:
        st.success(f"Total fraction = {total_fraction:.4f}")
    else:
        st.warning(f"Total fraction = {total_fraction:.4f}. Values will be normalized before submission.")

    with st.container(border=True):
        st.caption("Compaction-pressure sweep")
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

    run_disabled = len(valid_df) == 0 or cp_min >= cp_max
    run_clicked = st.button("Run empirical profile", type="primary", use_container_width=True, disabled=run_disabled)

if run_clicked:
    try:
        payload = normalise_formulation_frame(edited_df, label_to_id)
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
        render_empty_state("📈", "No profile yet", "Build a formulation and run the live /multiple_run endpoint to generate compressibility and tensile profiles.")
        st.stop()

    results_df = pd.DataFrame(result.get("results_df", []))
    metrics = derived_metrics(result)
    kawakita = result.get("kawakita_params", {})
    duckworth = result.get("duckworth_params", {})

    st.caption(f"Formulation: {payload_info.get('summary', '')}")
    st.caption(
        f"Pressure range: {payload_info.get('cp_min', cp_min):.0f} to {payload_info.get('cp_max', cp_max):.0f} MPa · {payload_info.get('n_runs', n_runs)} evaluations"
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Initial porosity a0", f"{float(kawakita.get('init_por', 0.0)):.4f}")
    k2.metric("Kawakita B", f"{float(kawakita.get('B', 0.0)):.5f}")
    k3.metric("Duckworth t-hat", f"{float(duckworth.get('t_hat', 0.0)):.4f} MPa")
    k4.metric("Duckworth kB", f"{float(duckworth.get('kb', 0.0)):.5f}")

    tab_profiles, tab_snapshot, tab_formulation, tab_raw = st.tabs(
        ["Profiles", "Blend snapshot", "Formulation", "Raw output"]
    )

    with tab_profiles:
        left, right = st.columns(2, gap="large")
        with left:
            st.plotly_chart(compressibility_figure(results_df), use_container_width=True)
            st.caption("Porosity response across compaction pressure from the empirical multi-run endpoint.")
        with right:
            st.plotly_chart(tensile_figure(results_df), use_container_width=True)
            st.caption("Tensile strength profile propagated through the Duckworth relation.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)

    with tab_snapshot:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("FFC", f"{result['ffc']:.3f}")
        s2.metric("Flow class", metrics["flow_class"])
        s3.metric("Porosity mean", f"{result['porosity_mean']:.4f}")
        s4.metric("Tensile mean", f"{result['tensile_mean']:.3f} MPa")
        st.info(
            f"Lower-bound pressure blend snapshot: Carr's index {metrics['carrs_index']:.2f} %, Hausner ratio {metrics['hausner_ratio']:.3f}, EAOIF {result['effective_angle_of_internal_friction']:.2f}°."
        )
        if result["effective_angle_of_internal_friction"] > 41.0:
            st.warning("EAOIF exceeds the common 41° practical threshold for good powder flow.")

    with tab_formulation:
        chart_left, chart_right = st.columns(2, gap="large")
        chart_labels = [format_component_option(component_id, options) for component_id in payload_info.get("components", [])]
        with chart_left:
            st.plotly_chart(formulation_pie(chart_labels, payload_info.get("fractions", [])), use_container_width=True)
        with chart_right:
            st.plotly_chart(formulation_bar(chart_labels, payload_info.get("fractions", [])), use_container_width=True)

    with tab_raw:
        st.download_button(
            "Download JSON",
            data=json.dumps(result, indent=2).encode("utf-8"),
            file_name="multiple_run_result.json",
            mime="application/json",
        )
        st.json(result)