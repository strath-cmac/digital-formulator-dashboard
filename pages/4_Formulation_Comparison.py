from __future__ import annotations

import json

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
from utils.plotting import (
    formulation_pie,
    overlay_ar_figure,
    overlay_psd_figure,
    radar_chart,
)


api_state = refresh_api_state()
if not api_state["ok"]:
    st.error(api_state["msg"])
    st.stop()

contract = api_state["contract"]
options = api_state["options"]

if "/single_run" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /single_run endpoint used for comparison studies.")
    st.stop()

display_options, label_to_id = component_select_maps(options)
if not display_options:
    st.error("No material components were returned by the API.")
    st.stop()


def _form_key(index: int) -> str:
    return f"cmp_form_{index}"


def _cp_key(index: int) -> str:
    return f"cmp_cp_{index}"


def _name_key(index: int) -> str:
    return f"cmp_name_{index}"


render_page_header(
    "Formulation comparison",
    "Run several candidate blends through the same single-run backend endpoint and compare predicted granular, morphology, and tablet responses side by side.",
    badge="/single_run",
)

setup_left, setup_right = st.columns([1, 2], gap="large")
with setup_left:
    n_forms = st.selectbox("Number of candidate formulations", options=[2, 3, 4, 5], index=1)
with setup_right:
    st.caption("Each candidate formulation is configured in its own tab. Fractions are normalized before being sent to the backend.")

for index in range(n_forms):
    if _form_key(index) not in st.session_state:
        st.session_state[_form_key(index)] = build_default_formulation(options)
    if _cp_key(index) not in st.session_state:
        st.session_state[_cp_key(index)] = 200.0
    if _name_key(index) not in st.session_state:
        st.session_state[_name_key(index)] = f"Formulation {chr(65 + index)}"

tabs = st.tabs([f"Candidate {chr(65 + index)}" for index in range(n_forms)])
configs: list[dict] = []

for index, tab in enumerate(tabs):
    with tab:
        left, right = st.columns([3, 1], gap="large")
        with left:
            st.text_input("Label", key=_name_key(index))
            edited_df = st.data_editor(
                st.session_state[_form_key(index)],
                key=f"cmp_editor_{index}",
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    "Component": st.column_config.SelectboxColumn("Component", options=display_options, required=True, width="large"),
                    "Fraction": st.column_config.NumberColumn("Fraction (w/w)", min_value=0.0001, max_value=1.0, step=0.005, format="%.4f", width="small"),
                },
            )
            st.session_state[_form_key(index)] = edited_df
        with right:
            st.slider("Compaction pressure", min_value=50.0, max_value=450.0, step=5.0, key=_cp_key(index))
            if st.button("Reset", key=f"cmp_reset_{index}", use_container_width=True):
                st.session_state[_form_key(index)] = build_default_formulation(options)
                st.rerun()
            valid_df = edited_df.dropna(subset=["Component", "Fraction"])
            total_fraction = float(pd.to_numeric(valid_df["Fraction"], errors="coerce").fillna(0).sum())
            if abs(total_fraction - 1.0) < 0.01:
                st.success(f"Total = {total_fraction:.4f}")
            else:
                st.warning(f"Total = {total_fraction:.4f}")

        configs.append(
            {
                "name": st.session_state[_name_key(index)],
                "frame": st.session_state[_form_key(index)],
                "cp": st.session_state[_cp_key(index)],
            }
        )

run_clicked = st.button("Run comparison study", type="primary", use_container_width=True)

if run_clicked:
    results: list[dict] = []
    progress = st.progress(0, text="Running comparison simulations")
    errors: list[str] = []
    for idx, config in enumerate(configs):
        try:
            payload = normalise_formulation_frame(config["frame"], label_to_id)
            response = single_run(
                titles=payload.titles,
                components=payload.components,
                fractions=payload.fractions,
                cp=float(config["cp"]),
            )
            results.append(
                {
                    "name": config["name"],
                    "cp": float(config["cp"]),
                    "components": payload.components,
                    "fractions": payload.fractions,
                    "result": response,
                    "metrics": derived_metrics(response),
                }
            )
        except Exception as exc:
            errors.append(f"{config['name']}: {exc}")

        progress.progress((idx + 1) / len(configs), text=f"Completed {idx + 1} of {len(configs)} formulations")

    progress.empty()
    for error in errors:
        st.warning(error)

    if results:
        st.session_state["cmp_results"] = results
    else:
        st.error("All comparison runs failed.")

results = st.session_state.get("cmp_results", [])
if not results:
    render_empty_state("⚗️", "No comparison results yet", "Configure at least two candidate formulations and run the live backend simulations.")
    st.stop()

summary_rows = []
for item in results:
    result = item["result"]
    metrics = item["metrics"]
    summary_rows.append(
        {
            "Formulation": item["name"],
            "CP (MPa)": item["cp"],
            "True density": result["true_density"],
            "Bulk density": result["bulk_density"],
            "Tapped density": result["tapped_density"],
            "FFC": result["ffc"],
            "EAOIF": result["effective_angle_of_internal_friction"],
            "Carr's index": metrics["carrs_index"],
            "Hausner ratio": metrics["hausner_ratio"],
            "Porosity mean": result["porosity_mean"],
            "Tensile mean": result["tensile_mean"],
        }
    )

summary_df = pd.DataFrame(summary_rows)
tab_table, tab_radar, tab_psd, tab_ar, tab_form, tab_raw = st.tabs(
    ["Property table", "Radar", "PSD overlay", "Aspect-ratio overlay", "Compositions", "Raw export"]
)

with tab_table:
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

with tab_radar:
    radar_keys = [
        ("FFC", "FFC"),
        ("Tensile mean", "Tensile\nmean"),
        ("Porosity mean", "Porosity"),
        ("Carr's index", "Carr's\nindex"),
        ("Hausner ratio", "Hausner\nratio"),
        ("EAOIF", "EAOIF"),
        ("True density", "True\ndensity"),
    ]
    matrix = [[float(row[key]) for key, _ in radar_keys] for _, row in summary_df.iterrows()]
    st.plotly_chart(
        radar_chart(summary_df["Formulation"].tolist(), matrix, [label for _, label in radar_keys]),
        use_container_width=True,
    )

with tab_psd:
    datasets = [
        (item["name"], item["result"]["ce_diameter"], item["result"]["particle_size_dist"])
        for item in results
    ]
    st.plotly_chart(overlay_psd_figure(datasets), use_container_width=True)

with tab_ar:
    datasets = [
        (item["name"], item["result"]["Aspect Ratio"], item["result"]["aspect_ratio_dist"])
        for item in results
    ]
    st.plotly_chart(overlay_ar_figure(datasets), use_container_width=True)

with tab_form:
    columns = st.columns(min(3, len(results)))
    for idx, item in enumerate(results):
        with columns[idx % len(columns)]:
            st.caption(f"{item['name']} · {item['cp']:.0f} MPa")
            chart_labels = [format_component_option(component_id, options) for component_id in item["components"]]
            st.plotly_chart(
                formulation_pie(chart_labels, item["fractions"]),
                use_container_width=True,
                key=f"cmp_formulation_pie_{idx}",
            )

with tab_raw:
    export_payload = {
        item["name"]: {
            "cp": item["cp"],
            "components": item["components"],
            "fractions": item["fractions"],
            "result": item["result"],
        }
        for item in results
    }
    st.download_button(
        "Download JSON",
        data=json.dumps(export_payload, indent=2).encode("utf-8"),
        file_name="formulation_comparison.json",
        mime="application/json",
    )
    st.json(export_payload)