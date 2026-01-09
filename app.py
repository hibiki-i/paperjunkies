from __future__ import annotations

import streamlit as st

from lib.ui import apply_max_width


def main() -> None:
    st.set_page_config(page_title="Paperjunkies", layout="wide")
    apply_max_width()

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
