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


def render_page_header(title: str, subtitle: str, badge: Optional[str] = None) -> None:
    badge_html = f"<span class='page-badge'>{badge}</span>" if badge else ""
    st.markdown(
        f"""
<div class='page-shell'>
  <div class='page-header'>
    <div>
      <div class='page-kicker'>Digital Formulator Dashboard</div>
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