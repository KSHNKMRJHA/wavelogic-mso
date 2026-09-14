"""WaveLogic MSO — Credits page."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from branding import (  # noqa: E402
    APP_NAME,
    DESIGNER,
    DEVELOPER,
    DEVELOPER_URL,
    REPO_URL,
    TAGLINE,
    page_setup,
    render_brand_footer,
)

page_setup("Credits", "🧑‍🔧")

st.header("Credits")

st.markdown(
    f"Every project that gives people back their own data deserves its "
    f"credits, so here they are."
)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f"### Designed by\n"
        f"**{DESIGNER}**  \n"
        "Visual identity, flow, and the MSO-style interface."
    )
with col2:
    st.markdown(
        f"### Developed by\n"
        f"**{DEVELOPER}**  \n"
        f"[{DEVELOPER_URL}]({DEVELOPER_URL})  \n"
        "Engineering, protocol decoders, and architecture."
    )
with col3:
    st.markdown(
        f"### Made with\n"
        f"**{TAGLINE}**  \n"
        "Copilot-era tooling brought this from idea to open source."
    )

st.markdown("---")
st.subheader("Powered by open-source software")
st.markdown(
    "- **Streamlit** — the web framework\n"
    "- **NumPy** & **pandas** — numeric and tabular heavy lifting\n"
    "- **Plotly** — interactive charts and offline exports\n"
    "- **Python** — the language that makes signal work readable"
)

st.subheader("License")
st.markdown(
    "Released under the **MIT License**. Use it, study it, ship it, teach it. "
    "If it helps you debug a real hardware problem, that is all the credit "
    "we need."
)

st.markdown(
    "### Repository\n"
    f"[{REPO_URL}]({REPO_URL})\n\n"
    "Issues, feature requests and pull requests are welcome."
)

st.info(f"{APP_NAME} · {TAGLINE} — free forever, like it should be.")

render_brand_footer()