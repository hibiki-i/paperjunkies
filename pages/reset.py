from __future__ import annotations

from urllib.parse import parse_qs

import streamlit as st

from lib.auth import exchange_recovery_tokens_for_session, get_auth_state, update_password
from lib.settings import get_settings
from lib.ui import apply_max_width

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:  # pragma: no cover
    streamlit_js_eval = None  # type: ignore[assignment]


def _extract_tokens_from_hash(url_hash: str) -> tuple[str | None, str | None]:
    # Supabase commonly redirects with a fragment like:
    #   #access_token=...&refresh_token=...&type=recovery
    h = (url_hash or "").strip()
    if not h:
        return None, None
    if h.startswith("#"):
        h = h[1:]
    parsed = parse_qs(h)
    access_token = (parsed.get("access_token") or [None])[0]
    refresh_token = (parsed.get("refresh_token") or [None])[0]
    return access_token, refresh_token


def _get_query_param(name: str) -> str | None:
    try:
        # Streamlit 1.32+ (and current 1.52) supports st.query_params
        val = st.query_params.get(name)
        if isinstance(val, list):
            val = val[0] if val else None
        if val is None:
            return None
        s = str(val).strip()
        return s or None
    except Exception:
        try:
            qp = st.experimental_get_query_params()
            vals = qp.get(name)
            if not vals:
                return None
            s = str(vals[0]).strip()
            return s or None
        except Exception:
            return None


def main() -> None:
    apply_max_width()
    st.title("Reset password")

    settings = get_settings()

    # If already authenticated, allow changing password directly.
    auth = get_auth_state()

    if auth is None:
        # Try to obtain tokens from query params first.
        access = _get_query_param("access_token")
        refresh = _get_query_param("refresh_token")

        if not access or not refresh:
            # Fall back to reading URL fragment via JS (Supabase commonly uses the hash).
            if streamlit_js_eval is not None and not st.session_state.get("recovery_tokens"):
                url_hash = streamlit_js_eval(js_expressions="window.location.hash", want_output=True, key="reset_hash")
                if isinstance(url_hash, str) and url_hash.strip():
                    a, r = _extract_tokens_from_hash(url_hash)
                    if a and r:
                        st.session_state["recovery_tokens"] = {"access_token": a, "refresh_token": r}
                        st.rerun()

            tokens = st.session_state.get("recovery_tokens")
            if isinstance(tokens, dict):
                access = str(tokens.get("access_token") or "").strip() or None
                refresh = str(tokens.get("refresh_token") or "").strip() or None

        if access and refresh and not st.session_state.get("recovery_session_set"):
            try:
                exchange_recovery_tokens_for_session(settings, access_token=access, refresh_token=refresh)
                st.session_state["recovery_session_set"] = True
                st.rerun()
            except Exception as e:
                st.error(f"Could not start recovery session: {e}")

        auth = get_auth_state()

    if auth is None:
        st.info("Open the reset link from your email to continue.")
        if hasattr(st, "switch_page") and st.button("Back to login", type="primary"):
            st.switch_page("pages/login.py")
        return

    st.subheader("Choose a new password")
    with st.form("set_new_password"):
        new_password = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        submit = st.form_submit_button("Update password", type="primary")

    if submit:
        if not new_password:
            st.error("Please enter a new password.")
            st.stop()
        if new_password != confirm:
            st.error("Passwords do not match.")
            st.stop()
        if len(new_password) < 8:
            st.error("Password must be at least 8 characters.")
            st.stop()

        try:
            update_password(settings=settings, access_token=auth.access_token or "", new_password=new_password)
        except Exception as e:
            st.error(f"Could not update password: {e}")
            st.stop()

        st.success("Password updated.")
        if hasattr(st, "switch_page") and st.button("Go to Timeline", type="primary"):
            st.switch_page("pages/1_Timeline.py")


if __name__ == "__main__":
    main()
