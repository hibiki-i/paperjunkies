from __future__ import annotations

from zoneinfo import ZoneInfo

import streamlit as st

from lib.auth import get_current_user_id, require_auth
from lib.db import fetch_profile, upsert_profile_display_name, upsert_profile_style, upsert_profile_timezone
from lib.settings import get_settings
from lib.supabase_client import create_supabase
from lib.timezone_streamlit import detect_device_timezone
from lib.ui import CITATION_STYLE_OPTIONS, apply_max_width


def main() -> None:
    apply_max_width()
    st.title("Profile")

    settings = get_settings()
    auth = require_auth(settings)
    sb = create_supabase(settings, access_token=auth.access_token)

    user_id = get_current_user_id()

    me = fetch_profile(sb, user_id)
    if me is None:
        st.error("Profile not found for current user. Ensure a row exists in profiles for your auth.users.id.")
        st.stop()

    st.subheader("Update your profile")

    display_name = st.text_input("Display name", value=me.display_name, max_chars=80)

    current_style = (me.citation_style or "apa").lower()
    style_index = CITATION_STYLE_OPTIONS.index(current_style) if current_style in CITATION_STYLE_OPTIONS else 0
    citation_style = st.selectbox("Citation style", options=CITATION_STYLE_OPTIONS, index=style_index)

    detected_tz = detect_device_timezone(key="profile_device_tz")
    tz_help = "Use an IANA name like 'America/New_York'. Leave blank to auto-detect from your device."
    tz_placeholder = detected_tz or "America/New_York"
    timezone_input = st.text_input(
        "Timezone",
        value=(me.timezone or ""),
        placeholder=tz_placeholder,
        help=tz_help,
    )

    save = st.button("Save", type="primary")
    if save:
        next_name = display_name.strip()
        if not next_name:
            st.error("Display name cannot be empty.")
            st.stop()

        changed = False
        if next_name != me.display_name:
            upsert_profile_display_name(sb, user_id, next_name)
            changed = True

        if citation_style != me.citation_style:
            upsert_profile_style(sb, user_id, citation_style)
            changed = True

        next_tz_raw = timezone_input.strip()
        next_tz: str | None
        if not next_tz_raw:
            next_tz = None
        else:
            try:
                ZoneInfo(next_tz_raw)
            except Exception:
                st.error("Invalid timezone. Use an IANA name like 'America/New_York'.")
                st.stop()
            next_tz = next_tz_raw

        if next_tz != me.timezone:
            upsert_profile_timezone(sb, user_id, next_tz)
            changed = True

        if changed:
            st.success("Saved.")
            st.rerun()
        else:
            st.info("No changes to save.")


if __name__ == "__main__":
    main()
