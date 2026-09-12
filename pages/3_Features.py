"""WaveLogic MSO — Feature list page."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from branding import (  # noqa: E402
    APP_NAME,
    page_setup,
    render_brand_footer,
)

page_setup("Features", "📊")

st.header("Features")

st.markdown(
    f"Everything below ships inside {APP_NAME}. There is no separate "
    f"'pro' tier and nothing is paywalled."
)

st.subheader("Scope & measurement")
scope = [
    ("Simultaneous channels", "Any subset of channels on one shared time axis, with transparent color-coded overlays."),
    ("Automatic decimation", "Large captures stay responsive; exports always keep full resolution."),
    ("Crosshair cursors", "Pointer readouts with per-channel values and time deltas."),
    ("Differential & inverted channels", "A - B math and inverted copies, drawn as real traces."),
    ("Window readouts", "Edge frequency, duty cycle, logic levels, transition counts, per-window."),
    ("Offline HTML export", "Self-contained Plotly chart of the visible window; no CDN required."),
]

st.subheader("Protocol decoders")
decoders = [
    ("UART / RS-232", "Baud, data bits, parity, stop bits, idle level, bit order; per-frame framing/parity status."),
    ("SPI (4-wire)", "CPOL/CPHA, active chip-select level, bits per word, MSB-first option, CS-gap merging."),
    ("I2C (7-bit)", "Full transaction transcript: START, address + R/W, ACK/NACK per byte, STOP; end-of-stream robust."),
    ("Manchester (Biphase-L)", "Standard bit alignment with midpoint transition handling."),
    ("Differential Manchester (legacy)", "Original project convention; midpoint transition means 0; 16-bit boundaries aligned."),
    ("NRZ (clocked)", "Phase alignment, bits per word, MSB-first, robust clock fitting."),
    ("PWM", "Per-pulse period and duty measured directly from the waveform, with stable clock domain checks."),
]

st.subheader("Robustness & quality")
robust = [
    ("Timestamp repair", "Duplicate or non-monotonic timestamps no longer break decoding; a uniform time base is reconstructed and reported."),
    ("Schmitt-style logic extraction", "Noise-resistant hysteresis thresholding of analog samples into 0/1 levels."),
    ("Status chips everywhere", "OK / FAIL / WARNING per decode, plus per-protocol metrics tiles (BAUD, frames, NACK, duty, ...)."),
    ("Plain-text decode log", "A human-readable transcript you can copy into a bug report or JIRA ticket."),
    ("Local-first", "Everything runs in your browser locally; no cloud submission of your capture data."),
]

for title, rows in (
    ("Scope & measurement", scope),
    ("Protocol decoders", decoders),
    ("Robustness & quality", robust),
):
    st.subheader(title)
    for name, text in rows:
        st.markdown(f"- **{name}** — {text}")

st.markdown("---")
st.markdown(
    "Not on the list? The project is open source — open an issue or a pull "
    "request on GitHub and help make it cover more tools and protocols."
)

render_brand_footer()