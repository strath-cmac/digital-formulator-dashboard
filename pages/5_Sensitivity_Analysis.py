"""
Sensitivity Analysis Page

Quantify how model outputs respond to systematic changes in a single
formulation parameter while holding all others fixed.

Two sweep modes
---------------
Vary Fraction
    Sweep the weight fraction of one chosen excipient across a range.
    All other components are rescaled proportionally so fractions always
    sum to 1.

Vary Compaction Pressure
    Sweep CP from a minimum to a maximum value with the formulation fixed.
    Unlike the Multiple Run page (which uses empirical Kawakita/Duckworth
    fits), this mode calls the ML model directly at each CP point and
    therefore also reports granular properties (FFC, density, etc.).

Output tabs
-----------
💧 Flowability  — FFC, Carr's Index, Hausner Ratio, EAOIF
💊 Tablet       — porosity and tensile strength (with ±std bands)
⚖️  Density      — true, bulk, and tapped density
📋 Table        — raw numeric data table + CSV download
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from utils.api_client import (
    get_options,
    single_run,
    component_label,
    component_short_name,
)
from utils.plotting import (
    multi_line_figure,
    sensitivity_band_figure,
    formulation_pie,
)

# Colour constants (mirrored from plotting module)
_BLUE   = "#3b82f6"
_ORANGE = "#f97316"
_GREEN  = "#22c55e"
_PURPLE = "#a855f7"
_TEAL   = "#14b8a6"
_YELLOW = "#eab308"

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sensitivity Analysis | Digital Formulator",
    page_icon="📐",
    layout="wide",
)

st.title("📐 Sensitivity Analysis")
st.markdown(
    "Investigate how model outputs respond when a single parameter "
    "is swept over a range while all other inputs remain fixed.  "
    "Useful for understanding model sensitivity and design-space boundaries."
)
st.divider()

# ── API options ───────────────────────────────────────────────────────────
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
    st.header("📐 Analysis Setup")

    mode: str = st.radio(
        "Sensitivity Mode",
        options=["Vary Fraction", "Vary Compaction Pressure"],
        index=0,
        help=(
            "**Vary Fraction** — sweep the weight fraction of one chosen "
            "excipient; all others are rescaled proportionally.  \n\n"
            "**Vary Compaction Pressure** — sweep CP across a range with "
            "a fixed formulation; calls the ML model directly at each point."
        ),
    )

    st.divider()
    st.subheader("Base Formulation")

    _DEFAULTS = ["mc5", "la9", "cc1", "ms1"]
    safe_defs  = [d for d in _DEFAULTS if d in all_excipients]

    selected: list[str] = st.multiselect(
        "Components",
        options=all_excipients,
        default=safe_defs if safe_defs else all_excipients[:3],
        format_func=component_label,
        key="sa_sel",
    )

    fracs: dict[str, float] = {}
    if selected:
        eq_frac = round(1.0 / len(selected), 4)
        for comp in selected:
            fracs[comp] = st.number_input(
                component_label(comp),
                min_value=0.001,
                max_value=1.0,
                value=eq_frac,
                step=0.005,
                format="%.4f",
                key=f"sa_frac_{comp}",
            )
        total_f = sum(fracs.values())
        col = "green" if abs(total_f - 1.0) < 0.005 else "orange"
        st.markdown(
            f"Sum: :{col}[{total_f:.4f}]"
            + (" ✓" if col == "green" else " → will be normalised")
        )

    st.divider()

    # ── Mode-specific controls ────────────────────────────────────────
    x_label  = ""
    x_range: list[float] = []
    vary_comp: str | None = None
    cp_fixed: float = 200.0

    if mode == "Vary Fraction" and selected:
        st.subheader("Fraction Sweep")
        vary_comp = st.selectbox(
            "Component to vary",
            options=selected,
            format_func=component_label,
            key="sa_vary_comp",
        )
        frac_min = st.slider("Min fraction", 0.01, 0.80, 0.05, 0.01, key="sa_fmin")
        frac_max = st.slider(
            "Max fraction",
            min_value=float(round(frac_min + 0.05, 2)),
            max_value=0.95,
            value=min(0.60, max(float(round(frac_min + 0.10, 2)), 0.50)),
            step=0.01,
            key="sa_fmax",
        )
        n_pts    = st.slider("Number of evaluation points", 5, 25, 12, key="sa_npts")
        cp_fixed = st.slider("Fixed CP (MPa)", 50.0, 450.0, 200.0, 5.0, key="sa_cp_fixed")
        x_label  = f"{component_label(vary_comp)} — fraction"
        x_range  = np.linspace(frac_min, frac_max, n_pts).tolist()

    elif mode == "Vary Compaction Pressure" and selected:
        st.subheader("CP Sweep")
        cp_min = st.slider("Min CP (MPa)", 30.0, 300.0, 70.0,  5.0, key="sa_cpmin")
        cp_max = st.slider("Max CP (MPa)", float(round(cp_min + 20.0, 0)), 450.0, 300.0, 5.0, key="sa_cpmax")
        n_pts  = st.slider("Number of evaluation points", 5, 25, 12, key="sa_npts_cp")
        x_label = "Compaction Pressure (MPa)"
        x_range = np.linspace(cp_min, cp_max, n_pts).tolist()

    st.divider()
    can_run = len(selected) >= 1 and len(x_range) >= 2
    run_btn = st.button(
        "▶ Run Sensitivity Analysis",
        type="primary",
        use_container_width=True,
        disabled=not can_run,
    )

# ── Guard: not enough inputs ──────────────────────────────────────────────
if not can_run:
    st.info("👈  Select components, configure the sweep range, and click **▶ Run Sensitivity Analysis**.")
    st.stop()

# ── Helper: build a single result row ────────────────────────────────────
def _result_row(res: dict, x_val: float) -> dict:
    bd = res["bulk_density"]
    td = res["tapped_density"]
    return {
        "x":             x_val,
        "true_density":  res["true_density"],
        "bulk_density":  bd,
        "tapped_density": td,
        "carrs_index":   (td - bd) / td * 100 if td else 0.0,
        "hausner_ratio": td / bd if bd else 0.0,
        "ffc":           res["ffc"],
        "eaoif":         res["effective_angle_of_internal_friction"],
        "porosity_mean": res["porosity_mean"],
        "porosity_std":  res["porosity_std"],
        "tensile_mean":  res["tensile_mean"],
        "tensile_std":   res["tensile_std"],
    }


# ── Run analysis ──────────────────────────────────────────────────────────
if run_btn:
    rows_list: list[dict] = []
    errors:    list[str]  = []

    prog = st.progress(0, text="Running analysis…")

    if mode == "Vary Fraction" and vary_comp and len(selected) >= 1:
        # Other components (fixed in relative ratio)
        other_comps = [c for c in selected if c != vary_comp]
        other_base  = sum(fracs.get(c, 0.0) for c in other_comps)

        for k, frac_x in enumerate(x_range):
            new_fracs: dict[str, float] = {vary_comp: frac_x}
            if other_comps:
                if other_base > 0:
                    scale = (1.0 - frac_x) / other_base
                    for c in other_comps:
                        new_fracs[c] = max(fracs.get(c, 0.0) * scale, 1e-6)
                else:
                    eq = (1.0 - frac_x) / len(other_comps)
                    for c in other_comps:
                        new_fracs[c] = eq

            comps_list  = list(new_fracs.keys())
            fracs_list  = list(new_fracs.values())
            frac_total  = sum(fracs_list)
            fracs_list  = [f / frac_total for f in fracs_list]
            titles_list = [component_short_name(c) for c in comps_list]

            try:
                res = single_run(
                    titles=titles_list,
                    components=comps_list,
                    fractions=fracs_list,
                    cp=cp_fixed,
                )
                rows_list.append(_result_row(res, frac_x))
            except Exception as e:
                errors.append(f"frac={frac_x:.3f}: {e}")

            prog.progress((k + 1) / len(x_range))

    elif mode == "Vary Compaction Pressure":
        total_f     = sum(fracs.values())
        comps_list  = list(fracs.keys())
        fracs_list  = [v / total_f for v in fracs.values()]
        titles_list = [component_short_name(c) for c in comps_list]

        for k, cp in enumerate(x_range):
            try:
                res = single_run(
                    titles=titles_list,
                    components=comps_list,
                    fractions=fracs_list,
                    cp=cp,
                )
                rows_list.append(_result_row(res, cp))
            except Exception as e:
                errors.append(f"CP={cp:.0f}: {e}")

            prog.progress((k + 1) / len(x_range))

    prog.empty()

    for err in errors:
        st.warning(f"Point skipped — {err}")

    if rows_list:
        st.session_state["sa_df"]      = pd.DataFrame(rows_list)
        st.session_state["sa_x_label"] = x_label
        st.session_state["sa_mode"]    = mode
        st.session_state["sa_fracs"]   = fracs
        st.session_state["sa_comps"]   = list(fracs.keys())
        st.session_state["sa_titles"]  = [component_short_name(c) for c in fracs]
        if mode == "Vary Fraction":
            st.session_state["sa_cp_fixed"] = cp_fixed
    else:
        st.error("All simulation points failed. Check the API connection.")
        st.stop()

# ── Guard: no results yet ─────────────────────────────────────────────────
df: pd.DataFrame | None = st.session_state.get("sa_df")
if df is None:
    st.info("Configure the sweep in the sidebar and click **▶ Run Sensitivity Analysis**.")
    st.stop()

x_label_disp: str = st.session_state.get("sa_x_label", "Parameter")
sa_mode: str      = st.session_state.get("sa_mode", mode)

# ── Summary banner ────────────────────────────────────────────────────────
n_pts_done = len(df)
x_min_val  = df["x"].min()
x_max_val  = df["x"].max()

if sa_mode == "Vary Fraction":
    saved_comps  = st.session_state.get("sa_comps", [])
    saved_titles = st.session_state.get("sa_titles", [])
    saved_fracs  = st.session_state.get("sa_fracs", {})
    saved_cp     = st.session_state.get("sa_cp_fixed", 200.0)
    vary_idx = None
    if vary_comp and vary_comp in saved_comps:
        vary_idx = saved_comps.index(vary_comp)
    st.success(
        f"**{n_pts_done} points** evaluated · "
        f"fraction of *{x_label_disp.split('—')[0].strip()}* "
        f"swept from **{x_min_val:.3f}** to **{x_max_val:.3f}** · "
        f"fixed CP = **{saved_cp:.0f} MPa**"
    )
else:
    st.success(
        f"**{n_pts_done} points** evaluated · "
        f"CP swept from **{x_min_val:.0f}** to **{x_max_val:.0f}** MPa"
    )

st.divider()

# ── Results tabs ──────────────────────────────────────────────────────────
tab_flow, tab_tablet, tab_density, tab_morph_note, tab_raw = st.tabs(
    ["💧 Flowability", "💊 Tablet", "⚖️ Density", "ℹ️ Morphology Note", "📋 Table"]
)

# ── Tab: Flowability ──────────────────────────────────────────────────────
with tab_flow:
    st.subheader("Flowability Properties vs Parameter")
    st.plotly_chart(
        multi_line_figure(
            df, "x",
            [
                ("ffc",          "FFC (flow function coeff.)",  _BLUE),
                ("carrs_index",  "Carr's Index (%)",            _ORANGE),
                ("hausner_ratio","Hausner Ratio",                _GREEN),
                ("eaoif",        "EAOIF (°)",                   _PURPLE),
            ],
            x_label_disp,
            "Flowability Response",
            "Value",
        ),
        use_container_width=True,
    )

    with st.expander("ℹ FFC Classification Guide"):
        st.markdown(
            """
