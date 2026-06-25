from __future__ import annotations

import json
import threading
import time as _time

import pandas as pd
import streamlit as st

from utils.api_client import (
    component_label,
    digital_formulator,
    get_component_choices,
    get_disintegrant_choices,
    get_filler_choices,
    get_lubricant_choices,
    is_disintegrant,
    is_lubricant,
)
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


def _component_role(cid: str, cmac_id: str) -> str:
    if cid == cmac_id:
        return "💊 API"
    if is_disintegrant(cid):
        return "🧪 Disintegrant"
    if is_lubricant(cid):
        return "⚙️ Lubricant"
    return "📦 Filler"


# Short ASCII-only constraint labels used in per-row selectboxes.
# No special unicode chars (μ σ ≥ ≤ ·) — avoids Streamlit widget state corruption.
_CON_LABELS: dict = {
    "tensile_strength_min":   "Tensile (mean-std) >= threshold [MPa]  [conservative]",
    "tensile_mean_min":       "Tensile mean >= threshold [MPa]  [mean only]",
    "ffc_min":                "FFC >= threshold  [flowability lower bound]",
    "eaoif_max":              "EAOIF <= threshold [deg]  [friction upper limit]",
    "porosity_min":           "Porosity mean >= threshold  [lower bound, mean only]",
    "porosity_minus_std_min": "Porosity (mean-std) >= threshold  [conservative]",
}
_CON_LABEL_TO_ID: dict = {v: k for k, v in _CON_LABELS.items()}
_CON_OPTIONS: list = list(_CON_LABELS.values())

# ─── API state & options ───────────────────────────────────────────────────────
api_state = refresh_api_state()
if not api_state["ok"]:
    st.error(api_state["msg"])
    st.stop()

contract = api_state["contract"]
options  = api_state["options"]

if "/digital_formulator" not in contract.get("path_map", {}):
    st.error("The connected backend does not publish the /digital_formulator endpoint.")
    st.stop()

components = get_component_choices(options)
if not components:
    st.error("No material components were returned by the API.")
    st.stop()

display_options, label_to_id = component_select_maps(options)

defaults       = options.get("current_defaults", {})
api_candidates = options.get("available_apis", []) or components
disint_ids     = get_disintegrant_choices(options) or [defaults.get("disintegrant_id", components[0])]
lubricant_ids  = get_lubricant_choices(options)    or [defaults.get("lubricant_id",    components[0])]
filler_ids     = get_filler_choices(options)       or [
    cid for cid in components
    if cid not in set(api_candidates) | set(disint_ids) | set(lubricant_ids)
]

avail_objectives  = options.get("available_objectives", [])
avail_constraints = options.get("available_constraints", [])
default_constraints = defaults.get("constraints", [])

# Initialise constraint editor state as a plain list of dicts
if "df_constraints_list" not in st.session_state:
    st.session_state["df_constraints_list"] = [
        {
            "active":    True,
            "con_id":    c.get("name", avail_constraints[0] if avail_constraints else "tensile_strength_min"),
            "threshold": float(c.get("threshold", 0.0)),
        }
        for c in (default_constraints or [])
    ]
if "df_con_gen" not in st.session_state:
    st.session_state["df_con_gen"] = 0

render_page_header(
    "In-Silico Formulation Optimisation",
    "Define your target product profile — set optimisation objectives and feasibility constraints, "
    "select the API, fixed excipients, and filler candidates — then search the formulation design "
    "space using a genetic algorithm to identify compositions that maximise flowability, "
    "mechanical integrity, or both simultaneously (NSGA-II multi-objective).",
)

# ══════════════════════════════════════════════════════════════════════════════
# Layout: left (config) | right (search space + solver)
# ══════════════════════════════════════════════════════════════════════════════
left_col, right_col = st.columns([1.1, 1.3], gap="large")

