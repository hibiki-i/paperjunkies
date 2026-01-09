from __future__ import annotations

from zoneinfo import ZoneInfo

import streamlit as st

from .db import upsert_profile_timezone
from .timezone_utils import DEFAULT_TIMEZONE, normalize_timezone_name

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:  # pragma: no cover
    streamlit_js_eval = None  # type: ignore[assignment]


def _is_valid_tz(tz_name: str) -> bool:
    try:
        ZoneInfo(tz_name)
        return True
    except Exception:
        return False


def detect_device_timezone(*, key: str = "__device_timezone") -> str | None:
    """Best-effort browser timezone detection.

    Returns an IANA timezone name like 'America/Los_Angeles', or None.

    Note: it may return None on the first run and populate on a rerun.
    """

    if streamlit_js_eval is None:
        return None

    tz = streamlit_js_eval(
        js_expressions="Intl.DateTimeFormat().resolvedOptions().timeZone",
        key=key,
        want_output=True,
    )

    if isinstance(tz, str) and tz.strip() and _is_valid_tz(tz.strip()):
        return tz.strip()
    return None


def get_effective_timezone(*, profile_timezone: str | None) -> str:
    """Resolve timezone for rendering/grouping.

    Precedence:
    1) Profile timezone if set
    2) Session cached device timezone
    3) UTC
    """

    if profile_timezone and str(profile_timezone).strip():
        return normalize_timezone_name(profile_timezone)

    cached = st.session_state.get("device_timezone")
    if isinstance(cached, str) and cached.strip() and _is_valid_tz(cached.strip()):
        return normalize_timezone_name(cached)

    return DEFAULT_TIMEZONE


def maybe_detect_and_persist_timezone(*, sb, user_id: str, profile_timezone: str | None) -> str:
    """If profile timezone is NULL, detect from device, cache, and persist once."""

    if profile_timezone and str(profile_timezone).strip():
        return normalize_timezone_name(profile_timezone)

    if not st.session_state.get("device_timezone"):
        tz = detect_device_timezone()
        if tz:
            st.session_state["device_timezone"] = tz

    effective = get_effective_timezone(profile_timezone=profile_timezone)

    # Persist only if we have a detected tz (not just UTC fallback).
    detected = st.session_state.get("device_timezone")
    if (
        not (profile_timezone and str(profile_timezone).strip())
        and isinstance(detected, str)
        and detected.strip()
        and effective != DEFAULT_TIMEZONE
        and not st.session_state.get("persisted_timezone")
    ):
        try:
            upsert_profile_timezone(sb, user_id, effective)
            st.session_state["persisted_timezone"] = True
        except Exception:
            # Non-fatal: keep rendering with effective tz.
            pass

    return effective