| FFC | Class |
|-----|-------|
| > 10 | Free-flowing |
| 4 – 10 | Easy-flowing |
| 2 – 4 | Cohesive |
| < 2 | Very cohesive |
"""
        )

# ── Tab: Tablet ───────────────────────────────────────────────────────────
with tab_tablet:
    st.subheader("Tablet Properties vs Parameter")

    col_por, col_ten = st.columns(2)

    with col_por:
        st.plotly_chart(
            sensitivity_band_figure(
                df, "x", "porosity_mean", "porosity_std",
                x_label_disp, "Porosity (–)",
                "Porosity (mean ± std)",
                color=_BLUE,
            ),
            use_container_width=True,
        )

    with col_ten:
        st.plotly_chart(
            sensitivity_band_figure(
                df, "x", "tensile_mean", "tensile_std",
                x_label_disp, "Tensile Strength (MPa)",
                "Tensile Strength (mean ± std)",
                color=_ORANGE,
            ),
            use_container_width=True,
        )

    st.caption(
        "Shaded band = mean ± 1 std.  "
        "Porosity decreases with increasing compaction pressure; "
        "tensile strength typically peaks at intermediate porosity (Duckworth relationship)."
    )

# ── Tab: Density ──────────────────────────────────────────────────────────
with tab_density:
    st.subheader("Blend Density vs Parameter")
    st.plotly_chart(
        multi_line_figure(
            df, "x",
            [
                ("true_density",   "True Density (g/cm³)",   _BLUE),
                ("bulk_density",   "Bulk Density (g/cm³)",   _ORANGE),
                ("tapped_density", "Tapped Density (g/cm³)", _GREEN),
            ],
            x_label_disp,
            "Density Response",
            "Density (g/cm³)",
        ),
        use_container_width=True,
    )
    st.caption(
        "True density reflects composition (mixture rule); bulk and tapped density "
        "are sensitive to particle packing and shape."
    )

# ── Tab: Morphology note ──────────────────────────────────────────────────
with tab_morph_note:
    st.info(
        "Particle size and aspect-ratio distributions are properties of the **blend "
        "morphology** and do not change with compaction pressure.  "
        "For morphology visualisation at a fixed formulation, use the **Single Run** page."
    )
    if sa_mode == "Vary Fraction":
        saved_comps2  = st.session_state.get("sa_comps", [])
        saved_titles2 = st.session_state.get("sa_titles", [])
        saved_fracs2  = st.session_state.get("sa_fracs", {})
        if saved_comps2 and saved_titles2:
            total_f2    = sum(saved_fracs2.values())
            base_fracs2 = [v / total_f2 for v in saved_fracs2.values()]
            st.subheader("Base Formulation Composition")
            st.plotly_chart(
                formulation_pie(saved_titles2, base_fracs2),
                use_container_width=True,
            )

# ── Tab: Raw table ────────────────────────────────────────────────────────
with tab_raw:
    st.subheader("Raw Sensitivity Data")

    display_cols = {
        "x":             x_label_disp,
        "true_density":  "True Density (g/cm³)",
        "bulk_density":  "Bulk Density (g/cm³)",
        "tapped_density":"Tapped Density (g/cm³)",
        "carrs_index":   "Carr's Index (%)",
        "hausner_ratio": "Hausner Ratio",
        "ffc":           "FFC",
        "eaoif":         "EAOIF (°)",
        "porosity_mean": "Porosity Mean",
        "porosity_std":  "Porosity Std",
        "tensile_mean":  "Tensile Mean (MPa)",
        "tensile_std":   "Tensile Std (MPa)",
    }
    df_display = df.rename(columns=display_cols)

    st.dataframe(
        df_display.style.format("{:.4f}"),
        use_container_width=True,
        hide_index=True,
    )

    csv_data = df_display.to_csv(index=False)
    st.download_button(
        "⬇ Download CSV",
        data=csv_data,
        file_name="sensitivity_analysis.csv",
        mime="text/csv",
    )
