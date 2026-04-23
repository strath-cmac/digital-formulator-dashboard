"""
Digital Formulator — In-Silico Formulation Optimisation

GUI over POST /digital_formulator:
  ① API / Drug Settings      – select the active ingredient and drug loading
  ② Objectives               – 1 objective → GA,  2+ → NSGA-II Pareto
  ③ Constraints              – add / remove feasibility constraints dynamically
  ④ Fixed Excipients         – disintegrant and lubricant (fixed fractions)
  ⑤ Filler Search Space      – candidate fillers, CP range, filler bounds
  ⑥ Solver Settings          – pop_size, n_iters, n_threads, seed
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import (
    get_options,
    digital_formulator,
    component_label,
    component_short_name,
    is_api,
)
from utils.plotting import psd_figure, ar_figure, formulation_pie, formulation_bar, pca_bar

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='page-header'>
  <div class='ph-title'>🚀 Formulation Optimisation</div>
  <div class='ph-sub'>Multi-objective genetic algorithm (NSGA-II) or single-objective GA to find optimal
  tablet formulations &mdash; typical runtimes 1–10 min depending on solver settings</div>
</div>""", unsafe_allow_html=True)

# ── Load API options ──────────────────────────────────────────────────────────
if "api_options" not in st.session_state:
    try:
        st.session_state["api_options"] = get_options()
    except Exception as exc:
        st.error(f"Cannot reach the Digital Formulator API: {exc}")
        st.stop()

opts            = st.session_state["api_options"]
all_excipients  = opts.get("available_excipients", [])
all_apis        = opts.get("available_apis", [])
all_components  = all_apis + all_excipients
all_objectives  = opts.get("available_objectives", [])
all_constraints = opts.get("available_constraints", [])
defs            = opts.get("current_defaults", {})

if not all_components:
    st.error("No components returned by the API. Is the backend running?")
    st.stop()

# For the API selector, prefer the known APIs list; if empty fall back to all materials
_api_candidates = all_apis if all_apis else all_components

# ── Session-state: dynamic constraints table ──────────────────────────────────
if "df_constraints" not in st.session_state:
    st.session_state["df_constraints"] = [
        {"name": c["name"], "threshold": float(c["threshold"])}
        for c in defs.get("constraints", [])
    ]

# ═══════════════════════════════════════════════════════════════════════════════
# ① API / Drug Settings
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("① API / Drug Settings", expanded=True):
    if all_apis:
        st.caption("APIs identified from the material database are shown first.")
    else:
        st.info(
            "The backend returned all materials under a single category.  "
            "Select the component that is your **active pharmaceutical ingredient (API)** — "
            "components such as `dm1` (Dexamethasone), `ib2` (Ibuprofen) etc.",
            icon="ℹ️",
        )

    d1, d2 = st.columns(2)

    # Default to the first known API; fall back to first available component
    _default_api_idx = 0
    if _api_candidates:
        for i, c in enumerate(_api_candidates):
            if is_api(c):
                _default_api_idx = i
                break

    cmac_id = d1.selectbox(
        "Active Pharmaceutical Ingredient (API)",
        options=_api_candidates,
        index=_default_api_idx,
        format_func=component_label,
        help=(
            "The selected component is treated as the API in the optimisation.  "
            "Its PSD and density are looked up from the training database; "
            "its weight fraction is optimised as a decision variable."
        ),
    )

    drug_loading = d2.slider(
        "Target Drug Loading (w/w)",
        min_value=0.01,
        max_value=0.80,
        value=0.20,
        step=0.01,
        help=(
            "Nominal API weight fraction.  "
            "Used to auto-compute the API fraction search bounds when "
            "'Allow API fraction to vary' is enabled."
        ),
    )

    api_fraction_variable = st.checkbox(
        "Allow API fraction to vary during optimisation",
        value=True,
        help=(
            "If checked, the optimiser searches over API fractions around the "
            "target drug loading.  If unchecked, the API fraction is fixed at "
            "the target drug loading value."
        ),
    )

    use_custom_api_bounds = False
    api_fraction_bounds   = None
    if api_fraction_variable:
        use_custom_api_bounds = st.checkbox("Set custom API fraction bounds", value=False)
        if use_custom_api_bounds:
            bc1, bc2 = st.columns(2)
            api_lb = bc1.number_input(
                "API fraction lower bound",
                min_value=0.01, max_value=0.95,
                value=max(0.01, round(drug_loading * 0.7, 3)),
                step=0.01,
            )
            api_ub = bc2.number_input(
                "API fraction upper bound",
                min_value=0.01, max_value=0.95,
                value=min(0.95, round(drug_loading * 1.3, 3)),
                step=0.01,
            )
            if api_lb >= api_ub:
                st.error("Lower bound must be less than upper bound.")
            else:
                api_fraction_bounds = (api_lb, api_ub)

