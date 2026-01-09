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
    auth.require_auth(settings)
    auth.render_auth_sidebar(settings=settings)

    nav = st.navigation(
        [
            st.Page("pages/1_Timeline.py", title="Timeline", icon=":material/receipt_long:", default=True),
            st.Page("pages/2_Dashboard.py", title="Dashboard", icon=":material/insights:"),
            st.Page("pages/3_Profile.py", title="Profile", icon=":material/person:"),
        ]
    )
    nav.run()


if __name__ == "__main__":
    main()
