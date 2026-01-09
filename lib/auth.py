from __future__ import annotations

import os

import streamlit as st


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
