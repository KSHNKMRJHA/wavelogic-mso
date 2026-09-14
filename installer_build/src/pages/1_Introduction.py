"""WaveLogic MSO — Introduction page."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from branding import (  # noqa: E402
    APP_NAME,
    APP_TITLE,
    DEVELOPER_URL,
    DESIGNER,
    DEVELOPER,
    REPO_URL,
    TAGLINE,
    page_setup,
    render_brand_footer,
)

page_setup("Introduction", "📈")

st.markdown(
    f"""
    <div style="padding:28px 8px 8px 8px">
      <div style="font-size:2.6rem;font-weight:700;letter-spacing:-1px">
        {APP_NAME}
      </div>
      <div style="font-size:1.15rem;color:#8CA3C1;margin-top:4px">
        {APP_TITLE}
      </div>
      <div style="margin-top:12px;font-size:0.95rem;color:#5B7495">
        {TAGLINE}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(f"""
{APP_NAME} turns plain CSV recordings into a bench-style oscilloscope: upload a
capture, view any combination of channels on a shared time axis, zoom and cursor
through it, compare signals, and decode the protocols hidden in the waveforms —
without a vendor tool, a license key, or the cloud.

It was born from a simple frustration: a CSV from a logic analyzer or scope that
"could not be decoded because the timestamps were not strictly increasing".
So the decoder was built to reconstruct a proper time base from any capture,
monotonic or not, and ship an entire protocol suite with it — as open source.
""")

st.subheader("What it gives you")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        "**Scope view**\n\n"
        "Multiple channels, user-selectable colors, transparent overlays, "
        "crosshair cursors with per-channel readouts, and a full-resolution "
        "PDF-style offline HTML export of the visible window."
    )
with col2:
    st.markdown(
        "**Signal math**\n\n"
        "Differential channels (A - B), plus edge-frequency, duty-cycle, "
        "logic-state, count, and exported-logic readouts per window."
    )
with col3:
    st.markdown(
        "**Protocol decoders**\n\n"
        "Differential Manchester (legacy), Manchester, UART, SPI, I2C, NRZ and "
        "PWM — each with configurable options, status chips, metrics, tables, "
        "and a plain-text decode log."
    )

st.markdown("---")
st.markdown("### Project quick links")
st.markdown(
    f"- **Source code** — [{REPO_URL}]({REPO_URL})\n"
    f"- **Step-by-step user guide** — see the *User Guide* page in the sidebar\n"
    f"- **Feature list** — see the *Features* page\n"
    f"- **Credits** — see the *Credits* page\n"
    f"- **Developer** — [{DEVELOPER}]({DEVELOPER_URL}) · **Designer** — {DESIGNER}"
)

st.markdown("### Runtime requirements")
st.markdown(
    "Python 3.10+ with **Streamlit**, **NumPy**, **pandas** and **Plotly**. "
    "Everything runs locally; no account, API key, or internet needed to use it."
)

render_brand_footer()