# ═══════════════════════════════════════════════════════════════════════════════
# ② Objectives
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("② Objectives", expanded=True):
    _OBJ_HELP: dict = {
        "maximise_tensile":
            "Maximise mean tensile strength (MPa) — pymoo minimises its negation",
        "minimise_tablet_weight":
            "Minimise API w/w fraction (drive toward minimum viable drug loading)",
        "maximise_porosity":
            "Maximise tablet porosity (favours rapid disintegration)",
        "maximise_ffc":
            "Maximise flow function coefficient (better powder flowability)",
        "minimise_eaoif":
            "Minimise effective angle of internal friction (lower = more free-flowing)",
    }
    st.caption(
        "**1 objective** → mixed-variable single-objective GA  |  "
        "**2+ objectives** → NSGA-II Pareto front"
    )
    selected_objectives = st.multiselect(
        "Select objectives",
        options=all_objectives,
        default=defs.get("objectives", all_objectives[:2]),
        format_func=lambda o: f"{o}  —  {_OBJ_HELP.get(o, '')}",
    )
    if len(selected_objectives) == 1:
        st.info(
            "Single-objective mode selected.  "
            "Consider setting **Iterations ≥ 500** in Solver Settings for reliable convergence.",
            icon="ℹ️",
        )

# ═══════════════════════════════════════════════════════════════════════════════
# ③ Constraints
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("③ Constraints", expanded=True):
    st.caption(
        "Every optimised formulation must satisfy **all** active constraints.  "
        "Feasibility condition: `constraint_fn(result) ≤ 0`."
    )

    to_delete: list = []
    for idx, con in enumerate(st.session_state["df_constraints"]):
        row_c1, row_c2, row_c3, row_c4 = st.columns([3, 0.5, 2, 0.8])
        row_c1.markdown(f"**{con['name']}**")
        row_c2.markdown("≥" if "min" in con["name"] else "≤")
        new_thresh = row_c3.number_input(
            "threshold",
            value=float(con["threshold"]),
            step=0.01,
            key=f"con_thresh_{idx}",
            label_visibility="collapsed",
        )
        st.session_state["df_constraints"][idx]["threshold"] = new_thresh
        if row_c4.button("✕ Remove", key=f"del_con_{idx}"):
            to_delete.append(idx)

    for idx in reversed(to_delete):
        st.session_state["df_constraints"].pop(idx)
        st.rerun()

    st.divider()

    add_c1, add_c2, add_c3 = st.columns([3, 2, 1])
    already_added    = {c["name"] for c in st.session_state["df_constraints"]}
    remaining_constr = ["— select —"] + [c for c in all_constraints if c not in already_added]

    new_con_name = add_c1.selectbox(
        "Add constraint",
        options=remaining_constr,
        key="new_con_name",
        label_visibility="collapsed",
    )
    new_con_thresh = add_c2.number_input(
        "threshold value",
        value=0.0,
        step=0.01,
        key="new_con_thresh",
        label_visibility="collapsed",
    )
    if add_c3.button("＋ Add", use_container_width=True):
        if new_con_name and new_con_name != "— select —":
            st.session_state["df_constraints"].append(
                {"name": new_con_name, "threshold": new_con_thresh}
            )
            st.rerun()

    _, reset_col = st.columns([3, 1])
    if reset_col.button("↺ Reset to defaults"):
        st.session_state["df_constraints"] = [
            {"name": c["name"], "threshold": float(c["threshold"])}
            for c in defs.get("constraints", [])
        ]
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# ④ Fixed Excipients
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("④ Fixed Excipients (Disintegrant & Lubricant)"):
    st.caption(
        "These components are held at fixed fractions throughout the optimisation.  "
        "They are not included in the decision variable search space."
    )
    fe1, fe2 = st.columns(2)

    _default_dis_id = defs.get("disintegrant_id", "cc1")
    dis_idx = (
        all_excipients.index(_default_dis_id)
        if _default_dis_id in all_excipients else 0
    )
    disintegrant_id = fe1.selectbox(
        "Disintegrant",
        options=all_excipients,
        index=dis_idx,
        format_func=component_label,
        help="Croscarmellose sodium (cc1) is the standard default.",
    )
    disintegrant_fraction = fe1.number_input(
        "Disintegrant fraction (w/w)",
        min_value=0.001, max_value=0.3,
        value=float(defs.get("disintegrant_fraction", 0.08)),
        step=0.005,
        format="%.4f",
        help="Typically 8 % for croscarmellose sodium.",
    )

    _default_lub_id = defs.get("lubricant_id", "ms1")
    lub_idx = (
        all_excipients.index(_default_lub_id)
        if _default_lub_id in all_excipients else 0
    )
    lubricant_id = fe2.selectbox(
        "Lubricant",
        options=all_excipients,
        index=lub_idx,
        format_func=component_label,
        help="Magnesium stearate (ms1) is the standard default.",
    )
    lubricant_fraction = fe2.number_input(
        "Lubricant fraction (w/w)",
        min_value=0.001, max_value=0.1,
        value=float(defs.get("lubricant_fraction", 0.01)),
        step=0.001,
        format="%.4f",
        help="Typically 1 % for magnesium stearate.",
    )

