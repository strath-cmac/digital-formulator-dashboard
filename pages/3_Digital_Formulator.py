"""
Digital Formulator — In-Silico Formulation Optimisation Page

Provides a full GUI over the /digital_formulator endpoint:
  ① API / drug settings  (required)
  ② Objectives           (single → GA,  multi → NSGA-II)
  ③ Constraints          (dynamic add / remove)
  ④ Fixed excipients     (disintegrant, lubricant)
  ⑤ Search space         (candidate fillers, CP range, filler bounds)
  ⑥ Solver settings      (pop_size, n_iters, n_threads, seed)
"""

import json

import pandas as pd
import streamlit as st

from utils.api_client import (
    get_options,
    digital_formulator,
    component_label,
    component_short_name,
)
from utils.plotting import (
    psd_figure,
    ar_figure,
    formulation_pie,
    formulation_bar,
    pca_bar,
)

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Digital Formulator | Optimisation",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Digital Formulator — Formulation Optimisation")
st.markdown(
    "Use a **multi-objective genetic algorithm (NSGA-II)** or "
    "**single-objective GA** to find optimal tablet formulations that "
    "satisfy your process and product constraints.  "
    "Expect runtimes of 1 – 10 minutes depending on solver settings."
)
st.divider()

# ── Ensure API options are loaded ─────────────────────────────────────────
if "api_options" not in st.session_state:
    try:
        st.session_state["api_options"] = get_options()
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        st.stop()

opts             = st.session_state["api_options"]
all_excipients   = opts.get("available_excipients",  [])
all_objectives   = opts.get("available_objectives",  [])
all_constraints  = opts.get("available_constraints", [])
defs             = opts.get("current_defaults",      {})

if not all_excipients:
    st.error("No excipients returned by the API. Is the backend running?")
    st.stop()

# ── Session-state: dynamic constraints table ──────────────────────────────
if "df_constraints" not in st.session_state:
    st.session_state["df_constraints"] = [
        {"name": c["name"], "threshold": float(c["threshold"])}
        for c in defs.get("constraints", [])
    ]

# ── Input sections ────────────────────────────────────────────────────────

# ① API / Drug Settings ───────────────────────────────────────────────────
with st.expander("① API / Drug Settings", expanded=True):
    d1, d2 = st.columns(2)

    cmac_id = d1.selectbox(
        "API Identifier (cmac_id)",
        options=all_excipients,
        format_func=component_label,
        help=(
            "Select the active pharmaceutical ingredient. "
            "The optimiser fixes its PSD from the database and varies the fraction."
        ),
    )

    drug_loading = d2.slider(
        "Target Drug Loading (w/w)",
        min_value=0.01,
        max_value=0.80,
        value=0.20,
        step=0.01,
        help="Nominal drug fraction used to auto-compute API fraction search bounds.",
    )

    api_fraction_variable = st.checkbox(
        "Allow API fraction to vary during optimisation",
        value=True,
        help="If unchecked the API fraction is fixed at drug_loading.",
    )

    # Custom bounds (only shown when API fraction is variable)
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

# ② Objectives ────────────────────────────────────────────────────────────
with st.expander("② Objectives", expanded=True):
    _OBJ_HELP = {
        "maximise_tensile":       "Maximise mean tensile strength (MPa) — pymoo minimises its negative",
        "minimise_tablet_weight": "Minimise API w/w fraction (lighter tablet toward target loading)",
        "maximise_porosity":      "Maximise tablet porosity",
        "maximise_ffc":           "Maximise flow function coefficient",
        "minimise_eaoif":         "Minimise effective angle of internal friction",
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
            "Consider setting **n_iters ≥ 500** in Solver Settings for reliable convergence."
        )

