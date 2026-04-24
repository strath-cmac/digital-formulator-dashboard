from __future__ import annotations

import json
from typing import Sequence

import numpy as np
import pandas as pd
import streamlit as st

from utils.api_client import single_run
from utils.dashboard import (
    component_select_maps,
    derived_metrics,
    format_component_option,
    normalise_formulation_frame,
    refresh_api_state,
    render_empty_state,
    render_page_header,
    render_smart_formulation_editor,
)
from utils.plotting import sensitivity_figure




api_state = refresh_api_state()
if not api_state["ok"]:
    st.error(api_state["msg"])
    st.stop()

contract = api_state["contract"]
options  = api_state["options"]

if "/single_run" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /single_run endpoint used by this analysis.")
    st.stop()

_, label_to_id = component_select_maps(options)
if not label_to_id:
    st.error("No material components were returned by the API.")
    st.stop()

render_page_header(
    "Sensitivity Analysis",
    "Sweep one input variable (a component fraction or the compaction pressure) across a "
    "defined range and observe how key performance indicators respond.",
    badge="/single_run",
)

config_col, result_col = st.columns([1.15, 1.6], gap="large")

with config_col:
    form_df, form_valid = render_smart_formulation_editor(options, key_prefix="sa")

    with st.container(border=True):
        st.markdown("<p class='form-section-title'>Sweep Variable</p>", unsafe_allow_html=True)
        sweep_type = st.radio(
            "Sweep type",
            options=["Component fraction", "Compaction pressure"],
            horizontal=True,
        )

        if sweep_type == "Component fraction":
            component_choices = form_df["Component"].tolist() if form_valid and not form_df.empty else []
            if not component_choices:
                st.info("Define a valid formulation above to select a component to sweep.")
                st.stop()
            varied_label = st.selectbox("Component to vary", options=component_choices)
            base_frac_val = float(
                form_df.loc[form_df["Component"] == varied_label, "Fraction"].iloc[0]
                if not form_df.empty and varied_label in form_df["Component"].values
                else 0.05
            )
            sweep_min, sweep_max = st.slider(
                "Fraction range",
                min_value=0.001, max_value=0.995,
                value=(max(0.001, round(base_frac_val * 0.5, 3)),
                       min(0.995, round(base_frac_val * 1.5, 3))),
                step=0.001,
            )
            cp_fixed = st.slider(
                "Fixed CP (MPa)", min_value=50.0, max_value=450.0, value=200.0, step=5.0
            )
            x_label = f"{varied_label} fraction"
        else:
            varied_label = None
            cp_min, cp_max = st.slider(
                "CP range (MPa)", min_value=30.0, max_value=450.0,
                value=(70.0, 300.0), step=5.0,
            )
            x_label = "Compaction pressure (MPa)"

        n_steps = st.slider("Number of sweep points", min_value=3, max_value=30, value=8, step=1)

    run_disabled = not form_valid
    run_clicked = st.button(
        "▶  Run Sensitivity Sweep",
        type="primary",
        use_container_width=True,
        disabled=run_disabled,
    )

if run_clicked:
    try:
        base_payload = normalise_formulation_frame(form_df, label_to_id)
        base_comp   = list(base_payload.components)
        base_frac   = list(base_payload.fractions)
        base_titles = list(base_payload.titles)

        if sweep_type == "Component fraction":
            sweep_values: list[float] = list(np.linspace(sweep_min, sweep_max, n_steps))
        else:
            sweep_values = list(np.linspace(cp_min, cp_max, n_steps))

        sweep_results: list[dict] = []
        progress = st.progress(0, text="Running sensitivity sweep…")

        for i, val in enumerate(sweep_values):
            try:
                if sweep_type == "Component fraction" and varied_label is not None:
                    varied_id  = label_to_id[varied_label]
                    varied_idx = base_comp.index(varied_id) if varied_id in base_comp else None
                    if varied_idx is None:
                        st.warning(f"'{varied_label}' not in processed formulation.")
                        continue
                    new_frac = base_frac.copy()
                    new_frac[varied_idx] = float(val)
                    total = sum(new_frac)
                    if total > 0:
                        new_frac = [f / total for f in new_frac]
                    resp = single_run(titles=base_titles, components=base_comp, fractions=new_frac, cp=float(cp_fixed))
                    sweep_results.append({"sweep_value": val, "result": resp, "metrics": derived_metrics(resp)})
                else:
                    resp = single_run(titles=base_titles, components=base_comp, fractions=base_frac, cp=float(val))
                    sweep_results.append({"sweep_value": val, "result": resp, "metrics": derived_metrics(resp)})
            except Exception as exc:
                st.warning(f"Step {i + 1} failed: {exc}")
            progress.progress((i + 1) / n_steps, text=f"Step {i + 1}/{n_steps}")

        progress.empty()
        if sweep_results:
            st.session_state["sa_results"] = sweep_results
            st.session_state["sa_x_label"] = x_label
        else:
            st.error("All sweep points failed.")
    except Exception as exc:
        st.error(f"Sensitivity sweep failed: {exc}")

sweep_results = st.session_state.get("sa_results", [])
saved_x_label = st.session_state.get("sa_x_label", "Parameter")

with result_col:
    if not sweep_results:
        render_empty_state(
            "📊",
            "No sweep results yet",
            "Configure the formulation and sweep variable, then run the analysis.",
        )
        st.stop()

    rows = []
    for item in sweep_results:
        r = item["result"]
        m = item["metrics"]
        rows.append({
            saved_x_label:      item["sweep_value"],
            "FFC":              r["ffc"],
            "EAOIF":            r["effective_angle_of_internal_friction"],
            "Porosity mean":    r["porosity_mean"],
            "Porosity std":     r["porosity_std"],
            "Tensile mean":     r["tensile_mean"],
            "Tensile std":      r["tensile_std"],
            "True density":     r["true_density"],
            "Carr's index":     m["carrs_index"],
            "Hausner ratio":    m["hausner_ratio"],
        })
    sweep_df = pd.DataFrame(rows)

    x_vals = [item["sweep_value"] for item in sweep_results]
    kpi_options = [c for c in sweep_df.columns if c != saved_x_label]
    selected_kpis = st.multiselect("KPIs to plot", options=kpi_options, default=kpi_options[:4])

    if selected_kpis:
        for kpi in selected_kpis:
            fig = sensitivity_figure(x_vals, sweep_df[kpi].tolist(), x_label=saved_x_label, y_label=kpi)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select at least one KPI to display the response curves.")

    tab_table, tab_raw = st.tabs(["Results table", "Raw export"])
    with tab_table:
        st.dataframe(sweep_df, use_container_width=True, hide_index=True)
    with tab_raw:
        export_payload = {
            "x_label": saved_x_label,
            "sweep_results": [
                {"x": item["sweep_value"], "result": item["result"]} for item in sweep_results
            ],
        }
        st.download_button(
            "⬇  Download JSON",
            data=json.dumps(export_payload, indent=2).encode("utf-8"),
            file_name="sensitivity_analysis.json",
            mime="application/json",
        )
        st.json(export_payload)
