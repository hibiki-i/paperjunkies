from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
from scipy import stats


def stream_plot(df: pd.DataFrame) -> go.Figure:
    """Stacked area stream/river-style plot.

    Expected columns: period (datetime), term (str), count (int)
    """

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig

    unique_periods = df["period"].nunique(dropna=True)
    if unique_periods <= 1:
        agg = (
            df.groupby("term", as_index=False)["count"]
            .sum()
            .sort_values("count", ascending=False)
        )
        fig = px.bar(
            agg,
            x="term",
            y="count",
            color="term",
            labels={"count": "Term frequency", "term": "Term"},
        )
        fig.update_layout(
            height=320,
            margin=dict(l=20, r=20, t=10, b=20),
            showlegend=False
        )
        return fig

    # This provides a standard stacked area visualization.
    fig = px.area(
        df,
        x="period",
        y="count",
        color="term",
        line_shape="spline",  # Softer curves for "stream" feel
        labels={"count": "Term frequency", "period": "Period", "term": "Term"},
    )
    
    fig.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode="x unified",  # Critical for stacked charts
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)'),
    )

    return fig


def ridgeline_hours(
    df: pd.DataFrame, *, max_groups: int = 12, color_by: str | None = None
) -> go.Figure:
    """Ridgeline-style density plot of read hour by group using gaussian_kde.

    Expected columns:
    - group (str)
    - hour (int)
    - optionally a categorical column named by color_by (e.g. 'scope')
    """

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig

    # Keep it readable by limiting groups (most recent max_groups)
    groups = sorted(df["group"].unique().tolist())[-max_groups:]
    df = df[df["group"].isin(groups)]

    fig = go.Figure()
    
    # Grid for evaluation
    x_grid = np.linspace(0, 24, 200)

    # Vertical spacing between groups
    spacing = 0.5 

    # Color handling
    # If color_by is used, we need consistent colors for each category
    color_map = {}
    if color_by:
        unique_colors = sorted(df[color_by].unique().tolist())
        palette = px.colors.qualitative.Plotly
        for i, c in enumerate(unique_colors):
            color_map[c] = palette[i % len(palette)]

    for g_idx, g in enumerate(groups):
        sub_df = df[df["group"] == g]
        if sub_df.empty:
            continue
            
        offset = g_idx * spacing
        
        # Determine subgroups (traces)
        sub_traces = []
        if color_by:
            for cat in sorted(sub_df[color_by].unique()):
                vals = sub_df[sub_df[color_by] == cat]["hour"].dropna().tolist()
                color = color_map.get(cat, '#636EFA')
                sub_traces.append((vals, f"{g} - {cat}", color, cat))
        else:
            vals = sub_df["hour"].dropna().tolist()
            sub_traces.append((vals, g, None, g))

        for vals, label, color, legend_group in sub_traces:
            if not vals:
                continue
            
            # Compute KDE
            try:
                if len(vals) < 2 or np.std(vals) == 0:
                    # Singular case: create a small Gaussian around the single value(s)
                    mean_val = np.mean(vals)
                    # Gaussian with sigma=1
                    pdf = stats.norm.pdf(x_grid, loc=mean_val, scale=1.0)
                else:
                    kernel = stats.gaussian_kde(vals)
                    # Enforce a smoothing factor if needed, default is mostly fine but can be noisy for few points
                    # kernel.set_bandwidth(bw_method=kernel.factor * 3) # Smoother
                    kernel.set_bandwidth(bw_method='scott') 
                    pdf = kernel(x_grid)
            except Exception:
                 # Fallback
                 continue

            # Scale PDF to fit nicely in the spacing
            # Max height should be around spacing * 0.8 to 1.5
            if np.max(pdf) > 0:
                scale_factor = (spacing * 1.5) / np.max(pdf)
                y_density = pdf * scale_factor
            else:
                y_density = pdf

            # Shift Y
            y_shifted = y_density + offset
            
            # Construct polygon
            x_poly = list(x_grid)
            y_poly = list(y_shifted)
            
            # Close the polygon at the baseline
            x_poly.extend(x_poly[::-1])
            y_poly.extend([offset] * len(x_poly))
            # Truncate to match length (doubled)
            y_poly = y_poly[:len(x_poly)]

            show_legend = False
            if color_by:
                # Show legend only for the first occurrence of this category
                # We need a way to track global state or just check if it's already in fig?
                # Simpler: check if trace with this name exists in fig.data
                existing_names = [t.name for t in fig.data]
                if legend_group not in existing_names:
                     show_legend = True
                     # Use category name for legend loc
                     legend_name = legend_group
            else:
                 legend_name = label
                 # Typically ridgeline doesn't need legend for groups as they are on Y axis
                 show_legend = False

            fig.add_trace(go.Scatter(
                x=x_poly,
                y=y_poly,
                mode='lines',
                line=dict(width=1.5, color=color or '#636EFA'),
                fill='toself',
                name=legend_name if color_by else label, 
                legendgroup=legend_group if color_by else None,
                showlegend=show_legend,
                hovertemplate="<b>%{text}</b><br>Hour: %{x:.1f}<extra></extra>",
                text=[label] * len(x_poly), # Pass label for hover template
            ))

    # Layout updates
    tick_vals = [i * spacing for i in range(len(groups))]
    tick_text = groups
    
    fig.update_layout(
        xaxis=dict(
            title="Hour of day", 
            range=[0, 24],
            tickmode='array',
            tickvals=[0, 6, 12, 18, 24],
            ticktext=["12 AM", "6 AM", "12 PM", "6 PM", "12 AM"],
        ),
        yaxis=dict(
            title=None,
            tickmode='array',
            tickvals=tick_vals,
            ticktext=tick_text,
            showgrid=False,
            zeroline=False
        ),
        height=max(400, len(groups) * 50),
        margin=dict(l=10, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) if color_by else None,
        hovermode="closest"
    )

    return fig
