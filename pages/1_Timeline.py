from __future__ import annotations

import streamlit as st

from lib.auth import get_current_user_id, require_auth
from lib.bibtex_utils import parse_bibtex_entry
from lib.citation import format_citation
from lib.db import fetch_profile, fetch_timeline_posts, fetch_user_post_dates
from lib.settings import get_settings
from lib.supabase_client import create_supabase
from lib.timeline_service import calculate_streak, post_read
from lib.timezone_streamlit import maybe_detect_and_persist_timezone
from lib.timezone_utils import format_in_timezone
from lib.ui import apply_max_width


@st.dialog("Post a new article")
def post_article_dialog(sb, user_id: str) -> None:
    bibtex_raw = st.text_area(
        "Paste a full BibTeX entry (must include abstract)",
        height=220,
        placeholder="@article{...\n  title={...},\n  abstract={...},\n  ...\n}",
    )
    note = st.text_input("Optional comment (note)")

    submit = st.button("Submit", type="primary", icon=":material/send:")
    if not submit:
        return

    try:
        parsed = parse_bibtex_entry(bibtex_raw)
        _, _post = post_read(sb, user_id=user_id, parsed=parsed, note=note.strip() or None)
        st.success("Posted!")
        st.rerun()
    except Exception as e:
        st.error(str(e))


def main() -> None:
    apply_max_width()
    st.title("Timeline")

    settings = get_settings()
    auth = require_auth(settings)
    sb = create_supabase(settings, access_token=auth.access_token)

    user_id = get_current_user_id()

    me = fetch_profile(sb, user_id)
    effective_tz = maybe_detect_and_persist_timezone(
        sb=sb,
        user_id=user_id,
        profile_timezone=me.timezone if me else None,
    )

    streak = 0
    if user_id:
        dates = fetch_user_post_dates(sb, user_id)
        streak = calculate_streak(dates, effective_tz)

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Post", type="primary", icon=":material/add:"):
            post_article_dialog(sb, user_id=user_id)

    with col2:
        if streak > 0:
            # Align with the button height (approx 37px in Streamlit) and center vertically
            st.markdown(
                f"<div style='display: flex; align-items: center; height: 37px; font-size: 1rem;'>"
                f"<span style='font-size: 1.25rem; color: #E25822; margin-right: 6px;'>🔥</span>"
                f"<span style='font-weight: 600; color: #444;'>{streak} day streak</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    timeline = fetch_timeline_posts(sb, limit=50)
    if not timeline:
        st.info("No posts yet.")
        return

    for item in timeline:
        with st.container(border=True):
            header_left, header_right = st.columns([6, 2])

            icon = ":material/account_circle:" if item.user_id == user_id else ":material/person:"
            with header_left:
                st.markdown(f"{icon} **{item.display_name}**")
            with header_right:
                st.markdown(
                    f"<div style='text-align: right; opacity: 0.7; font-size: 0.85rem;'>"
                    f"{format_in_timezone(item.read_at, effective_tz)}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            if item.note:
                st.write(item.note)
            st.write(format_citation(item.reference, item.citation_style))


if __name__ == "__main__":
    main()
