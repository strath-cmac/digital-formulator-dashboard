"""
Single-Point Simulation Page

The user picks components, sets fractions (auto-normalised), sets a
compaction pressure, and sees the full simulation output:
  • Granular properties (density, flowability, Carr's Index, Hausner Ratio)
  • Tablet properties  (porosity, tensile strength)
  • Morphology         (PSD, AR distributions, PCA scores)
"""

import json

import streamlit as st

from utils.api_client import (
    get_options, single_run, component_label, component_short_name,
    ffc_v3, ffc_v4_class,
)
from utils.plotting import psd_figure, ar_figure, pca_bar, formulation_pie

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Single Run | Digital Formulator",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 Single-Point Simulation")
st.markdown(
    "Predict granular and tablet properties for a specific formulation "
    "at a **fixed compaction pressure**."
)

# ── Ensure API options are loaded ─────────────────────────────────────────
if "api_options" not in st.session_state:
    try:
        st.session_state["api_options"] = get_options()
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        st.stop()

opts           = st.session_state["api_options"]
all_excipients = opts.get("available_excipients", [])

if not all_excipients:
    st.error("No excipients returned by the API. Is the backend running?")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔬 Single Run")
    st.caption("Build your formulation below.")

    # Sensible defaults that are likely in most deployments
    _DEFAULTS = ["mc5", "la9", "cc1", "ms1"]
    safe_defaults = [d for d in _DEFAULTS if d in all_excipients]

    selected = st.multiselect(
        "Select components",
        options=all_excipients,
        default=safe_defaults if safe_defaults else all_excipients[:3],
        format_func=component_label,
        help="Choose two or more excipients to build the formulation.",
    )

    st.divider()

    fractions: dict[str, float] = {}
    if selected:
        st.caption("Set component fractions (auto-normalised before submission).")
        default_frac = round(1.0 / len(selected), 4)
        for comp in selected:
            fractions[comp] = st.number_input(
                component_label(comp),
                min_value=0.001,
                max_value=1.0,
                value=default_frac,
                step=0.005,
                format="%.4f",
                key=f"sr_frac_{comp}",
            )

        total = sum(fractions.values())
        colour = "green" if abs(total - 1.0) < 0.005 else "orange"
        st.markdown(f"**Sum:** :{colour}[{total:.4f}]" + (" ✓" if colour == "green" else " → will be normalised"))

    st.divider()

    st.header("Process")
    cp = st.slider(
        "Compaction Pressure (MPa)",
        min_value=50.0,
        max_value=450.0,
        value=200.0,
        step=5.0,
    )

    fetch_ffc_models = st.checkbox(
        "Include FFC model comparison",
        value=False,
        help=(
            "Also calls the v3 regression and v4 classification FFC models "
            "(2 extra API calls). Uncheck for faster runs."
        ),
    )

    run_btn = st.button(
        "▶ Run Simulation",
        type="primary",
        use_container_width=True,
        disabled=len(selected) < 1,
    )

# ── Guard: nothing selected ───────────────────────────────────────────────
if not selected:
    st.info("👈  Select at least one component in the sidebar to begin.")
    st.stop()

# ── Run ───────────────────────────────────────────────────────────────────
if run_btn:
    frac_vals  = list(fractions.values())
    total_frac = sum(frac_vals)
    norm_fracs = [f / total_frac for f in frac_vals]
    comp_ids   = list(fractions.keys())
    titles_list = [component_short_name(c) for c in comp_ids]

    with st.spinner("Running simulation…"):
        try:
            result = single_run(
                titles=titles_list,
                components=comp_ids,
                fractions=norm_fracs,
                cp=cp,
            )
            st.session_state["sr_result"]   = result
            st.session_state["sr_titles"]   = titles_list
            st.session_state["sr_fracs"]    = norm_fracs
            st.session_state["sr_comp_ids"] = comp_ids
            # Optional extra FFC models
            if fetch_ffc_models:
                st.session_state["sr_ffc_v3"]  = ffc_v3(
                    titles=titles_list, components=comp_ids, fractions=norm_fracs
                )
                st.session_state["sr_ffc_v4"]  = ffc_v4_class(
                    titles=titles_list, components=comp_ids, fractions=norm_fracs
                )
            else:
                st.session_state.pop("sr_ffc_v3", None)
                st.session_state.pop("sr_ffc_v4", None)
        except Exception as e:
            st.error(f"Simulation failed: {e}")
            st.stop()

# ── Guard: no result yet ──────────────────────────────────────────────────
result = st.session_state.get("sr_result")
if result is None:
    st.info("Configure the formulation in the sidebar and click **▶ Run Simulation**.")
    st.stop()

# ── Results ───────────────────────────────────────────────────────────────
st.subheader("Simulation Results")

# Derived quantities
bd = result["bulk_density"]
td = result["tapped_density"]
ci = (td - bd) / td * 100 if td else 0.0
hr = td / bd if bd else 0.0
ffc_val = result["ffc"]
flow_class = (
    "Free-flowing"   if ffc_val > 10 else
    "Easy-flowing"   if ffc_val > 4  else
    "Cohesive"       if ffc_val > 2  else
    "Very cohesive"
)

tab_gran, tab_tablet, tab_morph, tab_form, tab_raw = st.tabs(
    ["Granular Properties", "Tablet Properties", "Morphology", "Formulation", "Raw Data"]
)

