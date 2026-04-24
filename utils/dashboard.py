from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from utils.api_client import (
    component_label,
    component_short_name,
    get_api_contract,
    get_component_choices,
    get_disintegrant_choices,
    get_filler_choices,
    get_lubricant_choices,
    get_options,
    health_check,
    is_api,
)


@dataclass
class FormulationPayload:
    frame: pd.DataFrame
    components: List[str]
    titles: List[str]
    fractions: List[float]
    total_fraction: float


def render_top_nav(pages: Optional[Dict[str, Any]] = None) -> None:
    """Render a horizontal top navigation bar using Streamlit page_link elements.

    Pass the ``pages`` dict returned by :func:`make_nav_pages` so that
    ``st.page_link`` receives ``st.Page`` objects (required when the home
    page is backed by a callable rather than a file path).
    """
    p = pages or {}
    c0, c1, c2, c3, c4, c5, c6 = st.columns([2.2, 0.9, 0.9, 1.0, 1.5, 1.3, 1.2])
    with c0:
        st.markdown("<div class='topnav-brand'>🧬 Digital Formulator</div>", unsafe_allow_html=True)
    with c1:
        st.page_link(p.get("home", "app.py"), label="Home", use_container_width=True)
    with c2:
        st.page_link(p.get("single_run", "pages/1_Single_Run.py"), label="Single Run", use_container_width=True)
    with c3:
        st.page_link(p.get("multiple_run", "pages/2_Multiple_Run.py"), label="Multi-Run", use_container_width=True)
    with c4:
        st.page_link(p.get("digital_formulator", "pages/3_Digital_Formulator.py"), label="Digital Formulator", use_container_width=True)
    with c5:
        st.page_link(p.get("comparison", "pages/4_Formulation_Comparison.py"), label="Comparison", use_container_width=True)
    with c6:
        st.page_link(p.get("sensitivity", "pages/5_Sensitivity_Analysis.py"), label="Sensitivity", use_container_width=True)
    st.markdown("<div class='topnav-divider'></div>", unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str, badge: Optional[str] = None) -> None:
    badge_html = f"<span class='page-badge'>{badge}</span>" if badge else ""
    st.markdown(
        f"""
<div class='page-shell'>
  <div class='page-header'>
    <div>
      <div class='page-kicker'>DM² · CMAC · University of Strathclyde</div>
      <div class='ph-title'>{title}</div>
      <div class='ph-sub'>{subtitle}</div>
    </div>
    <div>{badge_html}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_empty_state(icon: str, title: str, caption: str) -> None:
    st.markdown(
        f"""
<div class='empty-state'>
  <div class='empty-icon'>{icon}</div>
  <div class='empty-title'>{title}</div>
  <div class='empty-copy'>{caption}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def refresh_api_state(force_refresh: bool = False) -> Dict[str, Any]:
    if force_refresh:
        for key in ("api_ok", "api_msg", "api_options", "api_contract"):
            st.session_state.pop(key, None)

    if "api_ok" not in st.session_state or "api_options" not in st.session_state:
        ok, msg = health_check(force_refresh=force_refresh)
        st.session_state["api_ok"] = ok
        st.session_state["api_msg"] = msg
        st.session_state["api_contract"] = get_api_contract(force_refresh=force_refresh) if ok else {}
        st.session_state["api_options"] = get_options(force_refresh=force_refresh) if ok else {}
    elif st.session_state.get("api_ok", False) and not get_component_choices(st.session_state.get("api_options", {})):
        st.session_state["api_options"] = get_options(force_refresh=True)

    return {
        "ok": st.session_state.get("api_ok", False),
        "msg": st.session_state.get("api_msg", "Unavailable"),
        "contract": st.session_state.get("api_contract", {}),
        "options": st.session_state.get("api_options", {}),
    }


def get_component_catalog(options: Dict[str, Any]) -> pd.DataFrame:
    defaults = options.get("current_defaults", {})
    default_excipient_options = set(defaults.get("excipient_options", []))
    disintegrant_id = defaults.get("disintegrant_id")
    lubricant_id = defaults.get("lubricant_id")

    rows: List[Dict[str, Any]] = []
    for component_id in get_component_choices(options):
        role = "Material"
        if is_api(component_id, options):
            role = "API"
        elif component_id == disintegrant_id:
            role = "Default disintegrant"
        elif component_id == lubricant_id:
            role = "Default lubricant"
        elif component_id in default_excipient_options:
            role = "Candidate filler"

        rows.append(
            {
                "ID": component_id,
                "Label": component_label(component_id, options),
                "Role": role,
            }
        )

    return pd.DataFrame(rows)


def format_component_option(component_id: str, options: Dict[str, Any]) -> str:
    label = component_label(component_id, options)
    if label == component_id:
        return component_id
    return f"{component_id} - {label}"


def component_select_maps(options: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    components = get_component_choices(options)
    labels = [format_component_option(component_id, options) for component_id in components]
    return labels, {label: component_id for label, component_id in zip(labels, components)}


def build_default_formulation(options: Dict[str, Any], include_api: bool = True) -> pd.DataFrame:
    components = get_component_choices(options)
    defaults = options.get("current_defaults", {})
    selected: List[Tuple[str, float]] = []

    disintegrant_id = defaults.get("disintegrant_id")
    disintegrant_fraction = float(defaults.get("disintegrant_fraction", 0.0) or 0.0)
    lubricant_id = defaults.get("lubricant_id")
    lubricant_fraction = float(defaults.get("lubricant_fraction", 0.0) or 0.0)

    api_candidates = options.get("available_apis", [])
    if include_api and api_candidates:
        selected.append((api_candidates[0], 0.20))

    if disintegrant_id in components and disintegrant_fraction > 0:
        selected.append((disintegrant_id, disintegrant_fraction))
    if lubricant_id in components and lubricant_fraction > 0:
        selected.append((lubricant_id, lubricant_fraction))

    chosen_ids = {component_id for component_id, _ in selected}
    filler_candidates = [
        component_id
        for component_id in defaults.get("excipient_options", [])
        if component_id in components and component_id not in chosen_ids
    ]
    if not filler_candidates:
        filler_candidates = [component_id for component_id in components if component_id not in chosen_ids]

    filler_slots = filler_candidates[:2]
    if not filler_slots and components:
        filler_slots = components[: min(2, len(components))]

    used_fraction = sum(fraction for _, fraction in selected)
    remaining_fraction = max(1.0 - used_fraction, 0.0)
    filler_fraction = remaining_fraction / max(len(filler_slots), 1)
    for component_id in filler_slots:
        selected.append((component_id, filler_fraction))

    if not selected and components:
        equal_fraction = 1.0 / min(4, len(components))
        selected = [(component_id, equal_fraction) for component_id in components[: min(4, len(components))]]

    return pd.DataFrame(
        {
            "Component": [format_component_option(component_id, options) for component_id, _ in selected],
            "Fraction": [fraction for _, fraction in selected],
        }
    )


def normalise_formulation_frame(frame: pd.DataFrame, label_to_id: Dict[str, str]) -> FormulationPayload:
    valid = frame.dropna(subset=["Component", "Fraction"]).copy()
    valid["Fraction"] = pd.to_numeric(valid["Fraction"], errors="coerce")
    valid = valid[valid["Fraction"] > 0]

    if valid.empty:
        raise ValueError("Add at least one component with a positive fraction.")

    components = [label_to_id[label] for label in valid["Component"].tolist() if label in label_to_id]
    fractions = [float(value) for value in valid["Fraction"].tolist()]
    total = sum(fractions)
    if total <= 0:
        raise ValueError("Total fraction must be greater than zero.")

    normalised = [value / total for value in fractions]
    payload_frame = pd.DataFrame(
        {
            "component_id": components,
            "fraction": normalised,
        }
    )
    return FormulationPayload(
        frame=payload_frame,
        components=components,
        titles=[component_short_name(component_id) for component_id in components],
        fractions=normalised,
        total_fraction=total,
    )


def summarise_formulation(payload: FormulationPayload, options: Dict[str, Any]) -> str:
    return " | ".join(
        f"{component_label(component_id, options)} ({fraction:.3f})"
        for component_id, fraction in zip(payload.components, payload.fractions)
    )


def derived_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    bulk_density = float(result.get("bulk_density", 0.0) or 0.0)
    tapped_density = float(result.get("tapped_density", 0.0) or 0.0)
    ffc_value = float(result.get("ffc", 0.0) or 0.0)
    tensile_mean = float(result.get("tensile_mean", 0.0) or 0.0)
    tensile_std = float(result.get("tensile_std", 0.0) or 0.0)
    porosity_mean = float(result.get("porosity_mean", 0.0) or 0.0)
    porosity_std = float(result.get("porosity_std", 0.0) or 0.0)

    if ffc_value > 10:
        flow_class = "Free-flowing"
    elif ffc_value > 4:
        flow_class = "Easy-flowing"
    elif ffc_value > 2:
        flow_class = "Cohesive"
    else:
        flow_class = "Very cohesive"

    return {
        "carrs_index": ((tapped_density - bulk_density) / tapped_density * 100.0) if tapped_density else 0.0,
        "hausner_ratio": (tapped_density / bulk_density) if bulk_density else 0.0,
        "flow_class": flow_class,
        "tensile_lower": tensile_mean - tensile_std,
        "tensile_upper": tensile_mean + tensile_std,
        "porosity_lower": porosity_mean - porosity_std,
        "porosity_upper": porosity_mean + porosity_std,
    }


def objective_mode(selected_objectives: List[str]) -> str:
    return "Single-objective GA" if len(selected_objectives) == 1 else "Multi-objective NSGA-II"


def render_smart_formulation_editor(
    options: Dict[str, Any],
    key_prefix: str,
    show_reset: bool = True,
) -> Tuple[pd.DataFrame, bool]:
    """
    Render a role-aware formulation builder with separate sections for API,
    disintegrant (CCS), lubricant (MgSt), and filler excipients.

    Returns (DataFrame with Component/Fraction columns, is_valid).
    The Component column contains display labels compatible with normalise_formulation_frame().
    """
    defaults = options.get("current_defaults", {})
    api_ids = options.get("available_apis", []) or get_component_choices(options)
    disint_ids = get_disintegrant_choices(options)
    lubricant_ids = get_lubricant_choices(options)
    filler_ids = get_filler_choices(options)

    _, label_to_id = component_select_maps(options)
    id_to_label: Dict[str, str] = {v: k for k, v in label_to_id.items()}

    def _fmt(cid: str) -> str:
        return format_component_option(cid, options)

    # Reset helper
    def _clear_state() -> None:
        for k in list(st.session_state.keys()):
            if k.startswith(f"_sfe_{key_prefix}_"):
                del st.session_state[k]

    if show_reset:
        hcol1, hcol2 = st.columns([4, 1])
        with hcol1:
            st.markdown("<p class='form-section-title'>Formulation Builder</p>", unsafe_allow_html=True)
        with hcol2:
            if st.button("↺ Reset", key=f"_sfe_{key_prefix}_reset_btn", use_container_width=True):
                _clear_state()
                st.rerun()

    # ── 1. API ─────────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='role-pill role-api'>💊 API — Active Pharmaceutical Ingredient</div>",
            unsafe_allow_html=True,
        )
        a1, a2 = st.columns([3, 1])
        api_id = a1.selectbox(
            "API",
            options=api_ids,
            format_func=_fmt,
            key=f"_sfe_{key_prefix}_api",
            label_visibility="collapsed",
        )
        api_frac = a2.number_input(
            "API fraction",
            min_value=0.01,
            max_value=0.80,
            value=0.20,
            step=0.01,
            key=f"_sfe_{key_prefix}_api_f",
            format="%.3f",
            label_visibility="collapsed",
        )

    # ── 2. Disintegrant + Lubricant ────────────────────────────────────────────
    with st.container(border=True):
        d_col, l_col = st.columns(2, gap="medium")

        with d_col:
            st.markdown(
                "<div class='role-pill role-disint'>🧪 Disintegrant — CCS</div>",
                unsafe_allow_html=True,
            )
            default_disint = defaults.get("disintegrant_id")
            disint_opts = disint_ids if disint_ids else list(label_to_id.values())
            disint_default_idx = 0
            if default_disint and default_disint in disint_opts:
                disint_default_idx = disint_opts.index(default_disint)
            disint_id = st.selectbox(
                "Disintegrant",
                options=disint_opts,
                format_func=_fmt,
                index=disint_default_idx,
                key=f"_sfe_{key_prefix}_di",
                label_visibility="collapsed",
            )
            disint_frac = st.number_input(
                "Disint fraction",
                min_value=0.01,
                max_value=0.20,
                value=float(defaults.get("disintegrant_fraction", 0.08)),
                step=0.005,
                key=f"_sfe_{key_prefix}_di_f",
                format="%.3f",
                label_visibility="collapsed",
            )

        with l_col:
            st.markdown(
                "<div class='role-pill role-lubricant'>⚙️ Lubricant — MgSt</div>",
                unsafe_allow_html=True,
            )
            default_lubricant = defaults.get("lubricant_id")
            lubricant_opts = lubricant_ids if lubricant_ids else list(label_to_id.values())
            lubricant_default_idx = 0
            if default_lubricant and default_lubricant in lubricant_opts:
                lubricant_default_idx = lubricant_opts.index(default_lubricant)
            lubricant_id = st.selectbox(
                "Lubricant",
                options=lubricant_opts,
                format_func=_fmt,
                index=lubricant_default_idx,
                key=f"_sfe_{key_prefix}_lu",
                label_visibility="collapsed",
            )
            lubricant_frac = st.number_input(
                "Lubricant fraction",
                min_value=0.001,
                max_value=0.05,
                value=float(defaults.get("lubricant_fraction", 0.01)),
                step=0.001,
                key=f"_sfe_{key_prefix}_lu_f",
                format="%.3f",
                label_visibility="collapsed",
            )

    # ── 3. Fillers ─────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<div class='role-pill role-filler'>📦 Fillers / Bulk Excipients</div>",
            unsafe_allow_html=True,
        )
        filler_pool = filler_ids if filler_ids else [
            cid for cid in list(label_to_id.values())
            if cid not in {api_id, disint_id, lubricant_id}
        ]
        default_fillers = [
            cid for cid in defaults.get("excipient_options", []) if cid in filler_pool
        ] or filler_pool[:2]

        selected_fillers = st.multiselect(
            "Select fillers",
            options=filler_pool,
            default=[f for f in default_fillers if f in filler_pool],
            format_func=_fmt,
            key=f"_sfe_{key_prefix}_fillers",
            label_visibility="collapsed",
        )

        fixed_sum = api_frac + disint_frac + lubricant_frac
        remaining = max(0.0, 1.0 - fixed_sum)
        filler_fracs: Dict[str, float] = {}

        if selected_fillers:
            auto_share = round(remaining / len(selected_fillers), 4)
            pairs = [selected_fillers[i : i + 2] for i in range(0, len(selected_fillers), 2)]
            for pair in pairs:
                pair_cols = st.columns(len(pair), gap="small")
                for ci, fid in enumerate(pair):
                    with pair_cols[ci]:
                        filler_fracs[fid] = st.number_input(
                            _fmt(fid),
                            min_value=0.001,
                            max_value=0.99,
                            value=auto_share,
                            step=0.01,
                            key=f"_sfe_{key_prefix}_ff_{fid}",
                            format="%.3f",
                        )

    # ── Build output DataFrame ─────────────────────────────────────────────────
    cids: List[str] = [api_id]
    fracs: List[float] = [api_frac]
    if disint_id:
        cids.append(disint_id)
        fracs.append(disint_frac)
    if lubricant_id:
        cids.append(lubricant_id)
        fracs.append(lubricant_frac)
    for fid in selected_fillers:
        cids.append(fid)
        fracs.append(filler_fracs.get(fid, 0.0))

    display_labels = [id_to_label.get(cid, _fmt(cid)) for cid in cids]
    df = pd.DataFrame({"Component": display_labels, "Fraction": fracs})

    total = sum(fracs)
    if total > 0:
        if abs(total - 1.0) < 0.025:
            st.success(f"Total fraction = {total:.4f} ✓")
        else:
            st.warning(f"Total fraction = {total:.4f} — will be normalised before submission")

    is_valid = total > 0 and len(cids) >= 2
    return df, is_valid