# ═══════════════════════════════════════════════════════════════════════════════
# ⑤ Filler Search Space
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("⑤ Filler / Excipient Search Space"):
    st.caption(
        "The optimiser selects from the candidate filler list below and allocates "
        "the remaining fraction (after API, disintegrant, and lubricant) between "
        "two filler slots."
    )
    default_excipient_options = defs.get("excipient_options", [])
    safe_excipient_options    = [e for e in default_excipient_options if e in all_excipients]

    excipient_options = st.multiselect(
        "Candidate filler excipients",
        options=all_excipients,
        default=safe_excipient_options,
        format_func=component_label,
        help=(
            "The optimiser will pick the best filler pair from this list.  "
            "Include lactose, MCC, and mannitol variants for broad coverage."
        ),
    )

    _cp_bounds_default = defs.get("cp_bounds", (70.0, 250.0))
    cp_col1, cp_col2 = st.columns(2)
    cp_lb = cp_col1.number_input(
        "CP lower bound (MPa)",
        min_value=10.0, max_value=400.0,
        value=float(_cp_bounds_default[0]),
        step=5.0,
    )
    cp_ub = cp_col2.number_input(
        "CP upper bound (MPa)",
        min_value=20.0, max_value=450.0,
        value=float(_cp_bounds_default[1]),
        step=5.0,
    )

    filler1_fraction_lower = st.number_input(
        "Filler 1 minimum fraction",
        min_value=0.0, max_value=0.5,
        value=float(defs.get("filler1_fraction_lower", 0.0)),
        step=0.01,
        help=(
            "Minimum weight fraction enforced on filler 1.  "
            "Set > 0 to prevent the optimiser from zeroing out the primary filler."
        ),
    )

