"""Single-Point Simulation — predict all blend and tablet properties at a fixed CP."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import (
    get_options,
    single_run,
    component_label,
    component_short_name,
    ffc_v3,
    ffc_v4_class,
    is_api,
)
from utils.plotting import psd_figure, ar_figure, pca_bar, formulation_pie


# ── Load API options once per session ────────────────────────────────────────
if "api_options" not in st.session_state:
    try:
        st.session_state["api_options"] = get_options()
    except Exception as exc:
        st.error(f"Cannot reach the Digital Formulator API: {exc}")
        st.stop()

opts           = st.session_state["api_options"]
all_excipients = opts.get("available_excipients", [])
all_apis       = opts.get("available_apis", [])
all_components = all_apis + all_excipients   # APIs listed first

if not all_components:
    st.error(
        "The API returned no components. "
        "Check that the backend is running and the material database is accessible."
    )
    st.stop()

# Build label ↔ ID mappings for the data editor drop-downs
_label_options = [component_label(c) for c in all_components]
_id_from_label = {component_label(c): c for c in all_components}

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='page-header'>
  <div class='ph-title'>🔬 Single-Point Simulation</div>
  <div class='ph-sub'>Predict granular and tablet properties for a formulation at a fixed compaction pressure</div>
</div>""", unsafe_allow_html=True)

# ── Layout ────────────────────────────────────────────────────────────────────
cfg_col, res_col = st.columns([2, 3], gap="large")

# ── Sensible default formulation (API 20 % + fillers + dis + lub) ─────────────
_DEFAULT_IDS = ["mc5", "la9", "cc1", "ms1"]
_DEFAULT_FRACS = [0.71, 0.20, 0.08, 0.01]

def _build_default_df() -> pd.DataFrame:
    """Return an initial formulation DataFrame, falling back gracefully."""
    # Try the canonical defaults first
    pairs = [
        (c, f) for c, f in zip(_DEFAULT_IDS, _DEFAULT_FRACS)
        if c in all_components
    ]
    if not pairs:
        # Fall back to first 4 available components with equal fractions
        n = min(4, len(all_components))
        pairs = [(all_components[i], round(1.0 / n, 4)) for i in range(n)]
    # Add any known API at 20 % if defaults are only excipients
    if pairs and all_apis and not any(is_api(c) for c, _ in pairs):
        api_id = all_apis[0]
        pairs = [(api_id, 0.20)] + [(c, round(f * 0.80, 4)) for c, f in pairs]
    comps, fracs = zip(*pairs) if pairs else ([], [])
    return pd.DataFrame({
        "Component": [component_label(c) for c in comps],
        "Fraction":  list(fracs),
    })


