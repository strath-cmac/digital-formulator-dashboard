from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import digital_formulator, get_component_choices
from utils.dashboard import (
    component_select_maps,
    derived_metrics,
    format_component_option,
    objective_mode,
    refresh_api_state,
    render_empty_state,
    render_page_header,
)
from utils.plotting import ar_figure, formulation_bar, formulation_pie, pca_bar, psd_figure


def _constraint_status(result: dict, name: str, threshold: float) -> tuple[str, float]:
    if name == "tensile_strength_min":
        value = float(result["tensile_mean"] - result["tensile_std"])
        return ("Pass" if value >= threshold else "Fail", value)
    if name == "tensile_mean_min":
        value = float(result["tensile_mean"])
        return ("Pass" if value >= threshold else "Fail", value)
    if name == "ffc_min":
        value = float(result["ffc"])
        return ("Pass" if value >= threshold else "Fail", value)
    if name == "eaoif_max":
        value = float(result["effective_angle_of_internal_friction"])
        return ("Pass" if value <= threshold else "Fail", value)
    if name == "porosity_min":
        value = float(result["porosity_mean"])
        return ("Pass" if value >= threshold else "Fail", value)
    if name == "porosity_minus_std_min":
        value = float(result["porosity_mean"] - result["porosity_std"])
        return ("Pass" if value >= threshold else "Fail", value)
    return ("Unknown", float("nan"))


api_state = refresh_api_state()
if not api_state["ok"]:
    st.error(api_state["msg"])
    st.stop()

contract = api_state["contract"]
options = api_state["options"]

if "/digital_formulator" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /digital_formulator endpoint.")
    st.stop()

components = get_component_choices(options)
if not components:
    st.error("No material components were returned by the API.")
    st.stop()

display_options, label_to_id = component_select_maps(options)
label_by_id = {component_id: label for label, component_id in label_to_id.items()}

defaults = options.get("current_defaults", {})
api_candidates = options.get("available_apis", []) or components
search_candidates = [component_id for component_id in components]
default_constraints = defaults.get("constraints", [])

if "df_constraints_table" not in st.session_state:
    st.session_state["df_constraints_table"] = pd.DataFrame(default_constraints or [], columns=["name", "threshold"])

render_page_header(
    "Digital formulator optimisation",
    "Configure the backend search space, solver settings, and feasibility constraints, then request an optimised formulation recommendation from the DM2 optimisation pipeline.",
    badge="/digital_formulator",
)

if not options.get("available_apis"):
    st.info(
        "The backend options payload does not currently separate APIs from other materials. Any material can still be selected as the optimisation target API, but the dashboard cannot infer the role automatically."
    )

left_col, right_col = st.columns([1.1, 1.3], gap="large")

with left_col:
    with st.container(border=True):
        st.caption("1. API and target loading")
        api_labels = [format_component_option(component_id, options) for component_id in api_candidates]
        api_map = {label: component_id for label, component_id in zip(api_labels, api_candidates)}
        default_api_label = api_labels[0]
        cmac_label = st.selectbox("API material", options=api_labels, index=0)
        cmac_id = api_map[cmac_label]
        drug_loading = st.slider("Target drug loading (w/w)", min_value=0.01, max_value=0.80, value=0.20, step=0.01)
        api_fraction_variable = st.toggle("Allow API fraction to vary", value=True)
        custom_api_bounds = st.toggle("Set custom API bounds", value=False, disabled=not api_fraction_variable)
        api_fraction_bounds = None
        if api_fraction_variable and custom_api_bounds:
            b1, b2 = st.columns(2)
            api_lb = b1.number_input("API lower bound", min_value=0.01, max_value=0.95, value=max(0.01, round(drug_loading * 0.7, 3)), step=0.01)
            api_ub = b2.number_input("API upper bound", min_value=0.01, max_value=0.95, value=min(0.95, round(drug_loading * 1.3, 3)), step=0.01)
            if api_lb < api_ub:
                api_fraction_bounds = (api_lb, api_ub)
            else:
                st.error("API lower bound must be smaller than the upper bound.")

    with st.container(border=True):
        st.caption("2. Objectives")
        objective_defaults = defaults.get("objectives", [])
        selected_objectives = st.multiselect(
            "Objective functions",
            options=options.get("available_objectives", []),
            default=[objective for objective in objective_defaults if objective in options.get("available_objectives", [])],
        )
        if selected_objectives:
            st.write(objective_mode(selected_objectives))
        else:
            st.write("No objectives selected in the UI. The backend default objectives will be used.")

    with st.container(border=True):
        st.caption("3. Constraints")
        c_left, c_right = st.columns([2, 1])
        with c_right:
            if st.button("Reset defaults", use_container_width=True):
                st.session_state["df_constraints_table"] = pd.DataFrame(default_constraints or [], columns=["name", "threshold"])
                st.rerun()
        constraint_df = st.data_editor(
            st.session_state["df_constraints_table"],
            key="df_constraints_editor",
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": st.column_config.SelectboxColumn("Constraint", options=options.get("available_constraints", []), required=True),
                "threshold": st.column_config.NumberColumn("Threshold", step=0.01, format="%.4f", required=True),
            },
        )
        st.session_state["df_constraints_table"] = constraint_df

