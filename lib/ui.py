from __future__ import annotations

import streamlit as st


DEFAULT_MAX_WIDTH_PX = 1100
CITATION_STYLE_OPTIONS = ["apa", "mla", "chicago"]


def apply_max_width(*, max_width_px: int = DEFAULT_MAX_WIDTH_PX) -> None:
    """Constrain page content width for readability on wide screens."""

    st.markdown(
        f"""
<style>
.block-container {{
    max-width: {max_width_px}px;
}}
</style>
""",
        unsafe_allow_html=True,
    )
