from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str | None
    supabase_access_token: str | None


def get_settings() -> Settings:
    # Prefer environment variables, but support Streamlit secrets.
    url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip() or None

    if (not url) or (not anon_key):
        try:
            import streamlit as st  # local import to keep module usable outside Streamlit

            url = url or str(st.secrets.get("SUPABASE_URL", "")).strip()
            anon_key = anon_key or str(st.secrets.get("SUPABASE_ANON_KEY", "")).strip()
            service_role = service_role or str(st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip() or None
            access_token = access_token or str(st.secrets.get("SUPABASE_ACCESS_TOKEN", "")).strip() or None
        except Exception:
            pass

    if not url or not anon_key:
        raise RuntimeError(
            "Missing SUPABASE_URL / SUPABASE_ANON_KEY. Provide via env vars or .streamlit/secrets.toml."
        )

    return Settings(
        supabase_url=url,
        supabase_anon_key=anon_key,
        supabase_service_role_key=service_role,
        supabase_access_token=access_token,
    )
