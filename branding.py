from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

import streamlit as st

APP_NAME = "WaveLogic MSO"
APP_TITLE = f"{APP_NAME} — Multi-Channel Protocol Analyzer"
DEVELOPER = "Kishan J."
DEVELOPER_URL = "https://github.com/KSHNKMRJHA"
DESIGNER = "Piston"
TAGLINE = "Made with love and Open-Source AI"
REPO_URL = "https://github.com/KSHNKMRJHA/wavelogic-mso"

_REPO_ROOT = Path(__file__).resolve().parent


def _git_output(*args: str) -> str | None:
    """Return stripped stdout of a git command, or None if unavailable."""
    try:
        if not (_REPO_ROOT / ".git").exists():
            return None
        completed = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _build_info_from_git() -> tuple[int, str] | None:
    """Commit count and short SHA from the local checkout (equals deployed main)."""
    count = _git_output("rev-list", "--count", "HEAD")
    sha = _git_output("rev-parse", "--short=7", "HEAD")
    if count and count.isdigit() and sha:
        return int(count), sha
    return None


def _build_info_from_environment() -> tuple[int, str] | None:
    """Deployment fallback: explicit env vars set by the hosting environment."""
    count = os.environ.get("WAVELOGIC_COMMIT_COUNT", "").strip()
    sha = os.environ.get("WAVELOGIC_COMMIT_SHA", "").strip()
    if count.isdigit() and sha:
        return int(count), sha[:7]
    return None


def _build_info_from_secrets() -> tuple[int, str] | None:
    """Deployment fallback: Streamlit Cloud secrets, when configured."""
    try:
        st.secrets.load_if_toml_exists()
        count = str(st.secrets.get("wavelogic_commit_count", "")).strip()
        sha = str(st.secrets.get("wavelogic_commit_sha", "")).strip()
    except Exception:
        return None
    if count.isdigit() and sha:
        return int(count), sha[:7]
    return None


@lru_cache(maxsize=1)
def get_build_label() -> str | None:
    """Return ``v<N> · build <short-sha>`` or None if no build metadata exists.

    ``N`` is the commit count of the running commit (equal to the GitHub ``main``
    history for a published branch). Resolution order: git checkout, then
    deployment environment variables, then Streamlit secrets. Never raises.
    """
    for provider in (
        _build_info_from_git,
        _build_info_from_environment,
        _build_info_from_secrets,
    ):
        info = provider()
        if info is not None:
            count, sha = info
            return f"v{count} · build {sha}"
    return None


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