with right_col:
    with st.container(border=True):
        st.caption("4. Fixed excipients")
        disintegrant_default = defaults.get("disintegrant_id")
        lubricant_default = defaults.get("lubricant_id")
        disintegrant_label = label_by_id.get(disintegrant_default, default_api_label)
        lubricant_label = label_by_id.get(lubricant_default, default_api_label)
        d1, d2 = st.columns(2)
        disintegrant_id = label_to_id[d1.selectbox("Disintegrant", options=display_options, index=display_options.index(disintegrant_label) if disintegrant_label in display_options else 0)]
        lubricant_id = label_to_id[d2.selectbox("Lubricant", options=display_options, index=display_options.index(lubricant_label) if lubricant_label in display_options else 0)]
        disintegrant_fraction = d1.number_input("Disintegrant fraction", min_value=0.001, max_value=0.30, value=float(defaults.get("disintegrant_fraction", 0.08)), step=0.005, format="%.4f")
        lubricant_fraction = d2.number_input("Lubricant fraction", min_value=0.001, max_value=0.10, value=float(defaults.get("lubricant_fraction", 0.01)), step=0.001, format="%.4f")

    with st.container(border=True):
        st.caption("5. Search space")
        default_search = [component_id for component_id in defaults.get("excipient_options", []) if component_id in search_candidates]
        excipient_options = st.multiselect(
            "Candidate fillers",
            options=search_candidates,
            default=default_search,
            format_func=lambda component_id: format_component_option(component_id, options),
        )
        cp_bounds_default = defaults.get("cp_bounds", [70.0, 250.0])
        cp_lower, cp_upper = st.slider(
            "Compaction-pressure bounds (MPa)",
            min_value=30.0,
            max_value=450.0,
            value=(float(cp_bounds_default[0]), float(cp_bounds_default[1])) if len(cp_bounds_default) == 2 else (70.0, 250.0),
            step=5.0,
        )
        filler1_fraction_lower = st.number_input(
            "Minimum filler-1 fraction",
            min_value=0.0,
            max_value=0.6,
            value=float(defaults.get("filler1_fraction_lower", 0.0)),
            step=0.01,
        )

    with st.container(border=True):
        st.caption("6. Solver settings")
        s1, s2, s3, s4 = st.columns(4)
        pop_size = s1.number_input("Population", min_value=10, max_value=300, value=int(defaults.get("pop_size", 20)), step=5)
        n_iters = s2.number_input("Iterations", min_value=10, max_value=5000, value=int(defaults.get("n_iters", 50)), step=10)
        n_threads = s3.number_input("Threads", min_value=1, max_value=64, value=int(defaults.get("n_threads", 8)), step=1)
        seed = s4.number_input("Seed", min_value=0, max_value=9999, value=1, step=1)
        st.caption(f"Approximate evaluation budget: {int(pop_size) * int(n_iters):,} model calls.")

run_clicked = st.button("Run optimisation", type="primary", use_container_width=True)

if run_clicked:
    try:
        cleaned_constraints = (
            st.session_state["df_constraints_table"]
            .dropna(subset=["name", "threshold"])
            .to_dict(orient="records")
        )
        filtered_excipient_options = [
            component_id
            for component_id in excipient_options
            if component_id not in {cmac_id, disintegrant_id, lubricant_id}
        ]
        result = digital_formulator(
            cmac_id=cmac_id,
            drug_loading=drug_loading,
            objectives=selected_objectives or None,
            constraints=cleaned_constraints or None,
            api_fraction_variable=api_fraction_variable,
            api_fraction_bounds=api_fraction_bounds,
            disintegrant_id=disintegrant_id,
            disintegrant_fraction=disintegrant_fraction,
            lubricant_id=lubricant_id,
            lubricant_fraction=lubricant_fraction,
            excipient_options=filtered_excipient_options or None,
            filler1_fraction_lower=filler1_fraction_lower,
            cp_bounds=(cp_lower, cp_upper),
            pop_size=int(pop_size),
            n_iters=int(n_iters),
            n_threads=int(n_threads),
            seed=int(seed),
        )
        st.session_state["df_result"] = result
        st.session_state["df_request"] = {
            "cmac_id": cmac_id,
            "drug_loading": drug_loading,
            "objectives": selected_objectives or defaults.get("objectives", []),
            "constraints": cleaned_constraints,
            "excipient_options": filtered_excipient_options,
            "cp_bounds": (cp_lower, cp_upper),
        }
    except Exception as exc:
        st.error(f"Optimisation failed: {exc}")