# ③ Constraints ───────────────────────────────────────────────────────────
with st.expander("③ Constraints", expanded=True):
    st.caption(
        "Every optimised formulation must satisfy **all** constraints.  "
        "Feasibility condition: `constraint_fn(result) ≤ 0`."
    )

    # Render existing constraint rows
    to_delete = []
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

    # Add new constraint row
    add_label = st.columns([0.1, 0.9])[1]
    add_c1, add_c2, add_c3 = st.columns([3, 2, 1])

    already_added = {c["name"] for c in st.session_state["df_constraints"]}
    remaining_constraints = ["— select —"] + [
        c for c in all_constraints if c not in already_added
    ]
    new_con_name = add_c1.selectbox(
        "Add constraint",
        options=remaining_constraints,
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

# ④ Fixed Excipients ──────────────────────────────────────────────────────
with st.expander("④ Fixed Excipients (Disintegrant & Lubricant)"):
    fe1, fe2 = st.columns(2)

    _default_dis_id = defs.get("disintegrant_id", "cc1")
    dis_idx = all_excipients.index(_default_dis_id) if _default_dis_id in all_excipients else 0
    disintegrant_id = fe1.selectbox(
        "Disintegrant",
        options=all_excipients,
        index=dis_idx,
        format_func=component_label,
    )
    disintegrant_fraction = fe1.number_input(
        "Disintegrant fraction (w/w)",
        min_value=0.001,
        max_value=0.3,
        value=float(defs.get("disintegrant_fraction", 0.08)),
        step=0.005,
        format="%.4f",
    )

    _default_lub_id = defs.get("lubricant_id", "ms1")
    lub_idx = all_excipients.index(_default_lub_id) if _default_lub_id in all_excipients else 0
    lubricant_id = fe2.selectbox(
        "Lubricant",
        options=all_excipients,
        index=lub_idx,
        format_func=component_label,
    )
    lubricant_fraction = fe2.number_input(
        "Lubricant fraction (w/w)",
        min_value=0.001,
        max_value=0.1,
        value=float(defs.get("lubricant_fraction", 0.01)),
        step=0.001,
        format="%.4f",
    )

# ⑤ Search Space ──────────────────────────────────────────────────────────
with st.expander("⑤ Filler / Excipient Search Space"):
    default_excipient_options = defs.get("excipient_options", [])
    safe_excipient_options = [e for e in default_excipient_options if e in all_excipients]

    excipient_options = st.multiselect(
        "Candidate filler excipients",
        options=all_excipients,
        default=safe_excipient_options,
        format_func=component_label,
        help="The optimiser will pick the best combination from this list.",
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
        help="Minimum weight fraction enforced on the first filler variable.",
    )

# ⑥ Solver Settings ───────────────────────────────────────────────────────
with st.expander("⑥ Solver Settings"):
    sc1, sc2, sc3, sc4 = st.columns(4)
    pop_size  = sc1.number_input("Population Size",  10, 300,  int(defs.get("pop_size",  20)),  step=5)
    n_iters   = sc2.number_input("Iterations",       10, 5000, int(defs.get("n_iters",   50)),  step=10)
    n_threads = sc3.number_input("Threads",           1, 64,   int(defs.get("n_threads",  8)),  step=1)
    seed      = sc4.number_input("Random Seed",       0, 9999, int(defs.get("seed",        1)),  step=1)

    est_evals  = pop_size * n_iters
    est_t_s    = est_evals / max(n_threads, 1) / 5   # rough: ~5 evals/thread/s
    est_t_min  = max(1, round(est_t_s / 60))
    st.caption(
        f"~{est_evals:,} model evaluations  ·  "
        f"estimated runtime ≈ {est_t_min}–{est_t_min * 2} min  "
        "(varies with hardware)"
    )

# ── Validation & Launch ───────────────────────────────────────────────────
st.divider()

warnings = []
if not selected_objectives:
    warnings.append("⚠ Select at least one **objective**.")
if not excipient_options:
    warnings.append("⚠ Select at least one **candidate excipient** in Search Space.")
if cp_lb >= cp_ub:
    warnings.append("⚠ CP lower bound must be less than upper bound.")

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

# ── Run ───────────────────────────────────────────────────────────────────
if run_btn:
    constraint_list = st.session_state["df_constraints"] or None

    with st.spinner(
        "Optimising formulation…  This may take several minutes. Please wait."
    ):
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
        except Exception as e:
            st.error(f"Optimisation failed: {e}")
            st.stop()

# ── Guard: no result yet ──────────────────────────────────────────────────
result = st.session_state.get("df_opt_result")
if result is None:
    st.info("Results will appear here after running the optimisation.")
    st.stop()

# ── Results ───────────────────────────────────────────────────────────────
st.divider()
st.subheader("Optimisation Results")

# Optimal formulation header
opt_fracs  = result.get("optimized_fractions",  [])
opt_titles = result.get("optimized_titles",     [])
opt_comps  = result.get("optimized_components", [])

if opt_fracs and opt_titles:
    pie_col, tbl_col = st.columns([1, 1])

    with pie_col:
        st.plotly_chart(
            formulation_pie(opt_titles, opt_fracs),
            use_container_width=True,
        )

    with tbl_col:
        st.subheader("Optimal Formulation")
        df_form = pd.DataFrame({
            "Role":      opt_titles,
            "Excipient": [component_label(c) for c in opt_comps],
            "ID":        opt_comps,
            "Fraction":  [f"{f:.4f}" for f in opt_fracs],
        })
        st.dataframe(df_form, use_container_width=True, hide_index=True)

        # KPIs
        st.divider()
        kc1, kc2 = st.columns(2)
        kc1.metric("Tensile Strength (MPa)",  f"{result.get('tensile_mean', 0):.4f}")
        kc2.metric("Porosity (mean)",          f"{result.get('porosity_mean', 0):.4f}")

st.divider()

# Detail tabs
tab_gran, tab_tablet, tab_morph, tab_raw = st.tabs(
    ["Granular Properties", "Tablet Properties", "Morphology / PCA", "Raw Output"]
)

# ── Granular ──────────────────────────────────────────────────────────────
with tab_gran:
    bd      = result.get("bulk_density", 0)
    td      = result.get("tapped_density", 0)
    ci      = (td - bd) / td * 100 if td else 0.0
    hr      = td / bd if bd else 0.0
    ffc_val = result.get("ffc", 0)
    flow_class = (
        "Free-flowing"   if ffc_val > 10 else
        "Easy-flowing"   if ffc_val > 4  else
        "Cohesive"       if ffc_val > 2  else
        "Very cohesive"
    )

    gc1, gc2, gc3, gc4 = st.columns(4)
    gc1.metric("True Density (g/cm³)",   f"{result.get('true_density', 0):.4f}")
    gc2.metric("Bulk Density (g/cm³)",   f"{bd:.4f}")
    gc3.metric("Tapped Density (g/cm³)", f"{td:.4f}")
    gc4.metric("Carr's Index (%)",       f"{ci:.2f}")

    gc5, gc6, gc7, gc8 = st.columns(4)
    gc5.metric("Hausner Ratio",          f"{hr:.4f}")
    gc6.metric("FFC",                    f"{ffc_val:.4f}")
    gc7.metric("EAOIF (°)",              f"{result.get('effective_angle_of_internal_friction', 0):.4f}")
    gc8.metric("Flow Class",             flow_class)

# ── Tablet ────────────────────────────────────────────────────────────────
with tab_tablet:
    tc1, tc2, tc3, tc4 = st.columns(4)
    tc1.metric("Porosity Mean",       f"{result.get('porosity_mean', 0):.4f}")
    tc2.metric("Porosity Std",        f"{result.get('porosity_std',  0):.4f}")
    tc3.metric("Tensile Mean (MPa)",  f"{result.get('tensile_mean',  0):.4f}")
    tc4.metric("Tensile Std (MPa)",   f"{result.get('tensile_std',   0):.4f}")

    ts_lo = result.get("tensile_mean", 0) - result.get("tensile_std", 0)
    ts_hi = result.get("tensile_mean", 0) + result.get("tensile_std", 0)
    por_lo = result.get("porosity_mean", 0) - result.get("porosity_std", 0)
    por_hi = result.get("porosity_mean", 0) + result.get("porosity_std", 0)

    st.info(
        f"**Tensile (mean ± std):** {ts_lo:.3f} – {ts_hi:.3f} MPa  \n"
        f"**Porosity (mean ± std):** {por_lo:.4f} – {por_hi:.4f}"
    )

# ── Morphology ────────────────────────────────────────────────────────────
with tab_morph:
    mc1, mc2 = st.columns(2)
    with mc1:
        st.plotly_chart(
            psd_figure(result["ce_diameter"], result["particle_size_dist"]),
            use_container_width=True,
        )
    with mc2:
        st.plotly_chart(
            ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]),
            use_container_width=True,
        )

    pc1, pc2 = st.columns(2)
    with pc1:
        st.plotly_chart(
            pca_bar(result["PCs_PSD"], "PCA Scores — Particle Size Distribution"),
            use_container_width=True,
        )
    with pc2:
        st.plotly_chart(
            pca_bar(result["PCs_AR"], "PCA Scores — Aspect Ratio Distribution"),
            use_container_width=True,
        )

# ── Raw JSON ──────────────────────────────────────────────────────────────
with tab_raw:
    st.json(result)
    st.download_button(
        label="⬇ Download JSON",
        data=json.dumps(result, indent=2),
        file_name="digital_formulator_result.json",
        mime="application/json",
    )