# ═══════════════════════════════════════════════════════════════════════════════
# ⑥ Solver Settings
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("⑥ Solver Settings"):
    sc1, sc2, sc3, sc4 = st.columns(4)
    pop_size  = sc1.number_input("Population Size",  10, 300,  int(defs.get("pop_size",  20)), step=5)
    n_iters   = sc2.number_input("Iterations",       10, 5000, int(defs.get("n_iters",   50)), step=10)
    n_threads = sc3.number_input("Threads",           1, 64,   int(defs.get("n_threads",  8)), step=1)
    seed      = sc4.number_input("Random Seed",       0, 9999, 1,                              step=1)

    est_evals = pop_size * n_iters
    est_t_s   = est_evals / max(n_threads, 1) / 5
    est_t_min = max(1, round(est_t_s / 60))
    st.caption(
        f"~{est_evals:,} model evaluations  ·  "
        f"estimated runtime ≈ {est_t_min}–{est_t_min * 2} min  "
        "(varies with hardware and formulation complexity)"
    )

# ── Validation & Launch ───────────────────────────────────────────────────────
st.divider()

warnings: list = []
if not selected_objectives:
    warnings.append("⚠ Select at least one **objective**.")
if not excipient_options:
    warnings.append("⚠ Select at least one **candidate excipient** in Search Space.")
if cp_lb >= cp_ub:
    warnings.append("⚠ CP lower bound must be less than upper bound.")
if use_custom_api_bounds and api_fraction_bounds is None:
    warnings.append("⚠ Custom API bounds are invalid (lower ≥ upper).")

for w in warnings:
    st.warning(w)

_, launch_col, _ = st.columns([2, 3, 2])
with launch_col:
    run_btn = st.button(
        "🚀 Run Optimisation",
        type="primary",
        use_container_width=True,
        disabled=len(warnings) > 0,
    )

# ── Run ───────────────────────────────────────────────────────────────────────
if run_btn:
    constraint_list = st.session_state["df_constraints"] or None
    with st.spinner("Optimising formulation… This may take several minutes. Please wait."):
        try:
            result = digital_formulator(
                cmac_id=cmac_id,
                drug_loading=drug_loading,
                objectives=selected_objectives if selected_objectives else None,
                constraints=constraint_list,
                api_fraction_variable=api_fraction_variable,
                api_fraction_bounds=api_fraction_bounds if use_custom_api_bounds else None,
                disintegrant_id=disintegrant_id,
                disintegrant_fraction=disintegrant_fraction,
                lubricant_id=lubricant_id,
                lubricant_fraction=lubricant_fraction,
                excipient_options=excipient_options if excipient_options else None,
                filler1_fraction_lower=filler1_fraction_lower,
                cp_bounds=(cp_lb, cp_ub),
                pop_size=pop_size,
                n_iters=n_iters,
                n_threads=n_threads,
                seed=seed,
            )
            st.session_state["df_opt_result"] = result
            st.success("✅  Optimisation complete!")
        except Exception as exc:
            st.error(f"Optimisation failed: {exc}")
            st.stop()

# ── Guard ─────────────────────────────────────────────────────────────────────
result = st.session_state.get("df_opt_result")
if result is None:
    st.info("Results will appear here after running the optimisation.")
    st.stop()

# ── Results ───────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Optimisation Results")

opt_fracs  = result.get("optimized_fractions",  [])
opt_titles = result.get("optimized_titles",     [])
opt_comps  = result.get("optimized_components", [])

if opt_fracs and opt_comps:
    pie_col, tbl_col = st.columns([1, 1])

    with pie_col:
        st.plotly_chart(
            formulation_pie(
                [component_label(c) for c in opt_comps],
                opt_fracs,
            ),
            use_container_width=True,
        )

    with tbl_col:
        st.subheader("Optimal Formulation")
        df_form = pd.DataFrame({
            "Role":      opt_titles,
            "ID":        opt_comps,
            "Name":      [component_label(c) for c in opt_comps],
            "Fraction":  [f"{f:.4f}" for f in opt_fracs],
        })
        st.dataframe(df_form, use_container_width=True, hide_index=True)

        st.divider()
        kc1, kc2 = st.columns(2)
        kc1.metric("Tensile Strength (MPa)", f"{result.get('tensile_mean', 0):.4f}")
        kc2.metric("Porosity (mean)",         f"{result.get('porosity_mean', 0):.4f}")

