from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:  # pragma: no cover
    streamlit_js_eval = None  # type: ignore[assignment]

from .settings import Settings
from .supabase_client import create_supabase


@dataclass(frozen=True)
class AuthState:
    user_id: str
    access_token: str | None
    refresh_token: str | None
    email: str | None


DEFAULT_LOGIN_PAGE = "pages/login.py"

PERSISTENT_REFRESH_COOKIE = "paperjunkies_rt"


def _should_set_secure_cookie() -> bool:
    try:
        origin = str(getattr(st, "context").headers.get("origin") or "")
    except Exception:
        origin = ""
    return origin.startswith("https://")


def _clear_persistent_refresh_cookie() -> None:
    if streamlit_js_eval is None:
        return
    secure = "; Secure" if _should_set_secure_cookie() else ""
    js = (
        "(() => {"
        f"const n={PERSISTENT_REFRESH_COOKIE!r};"
        f"document.cookie = encodeURIComponent(n) + '=; Max-Age=0; path=/; SameSite=Lax{secure}';"
        "return true;"
        "})()"
    )
    streamlit_js_eval(js_expressions=js, want_output=False, key="clear_persistent_rt_sidebar")


_SESSION_USER_ID_KEY = "user_id"
_SESSION_ACCESS_TOKEN_KEY = "supabase_access_token"
_SESSION_REFRESH_TOKEN_KEY = "supabase_refresh_token"
_SESSION_EMAIL_KEY = "user_email"

# When set, the app should avoid restoring sessions from cookies and should
# best-effort clear any persisted refresh token once the cookie component is ready.
_SESSION_SIGNOUT_PENDING_KEY = "auth_signout_pending"


def _get_session_str(key: str) -> str | None:
    val = st.session_state.get(key)
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def get_auth_state() -> AuthState | None:
    """Return current auth state from Streamlit session.

    Local dev fallbacks:
    - SUPABASE_USER_ID (env or Streamlit secrets)
    - SUPABASE_ACCESS_TOKEN (env or Streamlit secrets)
    """

    user_id = _get_session_str(_SESSION_USER_ID_KEY)
    access_token = _get_session_str(_SESSION_ACCESS_TOKEN_KEY)
    refresh_token = _get_session_str(_SESSION_REFRESH_TOKEN_KEY)
    email = _get_session_str(_SESSION_EMAIL_KEY)

    if user_id:
        return AuthState(user_id=user_id, access_token=access_token, refresh_token=refresh_token, email=email)

    # Local dev fallbacks
    env_user_id = os.getenv("SUPABASE_USER_ID", "").strip() or None
    if env_user_id:
        env_access_token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip() or None
        return AuthState(
            user_id=env_user_id,
            access_token=env_access_token,
            refresh_token=None,
            email=None,
        )

    try:
        secrets_user_id = str(st.secrets.get("SUPABASE_USER_ID", "")).strip() or None
        if secrets_user_id:
            secrets_access_token = str(st.secrets.get("SUPABASE_ACCESS_TOKEN", "")).strip() or None
            return AuthState(
                user_id=secrets_user_id,
                access_token=secrets_access_token,
                refresh_token=None,
                email=None,
            )
    except Exception:
        pass

    return None


def set_auth_state(*, user_id: str, access_token: str | None, refresh_token: str | None, email: str | None) -> None:
    st.session_state[_SESSION_USER_ID_KEY] = user_id
    if access_token:
        st.session_state[_SESSION_ACCESS_TOKEN_KEY] = access_token
    else:
        st.session_state.pop(_SESSION_ACCESS_TOKEN_KEY, None)
    if refresh_token:
        st.session_state[_SESSION_REFRESH_TOKEN_KEY] = refresh_token
    else:
        st.session_state.pop(_SESSION_REFRESH_TOKEN_KEY, None)
    if email:
        st.session_state[_SESSION_EMAIL_KEY] = email
    else:
        st.session_state.pop(_SESSION_EMAIL_KEY, None)


def clear_auth_state() -> None:
    st.session_state.pop(_SESSION_USER_ID_KEY, None)
    st.session_state.pop(_SESSION_ACCESS_TOKEN_KEY, None)
    st.session_state.pop(_SESSION_REFRESH_TOKEN_KEY, None)
    st.session_state.pop(_SESSION_EMAIL_KEY, None)


def _session_to_auth_state(session: Any) -> AuthState:
    # supabase-py returns an object with .access_token/.refresh_token and .user
    access_token = getattr(session, "access_token", None)
    refresh_token = getattr(session, "refresh_token", None)
    user = getattr(session, "user", None)
    user_id = getattr(user, "id", None) if user is not None else None
    email = getattr(user, "email", None) if user is not None else None
    if not user_id:
        raise RuntimeError("Supabase sign-in succeeded but no user id was returned.")
    return AuthState(
        user_id=str(user_id),
        access_token=str(access_token) if access_token else None,
        refresh_token=str(refresh_token) if refresh_token else None,
        email=str(email) if email else None,
    )


def auth_state_from_session(session: Any) -> AuthState:
    return _session_to_auth_state(session)


