"""Multiple-Run Simulation — compressibility and tensile-strength profiles via Kawakita & Duckworth models."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import (
    get_options,
    multiple_run,
    component_label,
    component_short_name,
    is_api,
)
from utils.plotting import (
    compressibility_figure,
    tensile_figure,
    formulation_pie,
    formulation_bar,
)


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
all_components = all_apis + all_excipients

if not all_components:
    st.error(
        "The API returned no components. "
        "Check that the backend is running and the material database is accessible."
    )
    st.stop()

_label_options = [component_label(c) for c in all_components]
_id_from_label = {component_label(c): c for c in all_components}

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='page-header'>
  <div class='ph-title'>📈 Multiple-Run Simulation</div>
  <div class='ph-sub'>Generate a compressibility and tensile-strength profile across a compaction-pressure range
  using the Kawakita and Duckworth empirical models</div>
</div>""", unsafe_allow_html=True)

# ── Sensible default formulation ──────────────────────────────────────────────
_DEFAULT_IDS   = ["mc5", "la9", "cc1", "ms1"]
_DEFAULT_FRACS = [0.71, 0.20, 0.08, 0.01]


def _build_default_df() -> pd.DataFrame:
    pairs = [
        (c, f) for c, f in zip(_DEFAULT_IDS, _DEFAULT_FRACS)
        if c in all_components
    ]
    if not pairs:
        n = min(4, len(all_components))
        pairs = [(all_components[i], round(1.0 / n, 4)) for i in range(n)]
    if pairs and all_apis and not any(is_api(c) for c, _ in pairs):
        api_id = all_apis[0]
        pairs = [(api_id, 0.20)] + [(c, round(f * 0.80, 4)) for c, f in pairs]
    comps, fracs = zip(*pairs) if pairs else ([], [])
    return pd.DataFrame({
        "Component": [component_label(c) for c in comps],
        "Fraction":  list(fracs),
    })


# ── Layout ────────────────────────────────────────────────────────────────────
cfg_col, res_col = st.columns([2, 3], gap="large")

