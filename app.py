from __future__ import annotations

import importlib

import streamlit as st

import lib.auth as auth
from lib.settings import get_settings
from lib.ui import apply_max_width
from streamlit_cookies_manager import EncryptedCookieManager
from lib.supabase_client import create_supabase

def main() -> None:
    st.set_page_config(page_title="Paperjunkies", layout="wide")
    apply_max_width()

    settings = get_settings()

    cookies = EncryptedCookieManager(
        prefix="paperjunkies/auth/",
        password=st.secrets.get("COOKIES_PASSWORD", "")
    )

    if not cookies.ready():
        # Wait for the component to load and send back the cookies.
        # We don't stop the app here because it might cause a white page glitch
        # if the component takes time to load or if we are in a transition.
        # Just skip the restore logic for this run.
        pass

    st.session_state["cookies"] = cookies

    # If the user explicitly clicked "Sign out", avoid immediately restoring a
    # session from any persisted cookie value and clear it once cookies are ready.
    if st.session_state.get("auth_signout_pending"):
        if cookies.ready():
            try:
                cookies["sb_refresh_token"] = ""
                cookies.save()
            except Exception:
                pass
            st.session_state.pop("auth_signout_pending", None)
        # Clear any in-memory auth state as a safety net.
        auth.clear_auth_state()
        refresh_token = None
    else:
        refresh_token = cookies.get("sb_refresh_token") if cookies.ready() else None

    if refresh_token and auth.get_auth_state() is None:
        try:
            sb = create_supabase(settings)
            resp = sb.auth.refresh_session(refresh_token)
            session = getattr(resp, "session", None)
            if session:
                auth_state = auth.auth_state_from_session(session)
                auth.set_auth_state(
                    user_id=auth_state.user_id,
                    access_token=auth_state.access_token,
                    refresh_token=auth_state.refresh_token,
                    email=auth_state.email
                )
                if auth_state.refresh_token and auth_state.refresh_token != refresh_token:
                    cookies["sb_refresh_token"] = auth_state.refresh_token
                    cookies.save()
                    st.rerun()
        except Exception as e:
            st.warning(f"Session refresh failed: {e}")
    
    # Streamlit sometimes keeps imported modules cached across reruns.
    # Import `lib.auth` as a module so we can reload if needed.
    if not hasattr(auth, "require_auth") or not hasattr(auth, "render_auth_sidebar"):
        importlib.reload(auth)

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
