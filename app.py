from __future__ import annotations

import importlib

import streamlit as st

import lib.auth as auth
from lib.settings import get_settings
from lib.ui import apply_max_width


def main() -> None:
    st.set_page_config(page_title="Paperjunkies", layout="wide")
    apply_max_width()

    # Streamlit sometimes keeps imported modules cached across reruns.
    # Import `lib.auth` as a module so we can reload if needed.
    if not hasattr(auth, "require_auth") or not hasattr(auth, "render_auth_sidebar"):
        importlib.reload(auth)

    settings = get_settings()
    st.sidebar.markdown("**Paperjunkies**")

    pages = [
        # Auth utility routes (kept out of sidebar links below)
        st.Page("pages/login.py", title="Login", icon=":material/login:", url_path="login"),
        st.Page("pages/reset.py", title="Reset Password", icon=":material/lock_reset:", url_path="reset"),
        # Main app pages
        st.Page("pages/1_Timeline.py", title="Timeline", icon=":material/receipt_long:", url_path="timeline", default=True),
        st.Page("pages/2_Dashboard.py", title="Dashboard", icon=":material/insights:", url_path="dashboard"),
        st.Page("pages/3_Profile.py", title="Profile", icon=":material/person:", url_path="profile"),
    ]

    # Best practice: keep auth pages reachable by URL, but out of the main sidebar nav.
    # Use hidden navigation (routing still works) and render only app links manually.
    try:
        nav = st.navigation(pages, position="hidden")
    except TypeError:
        nav = st.navigation(pages)

    if hasattr(st.sidebar, "page_link"):
        st.sidebar.page_link("pages/1_Timeline.py", label="Timeline", icon=":material/receipt_long:")
        st.sidebar.page_link("pages/2_Dashboard.py", label="Dashboard", icon=":material/insights:")
        st.sidebar.page_link("pages/3_Profile.py", label="Profile", icon=":material/person:")

    footer = st.sidebar.container()
    auth.render_auth_sidebar(settings=settings, container=footer, show_title=False)
    nav.run()


if __name__ == "__main__":
    main()
