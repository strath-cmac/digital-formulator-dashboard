"""Multiple-Run Simulation — redesigned UI"""
from __future__ import annotations
import json
import pandas as pd
import streamlit as st
from utils.api_client import get_options, multiple_run, component_label, component_short_name
from utils.plotting import compressibility_figure, tensile_figure, formulation_pie, formulation_bar

st.set_page_config(page_title="Multiple Run | Digital Formulator", page_icon="\U0001f4c8", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
[data-testid="stMetric"]{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:14px 18px !important;}
[data-testid="stCaptionContainer"]>p{text-transform:uppercase;letter-spacing:.07em;font-size:.69rem !important;font-weight:600;color:rgba(255,255,255,0.4) !important;}
[data-testid="collapsedControl"]{display:none;}
</style>""", unsafe_allow_html=True)

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

st.markdown("# \U0001f4c8 Multiple-Run Simulation")
st.markdown("Generate a compressibility and tensile-strength **profile across a compaction-pressure range** using Kawakita and Duckworth models.")
st.divider()

cfg_col, res_col = st.columns([2, 3], gap="large")

with cfg_col:
    with st.container(border=True):
        st.caption("Formulation")
        st.markdown("#### Build your formulation")
        _DEFAULTS = ["mc5", "la9", "cc1", "ms1"]
        safe_defaults = [d for d in _DEFAULTS if d in all_excipients]
        if "mr_form_df" not in st.session_state:
            n = len(safe_defaults)
            st.session_state["mr_form_df"] = pd.DataFrame({
                "Component": [component_label(c) for c in safe_defaults],
                "Fraction":  [round(1.0 / n, 4)] * n,
            })
        edited_df = st.data_editor(
            st.session_state["mr_form_df"],
            column_config={
                "Component": st.column_config.SelectboxColumn("Component", options=_label_options, required=True, width="large"),
                "Fraction":  st.column_config.NumberColumn("Fraction (w/w)", min_value=0.001, max_value=1.0, step=0.005, format="%.4f", width="small"),
            },
            num_rows="dynamic", use_container_width=True, key="mr_form_editor", hide_index=True,
        )
        st.session_state["mr_form_df"] = edited_df
        valid_rows = edited_df.dropna(subset=["Component", "Fraction"])
        total_frac = float(valid_rows["Fraction"].sum()) if not valid_rows.empty else 0.0
        if abs(total_frac - 1.0) < 0.005:
            st.success(f"Sum: **{total_frac:.4f}** \u2713", icon="\u2705")
        else:
            st.warning(f"Sum: **{total_frac:.4f}** \u2014 will be normalised", icon="\u26a0\ufe0f")

    with st.container(border=True):
        st.caption("Compaction Pressure Range")
        cp_c1, cp_c2 = st.columns(2)
        cp_min = cp_c1.number_input("Min CP (MPa)", min_value=30.0, max_value=400.0, value=70.0,  step=5.0)
        cp_max = cp_c2.number_input("Max CP (MPa)", min_value=50.0, max_value=450.0, value=250.0, step=5.0)
        if cp_min >= cp_max:
            st.error("Min CP must be less than Max CP.")
        n_runs = st.slider("Number of simulation points", min_value=3, max_value=20, value=7, step=1)
        st.caption(f"CP points: {cp_min:.0f} \u2013 {cp_max:.0f} MPa  \u00b7  {n_runs} evaluations")

    n_valid = len(edited_df.dropna(subset=["Component"]))
    run_btn = st.button("\u25b6\u2002Run Profile", type="primary", use_container_width=True, disabled=(n_valid < 1 or cp_min >= cp_max))

if run_btn:
    valid_rows  = edited_df.dropna(subset=["Component", "Fraction"])
    comp_labels = valid_rows["Component"].tolist()
    comp_ids    = [_id_from_label[lbl] for lbl in comp_labels if lbl in _id_from_label]
    frac_vals   = [float(v) for v in valid_rows["Fraction"].tolist()]
    total_frac  = sum(frac_vals)
    norm_fracs  = [f / total_frac for f in frac_vals]
    titles_list = [component_short_name(c) for c in comp_ids]
    with res_col:
        with st.spinner(f"Running {n_runs} simulations across {cp_min:.0f}\u2013{cp_max:.0f} MPa\u2026"):
            try:
                result = multiple_run(titles=titles_list, components=comp_ids, fractions=norm_fracs, cp_range=(cp_min, cp_max), n_runs=n_runs)
                st.session_state.update({"mr_result": result, "mr_titles": titles_list, "mr_fracs": norm_fracs, "mr_comp_ids": comp_ids, "mr_cp_min": cp_min, "mr_cp_max": cp_max})
            except Exception as e:
                st.error(f"Simulation failed: {e}")

result = st.session_state.get("mr_result")
with res_col:
    if result is None:
        st.markdown("### Results")
        with st.container(border=True):
            st.markdown('''<div style="text-align:center;padding:3rem 0;opacity:0.4"><div style="font-size:3rem">\U0001f4c8</div><div style="font-size:1.1rem;margin-top:.5rem">Configure the formulation and click <strong>\u25b6 Run Profile</strong></div></div>''', unsafe_allow_html=True)
        st.stop()

    results_df = pd.DataFrame(result.get("results_df", []))
    kp = result.get("kawakita_params", {}); dp = result.get("duckworth_params", {})
    cp_min_used = st.session_state.get("mr_cp_min", 70.0); cp_max_used = st.session_state.get("mr_cp_max", 250.0)

    _sep = " \u00b7 "
    st.markdown(f"### Results  \u00b7  {cp_min_used:.0f} \u2013 {cp_max_used:.0f} MPa")
    st.caption("Formulation: " + _sep.join(st.session_state.get("mr_titles", [])))

    tab_comp, tab_ten, tab_emp, tab_gran, tab_form, tab_raw = st.tabs(["\U0001f4ca Compressibility", "\U0001f4aa Tensile Strength", "\U0001f9ee Empirical Models", "\u2696\ufe0f Granular Props", "\U0001f369 Formulation", "\U0001f4cb Raw Data"])

    with tab_comp:
        st.plotly_chart(compressibility_figure(results_df), use_container_width=True)
        if kp:
            kc1, kc2, kc3 = st.columns(3)
            kc1.metric("Initial Porosity (a\u2080)", f"{kp.get('init_por', 0):.5f}" if isinstance(kp.get('init_por'), float) else "N/A")
            kc2.metric("Kawakita Constant (B)", f"{kp.get('B', 0):.6f}" if isinstance(kp.get('B'), float) else "N/A")
            kc3.metric("CP Range (MPa)", f"{cp_min_used:.0f} \u2013 {cp_max_used:.0f}")

    with tab_ten:
        st.plotly_chart(tensile_figure(results_df), use_container_width=True)
        if dp:
            dc1, dc2 = st.columns(2)
            dc1.metric("t\u0302 \u2014 Zero-porosity Tensile (MPa)", f"{dp.get('t_hat', 0):.5f}" if isinstance(dp.get('t_hat'), float) else "N/A")
            dc2.metric("k\u0299 \u2014 Sensitivity Constant", f"{dp.get('kb', 0):.6f}" if isinstance(dp.get('kb'), float) else "N/A")

    with tab_emp:
        ec1, ec2 = st.columns(2)
        with ec1:
            st.markdown("#### Kawakita Equation")
            st.latex(r"\varepsilon(P) = \dfrac{a_0}{1 + B \cdot P}")
            st.markdown("| Symbol | Meaning |\n|--------|---------|\n| \u03b5 | Porosity |\n| P | Compaction pressure (MPa) |\n| a\u2080 | Initial porosity |\n| B | Compressibility constant |")
            if kp and isinstance(kp.get("init_por"), float) and isinstance(kp.get("B"), float):
                st.info(f"**Fitted:** a\u2080 = {kp['init_por']:.5f},  B = {kp['B']:.6f}")
        with ec2:
            st.markdown("#### Duckworth Equation")
            st.latex(r"\sigma_T(\varepsilon) = \hat{t} \cdot e^{-k_B \cdot \varepsilon}")
            st.markdown("| Symbol | Meaning |\n|--------|---------|\n| \u03c3\u1d40 | Tensile strength (MPa) |\n| \u03b5 | Porosity |\n| t\u0302 | Tensile at zero porosity |\n| k\u0299 | Porosity sensitivity |")
            if dp and isinstance(dp.get("t_hat"), float) and isinstance(dp.get("kb"), float):
                st.info(f"**Fitted:** t\u0302 = {dp['t_hat']:.5f},  k\u0299 = {dp['kb']:.6f}")

    with tab_gran:
        bd = result.get("bulk_density", 0); td = result.get("tapped_density", 0)
        ci = (td - bd) / td * 100 if td else 0.0; hr = td / bd if bd else 0.0; ffc_val = result.get("ffc", 0)
        gc1, gc2, gc3, gc4 = st.columns(4)
        gc1.metric("True Density", f"{result.get('true_density', 0):.4f} g/cm\u00b3")
        gc2.metric("Bulk Density", f"{bd:.4f} g/cm\u00b3")
        gc3.metric("Tapped Density", f"{td:.4f} g/cm\u00b3")
        gc4.metric("Carr's Index", f"{ci:.2f} %")
        gc5, gc6, gc7 = st.columns(3)
        gc5.metric("Hausner Ratio", f"{hr:.4f}")
        gc6.metric("FFC", f"{ffc_val:.4f}")
        gc7.metric("EAOIF (\u00b0)", f"{result.get('effective_angle_of_internal_friction', 0):.4f}")
        eaoif_val = result.get("effective_angle_of_internal_friction", 0.0)
        if eaoif_val > 41.0:
            st.warning(f"EAOIF = {eaoif_val:.2f}\u00b0 exceeds the recommended maximum of **41\u00b0**.", icon="\u26a0\ufe0f")

    with tab_form:
        titles_disp = st.session_state.get("mr_titles", []); fracs_disp = st.session_state.get("mr_fracs", [])
        comp_ids_disp = st.session_state.get("mr_comp_ids", [])
        if titles_disp and fracs_disp:
            pie_c, tbl_c = st.columns(2)
            with pie_c:
                st.plotly_chart(formulation_pie(titles_disp, fracs_disp), use_container_width=True)
            with tbl_c:
                df_form = pd.DataFrame({"Component": [component_label(c) for c in comp_ids_disp], "ID": comp_ids_disp, "Fraction": [f"{f:.4f}" for f in fracs_disp]})
                st.dataframe(df_form, use_container_width=True, hide_index=True)

    with tab_raw:
        if not results_df.empty:
            st.subheader("Profile DataFrame")
            st.dataframe(results_df, use_container_width=True)
            st.download_button("\u2b07 Download CSV", data=results_df.to_csv(index=False).encode(), file_name="multiple_run_profile.csv", mime="text/csv")
        st.subheader("Full JSON Response"); st.json(result)
