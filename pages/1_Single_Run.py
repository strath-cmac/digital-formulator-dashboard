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
    "Single-Point Formulation Assessment",
    "Select a formulation composition and compaction pressure to receive a comprehensive prediction: "
    "blend flowability (FFC, EAOIF, Carr\u2019s index), powder bulk and tapped density, particle size "
    "and shape distributions, tablet porosity, and tensile strength.",
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
        st.markdown("<p class='form-section-title'>Optional Auxiliary Comparison</p>", unsafe_allow_html=True)
        extra_ffc_supported = supports_endpoint("/ffc_new") or supports_endpoint("/ffc_class")
        compare_ffc = st.toggle(
            "Compare auxiliary FFC model variants",
            value=False,
            disabled=not extra_ffc_supported,
            help="Calls secondary FFC model endpoints when available on the connected backend.",
        )
        if not extra_ffc_supported:
            st.caption("Auxiliary FFC comparison endpoints are not available on this backend.")

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
        # Powder flow interpretation
        ffc_val = result['ffc']
        if ffc_val > 10:
            flow_interpretation = "Free-flowing — suitable for direct compression without flow aids."
        elif ffc_val > 4:
            flow_interpretation = "Easy-flowing — generally suitable for direct compression."
        elif ffc_val > 2:
            flow_interpretation = "Cohesive — may require flow enhancement (e.g. glidant addition)."
        else:
            flow_interpretation = "Very cohesive — direct compression likely problematic without reformulation."
        info_a.info(
            f"**Powder flow (FFC {ffc_val:.2f}):** {metrics['flow_class']}\n\n"
            f"{flow_interpretation}\n\n"
            f"**EAOIF:** {result['effective_angle_of_internal_friction']:.2f}° "
            f"{'⚠ Exceeds 41° hopper-flow threshold' if result['effective_angle_of_internal_friction'] > 41.0 else '✓ Within acceptable range'}"
        )
        # Tablet performance interpretation
        ts = result['tensile_mean']
        if ts >= 2.0:
            tablet_note = "Good mechanical integrity — typically acceptable for tablet handling and packaging."
        elif ts >= 1.0:
            tablet_note = "Adequate tensile strength — borderline for conventional tablet robustness."
        else:
            tablet_note = "Low tensile strength — tablet may be friable; consider adjusting compaction pressure or composition."
        info_b.info(
            f"**Tensile strength:** {metrics['tensile_lower']:.3f}\u2013{metrics['tensile_upper']:.3f} MPa\n\n"
            f"{tablet_note}\n\n"
            f"**Porosity:** {metrics['porosity_lower']:.4f}\u2013{metrics['porosity_upper']:.4f}"
        )

        if result["effective_angle_of_internal_friction"] > 41.0:
            st.warning("EAOIF exceeds the 41° practical threshold — powder may exhibit poor hopper discharge. Consider adjusting the filler or lubricant.")
        if result["tensile_mean"] < 1.0:
            st.warning("Tensile strength below 1 MPa — the predicted tablet is likely too fragile for conventional processing. Try increasing the compaction pressure or substituting a filler with higher compactibility.")

        if st.session_state.get("sr_ffc_v3") is not None or st.session_state.get("sr_ffc_v4") is not None:
            ffc_col1, ffc_col2, ffc_col3 = st.columns(3)
            ffc_col1.metric("FFC (primary model)", f"{result['ffc']:.3f}")
            if st.session_state.get("sr_ffc_v3") is not None:
                ffc_col2.metric("FFC (auxiliary v3)", f"{st.session_state['sr_ffc_v3']:.3f}")
            if st.session_state.get("sr_ffc_v4") is not None:
                ffc_col3.metric("FFC class", st.session_state["sr_ffc_v4"])

        scalar_rows = [
            {"Property": "True density",              "Value": f"{result['true_density']:.4f}",   "Unit": "g/cm³", "Description": "Theoretical density of the blend based on component densities"},
            {"Property": "Bulk density",              "Value": f"{result['bulk_density']:.4f}",   "Unit": "g/cm³", "Description": "Freely settled powder density"},
            {"Property": "Tapped density",            "Value": f"{result['tapped_density']:.4f}", "Unit": "g/cm³", "Description": "Density after mechanical tapping"},
            {"Property": "Carr\u2019s index",         "Value": f"{metrics['carrs_index']:.2f}",   "Unit": "%",     "Description": "Compressibility index — <15 % excellent, 15\u201325 % passable, >35 % very poor"},
            {"Property": "Hausner ratio",             "Value": f"{metrics['hausner_ratio']:.3f}", "Unit": "\u2014", "Description": "Tapped/bulk density ratio — <1.25 good flow, >1.5 poor flow"},
            {"Property": "FFC",                       "Value": f"{result['ffc']:.3f}",            "Unit": "\u2014", "Description": "Flow Function Coefficient — >10 free-flowing, 4\u201310 easy, 2\u20134 cohesive, <2 very cohesive"},
            {"Property": "EAOIF",                     "Value": f"{result['effective_angle_of_internal_friction']:.2f}", "Unit": "\u00b0", "Description": "Effective Angle of Internal Friction — threshold for hopper flow \u224841\u00b0"},
            {"Property": "Tablet porosity (mean)",    "Value": f"{result['porosity_mean']:.4f}",  "Unit": "\u2014", "Description": "Volume fraction of voids in the tablet at specified compaction pressure"},
            {"Property": "Tablet porosity (std)",     "Value": f"{result['porosity_std']:.4f}",   "Unit": "\u2014", "Description": "Standard deviation of porosity prediction"},
            {"Property": "Tensile strength (mean)",   "Value": f"{result['tensile_mean']:.3f}",   "Unit": "MPa",   "Description": "Diametral tensile strength — target typically \u22652 MPa for robust tablets"},
            {"Property": "Tensile strength (std)",    "Value": f"{result['tensile_std']:.3f}",    "Unit": "MPa",   "Description": "Standard deviation of tensile strength prediction"},
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