def send_password_reset_email(*, settings: Settings, email: str, redirect_to: str | None = None) -> None:
    sb = create_supabase(settings)
    clean = email.strip()
    if not clean:
        raise ValueError("Email is required.")

    options: dict[str, Any] | None
    if redirect_to and redirect_to.strip():
        options = {"redirect_to": redirect_to.strip()}
    else:
        options = None

    if options is None:
        sb.auth.reset_password_for_email(clean)
    else:
        sb.auth.reset_password_for_email(clean, options)


def exchange_recovery_tokens_for_session(
    settings: Settings, *, access_token: str, refresh_token: str
) -> AuthState:
    sb = create_supabase(settings)
    resp = sb.auth.set_session(access_token, refresh_token)
    session = getattr(resp, "session", None) or resp
    auth = _session_to_auth_state(session)
    set_auth_state(
        user_id=auth.user_id,
        access_token=auth.access_token,
        refresh_token=auth.refresh_token,
        email=auth.email,
    )
    return auth


def update_password(
    *, settings: Settings, access_token: str, refresh_token: str, new_password: str
) -> None:
    if not new_password:
        raise ValueError("Password is required.")
    sb = create_supabase(settings, access_token=access_token)
    sb.auth.set_session(access_token, refresh_token)
    sb.auth.update_user({"password": new_password})


def require_auth(
    settings: Settings,
    *,
    title: str = "Paperjunkies",
    redirect_to_login: bool = True,
    login_page: str = DEFAULT_LOGIN_PAGE,
) -> AuthState:
    """Gate the app behind Supabase Auth (email/password).

    - If authenticated, returns AuthState.
    - If not, renders a login form and stops the Streamlit script.
    """

    existing = get_auth_state()
    if existing is not None:
        return existing

    # Check if we are waiting for cookies to load
    if "cookies" in st.session_state:
        cookies = st.session_state["cookies"]
        if not cookies.ready():
            st.stop()

    if redirect_to_login and hasattr(st, "switch_page"):
        try:
            st.switch_page(login_page)
        except Exception:
            # Fall back to inline login UI.
            pass

    st.title(f"{title} — Sign in")
    st.caption("Sign in with your Supabase account to continue.")

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

        session = getattr(resp, "session", None)
        if session is None:
            st.error("Sign in failed: no session returned.")
            st.stop()

        auth = _session_to_auth_state(session)
        set_auth_state(
            user_id=auth.user_id,
            access_token=auth.access_token,
            refresh_token=auth.refresh_token,
            email=auth.email,
        )

        if "cookies" in st.session_state:
            cookies = st.session_state["cookies"]
            if auth.refresh_token:
                cookies["sb_refresh_token"] = auth.refresh_token
                cookies.save()

        st.rerun()

    st.stop()


def render_auth_sidebar(
    *,
    settings: Settings,
    title: str = "Paperjunkies",
    container: Any | None = None,
    show_title: bool = True,
) -> None:
    """Optional sidebar widget showing user + logout.

    If `container` is provided, content is rendered there (useful for bottom-aligned sidebar layouts).
    """

    auth = get_auth_state()
    if auth is None:
        return

    label = auth.email or auth.user_id

    target = container if container is not None else st.sidebar

    if show_title:
        target.markdown(f"**{title}**")

    target.caption(f"Signed in as {label}")

    if target.button("Sign out", type="secondary"):
        # Mark sign-out intent so app bootstrap code can avoid re-auth from cookies
        # and clear the persisted refresh token once the cookie component is ready.
        st.session_state[_SESSION_SIGNOUT_PENDING_KEY] = True
        try:
            # Best-effort remote sign-out (clears refresh tokens server-side)
            sb = create_supabase(settings, access_token=auth.access_token)
            sb.auth.sign_out()
        except Exception:
            pass

        if "cookies" in st.session_state:
            cookies = st.session_state["cookies"]
            # Only mutate cookies if the component has initialized; otherwise we'll
            # clear it on the next run from app bootstrap code.
            try:
                if cookies.ready():
                    cookies["sb_refresh_token"] = ""
                    cookies.save()
            except Exception:
                pass
            
        clear_auth_state()
        _clear_persistent_refresh_cookie()

        # Prefer explicit navigation to the login page when available.
        if hasattr(st, "switch_page"):
            try:
                st.switch_page(DEFAULT_LOGIN_PAGE)
            except Exception:
                pass
        st.rerun()


def get_current_user_id() -> str:
    """Return the authenticated user's UUID.

    The prompt says to assume the user is authenticated.

    In practice, Streamlit needs a way to receive that identity. This function supports:
    - st.session_state['user_id'] (set by your auth integration)
    - env var SUPABASE_USER_ID (useful for local development)

    If neither is present, we fail fast with a clear message.
    """

    if "user_id" in st.session_state and str(st.session_state["user_id"]).strip():
        return str(st.session_state["user_id"]).strip()

    env_user_id = os.getenv("SUPABASE_USER_ID", "").strip()
    if env_user_id:
        return env_user_id

    try:
        secrets_user_id = str(st.secrets.get("SUPABASE_USER_ID", "")).strip()
        if secrets_user_id:
            return secrets_user_id
    except Exception:
        pass

    raise RuntimeError(
        "No user id found. Set st.session_state['user_id'] via your auth flow, "
        "or set SUPABASE_USER_ID for local development."
    )
