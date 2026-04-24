from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import ffc_v3, ffc_v4_class, single_run, supports_endpoint
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

_, label_to_id = component_select_maps(options)
if not label_to_id:
    st.error("No material components were returned by the API.")
    st.stop()

default_cp_bounds = options.get("current_defaults", {}).get("cp_bounds", [70.0, 250.0])
cp_lower = float(default_cp_bounds[0]) if len(default_cp_bounds) == 2 else 70.0
cp_upper = float(default_cp_bounds[1]) if len(default_cp_bounds) == 2 else 250.0
cp_default = float(round((cp_lower + cp_upper) / 2.0, 1))

render_page_header(
    "Single-Point Simulation",
    "Predict blend flowability, density, PSD, particle shape, tablet porosity, and tensile strength "
    "for one formulation at a fixed compaction pressure.",
    badge="/single_run",
)

config_col, result_col = st.columns([1.15, 1.6], gap="large")

with config_col:
    form_df, form_valid = render_smart_formulation_editor(options, key_prefix="sr")

    with st.container(border=True):
        st.markdown("<p class='form-section-title'>Process Settings</p>", unsafe_allow_html=True)
        cp = st.slider(
            "Compaction pressure (MPa)",
            min_value=30.0,
            max_value=450.0,
            value=min(max(cp_default, 30.0), 450.0),
            step=5.0,
        )

    with st.container(border=True):
        st.markdown("<p class='form-section-title'>Optional Model Comparison</p>", unsafe_allow_html=True)
        extra_ffc_supported = supports_endpoint("/ffc_new") or supports_endpoint("/ffc_class")
        compare_ffc = st.toggle(
            "Compare FFC auxiliary endpoints",
            value=False,
            disabled=not extra_ffc_supported,
            help="Calls /ffc_new and /ffc_class when available on the connected backend.",
        )
        if not extra_ffc_supported:
            st.caption("The connected backend does not currently expose the auxiliary FFC comparison endpoints.")

    run_clicked = st.button(
        "▶  Run Simulation",
        type="primary",
        use_container_width=True,
        disabled=not form_valid,
    )

if run_clicked:
    try:
        payload = normalise_formulation_frame(form_df, label_to_id)
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
        st.session_state["sr_ffc_v3"] = (
            ffc_v3(payload.titles, payload.components, payload.fractions) if compare_ffc else None
        )
        st.session_state["sr_ffc_v4"] = (
            ffc_v4_class(payload.titles, payload.components, payload.fractions) if compare_ffc else None
        )
    except Exception as exc:
        st.error(f"Simulation failed: {exc}")

result = st.session_state.get("sr_result")
payload_info = st.session_state.get("sr_payload", {})

with result_col:
    if result is None:
        render_empty_state(
            "🔬",
            "No simulation yet",
            "Configure your formulation on the left and press Run Simulation.",
        )
        st.stop()

    metrics = derived_metrics(result)
    st.caption(f"**Formulation:** {payload_info.get('summary', '')}")
    st.caption(f"**Compaction pressure:** {payload_info.get('cp', cp):.0f} MPa")

    # ── Key Performance Indicators ──────────────────────────────────────
    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("True density",   f"{result['true_density']:.4f} g/cm³")
    r1c2.metric("Bulk density",   f"{result['bulk_density']:.4f} g/cm³")
    r1c3.metric("Tapped density", f"{result['tapped_density']:.4f} g/cm³")

    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.metric("FFC",            f"{result['ffc']:.3f}")
    r2c2.metric("Carr's index",   f"{metrics['carrs_index']:.2f} %")
    r2c3.metric("Hausner ratio",  f"{metrics['hausner_ratio']:.3f}")

    r3c1, r3c2, r3c3 = st.columns(3)
    r3c1.metric("Flow class",    metrics["flow_class"])
    r3c2.metric("Porosity mean", f"{result['porosity_mean']:.4f}")
    r3c3.metric("Tensile mean",  f"{result['tensile_mean']:.3f} MPa")

    st.markdown("<br>", unsafe_allow_html=True)

    tab_overview, tab_morphology, tab_formulation, tab_raw = st.tabs(
        ["Overview", "Morphology", "Formulation", "Raw output"]
    )

    with tab_overview:
        info_a, info_b = st.columns(2, gap="medium")
        info_a.info(
            f"**Flow class:** {metrics['flow_class']}\n\n"
            f"**EAOIF:** {result['effective_angle_of_internal_friction']:.2f}°"
        )
        info_b.info(
            f"**Tensile window:** {metrics['tensile_lower']:.3f} – {metrics['tensile_upper']:.3f} MPa\n\n"
            f"**Porosity window:** {metrics['porosity_lower']:.4f} – {metrics['porosity_upper']:.4f}"
        )
        if result["effective_angle_of_internal_friction"] > 41.0:
            st.warning("EAOIF exceeds the common 41° practical threshold for robust hopper flow.")
        if result["tensile_mean"] < 1.0:
            st.warning("Predicted tensile strength is low for a conventional direct-compression tablet.")

        ffc_col1, ffc_col2, ffc_col3 = st.columns(3)
        ffc_col1.metric("FFC (primary)", f"{result['ffc']:.3f}")
        if st.session_state.get("sr_ffc_v3") is not None:
            ffc_col2.metric("FFC v3", f"{st.session_state['sr_ffc_v3']:.3f}")
        if st.session_state.get("sr_ffc_v4") is not None:
            ffc_col3.metric("FFC class", st.session_state["sr_ffc_v4"])

        scalar_rows = [
            {"Property": "True density",   "Value": f"{result['true_density']:.4f}",   "Unit": "g/cm³"},
            {"Property": "Bulk density",   "Value": f"{result['bulk_density']:.4f}",   "Unit": "g/cm³"},
            {"Property": "Tapped density", "Value": f"{result['tapped_density']:.4f}", "Unit": "g/cm³"},
            {"Property": "FFC",            "Value": f"{result['ffc']:.3f}",            "Unit": "—"},
            {"Property": "EAOIF",          "Value": f"{result['effective_angle_of_internal_friction']:.2f}", "Unit": "°"},
            {"Property": "Porosity mean",  "Value": f"{result['porosity_mean']:.4f}",  "Unit": "—"},
            {"Property": "Porosity std",   "Value": f"{result['porosity_std']:.4f}",   "Unit": "—"},
            {"Property": "Tensile mean",   "Value": f"{result['tensile_mean']:.3f}",   "Unit": "MPa"},
            {"Property": "Tensile std",    "Value": f"{result['tensile_std']:.3f}",    "Unit": "MPa"},
        ]
        st.dataframe(pd.DataFrame(scalar_rows), use_container_width=True, hide_index=True)

    with tab_morphology:
        left, right = st.columns(2, gap="medium")
        with left:
            st.plotly_chart(psd_figure(result["ce_diameter"], result["particle_size_dist"]), use_container_width=True)
            st.plotly_chart(pca_bar(result["PCs_PSD"], "PSD principal component scores"), use_container_width=True)
        with right:
            st.plotly_chart(ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]), use_container_width=True)
            st.plotly_chart(pca_bar(result["PCs_AR"], "Aspect-ratio principal component scores"), use_container_width=True)

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
            file_name="single_run_result.json",
            mime="application/json",
        )
        st.json(result)
