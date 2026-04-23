"""Single-Point Simulation — redesigned UI"""
from __future__ import annotations
import json
import pandas as pd
import streamlit as st
from utils.api_client import (
    get_options, single_run, component_label, component_short_name, ffc_v3, ffc_v4_class,
)
from utils.plotting import psd_figure, ar_figure, pca_bar, formulation_pie


# ── API options ───────────────────────────────────────────────────────────
if "api_options" not in st.session_state:
    try:
        st.session_state["api_options"] = get_options()
    except Exception as e:
        st.error(f"Cannot reach API: {e}"); st.stop()

opts           = st.session_state["api_options"]
all_excipients = opts.get("available_excipients", [])
all_apis       = opts.get("available_apis", [])
all_components = all_apis + all_excipients   # APIs listed first
if not all_components:
    st.error("No components returned by the API."); st.stop()

_label_options = [component_label(c) for c in all_components]
_id_from_label = {component_label(c): c for c in all_components}

st.markdown("""
<div class='page-header'>
  <div class='ph-title'>\U0001f52c Single-Point Simulation</div>
  <div class='ph-sub'>Predict granular and tablet properties for a specific formulation at a fixed compaction pressure</div>
</div>""", unsafe_allow_html=True)

# ── Layout ────────────────────────────────────────────────────────────────
cfg_col, res_col = st.columns([2, 3], gap="large")

with cfg_col:
    with st.container(border=True):
        st.caption("Formulation")
        st.markdown("#### Build your formulation")
        _DEFAULTS = ["mc5", "la9", "cc1", "ms1"]
        safe_defaults = [d for d in _DEFAULTS if d in all_excipients]
        if "sr_form_df" not in st.session_state:
            n = len(safe_defaults)
            st.session_state["sr_form_df"] = pd.DataFrame({
                "Component": [component_label(c) for c in safe_defaults],
                "Fraction":  [round(1.0 / n, 4)] * n,
            })
        edited_df = st.data_editor(
            st.session_state["sr_form_df"],
            column_config={
                "Component": st.column_config.SelectboxColumn("Component", options=_label_options, required=True, width="large"),
                "Fraction":  st.column_config.NumberColumn("Fraction (w/w)", min_value=0.001, max_value=1.0, step=0.005, format="%.4f", width="small"),
            },
            num_rows="dynamic", use_container_width=True, key="sr_form_editor", hide_index=True,
        )
        st.session_state["sr_form_df"] = edited_df
        valid_rows = edited_df.dropna(subset=["Component", "Fraction"])
        total_frac = float(valid_rows["Fraction"].sum()) if not valid_rows.empty else 0.0
        if abs(total_frac - 1.0) < 0.005:
            st.success(f"Sum: **{total_frac:.4f}** \u2713", icon="\u2705")
        else:
            st.warning(f"Sum: **{total_frac:.4f}** \u2014 will be normalised", icon="\u26a0\ufe0f")

    with st.container(border=True):
        st.caption("Process")
        st.markdown("#### Compaction Pressure")
        cp = st.slider("CP (MPa)", min_value=50.0, max_value=450.0, value=200.0, step=5.0, label_visibility="collapsed", format="%.0f MPa")
        st.markdown(f"**Selected:** {cp:.0f} MPa")

    with st.container(border=True):
        st.caption("Options")
        fetch_ffc_models = st.toggle("Compare FFC model versions (v1 / v3 / v4)", value=False,
            help="Calls two extra API endpoints. Shows a v1/v3/v4 comparison.")

    n_valid = len(edited_df.dropna(subset=["Component"]))
    run_btn = st.button("\u25b6\u2002Run Simulation", type="primary", use_container_width=True, disabled=n_valid < 1)

if run_btn:
    valid_rows  = edited_df.dropna(subset=["Component", "Fraction"])
    comp_labels = valid_rows["Component"].tolist()
    comp_ids    = [_id_from_label[lbl] for lbl in comp_labels if lbl in _id_from_label]
    frac_vals   = [float(v) for v in valid_rows["Fraction"].tolist()]
    total_frac  = sum(frac_vals)
    norm_fracs  = [f / total_frac for f in frac_vals]
    titles_list = [component_short_name(c) for c in comp_ids]
    with res_col:
        with st.spinner("Running simulation\u2026"):
            try:
                result = single_run(titles=titles_list, components=comp_ids, fractions=norm_fracs, cp=cp)
                st.session_state.update({"sr_result": result, "sr_titles": titles_list, "sr_fracs": norm_fracs, "sr_comp_ids": comp_ids, "sr_cp": cp})
                if fetch_ffc_models:
                    st.session_state["sr_ffc_v3"] = ffc_v3(titles=titles_list, components=comp_ids, fractions=norm_fracs)
                    st.session_state["sr_ffc_v4"] = ffc_v4_class(titles=titles_list, components=comp_ids, fractions=norm_fracs)
                else:
                    st.session_state.pop("sr_ffc_v3", None); st.session_state.pop("sr_ffc_v4", None)
            except Exception as e:
                st.error(f"Simulation failed: {e}")

