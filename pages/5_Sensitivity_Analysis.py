from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from utils.api_client import single_run
from utils.dashboard import (
    build_default_formulation,
    component_select_maps,
    derived_metrics,
    format_component_option,
    normalise_formulation_frame,
    refresh_api_state,
    render_empty_state,
    render_page_header,
)
from utils.plotting import formulation_pie, multi_line_figure, sensitivity_band_figure


_BLUE = "#0b6e69"
_ORANGE = "#c96b32"
_GREEN = "#4c7c59"
_PURPLE = "#7b5ea7"


api_state = refresh_api_state()
if not api_state["ok"]:
    st.error(api_state["msg"])
    st.stop()

contract = api_state["contract"]
options = api_state["options"]

if "/single_run" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /single_run endpoint used for sweep analysis.")
    st.stop()

display_options, label_to_id = component_select_maps(options)
if not display_options:
    st.error("No material components were returned by the API.")
    st.stop()

if "sa_form_df" not in st.session_state:
    st.session_state["sa_form_df"] = build_default_formulation(options)

render_page_header(
    "Sensitivity analysis",
    "Sweep one formulation fraction or the compaction pressure and inspect how flowability, density, porosity, and tensile response evolve across the design space.",
    badge="/single_run",
)

config_col, result_col = st.columns([1.1, 1.5], gap="large")

with config_col:
    with st.container(border=True):
        st.caption("Sweep mode")
        mode = st.radio("Mode", options=["Fraction sweep", "Pressure sweep"], horizontal=True, label_visibility="collapsed")

    with st.container(border=True):
        header_left, header_right = st.columns([2, 1])
        with header_left:
            st.caption("Base formulation")
        with header_right:
            if st.button("Reset defaults", use_container_width=True):
                st.session_state["sa_form_df"] = build_default_formulation(options)
                st.session_state.pop("sa_result_df", None)
                st.rerun()

        edited_df = st.data_editor(
            st.session_state["sa_form_df"],
            key="sa_editor",
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "Component": st.column_config.SelectboxColumn("Component", options=display_options, required=True, width="large"),
                "Fraction": st.column_config.NumberColumn("Fraction (w/w)", min_value=0.0001, max_value=1.0, step=0.005, format="%.4f", width="small"),
            },
        )
        st.session_state["sa_form_df"] = edited_df

    valid_df = edited_df.dropna(subset=["Component", "Fraction"])
    component_labels = valid_df["Component"].tolist()

    with st.container(border=True):
        st.caption("Sweep settings")
        x_values: list[float] = []
        x_label = "Parameter"
        fixed_cp = 200.0
        varied_component_label = None

        if mode == "Fraction sweep" and component_labels:
            varied_component_label = st.selectbox("Component to vary", options=component_labels)
            min_fraction = st.slider("Minimum fraction", min_value=0.01, max_value=0.80, value=0.05, step=0.01)
            max_fraction = st.slider("Maximum fraction", min_value=float(round(min_fraction + 0.05, 2)), max_value=0.95, value=max(0.40, float(round(min_fraction + 0.15, 2))), step=0.01)
            n_points = st.slider("Number of evaluation points", min_value=5, max_value=25, value=12, step=1)
            fixed_cp = st.slider("Fixed compaction pressure", min_value=50.0, max_value=450.0, value=200.0, step=5.0)
            x_values = np.linspace(min_fraction, max_fraction, n_points).tolist()
            x_label = f"{varied_component_label} fraction"
        elif mode == "Pressure sweep":
            cp_min, cp_max = st.slider("Compaction-pressure range", min_value=30.0, max_value=450.0, value=(70.0, 300.0), step=5.0)
            n_points = st.slider("Number of evaluation points", min_value=5, max_value=25, value=12, step=1)
            x_values = np.linspace(cp_min, cp_max, n_points).tolist()
            x_label = "Compaction pressure (MPa)"

    run_disabled = len(valid_df) == 0 or len(x_values) < 2
    run_clicked = st.button("Run sensitivity study", type="primary", use_container_width=True, disabled=run_disabled)


def _run_single(components: list[str], fractions: list[float], cp: float) -> dict:
    return single_run(
        titles=components,
        components=components,
        fractions=fractions,
        cp=cp,
    )