result = st.session_state.get("df_result")
request_info = st.session_state.get("df_request", {})

if result is None:
    render_empty_state("🧭", "No optimisation yet", "Configure the search space and run the live /digital_formulator endpoint.")
    st.stop()

metrics = derived_metrics(result)
optimized_components = result.get("optimized_components", [])
optimized_fractions = result.get("optimized_fractions", [])
summary = " | ".join(
    f"{format_component_option(component_id, options)} ({fraction:.3f})"
    for component_id, fraction in zip(optimized_components, optimized_fractions)
)

st.caption(f"Optimised formulation: {summary}")
st.caption(
    f"Objective mode: {objective_mode(request_info.get('objectives', [])) if request_info.get('objectives') else 'Backend defaults'} · CP bounds searched: {request_info.get('cp_bounds', ('?', '?'))[0]} to {request_info.get('cp_bounds', ('?', '?'))[1]} MPa"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("FFC", f"{result['ffc']:.3f}")
k2.metric("Flow class", metrics["flow_class"])
k3.metric("Porosity mean", f"{result['porosity_mean']:.4f}")
k4.metric("Tensile mean", f"{result['tensile_mean']:.3f} MPa")

tab_outcome, tab_constraints, tab_morphology, tab_raw = st.tabs(
    ["Outcome", "Constraint check", "Morphology", "Raw output"]
)

with tab_outcome:
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.info(
            f"True density {result['true_density']:.4f} g/cm³ · Bulk density {result['bulk_density']:.4f} g/cm³ · Tapped density {result['tapped_density']:.4f} g/cm³"
        )
        st.info(
            f"Tensile window {metrics['tensile_lower']:.3f} to {metrics['tensile_upper']:.3f} MPa · Porosity window {metrics['porosity_lower']:.4f} to {metrics['porosity_upper']:.4f}"
        )
        if result["effective_angle_of_internal_friction"] > 41.0:
            st.warning("EAOIF exceeds the common 41° practical threshold for robust flow handling.")
        st.caption("The current backend response does not expose the selected optimum compaction pressure explicitly, so the dashboard reports the searched pressure bounds rather than a final chosen CP.")
    with right:
        optimized_labels = [format_component_option(component_id, options) for component_id in optimized_components]
        st.plotly_chart(formulation_pie(optimized_labels, optimized_fractions), use_container_width=True)
        st.plotly_chart(formulation_bar(optimized_labels, optimized_fractions), use_container_width=True)

with tab_constraints:
    constraints_to_check = request_info.get("constraints", [])
    if constraints_to_check:
        rows = []
        for item in constraints_to_check:
            status, value = _constraint_status(result, item["name"], float(item["threshold"]))
            rows.append(
                {
                    "Constraint": item["name"],
                    "Threshold": float(item["threshold"]),
                    "Observed": value,
                    "Status": status,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No explicit constraints were sent from the UI. The backend used its default feasibility configuration if defined.")

    if request_info.get("objectives"):
        st.write("Objectives used:")
        for objective in request_info["objectives"]:
            st.write(f"- {objective}")

with tab_morphology:
    left, right = st.columns(2, gap="large")
    with left:
        st.plotly_chart(psd_figure(result["ce_diameter"], result["particle_size_dist"]), use_container_width=True)
        st.plotly_chart(pca_bar(result["PCs_PSD"], "PSD principal component scores"), use_container_width=True)
    with right:
        st.plotly_chart(ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]), use_container_width=True)
        st.plotly_chart(pca_bar(result["PCs_AR"], "Aspect-ratio principal component scores"), use_container_width=True)

with tab_raw:
    st.download_button(
        "Download JSON",
        data=json.dumps(result, indent=2).encode("utf-8"),
        file_name="digital_formulator_result.json",
        mime="application/json",
    )
    st.json(result)