with cfg_col:
    # ── Formulation builder ──────────────────────────────────────────────
    with st.container(border=True):
        st.caption("Formulation")
        st.markdown("#### Build your formulation")
        st.caption(
            "Typical tablet: API (~20 %) · Filler(s) · "
            "Disintegrant (~8 %) · Lubricant (~1 %)"
        )

        if "sr_form_df" not in st.session_state:
            st.session_state["sr_form_df"] = _build_default_df()

        edited_df = st.data_editor(
            st.session_state["sr_form_df"],
            column_config={
                "Component": st.column_config.SelectboxColumn(
                    "Component",
                    options=_label_options,
                    required=True,
                    width="large",
                    help="Select a component from the material database.",
                ),
                "Fraction": st.column_config.NumberColumn(
                    "Fraction (w/w)",
                    min_value=0.001,
                    max_value=1.0,
                    step=0.005,
                    format="%.4f",
                    width="small",
                ),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="sr_form_editor",
            hide_index=True,
        )
        st.session_state["sr_form_df"] = edited_df

        valid_rows  = edited_df.dropna(subset=["Component", "Fraction"])
        total_frac  = float(valid_rows["Fraction"].sum()) if not valid_rows.empty else 0.0
        if abs(total_frac - 1.0) < 0.005:
            st.success(f"Sum: **{total_frac:.4f}** ✓", icon="✅")
        else:
            st.warning(f"Sum: **{total_frac:.4f}** — will be normalised before sending", icon="⚠️")

    # ── Compaction pressure ──────────────────────────────────────────────
    with st.container(border=True):
        st.caption("Process Parameter")
        st.markdown("#### Compaction Pressure")
        cp = st.slider(
            "CP (MPa)",
            min_value=50.0, max_value=450.0,
            value=200.0, step=5.0,
            label_visibility="collapsed",
            format="%.0f MPa",
            help="Punch compaction pressure applied during tablet manufacture.",
        )
        st.markdown(f"**Selected:** {cp:.0f} MPa")

    # ── Options ──────────────────────────────────────────────────────────
    with st.container(border=True):
        st.caption("Options")
        fetch_ffc_models = st.toggle(
            "Compare FFC model versions (v1 / v3 / v4)",
            value=False,
            help=(
                "Calls two additional API endpoints (/ffc_new, /ffc_class). "
                "Shows how the three FFC model generations compare on this formulation."
            ),
        )

    n_valid = len(valid_rows)
    run_btn = st.button(
        "▶  Run Simulation",
        type="primary",
        use_container_width=True,
        disabled=n_valid < 1,
    )

# ── Run ───────────────────────────────────────────────────────────────────────
if run_btn:
    vr          = edited_df.dropna(subset=["Component", "Fraction"])
    comp_labels = vr["Component"].tolist()
    comp_ids    = [_id_from_label[lbl] for lbl in comp_labels if lbl in _id_from_label]
    frac_vals   = [float(v) for v in vr["Fraction"].tolist()]
    total_frac  = sum(frac_vals)
    norm_fracs  = [f / total_frac for f in frac_vals]
    titles_list = [component_short_name(c) for c in comp_ids]

    with res_col:
        with st.spinner("Running simulation…"):
            try:
                result = single_run(
                    titles=titles_list,
                    components=comp_ids,
                    fractions=norm_fracs,
                    cp=cp,
                )
                st.session_state.update({
                    "sr_result":   result,
                    "sr_titles":   titles_list,
                    "sr_fracs":    norm_fracs,
                    "sr_comp_ids": comp_ids,
                    "sr_cp":       cp,
                })
                if fetch_ffc_models:
                    st.session_state["sr_ffc_v3"] = ffc_v3(
                        titles=titles_list, components=comp_ids, fractions=norm_fracs
                    )
                    st.session_state["sr_ffc_v4"] = ffc_v4_class(
                        titles=titles_list, components=comp_ids, fractions=norm_fracs
                    )
                else:
                    st.session_state.pop("sr_ffc_v3", None)
                    st.session_state.pop("sr_ffc_v4", None)
            except Exception as exc:
                st.error(f"Simulation failed: {exc}")

# ── Results ───────────────────────────────────────────────────────────────────
result = st.session_state.get("sr_result")
with res_col:
    if result is None:
        with st.container(border=True):
            st.markdown(
                '<div style="text-align:center;padding:3rem 0;opacity:0.4">'
                '<div style="font-size:3rem">🔬</div>'
                '<div style="font-size:1.1rem;margin-top:.5rem">'
                'Configure the formulation and click <strong>▶ Run Simulation</strong>'
                "</div></div>",
                unsafe_allow_html=True,
            )
        st.stop()

    cp_used   = st.session_state.get("sr_cp", 200.0)
    bd        = result["bulk_density"]
    td        = result["tapped_density"]
    ci        = (td - bd) / td * 100 if td else 0.0
    hr        = td / bd if bd else 0.0
    ffc_val   = result["ffc"]
    eaoif_val = result.get("effective_angle_of_internal_friction", 0.0)
    flow_class = (
        "Free-flowing" if ffc_val > 10 else
        "Easy-flowing" if ffc_val > 4  else
        "Cohesive"     if ffc_val > 2  else
        "Very cohesive"
    )

    st.markdown(f"### Results  ·  {cp_used:.0f} MPa")
    st.caption(
        "Formulation: "
        + " · ".join(
            f"{component_label(c)} ({f:.3f})"
            for c, f in zip(
                st.session_state.get("sr_comp_ids", []),
                st.session_state.get("sr_fracs", []),
            )
        )
    )

    tab_gran, tab_tablet, tab_morph, tab_form, tab_raw = st.tabs([
        "⚖️ Granular", "💊 Tablet", "🔬 Morphology", "🍩 Formulation", "📋 Raw Data",
    ])

    # ── Granular properties ──────────────────────────────────────────────
    with tab_gran:
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("True Density",   f"{result['true_density']:.4f} g/cm³")
        r2.metric("Bulk Density",   f"{result['bulk_density']:.4f} g/cm³")
        r3.metric("Tapped Density", f"{result['tapped_density']:.4f} g/cm³")
        r4.metric("Carr's Index",   f"{ci:.2f} %")

        r5, r6, r7, r8 = st.columns(4)
        r5.metric("Hausner Ratio",  f"{hr:.4f}")
        r6.metric("FFC",            f"{ffc_val:.4f}")
        r7.metric("EAOIF",          f"{eaoif_val:.4f} °")
        r8.metric("Flow Class",     flow_class)

        if eaoif_val > 41.0:
            st.warning(
                f"EAOIF = {eaoif_val:.2f}° exceeds the recommended maximum of **41°** "
                "(higher values indicate poorer powder flow through hoppers).",
                icon="⚠️",
            )

        with st.expander("ℹ️  Classification Guides"):
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**FFC → Flow class**")
                st.markdown(
                    "| FFC | Class |\n|---|---|\n"
                    "| > 10 | Free-flowing |\n| 4 – 10 | Easy-flowing |\n"
                    "| 2 – 4 | Cohesive |\n| < 2 | Very cohesive |"
                )
            with g2:
                st.markdown("**Carr's Index → Flowability**")
                st.markdown(
                    "| CI (%) | Class |\n|---|---|\n"
                    "| < 10 | Excellent |\n| 11 – 15 | Good |\n"
                    "| 16 – 20 | Fair |\n| 21 – 25 | Passable |\n| > 25 | Poor |"
                )

        ffc_v3_val = st.session_state.get("sr_ffc_v3")
        ffc_v4_lbl = st.session_state.get("sr_ffc_v4")
        if ffc_v3_val is not None or ffc_v4_lbl is not None:
            st.divider()
            st.caption("FFC model comparison — v1 · v3 · v4")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("FFC v1 — 1st-gen regression", f"{ffc_val:.4f}")
            if ffc_v3_val is not None:
                mc2.metric(
                    "FFC v3 — 2nd-gen regression",
                    f"{ffc_v3_val:.4f}",
                    delta=f"{ffc_v3_val - ffc_val:+.4f} vs v1",
                )
            if ffc_v4_lbl is not None:
                mc3.metric("FFC v4 — classification label", ffc_v4_lbl)

    # ── Tablet properties ────────────────────────────────────────────────
    with tab_tablet:
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.metric("Porosity Mean", f"{result['porosity_mean']:.4f}")
        tc2.metric("Porosity Std",  f"{result['porosity_std']:.4f}")
        tc3.metric("Tensile Mean",  f"{result['tensile_mean']:.4f} MPa")
        tc4.metric("Tensile Std",   f"{result['tensile_std']:.4f} MPa")

        ts_lo  = result["tensile_mean"]  - result["tensile_std"]
        ts_hi  = result["tensile_mean"]  + result["tensile_std"]
        por_lo = result["porosity_mean"] - result["porosity_std"]
        por_hi = result["porosity_mean"] + result["porosity_std"]

        ti1, ti2 = st.columns(2)
        ti1.info(f"**Tensile (mean ± std):** {ts_lo:.3f} – {ts_hi:.3f} MPa")
        ti2.info(f"**Porosity (mean ± std):** {por_lo:.4f} – {por_hi:.4f}")

        if result["tensile_mean"] < 1.0:
            st.warning(
                "Tensile strength < 1 MPa — the tablet may not have sufficient "
                "mechanical integrity.  Consider increasing compaction pressure "
                "or reducing high-plasticity excipients.",
                icon="⚠️",
            )

    # ── Morphology / PCA ─────────────────────────────────────────────────
    with tab_morph:
        p1, p2 = st.columns(2)
        with p1:
            st.plotly_chart(
                psd_figure(result["ce_diameter"], result["particle_size_dist"]),
                use_container_width=True,
            )
            st.plotly_chart(
                pca_bar(result["PCs_PSD"], "PCA Scores — Particle Size Distribution"),
                use_container_width=True,
            )
        with p2:
            st.plotly_chart(
                ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]),
                use_container_width=True,
            )
            st.plotly_chart(
                pca_bar(result["PCs_AR"], "PCA Scores — Aspect Ratio Distribution"),
                use_container_width=True,
            )
        st.caption(
            "PSD and AR distributions are blend-level predictions derived from the "
            "mixture model applied to raw material morphological data.  "
            "PCA scores summarise the distribution shape in the latent space used by "
            "the porosity and tensile strength models."
        )

    # ── Formulation composition ──────────────────────────────────────────
    with tab_form:
        titles_disp   = st.session_state.get("sr_titles", [])
        fracs_disp    = st.session_state.get("sr_fracs", [])
        comp_ids_disp = st.session_state.get("sr_comp_ids", [])
        if titles_disp and fracs_disp:
            pie_c, tbl_c = st.columns(2)
            with pie_c:
                st.plotly_chart(
                    formulation_pie(
                        [component_label(c) for c in comp_ids_disp],
                        fracs_disp,
                    ),
                    use_container_width=True,
                )
            with tbl_c:
                df_form = pd.DataFrame({
                    "ID":       comp_ids_disp,
                    "Name":     [component_label(c) for c in comp_ids_disp],
                    "Fraction": [f"{f:.4f}" for f in fracs_disp],
                })
                st.dataframe(df_form, use_container_width=True, hide_index=True)

    # ── Raw data download ─────────────────────────────────────────────────
    with tab_raw:
        st.json(result)
        st.download_button(
            "⬇ Download JSON",
            data=json.dumps(result, indent=2),
            file_name="single_run_result.json",
            mime="application/json",
        )