if run_clicked:
    try:
        base_payload = normalise_formulation_frame(edited_df, label_to_id)
        base_components = base_payload.components
        base_fraction_map = dict(zip(base_payload.components, base_payload.fractions))
        rows: list[dict] = []
        progress = st.progress(0, text="Running sensitivity study")

        if mode == "Fraction sweep" and varied_component_label is not None:
            varied_component = label_to_id[varied_component_label]
            other_components = [component for component in base_components if component != varied_component]
            base_other_total = sum(base_fraction_map[component] for component in other_components)

            for index, x_value in enumerate(x_values):
                fraction_map = {varied_component: x_value}
                if other_components:
                    if base_other_total > 0:
                        scale = (1.0 - x_value) / base_other_total
                        for component in other_components:
                            fraction_map[component] = max(base_fraction_map[component] * scale, 1e-6)
                    else:
                        equal_share = (1.0 - x_value) / len(other_components)
                        for component in other_components:
                            fraction_map[component] = equal_share

                run_components = list(fraction_map.keys())
                run_fractions = list(fraction_map.values())
                total = sum(run_fractions)
                run_fractions = [fraction / total for fraction in run_fractions]
                response = _run_single(run_components, run_fractions, fixed_cp)
                metrics = derived_metrics(response)
                rows.append(
                    {
                        "x": x_value,
                        "true_density": response["true_density"],
                        "bulk_density": response["bulk_density"],
                        "tapped_density": response["tapped_density"],
                        "ffc": response["ffc"],
                        "eaoif": response["effective_angle_of_internal_friction"],
                        "carrs_index": metrics["carrs_index"],
                        "hausner_ratio": metrics["hausner_ratio"],
                        "porosity_mean": response["porosity_mean"],
                        "porosity_std": response["porosity_std"],
                        "tensile_mean": response["tensile_mean"],
                        "tensile_std": response["tensile_std"],
                    }
                )
                progress.progress((index + 1) / len(x_values), text=f"Computed {index + 1} of {len(x_values)} points")
        else:
            for index, x_value in enumerate(x_values):
                response = _run_single(base_components, base_payload.fractions, float(x_value))
                metrics = derived_metrics(response)
                rows.append(
                    {
                        "x": x_value,
                        "true_density": response["true_density"],
                        "bulk_density": response["bulk_density"],
                        "tapped_density": response["tapped_density"],
                        "ffc": response["ffc"],
                        "eaoif": response["effective_angle_of_internal_friction"],
                        "carrs_index": metrics["carrs_index"],
                        "hausner_ratio": metrics["hausner_ratio"],
                        "porosity_mean": response["porosity_mean"],
                        "porosity_std": response["porosity_std"],
                        "tensile_mean": response["tensile_mean"],
                        "tensile_std": response["tensile_std"],
                    }
                )
                progress.progress((index + 1) / len(x_values), text=f"Computed {index + 1} of {len(x_values)} points")

        progress.empty()
        st.session_state["sa_result_df"] = pd.DataFrame(rows)
        st.session_state["sa_x_label"] = x_label
        st.session_state["sa_mode"] = mode
        st.session_state["sa_components"] = base_components
        st.session_state["sa_fractions"] = base_payload.fractions
        st.session_state["sa_fixed_cp"] = fixed_cp
    except Exception as exc:
        st.error(f"Sensitivity study failed: {exc}")

result_df = st.session_state.get("sa_result_df")
if result_df is None or result_df.empty:
    with result_col:
        render_empty_state("📐", "No sensitivity results yet", "Choose a sweep mode, configure the base formulation, and run the live backend study.")
    st.stop()

with result_col:
    st.caption(f"Mode: {st.session_state.get('sa_mode', mode)}")
    if st.session_state.get("sa_mode") == "Fraction sweep":
        st.caption(f"Fixed compaction pressure: {st.session_state.get('sa_fixed_cp', fixed_cp):.0f} MPa")

    tabs = st.tabs(["Flowability", "Tablet response", "Density", "Base formulation", "Raw table"])
    x_axis_label = st.session_state.get("sa_x_label", "Parameter")

    with tabs[0]:
        st.plotly_chart(
            multi_line_figure(
                result_df,
                "x",
                [
                    ("ffc", "FFC", _BLUE),
                    ("carrs_index", "Carr's index", _ORANGE),
                    ("hausner_ratio", "Hausner ratio", _GREEN),
                    ("eaoif", "EAOIF", _PURPLE),
                ],
                x_axis_label,
                "Flowability response",
                "Value",
            ),
            use_container_width=True,
        )

    with tabs[1]:
        left, right = st.columns(2, gap="large")
        with left:
            st.plotly_chart(
                sensitivity_band_figure(result_df, "x", "porosity_mean", "porosity_std", x_axis_label, "Porosity", "Porosity response", color=_BLUE),
                use_container_width=True,
            )
        with right:
            st.plotly_chart(
                sensitivity_band_figure(result_df, "x", "tensile_mean", "tensile_std", x_axis_label, "Tensile strength (MPa)", "Tensile response", color=_ORANGE),
                use_container_width=True,
            )

    with tabs[2]:
        st.plotly_chart(
            multi_line_figure(
                result_df,
                "x",
                [
                    ("true_density", "True density", _BLUE),
                    ("bulk_density", "Bulk density", _GREEN),
                    ("tapped_density", "Tapped density", _ORANGE),
                ],
                x_axis_label,
                "Density response",
                "Density (g/cm³)",
            ),
            use_container_width=True,
        )

    with tabs[3]:
        chart_labels = [format_component_option(component_id, options) for component_id in st.session_state.get("sa_components", [])]
        st.plotly_chart(
            formulation_pie(chart_labels, st.session_state.get("sa_fractions", [])),
            use_container_width=True,
        )

    with tabs[4]:
        st.dataframe(result_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV",
            data=result_df.to_csv(index=False).encode("utf-8"),
            file_name="sensitivity_analysis.csv",
            mime="text/csv",
        )