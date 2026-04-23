from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import ffc_v3, ffc_v4_class, single_run, supports_endpoint
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
from utils.plotting import ar_figure, formulation_bar, formulation_pie, pca_bar, psd_figure


api_state = refresh_api_state()
if not api_state["ok"]:
    st.error(api_state["msg"])
    st.stop()

contract = api_state["contract"]
options = api_state["options"]

if "/single_run" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /single_run endpoint.")
    st.stop()

display_options, label_to_id = component_select_maps(options)
if not display_options:
    st.error("No material components were returned by the API.")
    st.stop()

if "sr_form_df" not in st.session_state:
    st.session_state["sr_form_df"] = build_default_formulation(options)

default_cp_bounds = options.get("current_defaults", {}).get("cp_bounds", [70.0, 250.0])
cp_lower = float(default_cp_bounds[0]) if len(default_cp_bounds) == 2 else 70.0
cp_upper = float(default_cp_bounds[1]) if len(default_cp_bounds) == 2 else 250.0
cp_default = float(round((cp_lower + cp_upper) / 2.0, 1))

render_page_header(
    "Single-point simulation",
    "Predict blend flowability, density, PSD, particle shape, tablet porosity, and tensile strength for one formulation at a fixed compaction pressure.",
    badge="/single_run",
)

config_col, result_col = st.columns([1.1, 1.5], gap="large")

with config_col:
    top_left, top_right = st.columns([2, 1])
    with top_left:
        st.caption("Formulation builder")
    with top_right:
        if st.button("Reset defaults", use_container_width=True):
            st.session_state["sr_form_df"] = build_default_formulation(options)
            st.session_state.pop("sr_result", None)
            st.rerun()

    edited_df = st.data_editor(
        st.session_state["sr_form_df"],
        key="sr_editor",
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Component": st.column_config.SelectboxColumn(
                "Component",
                options=display_options,
                required=True,
                width="large",
                help="Material identifiers come from the live API options payload.",
            ),
            "Fraction": st.column_config.NumberColumn(
                "Fraction (w/w)",
                min_value=0.0001,
                max_value=1.0,
                step=0.005,
                format="%.4f",
                width="small",
            ),
        },
    )
    st.session_state["sr_form_df"] = edited_df

    valid_df = edited_df.dropna(subset=["Component", "Fraction"])
    total_fraction = float(pd.to_numeric(valid_df["Fraction"], errors="coerce").fillna(0).sum())
    if abs(total_fraction - 1.0) < 0.01:
        st.success(f"Total fraction = {total_fraction:.4f}")
    else:
        st.warning(f"Total fraction = {total_fraction:.4f}. Values will be normalized before submission.")

    with st.container(border=True):
        st.caption("Process settings")
        cp = st.slider(
            "Compaction pressure (MPa)",
            min_value=30.0,
            max_value=450.0,
            value=min(max(cp_default, 30.0), 450.0),
            step=5.0,
        )
        st.write(f"Selected pressure: {cp:.0f} MPa")

    with st.container(border=True):
        st.caption("Optional model comparison")
        extra_ffc_supported = supports_endpoint("/ffc_new") or supports_endpoint("/ffc_class")
        compare_ffc = st.toggle(
            "Compare FFC auxiliary endpoints",
            value=False,
            disabled=not extra_ffc_supported,
            help="Calls /ffc_new and /ffc_class when they are available on the connected backend.",
        )
        if not extra_ffc_supported:
            st.info("The connected backend does not currently expose the auxiliary FFC comparison endpoints.")

    run_disabled = len(valid_df) == 0
    run_clicked = st.button("Run single-point simulation", type="primary", use_container_width=True, disabled=run_disabled)

if run_clicked:
    try:
        payload = normalise_formulation_frame(edited_df, label_to_id)
        result = single_run(
            titles=payload.titles,
            components=payload.components,
            fractions=payload.fractions,
            cp=cp,
        )
        st.session_state["sr_payload"] = {
            "components": payload.components,
            "titles": payload.titles,
            "fractions": payload.fractions,
            "summary": summarise_formulation(payload, options),
            "cp": cp,
        }
        st.session_state["sr_result"] = result
        st.session_state["sr_ffc_v3"] = ffc_v3(payload.titles, payload.components, payload.fractions) if compare_ffc else None
        st.session_state["sr_ffc_v4"] = ffc_v4_class(payload.titles, payload.components, payload.fractions) if compare_ffc else None
    except Exception as exc:
        st.error(f"Simulation failed: {exc}")

