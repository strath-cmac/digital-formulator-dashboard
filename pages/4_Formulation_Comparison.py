"""
Formulation Comparison Page

Compare up to 5 formulations side-by-side across all granular and tablet
properties predicted by the Digital Formulator models.

Output tabs
-----------
📊 Properties  — styled numeric comparison table
🕸️ Radar       — normalised spider chart across key properties
🔬 PSD Overlay — overlaid particle size distributions
🔷 AR Overlay  — overlaid aspect ratio distributions
🍩 Compositions — donut charts per formulation
⬇ Download    — combined CSV and JSON export
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.api_client import (
    get_options,
    single_run,
    component_label,
    component_short_name,
    is_api,
)
from utils.plotting import (
    radar_chart,
    overlay_psd_figure,
    overlay_ar_figure,
    formulation_pie,
)


st.markdown("""
<div class='page-header'>
  <div class='ph-title'>\u2697\ufe0f Formulation Comparison</div>
  <div class='ph-sub'>Simulate up to 5 formulations and compare predicted properties via radar charts, PSD/AR overlays, and a numeric table</div>
</div>""", unsafe_allow_html=True)

if "api_options" not in st.session_state:
    try:
        st.session_state["api_options"] = get_options()
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        st.stop()

opts           = st.session_state["api_options"]
all_excipients = opts.get("available_excipients", [])
all_apis       = opts.get("available_apis", [])
all_components = all_apis + all_excipients   # APIs listed first

if not all_components:
    st.error("No components returned by the API. Is the backend running?")
    st.stop()

# ── Default component sets per slot ──────────────────────────────────────
_SLOT_DEFAULTS: list[list[str]] = [
    ["dm1", "mc5", "la9", "cc1", "ms1"],
    ["dm1", "mc6", "la6", "cc1", "ms1"],
    ["dm1", "mc7", "la3", "cc1", "ms1"],
    ["dm1", "mc5", "ma1", "cc1", "ms1"],
    ["dm1", "mc6", "la8", "cc1", "ms1"],
]


def _safe_defaults(comp_list: list[str], slot: int) -> list[str]:
    defs = _SLOT_DEFAULTS[slot % len(_SLOT_DEFAULTS)]
    safe = [d for d in defs if d in comp_list]
    return safe if safe else comp_list[: min(3, len(comp_list))]


# ── Properties shown in the comparison table ──────────────────────────────
_TABLE_PROPS: list[tuple[str, str]] = [
    ("true_density",                         "True Density (g/cm³)"),
    ("bulk_density",                         "Bulk Density (g/cm³)"),
    ("tapped_density",                       "Tapped Density (g/cm³)"),
    ("carrs_index",                          "Carr's Index (%)"),
    ("hausner_ratio",                        "Hausner Ratio"),
    ("ffc",                                  "FFC"),
    ("effective_angle_of_internal_friction", "EAOIF (°)"),
    ("porosity_mean",                        "Porosity Mean"),
    ("porosity_std",                         "Porosity Std"),
    ("tensile_mean",                         "Tensile Strength Mean (MPa)"),
    ("tensile_std",                          "Tensile Strength Std (MPa)"),
]

# Properties used in the radar chart (key, short axis label)
_RADAR_PROPS: list[tuple[str, str]] = [
    ("ffc",                                  "FFC"),
    ("tensile_mean",                         "Tensile\nStrength"),
    ("porosity_mean",                        "Porosity"),
    ("carrs_index",                          "Carr's\nIndex"),
    ("hausner_ratio",                        "Hausner\nRatio"),
    ("effective_angle_of_internal_friction", "EAOIF"),
    ("true_density",                         "True\nDensity"),
]

# ── Configuration ────────────────────────────────────────────────────────
with st.container(border=True):
    st.caption("Comparison Setup")
    hdr_c1, hdr_c2 = st.columns([1, 3])
    n_forms: int = hdr_c1.selectbox(
        "Number of formulations",
        options=[2, 3, 4, 5],
        index=0,
        key="cf_n",
    )
    # Invalidate previous results when the number of slots changes
    if st.session_state.get("_cf_n_prev") != n_forms:
        st.session_state["_cf_n_prev"] = n_forms
        st.session_state.pop("cf_results", None)

    slot_cols = st.columns(n_forms, gap="small")
    configs: list[dict] = []
    for i in range(n_forms):
        lbl = chr(65 + i)  # A, B, C, D, E
        with slot_cols[i]:
            with st.container(border=True):
                st.caption(f"Formulation {lbl}")
                name = st.text_input(
                    "Label", value=f"Formulation {lbl}", key=f"cf_name_{i}",
                    label_visibility="collapsed",
                )
                selected: list[str] = st.multiselect(
                    "Components",
                    options=all_components,
                    default=_safe_defaults(all_components, i),
                    format_func=component_label,
                    key=f"cf_sel_{i}",
                    label_visibility="collapsed",
                    placeholder="Add components…",
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
                            key=f"cf_frac_{i}_{comp}",
                        )
                    total_f = sum(fracs.values())
                    if abs(total_f - 1.0) < 0.005:
                        st.success(f"Sum: {total_f:.4f} ✓", icon="✅")
                    else:
                        st.warning(f"Sum: {total_f:.4f} → normalised", icon="⚠️")
                cp_val: float = st.slider(
                    "CP (MPa)", 50.0, 450.0, 200.0, 5.0,
                    key=f"cf_cp_{i}", format="%.0f MPa",
                )
                configs.append(
                    {"name": name, "comps": list(fracs.keys()), "fracs": fracs, "cp": cp_val}
                )

all_configured = all(len(c["comps"]) >= 1 for c in configs)
run_btn = st.button(
    "▶  Run All Formulations",
    type="primary",
    use_container_width=True,
    disabled=not all_configured,
)

# ── Guard: nothing configured ─────────────────────────────────────────────
if not all_configured:
    with st.container(border=True):
        st.markdown('<div style="text-align:center;padding:2.5rem 0;opacity:0.4"><div style="font-size:3rem">⚗️</div><div style="font-size:1.1rem;margin-top:.5rem">Select at least one component per slot and click <strong>▶ Run All Formulations</strong></div></div>', unsafe_allow_html=True)
    st.stop()

# ── Run simulations ───────────────────────────────────────────────────────
if run_btn:
    results: dict[int, dict] = {}
    prog = st.progress(0, text="Running simulations…")
    errors: list[str] = []

    for i, cfg in enumerate(configs):
        total_frac = sum(cfg["fracs"].values())
        comps      = cfg["comps"]
        nfracs     = [v / total_frac for v in cfg["fracs"].values()]
        titles     = [component_short_name(c) for c in comps]

        try:
            res = single_run(
                titles=titles, components=comps, fractions=nfracs, cp=cfg["cp"]
            )
            bd = res["bulk_density"]
            td = res["tapped_density"]
            res["carrs_index"]   = (td - bd) / td * 100 if td else 0.0
            res["hausner_ratio"] = td / bd if bd else 0.0
            results[i] = {
                "config": cfg,
                "result": res,
                "titles": titles,
                "fracs":  nfracs,
                "comps":  comps,
            }
        except Exception as e:
            errors.append(f"**{cfg['name']}**: {e}")

        prog.progress((i + 1) / len(configs), text=f"Completed {cfg['name']}…")

    prog.empty()
    if errors:
        for err in errors:
            st.error(f"Simulation failed — {err}")
    if results:
        st.session_state["cf_results"] = results
    else:
        st.error("All simulations failed. Check the API connection.")
        st.stop()

# ── Guard: no results yet ─────────────────────────────────────────────────
results: dict = st.session_state.get("cf_results", {})
if not results:
    with st.container(border=True):
        st.markdown('<div style="text-align:center;padding:2.5rem 0;opacity:0.4"><div style="font-size:3rem">📊</div><div style="font-size:1.1rem;margin-top:.5rem">Configure formulations above and click <strong>▶ Run All Formulations</strong></div></div>', unsafe_allow_html=True)
    st.stop()

# ── Build comparison DataFrame ─────────────────────────────────────────────
sorted_ids   = sorted(results.keys())
form_names   = [results[i]["config"]["name"] for i in sorted_ids]

rows: dict[str, dict] = {name: {} for name in form_names}
for i in sorted_ids:
    name = results[i]["config"]["name"]
    res  = results[i]["result"]
    for key, label in _TABLE_PROPS:
        rows[name][label] = res.get(key, float("nan"))

df_compare            = pd.DataFrame(rows).T
df_compare.index.name = "Formulation"

# ── Display tabs ──────────────────────────────────────────────────────────
tab_props, tab_radar, tab_psd, tab_ar, tab_form, tab_dl = st.tabs(
    ["📊 Properties", "🕸️ Radar", "🔬 PSD Overlay", "🔷 AR Overlay",
     "🍩 Compositions", "⬇ Download"]
)

# ── Tab: Properties ───────────────────────────────────────────────────────
with tab_props:
    st.subheader("Side-by-Side Property Table")
    st.dataframe(
        df_compare.style.format("{:.4f}", na_rep="—"),
        use_container_width=True,
        height=min(600, 42 * (len(df_compare) + 2)),
    )
    st.caption("Use the radar chart tab for a holistic cross-property view.")

    st.divider()
    st.subheader("Metric Cards")
    highlight_prop = st.selectbox(
        "Property to highlight",
        [label for _, label in _TABLE_PROPS],
        index=9,  # Tensile Strength Mean by default
    )
    cols = st.columns(len(form_names))
    for j, (i, name) in enumerate(zip(sorted_ids, form_names)):
        val = rows[name].get(highlight_prop, float("nan"))
        cols[j].metric(name, f"{val:.4f}" if val == val else "—")

# ── Tab: Radar ────────────────────────────────────────────────────────────
with tab_radar:
    st.subheader("Normalised Radar / Spider Chart")
    st.markdown(
        "Each axis is **independently normalised** to [0, 1] across the "
        "compared formulations.  A larger filled area indicates *relatively* "
        "higher values on those axes — interpret axis direction using domain knowledge.  \n"
        "*(Axes do not encode desirability — e.g. lower porosity may be preferable.)*"
    )

    radar_keys = [k for k, _ in _RADAR_PROPS]
    radar_lbls = [lbl for _, lbl in _RADAR_PROPS]
    matrix = [
        [results[i]["result"].get(k, 0.0) for k in radar_keys]
        for i in sorted_ids
    ]
    st.plotly_chart(
        radar_chart(form_names, matrix, radar_lbls),
        use_container_width=True,
    )

    # Mini reference table below the chart
    with st.expander("📖 Axis reference values (raw)"):
        ref_rows = {
            lbl: {name: results[i]["result"].get(key, float("nan"))
                  for i, name in zip(sorted_ids, form_names)}
            for key, lbl in _RADAR_PROPS
        }
        st.dataframe(
            pd.DataFrame(ref_rows).T.style.format("{:.4f}", na_rep="—"),
            use_container_width=True,
        )

# ── Tab: PSD Overlay ──────────────────────────────────────────────────────
with tab_psd:
    st.subheader("Particle Size Distribution Comparison")
    psd_datasets = [
        (
            results[i]["config"]["name"],
            results[i]["result"]["ce_diameter"],
            results[i]["result"]["particle_size_dist"],
        )
        for i in sorted_ids
    ]
    st.plotly_chart(overlay_psd_figure(psd_datasets), use_container_width=True)
    st.caption(
        "Curves show the predicted blend PSD computed by the mixture model from "
        "raw material PSD data.  Differences reflect how excipient choice and "
        "relative fractions reshape the blend particle size distribution."
    )

# ── Tab: AR Overlay ───────────────────────────────────────────────────────
with tab_ar:
    st.subheader("Aspect Ratio Distribution Comparison")
    ar_datasets = [
        (
            results[i]["config"]["name"],
            results[i]["result"]["Aspect Ratio"],
            results[i]["result"]["aspect_ratio_dist"],
        )
        for i in sorted_ids
    ]
    st.plotly_chart(overlay_ar_figure(ar_datasets), use_container_width=True)
    st.caption(
        "Aspect ratio reflects particle shape.  Values close to 1 = near-spherical; "
        "higher values indicate more elongated or irregular particles."
    )

# ── Tab: Compositions ─────────────────────────────────────────────────────
with tab_form:
    st.subheader("Formulation Compositions")
    n_cols = min(len(sorted_ids), 3)
    cols   = st.columns(n_cols)
    for j, i in enumerate(sorted_ids):
        with cols[j % n_cols]:
            cfg = results[i]["config"]
            cp_used = cfg["cp"]
            st.caption(f"**{cfg['name']}**  ·  CP = {cp_used:.0f} MPa")
            st.plotly_chart(
                formulation_pie(
                    [component_label(c) for c in results[i]["comps"]],
                    results[i]["fracs"],
                ),
                use_container_width=True,
            )

# ── Tab: Download ─────────────────────────────────────────────────────────
with tab_dl:
    st.subheader("Export Comparison Data")

    csv_data = df_compare.reset_index().to_csv(index=False)
    st.download_button(
        "⬇ Download CSV (property table)",
        data=csv_data,
        file_name="formulation_comparison.csv",
        mime="text/csv",
    )

    json_data = json.dumps(
        {
            results[i]["config"]["name"]: {
                "config": {
                    "components": results[i]["comps"],
                    "fractions":  results[i]["fracs"],
                    "cp_mpa":     results[i]["config"]["cp"],
                },
                "properties": results[i]["result"],
            }
            for i in sorted_ids
        },
        indent=2,
    )
    st.download_button(
        "⬇ Download JSON (full results)",
        data=json_data,
        file_name="formulation_comparison.json",
        mime="application/json",
    )
