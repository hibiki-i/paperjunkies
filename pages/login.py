from __future__ import annotations

import streamlit as st

from lib.auth import AuthState, auth_state_from_session, get_auth_state, send_password_reset_email, set_auth_state
from lib.settings import get_settings
from lib.supabase_client import create_supabase
from lib.ui import apply_max_width


def _build_reset_redirect_url(*, app_base_url: str | None) -> str | None:
    if not app_base_url:
        return None
    base = app_base_url.strip().rstrip("/")
    if not base:
        return None
    return f"{base}/reset"


@st.dialog("Forgot password")
def forgot_password_dialog(*, settings, default_email: str = "") -> None:
    email = st.text_input("Email", value=default_email, placeholder="you@example.com")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        send = st.button("Send reset link", type="primary")
    with col_b:
        cancel = st.button("Cancel")

    if cancel:
        st.rerun()

    if not send:
        return

    redirect_to = _build_reset_redirect_url(app_base_url=settings.app_base_url)

    try:
        send_password_reset_email(settings=settings, email=email, redirect_to=redirect_to)
    except Exception as e:
        st.error(f"Could not send reset email: {e}")
        return

    st.success("If that email exists, a reset link was sent.")
    st.caption(
        "If the link doesn’t open the app’s reset page, set APP_BASE_URL (and allow it in Supabase Auth redirect URLs)."
    )


def _session_to_auth(resp) -> AuthState:
    session = getattr(resp, "session", None)
    if session is None:
        raise RuntimeError("Sign in failed: no session returned.")
    return auth_state_from_session(session)


def main() -> None:
    apply_max_width()
    st.title("Paperjunkies — Sign in")

    settings = get_settings()

    existing = get_auth_state()
    if existing is not None:
        st.success("You are already signed in.")
        if hasattr(st, "switch_page") and st.button("Go to Timeline", type="primary"):
            st.switch_page("pages/1_Timeline.py")
        return

    with st.form("supabase_login", clear_on_submit=False):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if submitted:
        if not email.strip() or not password:
            st.error("Please enter both email and password.")
            st.stop()

        sb = create_supabase(settings)
        try:
            resp = sb.auth.sign_in_with_password({"email": email.strip(), "password": password})
        except Exception as e:
            st.error(f"Sign in failed: {e}")
            st.stop()

        try:
            auth = _session_to_auth(resp)
        except Exception as e:
            st.error(str(e))
            st.stop()

        set_auth_state(
            user_id=auth.user_id,
            access_token=auth.access_token,
            refresh_token=auth.refresh_token,
            email=auth.email,
        )

        # If the user previously signed out, clear the bootstrap skip flag.
        st.session_state.pop("auth_signout_pending", None)

        if "cookies" in st.session_state:
            cookies = st.session_state["cookies"]
            cookies["sb_refresh_token"] = auth.refresh_token
            # Set a very long expiry for the cookie (e.g. 365 days) if supported by the library,
            # effectively mimicking "infinite" timeout. The library usually persists if not session.
            cookies.save()

        if hasattr(st, "switch_page"):
            st.switch_page("pages/1_Timeline.py")
        else:
            st.rerun()

    col_left, _col_right = st.columns([1, 3])
    with col_left:
        if st.button("Forgot password", type="secondary"):
            forgot_password_dialog(settings=settings, default_email=email.strip())


if __name__ == "__main__":
    main()
