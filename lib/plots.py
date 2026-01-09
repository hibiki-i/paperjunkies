from __future__ import annotations

import altair as alt
import pandas as pd


def stream_plot(df: pd.DataFrame) -> alt.Chart:
    """Stacked area stream/river-style plot.

    Expected columns: period (datetime), term (str), count (int)
    """

    if df.empty:
        return alt.Chart(pd.DataFrame({"period": [], "term": [], "count": []}))

    unique_periods = df["period"].nunique(dropna=True)
    if unique_periods <= 1:
        agg = (
            df.groupby("term", as_index=False)["count"]
            .sum()
            .sort_values("count", ascending=False)
        )
        return (
            alt.Chart(agg)
            .mark_bar()
            .encode(
                x=alt.X("term:N", title=None, sort="-y"),
                y=alt.Y("count:Q", title="Term frequency"),
                color=alt.Color("term:N", title="Term"),
                tooltip=[alt.Tooltip("term:N"), alt.Tooltip("count:Q")],
            )
            .properties(height=320)
        )

    base = alt.Chart(df).mark_area().encode(
        x=alt.X("period:T", title="Period"),
        y=alt.Y("count:Q", stack="center", title="Term frequency"),
        color=alt.Color("term:N", title="Term"),
        tooltip=[alt.Tooltip("period:T"), alt.Tooltip("term:N"), alt.Tooltip("count:Q")],
    )

    return base.properties(height=320)


def ridgeline_hours(df: pd.DataFrame, *, max_groups: int = 12, color_by: str | None = None) -> alt.Chart:
    """Ridgeline-style density plot of read hour by group.

    Expected columns:
    - group (str)
    - hour (int)
    - optionally a categorical column named by color_by (e.g. 'scope')
    """

    if df.empty:
        return alt.Chart(pd.DataFrame({"group": [], "hour": []}))

    # Keep it readable by limiting groups (most recent max_groups)
    groups = sorted(df["group"].unique().tolist())[-max_groups:]
    df = df[df["group"].isin(groups)]

    density_groupby = ["group"]
    if color_by:
        density_groupby.append(color_by)

    chart = alt.Chart(df).transform_density(
        "hour",
        groupby=density_groupby,
        as_=["hour", "density"],
        extent=[0, 23],
        steps=60,
    )

    encode = {
        "x": alt.X("hour:Q", title="Hour of day", scale=alt.Scale(domain=[0, 23])),
        "y": alt.Y("density:Q", title=None, axis=None),
        "row": alt.Row("group:N", title=None, sort=groups),
    }
    if color_by:
        encode["color"] = alt.Color(
            f"{color_by}:N",
            title=None,
            legend=alt.Legend(orient="bottom", direction="horizontal"),
        )

    chart = chart.mark_area(opacity=0.55).encode(**encode).properties(height=40, width="container")

    return chart
