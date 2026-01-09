from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.auth import get_current_user_id
from lib.dashboard_service import compute_semantic_trends, compute_time_of_day
from lib.db import fetch_posts_for_dashboard, fetch_profile
from lib.plots import ridgeline_hours, stream_plot
from lib.settings import get_settings
from lib.supabase_client import create_supabase
from lib.timezone_streamlit import maybe_detect_and_persist_timezone
from lib.ui import apply_max_width


def main() -> None:
    apply_max_width()
    st.title("Dashboard")

    settings = get_settings()
    sb = create_supabase(settings)

    user_id = get_current_user_id()

    me = fetch_profile(sb, user_id)
    effective_tz = maybe_detect_and_persist_timezone(
        sb=sb,
        user_id=user_id,
        profile_timezone=me.timezone if me else None,
    )

    personal_posts = fetch_posts_for_dashboard(sb, user_id=user_id)
    team_posts = fetch_posts_for_dashboard(sb, user_id=None)

    st.divider()

    st.header(":material/schedule: Reading habits")
    group_by = st.selectbox("Group by", options=["daily", "weekly", "monthly", "yearly"], index=2)
    personal_tod = compute_time_of_day(personal_posts, group_by=group_by, timezone=effective_tz)
    team_tod = compute_time_of_day(team_posts, group_by=group_by, timezone=effective_tz)

    personal_df = personal_tod.data.copy()
    team_df = team_tod.data.copy()
    personal_df["scope"] = "Personal"
    team_df["scope"] = "Team"
    combined = pd.concat([team_df, personal_df], ignore_index=True)

    if combined.empty:
        st.info("Not enough data to compute time-of-day patterns yet.")
    else:
        st.altair_chart(ridgeline_hours(combined, max_groups=12, color_by="scope"), width="stretch")

    st.divider()

    st.header(":material/owl: Semantic trends")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        grain = st.selectbox("Aggregate by", options=["weekly", "monthly"], index=1)
    with col_a2:
        top_k = st.slider("Top terms", min_value=5, max_value=25, value=12, step=1)

    st.subheader("Personal")
    personal_trends = compute_semantic_trends(
        personal_posts,
        time_grain=grain,
        timezone=effective_tz,
        top_k_terms=top_k,
    )
    if personal_trends.data.empty:
        st.info("Not enough personal data to compute semantic trends yet.")
    else:
        st.altair_chart(stream_plot(personal_trends.data), width="stretch")

    st.subheader("Team")
    team_trends = compute_semantic_trends(
        team_posts,
        time_grain=grain,
        timezone=effective_tz,
        top_k_terms=top_k,
    )
    if team_trends.data.empty:
        st.info("Not enough team data to compute semantic trends yet.")
    else:
        st.altair_chart(stream_plot(team_trends.data), width="stretch")


if __name__ == "__main__":
    main()
