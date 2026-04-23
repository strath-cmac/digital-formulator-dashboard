"""
Multiple-Run Simulation Page

Runs a formulation across a range of compaction pressures and fits
Kawakita (porosity) and Duckworth (tensile strength) empirical models.
Produces full compressibility and tensile-strength profiles with
95 % confidence bands.
"""

import json

import pandas as pd
import streamlit as st

from utils.api_client import (
    get_options,
    multiple_run,
    component_label,
    component_short_name,
)
from utils.plotting import (
    compressibility_figure,
    tensile_figure,
    formulation_pie,
    formulation_bar,
)

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Multiple Run | Digital Formulator",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Multiple-Run Simulation")
st.markdown(
    "Generate a compressibility and tensile-strength **profile across a compaction-pressure range** "
    "using Kawakita and Duckworth empirical models.  Results include 95 % confidence bands."
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
    st.header("📈 Multiple Run")

    _DEFAULTS = ["mc5", "la9", "cc1", "ms1"]
    safe_defaults = [d for d in _DEFAULTS if d in all_excipients]

    selected = st.multiselect(
        "Select components",
        options=all_excipients,
        default=safe_defaults if safe_defaults else all_excipients[:3],
        format_func=component_label,
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
                key=f"mr_frac_{comp}",
            )

        total = sum(fractions.values())
        colour = "green" if abs(total - 1.0) < 0.005 else "orange"
        st.markdown(
            f"**Sum:** :{colour}[{total:.4f}]" + (" ✓" if colour == "green" else " → will be normalised")
        )

    st.divider()
    st.header("Process Range")

    cp_min = st.slider("Min CP (MPa)", 30.0, 300.0, 70.0,  5.0)
    cp_max = st.slider("Max CP (MPa)", cp_min + 20.0, 450.0, 250.0, 5.0)
    n_runs = st.slider("Number of Points", 3, 20, 7)

    run_btn = st.button(
        "▶ Run Profile",
        type="primary",
        use_container_width=True,
        disabled=len(selected) < 1,
    )

# ── Guard ─────────────────────────────────────────────────────────────────
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

    with st.spinner(
        f"Running {n_runs} simulations across {cp_min:.0f}–{cp_max:.0f} MPa…"
    ):
        try:
            result = multiple_run(
                titles=titles_list,
                components=comp_ids,
                fractions=norm_fracs,
                cp_range=(cp_min, cp_max),
                n_runs=n_runs,
            )
            st.session_state["mr_result"]   = result
            st.session_state["mr_titles"]   = titles_list
            st.session_state["mr_fracs"]    = norm_fracs
            st.session_state["mr_comp_ids"] = comp_ids
        except Exception as e:
            st.error(f"Simulation failed: {e}")
            st.stop()

# ── Guard: no result yet ──────────────────────────────────────────────────
result = st.session_state.get("mr_result")
if result is None:
    st.info("Configure the formulation in the sidebar and click **▶ Run Profile**.")
    st.stop()

# ── Unpack results ────────────────────────────────────────────────────────
results_df = pd.DataFrame(result.get("results_df", []))
kp         = result.get("kawakita_params",  {})
dp         = result.get("duckworth_params", {})

# ── Results ───────────────────────────────────────────────────────────────
st.subheader("Profile Results")

tab_comp, tab_ten, tab_emp, tab_gran, tab_form, tab_raw = st.tabs(
    ["Compressibility", "Tensile Strength", "Empirical Models", "Granular Props", "Formulation", "Raw Data"]
)

# ── Compressibility ───────────────────────────────────────────────────────
with tab_comp:
    st.plotly_chart(compressibility_figure(results_df), use_container_width=True)

    if kp:
        kc1, kc2, kc3 = st.columns(3)
        init_por = kp.get("init_por")
        B        = kp.get("B")
        kc1.metric("Initial Porosity (a₀)",    f"{init_por:.5f}" if isinstance(init_por, float) else "N/A")
        kc2.metric("Kawakita Constant (B)",    f"{B:.6f}"        if isinstance(B,        float) else "N/A")
        kc3.metric("CP Range (MPa)",           f"{cp_min:.0f} – {cp_max:.0f}")

    if not results_df.empty:
        st.divider()
        st.caption("Tabular data")
        por_cols = [c for c in results_df.columns if "Porosity" in c or "Compression" in c]
        st.dataframe(
            results_df[por_cols] if por_cols else results_df,
            use_container_width=True,
        )

# ── Tensile ───────────────────────────────────────────────────────────────
with tab_ten:
    st.plotly_chart(tensile_figure(results_df), use_container_width=True)

    if dp:
        dc1, dc2 = st.columns(2)
        t_hat = dp.get("t_hat")
        kb    = dp.get("kb")
        dc1.metric("t̂ — Zero-porosity Tensile (MPa)", f"{t_hat:.5f}" if isinstance(t_hat, float) else "N/A")
        dc2.metric("kB — Sensitivity Constant",       f"{kb:.6f}"    if isinstance(kb,    float) else "N/A")

    if not results_df.empty:
        st.divider()
        st.caption("Tabular data")
        ten_cols = [c for c in results_df.columns if "Tensile" in c or "Compression" in c]
        st.dataframe(
            results_df[ten_cols] if ten_cols else results_df,
            use_container_width=True,
        )

# ── Empirical Model Equations ─────────────────────────────────────────────
with tab_emp:
    ec1, ec2 = st.columns(2)
    with ec1:
        st.subheader("Kawakita Equation")
        st.markdown(
            r"""
$$\varepsilon(P) = \dfrac{a_0}{1 + B \cdot P}$$

| Symbol | Meaning |
|--------|---------|
| $\varepsilon$ | Tablet porosity |
| $P$ | Compaction pressure (MPa) |
| $a_0$ | Initial (zero-pressure) porosity |
| $B$ | Compressibility constant |
"""
        )
        if kp:
            init_por = kp.get("init_por")
            B        = kp.get("B")
            if isinstance(init_por, float) and isinstance(B, float):
                st.info(
                    f"**Fitted:** $a_0$ = {init_por:.5f},  $B$ = {B:.6f}"
                )

    with ec2:
        st.subheader("Duckworth Equation")
        st.markdown(
            r"""
$$\sigma_T(\varepsilon) = \hat{t} \cdot e^{-k_B \cdot \varepsilon}$$

| Symbol | Meaning |
|--------|---------|
| $\sigma_T$ | Tensile strength (MPa) |
| $\varepsilon$ | Porosity |
| $\hat{t}$ | Tensile strength at zero porosity (MPa) |
| $k_B$ | Porosity sensitivity constant |
"""
        )
        if dp:
            t_hat = dp.get("t_hat")
            kb    = dp.get("kb")
            if isinstance(t_hat, float) and isinstance(kb, float):
                st.info(
                    f"**Fitted:** $\\hat{{t}}$ = {t_hat:.5f},  $k_B$ = {kb:.6f}"
                )

# ── Granular props at first CP ────────────────────────────────────────────
with tab_gran:
    st.caption(
        "Granular properties are evaluated at the **first** compaction pressure "
        f"({cp_min:.0f} MPa)."
    )
    bd = result.get("bulk_density", 0)
    td = result.get("tapped_density", 0)
    ci = (td - bd) / td * 100 if td else 0.0
    hr = td / bd if bd else 0.0
    ffc_val = result.get("ffc", 0)

    gc1, gc2, gc3, gc4 = st.columns(4)
    gc1.metric("True Density (g/cm³)",   f"{result.get('true_density', 0):.4f}")
    gc2.metric("Bulk Density (g/cm³)",   f"{bd:.4f}")
    gc3.metric("Tapped Density (g/cm³)", f"{td:.4f}")
    gc4.metric("Carr's Index (%)",       f"{ci:.2f}")

    gc5, gc6, gc7 = st.columns(3)
    gc5.metric("Hausner Ratio",             f"{hr:.4f}")
    gc6.metric("FFC",                       f"{ffc_val:.4f}")
    gc7.metric("EAOIF (°)",                 f"{result.get('effective_angle_of_internal_friction', 0):.4f}")

# ── Formulation ───────────────────────────────────────────────────────────
with tab_form:
    titles_disp   = st.session_state.get("mr_titles",   [])
    fracs_disp    = st.session_state.get("mr_fracs",    [])
    comp_ids_disp = st.session_state.get("mr_comp_ids", [])

    if titles_disp and fracs_disp:
        fp_col, fb_col = st.columns(2)
        with fp_col:
            st.plotly_chart(formulation_pie(titles_disp, fracs_disp), use_container_width=True)
        with fb_col:
            df_form = pd.DataFrame({
                "Component": [component_label(c) for c in comp_ids_disp],
                "ID":        comp_ids_disp,
                "Fraction":  [f"{f:.4f}" for f in fracs_disp],
            })
            st.dataframe(df_form, use_container_width=True, hide_index=True)

# ── Raw ───────────────────────────────────────────────────────────────────
with tab_raw:
    # Show the profile DataFrame prominently
    if not results_df.empty:
        st.subheader("Profile DataFrame")
        st.dataframe(results_df, use_container_width=True)
        csv = results_df.to_csv(index=False).encode()
        st.download_button(
            "⬇ Download CSV",
            data=csv,
            file_name="multiple_run_profile.csv",
            mime="text/csv",
        )

    st.subheader("Full JSON Response")
    st.json(result)
    st.download_button(
        "⬇ Download JSON",
        data=json.dumps(result, indent=2),
        file_name="multiple_run_result.json",
        mime="application/json",
    )
