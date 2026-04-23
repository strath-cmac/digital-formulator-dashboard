"""
Reusable Plotly figure factories for the Digital Formulator dashboard.

All figures share a consistent dark theme (plotly_dark) with transparent
backgrounds so they render correctly on the Streamlit dark canvas.
"""

from __future__ import annotations

from typing import List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── Colour palette ──────────────────────────────────────────────────────
_BLUE   = "#3b82f6"
_ORANGE = "#f97316"
_GREEN  = "#22c55e"
_PURPLE = "#a855f7"
_TEAL   = "#14b8a6"
_YELLOW = "#eab308"
_PINK   = "#ec4899"

_PALETTE = [_BLUE, _ORANGE, _GREEN, _PURPLE, _TEAL, _YELLOW, _PINK,
            "#6366f1", "#0ea5e9", "#84cc16"]

# Shared layout overrides applied to every figure
_BASE_LAYOUT: dict = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15,23,42,0.6)",
    font=dict(family="sans-serif", size=13),
    margin=dict(l=55, r=20, t=48, b=48),
)


# ── Morphology ──────────────────────────────────────────────────────────

def psd_figure(ce_diameter: List[float], particle_size_dist: List[float]) -> go.Figure:
    """Particle size distribution (area-fill line chart)."""
    fig = go.Figure(
        go.Scatter(
            x=ce_diameter,
            y=particle_size_dist,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.2)",
            line=dict(color=_BLUE, width=2),
            name="PSD",
        )
    )
    fig.update_layout(
        title="Particle Size Distribution",
        xaxis_title="CE Diameter (µm)",
        yaxis_title="Frequency",
        height=320,
        **_BASE_LAYOUT,
    )
    return fig


def ar_figure(ar: List[float], ar_dist: List[float]) -> go.Figure:
    """Aspect ratio distribution (area-fill line chart)."""
    fig = go.Figure(
        go.Scatter(
            x=ar,
            y=ar_dist,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(168,85,247,0.2)",
            line=dict(color=_PURPLE, width=2),
            name="Aspect Ratio",
        )
    )
    fig.update_layout(
        title="Aspect Ratio Distribution",
        xaxis_title="Aspect Ratio",
        yaxis_title="Frequency",
        height=320,
        **_BASE_LAYOUT,
    )
    return fig


def pca_bar(pcs: List[float], title: str) -> go.Figure:
    """Bar chart of principal component scores."""
    labels = [f"PC{i + 1}" for i in range(len(pcs))]
    colours = [_BLUE if v >= 0 else _ORANGE for v in pcs]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=pcs,
            marker_color=colours,
            text=[f"{v:.3f}" for v in pcs],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Component",
        yaxis_title="Score",
        height=280,
        showlegend=False,
        **_BASE_LAYOUT,
    )
    return fig


# ── Compaction profiles ─────────────────────────────────────────────────

# Column names produced by single_run_emp_parameters
_CP_COL     = "Compression Pressure (MPa)"
_POR_MEAN   = "Porosity Mean (-)"
_POR_LB     = "Porosity LB (-)"
_POR_UB     = "Porosity UB (-)"
_TEN_MEAN   = "Tensile Strength Mean (MPa)"
_TEN_LB     = "Tensile Strength LB (MPa)"
_TEN_UB     = "Tensile Strength UB (MPa)"


def compressibility_figure(df: pd.DataFrame) -> go.Figure:
    """Porosity vs. compaction pressure with 95 % confidence band."""
    fig = go.Figure()

    if _CP_COL not in df.columns or _POR_MEAN not in df.columns:
        fig.update_layout(
            title="Compressibility Profile (no data)",
            height=380,
            **_BASE_LAYOUT,
        )
        return fig

    x = df[_CP_COL].tolist()

    if _POR_LB in df.columns and _POR_UB in df.columns:
        x_band = x + x[::-1]
        y_band = df[_POR_UB].tolist() + df[_POR_LB].tolist()[::-1]
        fig.add_trace(
            go.Scatter(
                x=x_band,
                y=y_band,
                fill="toself",
                fillcolor="rgba(59,130,246,0.15)",
                line=dict(color="rgba(0,0,0,0)"),
                name="95 % CI",
                hoverinfo="skip",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df[_POR_MEAN].tolist(),
            mode="lines+markers",
            line=dict(color=_BLUE, width=2.5),
            marker=dict(size=7),
            name="Porosity (mean)",
        )
    )

    fig.update_layout(
        title="Compressibility Profile — Kawakita Model",
        xaxis_title="Compression Pressure (MPa)",
        yaxis_title="Porosity (–)",
        height=380,
        **_BASE_LAYOUT,
    )
    return fig


def tensile_figure(df: pd.DataFrame) -> go.Figure:
    """Tensile strength vs. compaction pressure with 95 % confidence band."""
    fig = go.Figure()

    if _CP_COL not in df.columns or _TEN_MEAN not in df.columns:
        fig.update_layout(
            title="Tensile Strength Profile (no data)",
            height=380,
            **_BASE_LAYOUT,
        )
        return fig

    x = df[_CP_COL].tolist()

    if _TEN_LB in df.columns and _TEN_UB in df.columns:
        x_band = x + x[::-1]
        y_band = df[_TEN_UB].tolist() + df[_TEN_LB].tolist()[::-1]
        fig.add_trace(
            go.Scatter(
                x=x_band,
                y=y_band,
                fill="toself",
                fillcolor="rgba(249,115,22,0.15)",
                line=dict(color="rgba(0,0,0,0)"),
                name="95 % CI",
                hoverinfo="skip",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df[_TEN_MEAN].tolist(),
            mode="lines+markers",
            line=dict(color=_ORANGE, width=2.5),
            marker=dict(size=7),
            name="Tensile (mean)",
        )
    )

    fig.update_layout(
        title="Tensile Strength Profile — Duckworth Model",
        xaxis_title="Compression Pressure (MPa)",
        yaxis_title="Tensile Strength (MPa)",
        height=380,
        **_BASE_LAYOUT,
    )
    return fig


# ── Formulation composition ─────────────────────────────────────────────

def formulation_pie(titles: List[str], fractions: List[float]) -> go.Figure:
    """Donut chart of formulation composition."""
    fig = px.pie(
        names=titles,
        values=fractions,
        color_discrete_sequence=_PALETTE,
        hole=0.38,
    )
    fig.update_traces(
        textinfo="label+percent",
        hovertemplate="%{label}: %{value:.4f} (%{percent})<extra></extra>",
    )
    fig.update_layout(
        title="Formulation Composition",
        height=420,
        legend=dict(orientation="v", x=1.02, y=0.5),
        **_BASE_LAYOUT,
    )
    return fig


def formulation_bar(titles: List[str], fractions: List[float]) -> go.Figure:
    """Horizontal bar chart of formulation fractions."""
    pairs = sorted(zip(fractions, titles), reverse=True)
    sorted_fracs, sorted_titles = zip(*pairs) if pairs else ([], [])
    fig = go.Figure(
        go.Bar(
            x=list(sorted_fracs),
            y=list(sorted_titles),
            orientation="h",
            marker_color=_PALETTE[: len(sorted_titles)],
            text=[f"{f:.4f}" for f in sorted_fracs],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Component Fractions",
        xaxis_title="Fraction (w/w)",
        height=max(250, 60 * len(titles)),
        **_BASE_LAYOUT,
    )
    return fig