st.divider()

tab_gran, tab_tablet, tab_morph, tab_raw = st.tabs([
    "⚖️ Granular Properties",
    "💊 Tablet Properties",
    "🔬 Morphology / PCA",
    "📋 Raw Output",
])

# ── Granular ──────────────────────────────────────────────────────────────────
with tab_gran:
    bd        = result.get("bulk_density", 0)
    td        = result.get("tapped_density", 0)
    ci        = (td - bd) / td * 100 if td else 0.0
    hr        = td / bd if bd else 0.0
    ffc_val   = result.get("ffc", 0)
    eaoif_val = result.get("effective_angle_of_internal_friction", 0.0)
    flow_class = (
        "Free-flowing" if ffc_val > 10 else
        "Easy-flowing" if ffc_val > 4  else
        "Cohesive"     if ffc_val > 2  else
        "Very cohesive"
    )

    gc1, gc2, gc3, gc4 = st.columns(4)
    gc1.metric("True Density (g/cm³)",   f"{result.get('true_density', 0):.4f}")
    gc2.metric("Bulk Density (g/cm³)",   f"{bd:.4f}")
    gc3.metric("Tapped Density (g/cm³)", f"{td:.4f}")
    gc4.metric("Carr's Index (%)",       f"{ci:.2f}")

    gc5, gc6, gc7, gc8 = st.columns(4)
    gc5.metric("Hausner Ratio",  f"{hr:.4f}")
    gc6.metric("FFC",            f"{ffc_val:.4f}")
    gc7.metric("EAOIF (°)",      f"{eaoif_val:.4f}")
    gc8.metric("Flow Class",     flow_class)

# ── Tablet ────────────────────────────────────────────────────────────────────
with tab_tablet:
    tc1, tc2, tc3, tc4 = st.columns(4)
    tc1.metric("Porosity Mean",      f"{result.get('porosity_mean', 0):.4f}")
    tc2.metric("Porosity Std",       f"{result.get('porosity_std',  0):.4f}")
    tc3.metric("Tensile Mean (MPa)", f"{result.get('tensile_mean',  0):.4f}")
    tc4.metric("Tensile Std (MPa)",  f"{result.get('tensile_std',   0):.4f}")

    ts_lo  = result.get("tensile_mean",  0) - result.get("tensile_std",  0)
    ts_hi  = result.get("tensile_mean",  0) + result.get("tensile_std",  0)
    por_lo = result.get("porosity_mean", 0) - result.get("porosity_std", 0)
    por_hi = result.get("porosity_mean", 0) + result.get("porosity_std", 0)

    st.info(
        f"**Tensile (mean ± std):** {ts_lo:.3f} – {ts_hi:.3f} MPa  \n"
        f"**Porosity (mean ± std):** {por_lo:.4f} – {por_hi:.4f}"
    )

# ── Morphology ────────────────────────────────────────────────────────────────
with tab_morph:
    mc1, mc2 = st.columns(2)
    with mc1:
        st.plotly_chart(
            psd_figure(result["ce_diameter"], result["particle_size_dist"]),
            use_container_width=True,
        )
        st.plotly_chart(
            pca_bar(result["PCs_PSD"], "PCA Scores — Particle Size Distribution"),
            use_container_width=True,
        )
    with mc2:
        st.plotly_chart(
            ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]),
            use_container_width=True,
        )
        st.plotly_chart(
            pca_bar(result["PCs_AR"], "PCA Scores — Aspect Ratio Distribution"),
            use_container_width=True,
        )
    st.caption(
        "PSD and AR reflect blend morphology for the optimised formulation.  "
        "PCA scores are the inputs used by the porosity and tensile ML models."
    )

# ── Raw JSON ──────────────────────────────────────────────────────────────────
with tab_raw:
    st.json(result)
    st.download_button(
        "⬇ Download JSON",
        data=json.dumps(result, indent=2),
        file_name="digital_formulator_result.json",
        mime="application/json",
    )