result = st.session_state.get("sr_result")
with res_col:
    if result is None:
        st.markdown("### Results")
        with st.container(border=True):
            st.markdown('''<div style="text-align:center;padding:3rem 0;opacity:0.4"><div style="font-size:3rem">\U0001f52c</div><div style="font-size:1.1rem;margin-top:.5rem">Configure the formulation and click <strong>\u25b6 Run Simulation</strong></div></div>''', unsafe_allow_html=True)
        st.stop()

    cp_used   = st.session_state.get("sr_cp", 200.0)
    bd        = result["bulk_density"]; td = result["tapped_density"]
    ci        = (td - bd) / td * 100 if td else 0.0
    hr        = td / bd if bd else 0.0
    ffc_val   = result["ffc"]
    eaoif_val = result.get("effective_angle_of_internal_friction", 0.0)
    flow_class = ("Free-flowing" if ffc_val > 10 else "Easy-flowing" if ffc_val > 4 else "Cohesive" if ffc_val > 2 else "Very cohesive")

    _sep = " \u00b7 "
    st.markdown(f"### Results  \u00b7  {cp_used:.0f} MPa")
    st.caption("Formulation: " + _sep.join(st.session_state.get("sr_titles", [])))

    tab_gran, tab_tablet, tab_morph, tab_form, tab_raw = st.tabs(["\u2696\ufe0f Granular", "\U0001f48a Tablet", "\U0001f52c Morphology", "\U0001f369 Formulation", "\U0001f4cb Raw Data"])

    with tab_gran:
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("True Density",   f"{result['true_density']:.4f} g/cm\u00b3")
        r2.metric("Bulk Density",   f"{result['bulk_density']:.4f} g/cm\u00b3")
        r3.metric("Tapped Density", f"{result['tapped_density']:.4f} g/cm\u00b3")
        r4.metric("Carr's Index",   f"{ci:.2f} %")
        r5, r6, r7, r8 = st.columns(4)
        r5.metric("Hausner Ratio", f"{hr:.4f}")
        r6.metric("FFC",           f"{ffc_val:.4f}")
        r7.metric("EAOIF",         f"{eaoif_val:.4f} \u00b0")
        r8.metric("Flow Class",    flow_class)
        if eaoif_val > 41.0:
            st.warning(f"EAOIF = {eaoif_val:.2f}\u00b0 exceeds the recommended maximum of **41\u00b0**.", icon="\u26a0\ufe0f")
        with st.expander("\u2139\ufe0f  Classification Guides"):
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**FFC \u2192 Flow class**")
                st.markdown("|FFC|Class|\n|---|---|\n|>10|Free-flowing|\n|4\u201310|Easy-flowing|\n|2\u20134|Cohesive|\n|<2|Very cohesive|")
            with g2:
                st.markdown("**Carr's Index \u2192 Flowability**")
                st.markdown("|CI (%)|Class|\n|---|---|\n|<10|Excellent|\n|11\u201315|Good|\n|16\u201320|Fair|\n|21\u201325|Passable|\n|>25|Poor|")
        ffc_v3_val = st.session_state.get("sr_ffc_v3"); ffc_v4_lbl = st.session_state.get("sr_ffc_v4")
        if ffc_v3_val is not None or ffc_v4_lbl is not None:
            st.divider(); st.caption("FFC model comparison \u2014 v1 \u00b7 v3 \u00b7 v4")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("FFC v1 \u2014 1st-gen regression", f"{ffc_val:.4f}")
            if ffc_v3_val is not None:
                mc2.metric("FFC v3 \u2014 2nd-gen regression", f"{ffc_v3_val:.4f}", delta=f"{ffc_v3_val - ffc_val:+.4f} vs v1")
            if ffc_v4_lbl is not None:
                mc3.metric("FFC v4 \u2014 classification", ffc_v4_lbl)

    with tab_tablet:
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.metric("Porosity Mean", f"{result['porosity_mean']:.4f}")
        tc2.metric("Porosity Std",  f"{result['porosity_std']:.4f}")
        tc3.metric("Tensile Mean",  f"{result['tensile_mean']:.4f} MPa")
        tc4.metric("Tensile Std",   f"{result['tensile_std']:.4f} MPa")
        ts_lo = result["tensile_mean"] - result["tensile_std"]; ts_hi = result["tensile_mean"] + result["tensile_std"]
        por_lo = result["porosity_mean"] - result["porosity_std"]; por_hi = result["porosity_mean"] + result["porosity_std"]
        ti1, ti2 = st.columns(2)
        ti1.info(f"**Tensile (mean \u00b1 std):** {ts_lo:.3f} \u2013 {ts_hi:.3f} MPa")
        ti2.info(f"**Porosity (mean \u00b1 std):** {por_lo:.4f} \u2013 {por_hi:.4f}")

    with tab_morph:
        p1, p2 = st.columns(2)
        with p1:
            st.plotly_chart(psd_figure(result["ce_diameter"], result["particle_size_dist"]), use_container_width=True)
            st.plotly_chart(pca_bar(result["PCs_PSD"], "PCA Scores \u2014 Particle Size Distribution"), use_container_width=True)
        with p2:
            st.plotly_chart(ar_figure(result["Aspect Ratio"], result["aspect_ratio_dist"]), use_container_width=True)
            st.plotly_chart(pca_bar(result["PCs_AR"], "PCA Scores \u2014 Aspect Ratio Distribution"), use_container_width=True)

    with tab_form:
        titles_disp = st.session_state.get("sr_titles", []); fracs_disp = st.session_state.get("sr_fracs", [])
        comp_ids_disp = st.session_state.get("sr_comp_ids", [])
        if titles_disp and fracs_disp:
            pie_c, tbl_c = st.columns(2)
            with pie_c:
                st.plotly_chart(formulation_pie(titles_disp, fracs_disp), use_container_width=True)
            with tbl_c:
                df_form = pd.DataFrame({"Component": [component_label(c) for c in comp_ids_disp], "ID": comp_ids_disp, "Fraction": [f"{f:.4f}" for f in fracs_disp]})
                st.dataframe(df_form, use_container_width=True, hide_index=True)

    with tab_raw:
        st.json(result)
        st.download_button("\u2b07 Download JSON", data=json.dumps(result, indent=2), file_name="single_run_result.json", mime="application/json")
