"""Reusable Plotly figure factories for the Digital Formulator dashboard."""

from __future__ import annotations

from typing import List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── Colour palette ──────────────────────────────────────────────────────
_BLUE   = "#0b6e69"
_ORANGE = "#c96b32"
_GREEN  = "#4c7c59"
_PURPLE = "#7b5ea7"
_TEAL   = "#2a9d8f"
_YELLOW = "#c59d2f"
_PINK   = "#b24c63"

_PALETTE = [_BLUE, _ORANGE, _GREEN, _PURPLE, _TEAL, _YELLOW, _PINK,
            "#4f6dcf", "#2f97c1", "#6b9c3a"]

# Shared layout overrides applied to every figure
_BASE_LAYOUT: dict = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,250,241,0.78)",
    font=dict(family="IBM Plex Sans, sans-serif", size=13, color="#17313e"),
    margin=dict(l=55, r=20, t=48, b=48),
    title_font=dict(family="Space Grotesk, sans-serif", size=18, color="#17313e"),
    xaxis=dict(gridcolor="rgba(23,49,62,0.08)", zerolinecolor="rgba(23,49,62,0.08)"),
    yaxis=dict(gridcolor="rgba(23,49,62,0.08)", zerolinecolor="rgba(23,49,62,0.08)"),
    legend=dict(bgcolor="rgba(255,255,255,0.55)", bordercolor="rgba(23,49,62,0.08)", borderwidth=1),
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


# ── Multi-formulation comparison ────────────────────────────────────────

# Polar charts use a separate layout (plot_bgcolor has no effect on polar axes)
_POLAR_LAYOUT: dict = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="IBM Plex Sans, sans-serif", size=13, color="#17313e"),
    title_font=dict(family="Space Grotesk, sans-serif", size=18, color="#17313e"),
    margin=dict(l=60, r=60, t=68, b=60),
)


def _hex_rgba(hex_color: str, alpha: float = 0.15) -> str:
    """Convert a ``#rrggbb`` hex string to ``rgba(r,g,b,alpha)``."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def radar_chart(
    names: List[str],
    metric_matrix: List[List[float]],
    metric_labels: List[str],
) -> go.Figure:
    """
    Normalised radar/spider chart comparing multiple formulations.

    Each metric is linearly rescaled so that the minimum observed value → 0
    and the maximum → 1.  Where all formulations share the same value the
    metric is placed at 0.5.

    Parameters
    ----------
    names         : display name of each formulation
    metric_matrix : shape (n_formulations, n_metrics) – raw un-normalised values
    metric_labels : axis label for each metric (same length as inner lists)
    """
    import numpy as np

    arr = np.array(metric_matrix, dtype=float)
    mn, mx = arr.min(axis=0), arr.max(axis=0)
    rng = mx - mn

    norm = np.where(rng == 0, 0.5, (arr - mn) / rng)  # identical metric → 0.5

    theta = metric_labels + [metric_labels[0]]  # close the polygon

    fig = go.Figure()
    for i, (name, row) in enumerate(zip(names, norm.tolist())):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(
            go.Scatterpolar(
                r=row + [row[0]],
                theta=theta,
                fill="toself",
                fillcolor=_hex_rgba(color, 0.12),
                line=dict(color=color, width=2),
                name=name,
            )
        )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                showticklabels=False,
                gridcolor="rgba(23,49,62,0.10)",
            ),
            angularaxis=dict(direction="clockwise"),
            bgcolor="rgba(255,250,241,0.78)",
        ),
        title="Normalised Property Comparison  (0 = min across formulations, 1 = max)",
        height=520,
        showlegend=True,
        **_POLAR_LAYOUT,
    )
    return fig


def overlay_psd_figure(datasets: List[tuple]) -> go.Figure:
    """
    Overlay multiple PSD curves on one chart.

    Parameters
    ----------
    datasets : list of ``(name, ce_diameters, psd_values)`` tuples
    """
    fig = go.Figure()
    for i, (name, x, y) in enumerate(datasets):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(
            go.Scatter(
                x=x, y=y, mode="lines",
                name=name,
                line=dict(color=color, width=2),
                fill="tozeroy",
                fillcolor=_hex_rgba(color, 0.07),
            )
        )
    fig.update_layout(
        title="Particle Size Distribution Comparison",
        xaxis_title="CE Diameter (µm)",
        yaxis_title="Frequency",
        height=400,
        **_BASE_LAYOUT,
    )
    return fig


def overlay_ar_figure(datasets: List[tuple]) -> go.Figure:
    """
    Overlay multiple aspect-ratio distributions.

    Parameters
    ----------
    datasets : list of ``(name, ar_x, ar_y)`` tuples
    """
    fig = go.Figure()
    for i, (name, x, y) in enumerate(datasets):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(
            go.Scatter(
                x=x, y=y, mode="lines",
                name=name,
                line=dict(color=color, width=2),
                fill="tozeroy",
                fillcolor=_hex_rgba(color, 0.07),
            )
        )
    fig.update_layout(
        title="Aspect Ratio Distribution Comparison",
        xaxis_title="Aspect Ratio",
        yaxis_title="Frequency",
        height=400,
        **_BASE_LAYOUT,
    )
    return fig


def multi_line_figure(
    df: "pd.DataFrame",
    x_col: str,
    series: List[tuple],
    x_label: str,
    title: str,
    y_label: str = "Value",
) -> go.Figure:
    """
    Multi-line response-curve chart for sensitivity / parameter-sweep analysis.

    Parameters
    ----------
    df      : DataFrame containing ``x_col`` and the property columns
    x_col   : column to use as the x axis
    series  : list of ``(col_name, display_label, hex_color)`` tuples
    x_label : x-axis title
    title   : chart title
    y_label : y-axis title
    """
    fig = go.Figure()
    for col, label, color in series:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df[x_col].tolist(),
                    y=df[col].tolist(),
                    mode="lines+markers",
                    name=label,
                    line=dict(color=color, width=2),
                    marker=dict(size=6),
                )
            )
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=400,
        **_BASE_LAYOUT,
    )
    return fig


def sensitivity_band_figure(
    df: "pd.DataFrame",
    x_col: str,
    mean_col: str,
    std_col: str,
    x_label: str,
    y_label: str,
    title: str,
    color: str = _BLUE,
) -> go.Figure:
    """
    Single-property sensitivity line with a ±std confidence band.

    Parameters
    ----------
    df       : DataFrame
    x_col    : x-axis column
    mean_col : mean value column
    std_col  : std-dev column (band = mean ± std)
    """
    fig = go.Figure()
    x = df[x_col].tolist()
    mean = df[mean_col].tolist()
    std  = df[std_col].tolist() if std_col in df.columns else [0.0] * len(mean)

    upper = [m + s for m, s in zip(mean, std)]
    lower = [m - s for m, s in zip(mean, std)]

    # Confidence band
    fig.add_trace(
        go.Scatter(
            x=x + x[::-1],
            y=upper + lower[::-1],
            fill="toself",
            fillcolor=_hex_rgba(color, 0.15),
            line=dict(color="rgba(0,0,0,0)"),
            name="±std",
            hoverinfo="skip",
        )
    )
    # Mean line
    fig.add_trace(
        go.Scatter(
            x=x, y=mean,
            mode="lines+markers",
            name=mean_col,
            line=dict(color=color, width=2.5),
            marker=dict(size=6),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=400,
        **_BASE_LAYOUT,
    )
    return fig
