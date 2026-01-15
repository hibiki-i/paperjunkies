from __future__ import annotations

import importlib
import time
from urllib.parse import unquote

import streamlit as st

import lib.auth as auth
from lib.persistent_cookie import decrypt_value, encrypt_value
from lib.settings import get_settings
from lib.ui import apply_max_width
from streamlit_cookies_manager import EncryptedCookieManager
from lib.supabase_client import create_supabase

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:  # pragma: no cover
    streamlit_js_eval = None  # type: ignore[assignment]


PERSISTENT_REFRESH_COOKIE = "paperjunkies_rt"


def _should_set_secure_cookie() -> bool:
    try:
        headers = getattr(st, "context").headers
        origin = str(headers.get("origin") or "")
        xf_proto = str(headers.get("x-forwarded-proto") or "")
    except Exception:
        origin = ""
        xf_proto = ""
    return origin.startswith("https://") or xf_proto.lower().startswith("https")


def _set_persistent_refresh_cookie(*, refresh_token: str, cookie_password: str) -> None:
    if streamlit_js_eval is None:
        return
    if not cookie_password.strip() or not refresh_token.strip():
        return

    try:
        ciphertext = encrypt_value(password=cookie_password, value=refresh_token)
    except Exception:
        return

    secure = "; Secure" if _should_set_secure_cookie() else ""
    js = (
        "(() => {"
        f"const n={PERSISTENT_REFRESH_COOKIE!r};"
        f"const v={ciphertext!r};"
        "const maxAge = 365*24*60*60;"
        f"document.cookie = n + '=' + v + '; Max-Age=' + maxAge + '; Path=/; SameSite=Lax{secure}';"
        "return true;"
        "})()"
    )
    # Key includes a short hash so Streamlit treats it as a new component call when rotated.
    streamlit_js_eval(js_expressions=js, want_output=False, key=f"set_persistent_rt_{abs(hash(ciphertext)) % 1_000_000}")


def _clear_persistent_refresh_cookie() -> None:
    if streamlit_js_eval is None:
        return
    secure = "; Secure" if _should_set_secure_cookie() else ""
    js = (
        "(() => {"
        f"const n={PERSISTENT_REFRESH_COOKIE!r};"
        f"document.cookie = n + '=; Max-Age=0; Path=/; SameSite=Lax{secure}';"
        "return true;"
        "})()"
    )
    streamlit_js_eval(js_expressions=js, want_output=False, key="clear_persistent_rt")

def main() -> None:
    st.set_page_config(page_title="Paperjunkies", layout="wide")
    apply_max_width()

    settings = get_settings()

    cookies = EncryptedCookieManager(
        prefix="paperjunkies/auth/",
        password=st.secrets.get("COOKIES_PASSWORD", ""),
        # Force cookies to be readable across the entire app. Without an explicit
        # path, Streamlit/component routes can cause cookies to be scoped to an
        # internal path (e.g. /~/+) and then they won't be sent on normal page loads.
        path="/",
    )

    if not cookies.ready():
        # Wait for the component to load and send back the cookies.
        # We don't stop the app here because it might cause a white page glitch
        # if the component takes time to load or if we are in a transition.
        # Just skip the restore logic for this run.
        pass

    st.session_state["cookies"] = cookies

    cookie_password = str(st.secrets.get("COOKIES_PASSWORD", "") or "")

    # Preferred persistent auth cookie (root path, encrypted).
    persistent_refresh_token: str | None = None
    try:
        raw_cookie_val = getattr(st, "context").cookies.get(PERSISTENT_REFRESH_COOKIE)
        if raw_cookie_val:
            # Defensive: some JS cookie setters encode values; decode before decrypt.
            decoded = unquote(str(raw_cookie_val))
            persistent_refresh_token = decrypt_value(password=cookie_password, token=decoded)
    except Exception:
        persistent_refresh_token = None

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
        _clear_persistent_refresh_cookie()
        # Clear any in-memory auth state as a safety net.
        auth.clear_auth_state()
        refresh_token = None
    else:
        refresh_token = persistent_refresh_token
        if not refresh_token:
            refresh_token = cookies.get("sb_refresh_token") if cookies.ready() else None

    # If a refresh attempt just failed, avoid hammering Supabase on immediate reruns.
    last_refresh_failure_ts = st.session_state.get("auth_refresh_failure_ts")
    recently_failed_refresh = (
        isinstance(last_refresh_failure_ts, (int, float)) and (time.time() - float(last_refresh_failure_ts) < 30)
    )

    if refresh_token and auth.get_auth_state() is None and not recently_failed_refresh:
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
                st.session_state.pop("auth_refresh_failure_ts", None)
                if auth_state.refresh_token and auth_state.refresh_token != refresh_token:
                    # Supabase may rotate refresh tokens. Persist the new one so future restores work.
                    _set_persistent_refresh_cookie(refresh_token=auth_state.refresh_token, cookie_password=cookie_password)
                    cookies["sb_refresh_token"] = auth_state.refresh_token
                    cookies.save()
                    st.rerun()
        except Exception:
            # Token might be invalid/expired/revoked, or this could be a transient failure.
            # Don't immediately clear the cookie; let a successful login overwrite it.
            st.session_state["auth_refresh_failure_ts"] = time.time()
            st.session_state["auth_warning"] = "Session expired. Please sign in again."
    
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
