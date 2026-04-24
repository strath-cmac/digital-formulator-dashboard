from __future__ import annotations

import json

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
options  = api_state["options"]

if "/single_run" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /single_run endpoint used for comparison studies.")
    st.stop()

_, label_to_id = component_select_maps(options)
if not label_to_id:
    st.error("No material components were returned by the API.")
    st.stop()


def _cp_key(index: int) -> str:
    return f"cmp_cp_{index}"


def _name_key(index: int) -> str:
    return f"cmp_name_{index}"


render_page_header(
    "Formulation Comparison",
    "Run several candidate blends through the same single-run backend endpoint and compare predicted "
    "granular, morphology, and tablet responses side by side.",
    badge="/single_run",
)

setup_left, setup_right = st.columns([1, 3], gap="large")
with setup_left:
    n_forms = st.selectbox("Number of candidate formulations", options=[2, 3, 4, 5], index=1)
with setup_right:
    st.caption(
        "Each candidate formulation is configured in its own tab below. "
        "Fractions are normalised before being sent to the backend."
    )

for index in range(n_forms):
    if _cp_key(index) not in st.session_state:
        st.session_state[_cp_key(index)] = 200.0
    if _name_key(index) not in st.session_state:
        st.session_state[_name_key(index)] = f"Formulation {chr(65 + index)}"

tabs = st.tabs([f"Candidate {chr(65 + i)}" for i in range(n_forms)])
configs: list[dict] = []

for index, tab in enumerate(tabs):
    with tab:
        name_col, cp_col = st.columns([3, 1], gap="large")
        with name_col:
            st.text_input("Label", key=_name_key(index))
        with cp_col:
            st.slider(
                "CP (MPa)",
                min_value=50.0, max_value=450.0,
                step=5.0, key=_cp_key(index),
            )

        form_df, _ = render_smart_formulation_editor(
            options,
            key_prefix=f"cmp_{index}",
            show_reset=True,
        )
        configs.append(
            {
                "name": st.session_state[_name_key(index)],
                "frame": form_df,
                "cp": st.session_state[_cp_key(index)],
            }
        )

run_clicked = st.button("▶  Run Comparison Study", type="primary", use_container_width=True)

if run_clicked:
    results: list[dict] = []
    progress = st.progress(0, text="Running comparison simulations…")
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

        progress.progress((idx + 1) / len(configs), text=f"Completed {idx + 1} of {len(configs)}")

    progress.empty()
    for error in errors:
        st.warning(error)

    if results:
        st.session_state["cmp_results"] = results
    else:
        st.error("All comparison runs failed.")

results = st.session_state.get("cmp_results", [])
if not results:
    render_empty_state(
        "⚗️",
        "No comparison results yet",
        "Configure at least two candidate formulations above and run the comparison.",
    )
    st.stop()

summary_rows = []
for item in results:
    r = item["result"]
    m = item["metrics"]
    summary_rows.append(
        {
            "Formulation":   item["name"],
            "CP (MPa)":      item["cp"],
            "True density":  r["true_density"],
            "Bulk density":  r["bulk_density"],
            "Tapped density":r["tapped_density"],
            "FFC":           r["ffc"],
            "EAOIF":         r["effective_angle_of_internal_friction"],
            "Carr's index":  m["carrs_index"],
            "Hausner ratio": m["hausner_ratio"],
            "Porosity mean": r["porosity_mean"],
            "Tensile mean":  r["tensile_mean"],
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
        ("FFC",          "FFC"),
        ("Tensile mean", "Tensile\nmean"),
        ("Porosity mean","Porosity"),
        ("Carr's index", "Carr's\nindex"),
        ("Hausner ratio","Hausner\nratio"),
        ("EAOIF",        "EAOIF"),
        ("True density", "True\ndensity"),
    ]
    matrix = [[float(row[k]) for k, _ in radar_keys] for _, row in summary_df.iterrows()]
    st.plotly_chart(
        radar_chart(summary_df["Formulation"].tolist(), matrix, [lbl for _, lbl in radar_keys]),
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
            chart_labels = [format_component_option(cid, options) for cid in item["components"]]
            st.plotly_chart(
                formulation_pie(chart_labels, item["fractions"]),
                use_container_width=True,
                key=f"cmp_pie_{idx}",
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
        "⬇  Download JSON",
        data=json.dumps(export_payload, indent=2).encode("utf-8"),
        file_name="formulation_comparison.json",
        mime="application/json",
    )
    st.json(export_payload)