with left_col:

    # ── 1. API & target loading ─────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='role-pill role-api'>💊 API &amp; Target Drug Loading</div>",
            unsafe_allow_html=True,
        )
        api_labels = [format_component_option(cid, options) for cid in api_candidates]
        api_map    = {lbl: cid for lbl, cid in zip(api_labels, api_candidates)}
        cmac_label = st.selectbox("API material", options=api_labels, index=0)
        cmac_id    = api_map[cmac_label]

        dl_col, var_col = st.columns([2, 1])
        drug_loading          = dl_col.slider("Target drug loading (w/w)", min_value=0.01, max_value=0.80, value=0.20, step=0.01)
        api_fraction_variable = var_col.toggle("Vary API fraction", value=True)

        api_fraction_bounds = None
        if api_fraction_variable:
            custom_api_bounds = st.toggle("Custom API bounds", value=False)
            if custom_api_bounds:
                b1, b2 = st.columns(2)
                api_lb = b1.number_input("API lower bound", min_value=0.01, max_value=0.95,
                                          value=max(0.01, round(drug_loading * 0.7, 3)), step=0.01)
                api_ub = b2.number_input("API upper bound", min_value=0.01, max_value=0.95,
                                          value=min(0.95, round(drug_loading * 1.3, 3)), step=0.01)
                if api_lb < api_ub:
                    api_fraction_bounds = (api_lb, api_ub)
                else:
                    st.error("API lower bound must be smaller than the upper bound.")

    # ── 2. Objectives ───────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**Optimisation Objectives**")
        _OBJ_LABELS = {
            "maximise_ffc":           "Maximise FFC (powder flowability)",
            "maximise_tensile":       "Maximise tensile strength (tablet integrity)",
            "maximise_porosity":      "Maximise tablet porosity",
            "minimise_eaoif":         "Minimise EAOIF (reduce internal friction)",
            "minimise_tablet_weight": "Minimise tablet weight",
        }
        objective_display_options = [_OBJ_LABELS.get(o, o) for o in avail_objectives]
        obj_display_to_id = {_OBJ_LABELS.get(o, o): o for o in avail_objectives}
        objective_defaults = defaults.get("objectives", [])
        default_display = [_OBJ_LABELS.get(o, o) for o in objective_defaults if o in avail_objectives]
        selected_obj_display = st.multiselect(
            "Select one objective for single-objective GA, two or more for NSGA-II multi-objective optimisation",
            options=objective_display_options,
            default=default_display,
            label_visibility="visible",
        )
        selected_objectives = [obj_display_to_id[d] for d in selected_obj_display]
        if selected_objectives:
            st.caption(f"Solver mode: **{objective_mode(selected_objectives)}**")
        else:
            st.caption("No objectives selected — the backend will apply its configured defaults.")

    # ── 3. Constraints ──────────────────────────────────────────────────────
    with st.container(border=True):
        hc1, hc2 = st.columns([3, 1])
        hc1.markdown("**Feasibility Constraints**")
        hc1.caption(
            "Thresholds any accepted formulation must satisfy. "
            "mean-std constraints are conservative and account for prediction variability."
        )
        with hc2:
            if st.button("Reset", use_container_width=True, key="df_reset_constraints"):
                st.session_state["df_constraints_list"] = [
                    {
                        "active":    True,
                        "con_id":    c.get("name", avail_constraints[0] if avail_constraints else "tensile_strength_min"),
                        "threshold": float(c.get("threshold", 0.0)),
                    }
                    for c in (default_constraints or [])
                ]
                st.session_state["df_con_gen"] += 1
                st.rerun()

        con_list = st.session_state["df_constraints_list"]
        gen      = st.session_state["df_con_gen"]

        _to_delete = None
        if con_list:
            hrow = st.columns([0.5, 4.5, 1.5, 0.8])
            hrow[0].caption("On")
            hrow[1].caption("Constraint type")
            hrow[2].caption("Threshold")
            hrow[3].caption("")
            for i, con in enumerate(con_list):
                row = st.columns([0.5, 4.5, 1.5, 0.8])
                con["active"] = row[0].checkbox(
                    "a", value=con.get("active", True),
                    key=f"g{gen}_ca_{i}", label_visibility="collapsed",
                )
                current_label = _CON_LABELS.get(con.get("con_id", ""), _CON_OPTIONS[0])
                try:
                    sel_idx = _CON_OPTIONS.index(current_label)
                except ValueError:
                    sel_idx = 0
                selected_label = row[1].selectbox(
                    "n", options=_CON_OPTIONS, index=sel_idx,
                    key=f"g{gen}_cn_{i}", label_visibility="collapsed",
                )
                con["con_id"] = _CON_LABEL_TO_ID.get(selected_label, con.get("con_id", ""))
                con["threshold"] = row[2].number_input(
                    "t", value=float(con.get("threshold", 0.0)),
                    step=0.01, format="%.4f",
                    key=f"g{gen}_ct_{i}", label_visibility="collapsed",
                )
                if row[3].button("✕", key=f"g{gen}_cd_{i}", use_container_width=True):
                    _to_delete = i
        else:
            st.caption("No constraints defined. Click '+ Add constraint' to add one.")

        if _to_delete is not None:
            con_list.pop(_to_delete)
            st.session_state["df_con_gen"] += 1
            st.rerun()

        if st.button("+ Add constraint", key="df_add_constraint"):
            default_con_id = avail_constraints[0] if avail_constraints else "tensile_strength_min"
            con_list.append({"active": True, "con_id": default_con_id, "threshold": 0.0})
            st.rerun()