result = st.session_state.get("sr_result")
payload_info = st.session_state.get("sr_payload", {})

with result_col:
    if result is None:
        render_empty_state("🔬", "No simulation yet", "Build a formulation, set a compaction pressure, and run the live /single_run endpoint.")
        st.stop()

    metrics = derived_metrics(result)
    st.caption(f"Formulation: {payload_info.get('summary', '')}")
    st.caption(f"Compaction pressure: {payload_info.get('cp', cp):.0f} MPa")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("True density", f"{result['true_density']:.4f} g/cm³")
    k2.metric("Bulk density", f"{result['bulk_density']:.4f} g/cm³")
    k3.metric("Tapped density", f"{result['tapped_density']:.4f} g/cm³")
    k4.metric("FFC", f"{result['ffc']:.3f}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Carr's index", f"{metrics['carrs_index']:.2f} %")
    k6.metric("Hausner ratio", f"{metrics['hausner_ratio']:.3f}")
    k7.metric("Porosity mean", f"{result['porosity_mean']:.4f}")
    k8.metric("Tensile mean", f"{result['tensile_mean']:.3f} MPa")

    tab_overview, tab_morphology, tab_formulation, tab_raw = st.tabs(
        ["Overview", "Morphology", "Formulation", "Raw output"]
    )

    with tab_overview:
        left, right = st.columns([1.2, 1], gap="large")
        with left:
            info_a, info_b = st.columns(2)
            info_a.info(
                f"Flow classification: {metrics['flow_class']}\n\n"
                f"EAOIF = {result['effective_angle_of_internal_friction']:.2f}°"
            )
            info_b.info(
                f"Tensile window: {metrics['tensile_lower']:.3f} to {metrics['tensile_upper']:.3f} MPa\n\n"
                f"Porosity window: {metrics['porosity_lower']:.4f} to {metrics['porosity_upper']:.4f}"
            )
            if result["effective_angle_of_internal_friction"] > 41.0:
                st.warning("EAOIF exceeds the common 41° practical threshold for robust hopper flow.")
            if result["tensile_mean"] < 1.0:
                st.warning("Predicted tensile strength is low for a conventional direct-compression tablet.")

        with right:
            c1, c2, c3 = st.columns(3)
            c1.metric("Flow class", metrics["flow_class"])
            if st.session_state.get("sr_ffc_v3") is not None:
                c2.metric("FFC v3", f"{st.session_state['sr_ffc_v3']:.3f}")
            if st.session_state.get("sr_ffc_v4") is not None:
                c3.metric("FFC class", st.session_state["sr_ffc_v4"])

            scalar_rows = [
                {"Property": "True density", "Value": result["true_density"], "Unit": "g/cm³"},
                {"Property": "Bulk density", "Value": result["bulk_density"], "Unit": "g/cm³"},
                {"Property": "Tapped density", "Value": result["tapped_density"], "Unit": "g/cm³"},
                {"Property": "FFC", "Value": result["ffc"], "Unit": "-"},
                {"Property": "EAOIF", "Value": result["effective_angle_of_internal_friction"], "Unit": "°"},
                {"Property": "Porosity mean", "Value": result["porosity_mean"], "Unit": "-"},
                {"Property": "Porosity std", "Value": result["porosity_std"], "Unit": "-"},
                {"Property": "Tensile mean", "Value": result["tensile_mean"], "Unit": "MPa"},
                {"Property": "Tensile std", "Value": result["tensile_std"], "Unit": "MPa"},
            ]
            st.dataframe(pd.DataFrame(scalar_rows), use_container_width=True, hide_index=True)

    with tab_morphology:
        plot_left, plot_right = st.columns(2, gap="large")
        with plot_left:
            st.plotly_chart(psd_figure(result["ce_diameter"], result["particle_size_dist"]), use_container_width=True)
            st.plotly_chart(pca_bar(result["PCs_PSD"], "PSD principal component scores"), use_container_width=True)
        with plot_right:
            st.plotly_chart(ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]), use_container_width=True)
            st.plotly_chart(pca_bar(result["PCs_AR"], "Aspect-ratio principal component scores"), use_container_width=True)

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
            file_name="single_run_result.json",
            mime="application/json",
        )
        st.json(result)