with cfg_col:
    # ── Formulation builder ──────────────────────────────────────────────
    with st.container(border=True):
        st.caption("Formulation")
        st.markdown("#### Build your formulation")
        st.caption(
            "Typical tablet: API (~20 %) · Filler(s) · "
            "Disintegrant (~8 %) · Lubricant (~1 %)"
        )

        if "mr_form_df" not in st.session_state:
            st.session_state["mr_form_df"] = _build_default_df()

        edited_df = st.data_editor(
            st.session_state["mr_form_df"],
            column_config={
                "Component": st.column_config.SelectboxColumn(
                    "Component",
                    options=_label_options,
                    required=True,
                    width="large",
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
            key="mr_form_editor",
            hide_index=True,
        )
        st.session_state["mr_form_df"] = edited_df

        valid_rows = edited_df.dropna(subset=["Component", "Fraction"])
        total_frac = float(valid_rows["Fraction"].sum()) if not valid_rows.empty else 0.0
        if abs(total_frac - 1.0) < 0.005:
            st.success(f"Sum: **{total_frac:.4f}** ✓", icon="✅")
        else:
            st.warning(f"Sum: **{total_frac:.4f}** — will be normalised", icon="⚠️")

    # ── CP range ─────────────────────────────────────────────────────────
    with st.container(border=True):
        st.caption("Compaction Pressure Range")
        cp_c1, cp_c2 = st.columns(2)
        cp_min = cp_c1.number_input(
            "Min CP (MPa)", min_value=30.0, max_value=400.0, value=70.0, step=5.0
        )
        cp_max = cp_c2.number_input(
            "Max CP (MPa)", min_value=50.0, max_value=450.0, value=250.0, step=5.0
        )
        if cp_min >= cp_max:
            st.error("Min CP must be less than Max CP.")
        n_runs = st.slider(
            "Number of simulation points",
            min_value=3, max_value=20, value=7, step=1,
            help=(
                "More points give a smoother empirical fit but take longer. "
                "7 – 10 points is usually sufficient for reliable Kawakita and Duckworth fitting."
            ),
        )
        st.caption(
            f"CP range: {cp_min:.0f} – {cp_max:.0f} MPa  ·  {n_runs} evaluations"
        )

    n_valid = len(valid_rows)
    run_btn = st.button(
        "▶  Run Profile",
        type="primary",
        use_container_width=True,
        disabled=(n_valid < 1 or cp_min >= cp_max),
    )

# ── Run ───────────────────────────────────────────────────────────────────────
if run_btn:
    vr         = edited_df.dropna(subset=["Component", "Fraction"])
    comp_ids   = [_id_from_label[lbl] for lbl in vr["Component"].tolist() if lbl in _id_from_label]
    frac_vals  = [float(v) for v in vr["Fraction"].tolist()]
    total_frac = sum(frac_vals)
    norm_fracs = [f / total_frac for f in frac_vals]
    titles_list = [component_short_name(c) for c in comp_ids]

    with res_col:
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
                st.session_state.update({
                    "mr_result":   result,
                    "mr_titles":   titles_list,
                    "mr_fracs":    norm_fracs,
                    "mr_comp_ids": comp_ids,
                    "mr_cp_min":   cp_min,
                    "mr_cp_max":   cp_max,
                })
            except Exception as exc:
                st.error(f"Simulation failed: {exc}")

# ── Results ───────────────────────────────────────────────────────────────────
result = st.session_state.get("mr_result")
with res_col:
    if result is None:
        with st.container(border=True):
            st.markdown(
                '<div style="text-align:center;padding:3rem 0;opacity:0.4">'
                '<div style="font-size:3rem">📈</div>'
                '<div style="font-size:1.1rem;margin-top:.5rem">'
                'Configure the formulation and click <strong>▶ Run Profile</strong>'
                "</div></div>",
                unsafe_allow_html=True,
            )
        st.stop()

    results_df  = pd.DataFrame(result.get("results_df", []))
    kp          = result.get("kawakita_params", {})
    dp          = result.get("duckworth_params", {})
    cp_min_used = st.session_state.get("mr_cp_min", 70.0)
    cp_max_used = st.session_state.get("mr_cp_max", 250.0)

    st.markdown(f"### Results  ·  {cp_min_used:.0f} – {cp_max_used:.0f} MPa")
    st.caption(
        "Formulation: "
        + " · ".join(
            f"{component_label(c)} ({f:.3f})"
            for c, f in zip(
                st.session_state.get("mr_comp_ids", []),
                st.session_state.get("mr_fracs", []),
            )
        )
    )

    tab_comp, tab_ten, tab_emp, tab_gran, tab_form, tab_raw = st.tabs([
        "📊 Compressibility",
        "💪 Tensile Strength",
        "🧮 Empirical Models",
        "⚖️ Granular Props",
        "🍩 Formulation",
        "📋 Raw Data",
    ])

    # ── Compressibility profile ──────────────────────────────────────────
    with tab_comp:
        st.plotly_chart(compressibility_figure(results_df), use_container_width=True)
        if kp:
            kc1, kc2, kc3 = st.columns(3)
            kc1.metric(
                "Initial Porosity (a₀)",
                f"{kp.get('init_por', 0):.5f}"
                if isinstance(kp.get("init_por"), float) else "N/A",
            )
            kc2.metric(
                "Kawakita Constant (B)",
                f"{kp.get('B', 0):.6f}"
                if isinstance(kp.get("B"), float) else "N/A",
            )
            kc3.metric("CP Range (MPa)", f"{cp_min_used:.0f} – {cp_max_used:.0f}")
        st.caption(
            "Shaded band = ±17 % prediction interval on the Kawakita model fit "
            "(empirical calibration from experimental validation data)."
        )

    # ── Tensile strength profile ─────────────────────────────────────────
    with tab_ten:
        st.plotly_chart(tensile_figure(results_df), use_container_width=True)
        if dp:
            dc1, dc2 = st.columns(2)
            dc1.metric(
                "t̂ — Zero-porosity Tensile (MPa)",
                f"{dp.get('t_hat', 0):.5f}"
                if isinstance(dp.get("t_hat"), float) else "N/A",
            )
            dc2.metric(
                "k_B — Sensitivity Constant",
                f"{dp.get('kb', 0):.6f}"
                if isinstance(dp.get("kb"), float) else "N/A",
            )
        st.caption(
            "Tensile strength is predicted via the Duckworth equation fitted to the "
            "ML-predicted porosity profile.  Shaded band = ±17 % prediction interval."
        )

    # ── Empirical model equations ────────────────────────────────────────
    with tab_emp:
        ec1, ec2 = st.columns(2)
        with ec1:
            st.markdown("#### Kawakita Equation")
            st.latex(r"\varepsilon(P) = \dfrac{a_0}{1 + B \cdot P}")
            st.markdown(
                "| Symbol | Meaning |\n|--------|---------|\n"
                "| ε | Porosity (–) |\n"
                "| P | Compaction pressure (MPa) |\n"
                "| a₀ | Initial porosity |\n"
                "| B | Compressibility constant |"
            )
            if kp and isinstance(kp.get("init_por"), float) and isinstance(kp.get("B"), float):
                st.info(f"**Fitted:** a₀ = {kp['init_por']:.5f},  B = {kp['B']:.6f}")

        with ec2:
            st.markdown("#### Duckworth Equation")
            st.latex(r"\sigma_T(\varepsilon) = \hat{t} \cdot e^{-k_B \cdot \varepsilon}")
            st.markdown(
                "| Symbol | Meaning |\n|--------|---------|\n"
                "| σ_T | Tensile strength (MPa) |\n"
                "| ε | Porosity (–) |\n"
                "| t̂ | Tensile strength at zero porosity |\n"
                "| k_B | Porosity sensitivity constant |"
            )
            if dp and isinstance(dp.get("t_hat"), float) and isinstance(dp.get("kb"), float):
                st.info(f"**Fitted:** t̂ = {dp['t_hat']:.5f},  k_B = {dp['kb']:.6f}")

    # ── Granular properties (at cp_range[0]) ────────────────────────────
    with tab_gran:
        st.caption(f"Blend properties predicted at CP = {cp_min_used:.0f} MPa (lower bound of profile)")
        bd       = result.get("bulk_density", 0)
        td       = result.get("tapped_density", 0)
        ci       = (td - bd) / td * 100 if td else 0.0
        hr       = td / bd if bd else 0.0
        ffc_val  = result.get("ffc", 0)
        eaoif_val = result.get("effective_angle_of_internal_friction", 0.0)

        gc1, gc2, gc3, gc4 = st.columns(4)
        gc1.metric("True Density",   f"{result.get('true_density', 0):.4f} g/cm³")
        gc2.metric("Bulk Density",   f"{bd:.4f} g/cm³")
        gc3.metric("Tapped Density", f"{td:.4f} g/cm³")
        gc4.metric("Carr's Index",   f"{ci:.2f} %")

        gc5, gc6, gc7 = st.columns(3)
        gc5.metric("Hausner Ratio",  f"{hr:.4f}")
        gc6.metric("FFC",            f"{ffc_val:.4f}")
        gc7.metric("EAOIF (°)",      f"{eaoif_val:.4f}")

        if eaoif_val > 41.0:
            st.warning(
                f"EAOIF = {eaoif_val:.2f}° exceeds the recommended maximum of **41°**.",
                icon="⚠️",
            )

    # ── Formulation composition ──────────────────────────────────────────
    with tab_form:
        titles_disp   = st.session_state.get("mr_titles", [])
        fracs_disp    = st.session_state.get("mr_fracs", [])
        comp_ids_disp = st.session_state.get("mr_comp_ids", [])
        if titles_disp and fracs_disp:
            pie_c, bar_c = st.columns(2)
            with pie_c:
                st.plotly_chart(
                    formulation_pie(
                        [component_label(c) for c in comp_ids_disp],
                        fracs_disp,
                    ),
                    use_container_width=True,
                )
            with bar_c:
                st.plotly_chart(
                    formulation_bar(
                        [component_label(c) for c in comp_ids_disp],
                        fracs_disp,
                    ),
                    use_container_width=True,
                )

    # ── Raw data ─────────────────────────────────────────────────────────
    with tab_raw:
        if not results_df.empty:
            st.subheader("Compressibility Profile DataFrame")
            st.dataframe(results_df, use_container_width=True)
            st.download_button(
                "⬇ Download CSV",
                data=results_df.to_csv(index=False).encode(),
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