with right_col:

    # ── 4. Fixed excipients (disintegrant + lubricant) ──────────────────────
    with st.container(border=True):
        st.markdown("**Fixed Excipients**")
        disint_default_idx = 0
        if defaults.get("disintegrant_id") in disint_ids:
            disint_default_idx = disint_ids.index(defaults["disintegrant_id"])
        lubricant_default_idx = 0
        if defaults.get("lubricant_id") in lubricant_ids:
            lubricant_default_idx = lubricant_ids.index(defaults["lubricant_id"])

        di_col, lu_col = st.columns(2, gap="medium")
        with di_col:
            st.markdown(
                "<div class='role-pill role-disint'>🧪 Disintegrant — CCS</div>",
                unsafe_allow_html=True,
            )
            disintegrant_id = st.selectbox(
                "Disintegrant",
                options=disint_ids,
                format_func=lambda cid: format_component_option(cid, options),
                index=disint_default_idx,
                key="df_disint",
                label_visibility="collapsed",
            )
            disintegrant_fraction = st.number_input(
                "Disintegrant fraction",
                min_value=0.001, max_value=0.30,
                value=float(defaults.get("disintegrant_fraction", 0.04)),
                step=0.005, format="%.4f", key="df_disint_f",
                label_visibility="collapsed",
            )
        with lu_col:
            st.markdown(
                "<div class='role-pill role-lubricant'>⚙️ Lubricant — MgSt</div>",
                unsafe_allow_html=True,
            )
            lubricant_id = st.selectbox(
                "Lubricant",
                options=lubricant_ids,
                format_func=lambda cid: format_component_option(cid, options),
                index=lubricant_default_idx,
                key="df_lubricant",
                label_visibility="collapsed",
            )
            lubricant_fraction = st.number_input(
                "Lubricant fraction",
                min_value=0.001, max_value=0.10,
                value=float(defaults.get("lubricant_fraction", 0.01)),
                step=0.001, format="%.4f", key="df_lubricant_f",
                label_visibility="collapsed",
            )

    # ── 5. Search space (fillers + CP bounds) ───────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='role-pill role-filler'>📦 Candidate Fillers</div>",
            unsafe_allow_html=True,
        )
        default_search = [cid for cid in defaults.get("excipient_options", []) if cid in filler_ids]
        excipient_options = st.multiselect(
            "Candidate fillers",
            options=filler_ids,
            default=default_search or filler_ids[:3],
            format_func=lambda cid: format_component_option(cid, options),
            label_visibility="collapsed",
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Compaction-Pressure Bounds (MPa)**")
        cp_bounds_default = defaults.get("cp_bounds", [70.0, 250.0])
        cp_lower_val = float(cp_bounds_default[0]) if len(cp_bounds_default) == 2 else 70.0
        cp_upper_val = float(cp_bounds_default[1]) if len(cp_bounds_default) == 2 else 250.0
        cp_lower, cp_upper = st.slider(
            "CP bounds",
            min_value=30.0, max_value=450.0,
            value=(cp_lower_val, cp_upper_val),
            step=5.0,
            label_visibility="collapsed",
        )
        filler1_fraction_lower = st.number_input(
            "Minimum filler-1 fraction",
            min_value=0.0, max_value=0.6,
            value=float(defaults.get("filler1_fraction_lower", 0.0)),
            step=0.01,
        )

    # ── 6. Solver settings ──────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**Solver Settings**")
        s1, s2, s3, s4 = st.columns(4)
        pop_size  = s1.number_input("Population",  min_value=10,  max_value=300,  value=int(defaults.get("pop_size",  20)),  step=5)
        n_iters   = s2.number_input("Iterations",  min_value=10,  max_value=5000, value=int(defaults.get("n_iters",   50)),  step=10)
        n_threads = s3.number_input("Threads",     min_value=1,   max_value=64,   value=int(defaults.get("n_threads",  8)),  step=1)
        seed      = s4.number_input("Seed",        min_value=0,   max_value=9999, value=1,                                   step=1)
        st.caption(f"Approximate evaluation budget: **{int(pop_size) * int(n_iters):,}** model calls.")

run_clicked = st.button("▶  Run Optimisation", type="primary", use_container_width=True)

if run_clicked:
    # Build constraint payload from the list-based state; skip inactive rows
    cleaned_constraints = [
        {
            "name":      con["con_id"],
            "threshold": float(con["threshold"]),
        }
        for con in st.session_state.get("df_constraints_list", [])
        if con.get("active", True) and con.get("con_id")
    ]
    filtered_fillers = [
        cid for cid in excipient_options
        if cid not in {cmac_id, disintegrant_id, lubricant_id}
    ]

    # ── Progress display ────────────────────────────────────────────────────
    _prog_info = st.empty()
    _prog_bar  = st.empty()

    _result_holder: list = [None]
    _error_holder:  list = [None]
    _done = threading.Event()

    def _run_optimisation() -> None:
        try:
            _result_holder[0] = digital_formulator(
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
                excipient_options=filtered_fillers or None,
                filler1_fraction_lower=filler1_fraction_lower,
                cp_bounds=(cp_lower, cp_upper),
                pop_size=int(pop_size),
                n_iters=int(n_iters),
                n_threads=int(n_threads),
                seed=int(seed),
            )
        except Exception as exc:
            _error_holder[0] = exc
        finally:
            _done.set()

    _thread = threading.Thread(target=_run_optimisation, daemon=True)
    _thread.start()

    total_evals = int(pop_size) * int(n_iters)
    est_seconds = max(20.0, total_evals * 0.005)
    t_start     = _time.monotonic()
    mode_label  = objective_mode(selected_objectives) if selected_objectives else "Default objectives"

    _prog_info.info(
        f"**Running {mode_label}** · "
        f"Population {int(pop_size)} × {int(n_iters)} iterations = **{total_evals:,} evaluations**"
    )

    while not _done.wait(timeout=0.4):
        elapsed  = _time.monotonic() - t_start
        frac     = min(0.97, elapsed / est_seconds)
        est_gen  = int(frac * int(n_iters))
        _prog_bar.progress(frac, text=f"Generation ~{est_gen} / {int(n_iters)}  ·  {elapsed:.0f}s elapsed")

    _thread.join()
    _prog_info.empty()
    _prog_bar.empty()

    if _error_holder[0] is not None:
        st.error(f"Optimisation failed: {_error_holder[0]}")
    else:
        st.session_state["df_result"]  = _result_holder[0]
        st.session_state["df_request"] = {
            "cmac_id":               cmac_id,
            "drug_loading":          drug_loading,
            "objectives":            selected_objectives or defaults.get("objectives", []),
            "constraints":           cleaned_constraints,
            "excipient_options":     filtered_fillers,
            "cp_bounds":             (cp_lower, cp_upper),
            "disintegrant_id":       disintegrant_id,
            "disintegrant_fraction": disintegrant_fraction,
            "lubricant_id":          lubricant_id,
            "lubricant_fraction":    lubricant_fraction,
        }

result       = st.session_state.get("df_result")
request_info = st.session_state.get("df_request", {})

if result is None:
    render_empty_state(
        "🧬",
        "No optimisation yet",
        "Configure the search space on the left and press Run Optimisation.",
    )
    st.stop()

metrics              = derived_metrics(result)
optimized_components = result.get("optimized_components", [])
optimized_fractions  = result.get("optimized_fractions", [])

# Top summary line showing ID + name
summary_parts = []
for cid, frac in zip(optimized_components, optimized_fractions):
    name = component_label(cid, options)
    part = f"{cid} ({frac:.3f})" if name == cid else f"{cid} — {name} ({frac:.3f})"
    summary_parts.append(part)
st.caption(f"**Optimised formulation:** {' | '.join(summary_parts)}")
st.caption(
    f"Objective mode: "
    f"{objective_mode(request_info['objectives']) if request_info.get('objectives') else 'Backend defaults'} · "
    f"CP bounds: {request_info.get('cp_bounds', ('?','?'))[0]} – {request_info.get('cp_bounds', ('?','?'))[1]} MPa"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("FFC",           f"{result['ffc']:.3f}")
k2.metric("Flow class",    metrics["flow_class"])
k3.metric("Porosity mean", f"{result['porosity_mean']:.4f}")
k4.metric("Tensile mean",  f"{result['tensile_mean']:.3f} MPa")

tab_outcome, tab_constraints, tab_morphology, tab_raw = st.tabs(
    ["Outcome", "Constraint check", "Morphology", "Raw output"]
)

with tab_outcome:
    # ── Formulation composition table ───────────────────────────────────────
    st.markdown("#### Optimised Formulation Composition")
    comp_rows = []
    for cid, frac in zip(optimized_components, optimized_fractions):
        name = component_label(cid, options)
        comp_rows.append({
            "ID":            cid,
            "Material name": name if name != cid else "—",
            "Role":          _component_role(cid, request_info.get("cmac_id", "")),
            "Fraction":      round(frac, 4),
            "Weight %":      round(frac * 100, 1),
        })
    st.dataframe(
        pd.DataFrame(comp_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Fraction": st.column_config.NumberColumn(format="%.4f"),
            "Weight %": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    st.divider()

    # ── Powder flow & handling ──────────────────────────────────────────────
    st.markdown("#### Powder Flow & Handling")
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    fc1.metric("FFC (predicted)",  f"{result['ffc']:.3f}")
    fc2.metric("Flow class",       metrics["flow_class"])
    fc3.metric("Carr's Index",     f"{metrics['carrs_index']:.1f} %")
    fc4.metric("Hausner Ratio",    f"{metrics['hausner_ratio']:.3f}")
    fc5.metric("EAOIF",            f"{result['effective_angle_of_internal_friction']:.1f} °")
    if result["effective_angle_of_internal_friction"] > 41.0:
        st.warning(
            f"EAOIF = {result['effective_angle_of_internal_friction']:.1f}° exceeds the 41° "
            "practical threshold for robust powder flow handling."
        )

    st.divider()

    # ── Tablet mechanical properties ────────────────────────────────────────
    st.markdown("#### Tablet Mechanical Properties")
    tc1, tc2, tc3, tc4 = st.columns(4)
    tc1.metric("Tensile mean",  f"{result['tensile_mean']:.3f} MPa")
    tc2.metric("Tensile ± σ",   f"{metrics['tensile_lower']:.3f} – {metrics['tensile_upper']:.3f} MPa")
    tc3.metric("Porosity mean", f"{result['porosity_mean']:.4f}")
    tc4.metric("Porosity ± σ",  f"{metrics['porosity_lower']:.4f} – {metrics['porosity_upper']:.4f}")

    st.divider()

    # ── Bulk densities ──────────────────────────────────────────────────────
    st.markdown("#### Bulk Material Densities")
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("True density",   f"{result['true_density']:.4f} g/cm³")
    dc2.metric("Bulk density",   f"{result['bulk_density']:.4f} g/cm³")
    dc3.metric("Tapped density", f"{result['tapped_density']:.4f} g/cm³")

    st.divider()

    # ── Formulation charts ──────────────────────────────────────────────────
    st.markdown("#### Formulation Composition Charts")
    chart_labels = [
        f"{cid} – {component_label(cid, options)}"
        if component_label(cid, options) != cid else cid
        for cid in optimized_components
    ]
    lc, rc = st.columns([1.2, 1], gap="large")
    with lc:
        st.plotly_chart(formulation_pie(chart_labels, optimized_fractions), use_container_width=True)
    with rc:
        st.plotly_chart(formulation_bar(chart_labels, optimized_fractions), use_container_width=True)

with tab_constraints:
    _CON_DISPLAY = {
        "tensile_strength_min":  "Tensile (μ−σ) ≥ threshold [MPa]",
        "tensile_mean_min":      "Tensile mean μ ≥ threshold [MPa]",
        "ffc_min":               "FFC μ ≥ threshold",
        "eaoif_max":             "EAOIF μ ≤ threshold [°]",
        "porosity_min":          "Porosity mean μ ≥ threshold",
        "porosity_minus_std_min":"Porosity (μ−σ) ≥ threshold",
    }
    _OBJ_DISPLAY = {
        "maximise_ffc":           "Maximise FFC",
        "maximise_tensile":       "Maximise tensile strength",
        "maximise_porosity":      "Maximise porosity",
        "minimise_eaoif":         "Minimise EAOIF",
        "minimise_tablet_weight": "Minimise tablet weight",
    }
    constraints_to_check = request_info.get("constraints", [])
    if constraints_to_check:
        rows = []
        for item in constraints_to_check:
            status, value = _constraint_status(result, item["name"], float(item["threshold"]))
            rows.append({
                "Constraint":      _CON_DISPLAY.get(item["name"], item["name"]),
                "Threshold":       float(item["threshold"]),
                "Predicted value": round(value, 4),
                "Status":          "✅ Pass" if status == "Pass" else "❌ Fail",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No feasibility constraints were specified. The backend applied its default configuration.")

    if request_info.get("objectives"):
        st.markdown("**Objectives optimised:**")
        for obj in request_info["objectives"]:
            st.markdown(f"- {_OBJ_DISPLAY.get(obj, obj)}")

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
        "⬇  Download JSON",
        data=json.dumps(result, indent=2).encode("utf-8"),
        file_name="digital_formulator_result.json",
        mime="application/json",
    )
    st.json(result)