# ── Granular Properties ───────────────────────────────────────────────────
with tab_gran:
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.metric("True Density (g/cm³)",    f"{result['true_density']:.4f}")
    r1c2.metric("Bulk Density (g/cm³)",    f"{result['bulk_density']:.4f}")
    r1c3.metric("Tapped Density (g/cm³)",  f"{result['tapped_density']:.4f}")
    r1c4.metric("Carr's Index (%)",        f"{ci:.2f}")

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r2c1.metric("Hausner Ratio",                       f"{hr:.4f}")
    r2c2.metric("FFC",                                 f"{ffc_val:.4f}")
    r2c3.metric("Eff. Angle of Int. Friction (°)",    f"{result['effective_angle_of_internal_friction']:.4f}")
    r2c4.metric("Flow Classification",                flow_class)

    st.divider()
    # Flowability guide
    with st.expander("ℹ FFC Classification Guide"):
        st.markdown(
            """
| FFC range | Classification |
|-----------|----------------|
| > 10      | Free-flowing   |
| 4 – 10    | Easy-flowing   |
| 2 – 4     | Cohesive       |
| < 2       | Very cohesive  |
"""
        )

    # FFC model comparison (optional, only if checkbox was ticked)
    ffc_v3_val = st.session_state.get("sr_ffc_v3")
    ffc_v4_lbl = st.session_state.get("sr_ffc_v4")
    if ffc_v3_val is not None or ffc_v4_lbl is not None:
        st.divider()
        st.caption("**FFC Model Comparison** — v1 (regression) · v3 (new regression) · v4 (classification)")
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric(
            "FFC v1 — 1st-gen regression",
            f"{ffc_val:.4f}",
            help="Original regression model shipped with the platform.",
        )
        if ffc_v3_val is not None:
            delta_v3 = ffc_v3_val - ffc_val
            mc2.metric(
                "FFC v3 — 2nd-gen regression",
                f"{ffc_v3_val:.4f}",
                delta=f"{delta_v3:+.4f} vs v1",
                help="Improved regression model trained on extended dataset.",
            )
        if ffc_v4_lbl is not None:
            mc3.metric(
                "FFC v4 — classification",
                ffc_v4_lbl,
                help="Classification model predicting the discrete flow class.",
            )

# ── Tablet Properties ─────────────────────────────────────────────────────
with tab_tablet:
    tc1, tc2, tc3, tc4 = st.columns(4)
    tc1.metric("Porosity Mean",       f"{result['porosity_mean']:.4f}")
    tc2.metric("Porosity Std",        f"{result['porosity_std']:.4f}")
    tc3.metric("Tensile Mean (MPa)",  f"{result['tensile_mean']:.4f}")
    tc4.metric("Tensile Std (MPa)",   f"{result['tensile_std']:.4f}")

    ts_lo = result["tensile_mean"] - result["tensile_std"]
    ts_hi = result["tensile_mean"] + result["tensile_std"]
    st.info(
        f"**Tensile strength (mean ± std):** {ts_lo:.3f} – {ts_hi:.3f} MPa  "
        f"at {cp:.0f} MPa compaction pressure"
    )

    por_lo = result["porosity_mean"] - result["porosity_std"]
    por_hi = result["porosity_mean"] + result["porosity_std"]
    st.info(
        f"**Porosity (mean ± std):** {por_lo:.4f} – {por_hi:.4f}  "
        f"at {cp:.0f} MPa compaction pressure"
    )

# ── Morphology ────────────────────────────────────────────────────────────
with tab_morph:
    col_psd, col_ar = st.columns(2)
    with col_psd:
        st.plotly_chart(
            psd_figure(result["ce_diameter"], result["particle_size_dist"]),
            use_container_width=True,
        )
    with col_ar:
        st.plotly_chart(
            ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]),
            use_container_width=True,
        )

    col_pc1, col_pc2 = st.columns(2)
    with col_pc1:
        st.plotly_chart(
            pca_bar(result["PCs_PSD"], "PCA Scores — Particle Size Distribution"),
            use_container_width=True,
        )
    with col_pc2:
        st.plotly_chart(
            pca_bar(result["PCs_AR"], "PCA Scores — Aspect Ratio Distribution"),
            use_container_width=True,
        )

# ── Formulation composition ───────────────────────────────────────────────
with tab_form:
    titles_disp  = st.session_state.get("sr_titles",   [])
    fracs_disp   = st.session_state.get("sr_fracs",    [])
    comp_ids_disp = st.session_state.get("sr_comp_ids", [])

    if titles_disp and fracs_disp:
        c_pie, c_table = st.columns([1, 1])
        with c_pie:
            st.plotly_chart(
                formulation_pie(titles_disp, fracs_disp),
                use_container_width=True,
            )
        with c_table:
            import pandas as pd
            df_form = pd.DataFrame({
                "Component": [component_label(c) for c in comp_ids_disp],
                "ID":        comp_ids_disp,
                "Fraction":  [f"{f:.4f}" for f in fracs_disp],
            })
            st.dataframe(df_form, use_container_width=True, hide_index=True)

# ── Raw JSON ──────────────────────────────────────────────────────────────
with tab_raw:
    st.json(result)
    st.download_button(
        label="⬇ Download JSON",
        data=json.dumps(result, indent=2),
        file_name="single_run_result.json",
        mime="application/json",
    )
