from __future__ import annotations

import streamlit as st

APP_NAME = "WaveLogic MSO"
APP_TITLE = f"{APP_NAME} — Multi-Channel Protocol Analyzer"
DEVELOPER = "Kishan J."
DEVELOPER_URL = "https://github.com/KSHNKMRJHA"
DESIGNER = "Piston"
TAGLINE = "Made with love and Open-Source AI"
REPO_URL = "https://github.com/KSHNKMRJHA/wavelogic-mso"


def page_setup(title: str, icon: str) -> None:
    st.set_page_config(
        page_title=f"{title} · {APP_NAME}",
        page_icon=icon,
        layout="wide",
    )


def render_brand_footer() -> None:
    st.markdown(
        "<div style='margin-top:48px;padding:18px 20px;border-top:1px solid #1E293B;"
        "color:#8CA3C1;font-size:0.85rem;text-align:center'>"
        f"<b>{APP_NAME}</b> · Designed by <b>{DESIGNER}</b> · Developed by "
        f"<b>{DEVELOPER}</b><br>{TAGLINE} — free forever, like it should be."
        "</div>",
        unsafe_allow_html=True,
    )