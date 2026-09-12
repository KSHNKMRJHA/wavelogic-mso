"""WaveLogic MSO — Step-by-step user guide."""
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

page_setup("User Guide", "🧑‍💻")

st.header("Step-by-step guide")

st.markdown(
    f"Everything below is a workflow, not a feature lecture. After each step "
    f"you will have used a different part of {APP_NAME}."
)

st.subheader("1. Use the sample capture")
with st.expander("No CSV handy? Generate one right now", expanded=False):
    st.markdown(
        "Two-channel capture sample upload "
        "*(`sample_data/uart_example.csv` in the repository)*:\n"
        "```csv\n"
        "Time(s),TX\n"
        "0.000000,3.3\n"
        "0.000104,0.0\n"
        "...\n"
        "```\n"
        "Or export any CSV from your scope/logic analyzer — see step 4 for the "
        "exact format the import expects."
    )

st.subheader("2. Launch the app")
st.code(
    "python -m venv .venv\n"
    ".venv\\Scripts\\activate        # Windows\n"
    "python -m pip install -r requirements.txt\n"
    "streamlit run app.py",
    language="bash",
)
st.markdown(
    "Browser opens on **http://localhost:8501**. The analyzer is the entry "
    "page; the sidebar shows additional pages (Introduction, User Guide, "
    "Features, Credits)."
)

st.subheader("3. Import a CSV")
st.markdown(
    "- Click **Upload oscilloscope CSV**.  \n"
    "- Pick the delimiter: **Comma**, **Semicolon** or **Tab**.  \n"
    "- If the file has metadata lines above the header, set **Metadata rows "
    "before header** to skip them.  \n"
    "- The app auto-detects the time column; override it with the **Time "
    "column** dropdown if needed."
)

st.subheader("4. CSV format reference")
st.markdown(
    "One numeric time column plus one or more numeric channel columns. "
    "Values are in volts for voltage visualization."
)
st.code(
    "Time(s),CH1,CH2\n"
    "0.000000,3.3,1.20\n"
    "0.000001,3.3,1.21\n"
    "0.000002,0.0,1.22",
    language="text",
)
st.markdown(
    "Duplicate or non-monotonic timestamps are tolerated: the decoder "
    "reconstructs a uniform time base automatically and tells you when it does. "
    "This is exactly the case that used to make decoding fail."
)

st.subheader("5. View channels on the shared time axis")
st.markdown(
    "- **Show simultaneously** — tick the channels you want to draw.  \n"
    "- The plot uses a shared time axis with transparent overlays and a " 
    "per-channel color from the palette.  \n"
    "- **Decimation** is automatic for large files so the chart stays "
    "responsive; the exports always use full resolution."
)

st.subheader("6. Zoom and cursor readouts")
st.markdown(
    "Use the Plotly mode bar: **box zoom**, **pan**, **home**. Clicking the "
    "crosshair tool update the cursor readouts at the bottom, which show "
    "per-channel values and time deltas at the current pointer position."
)

st.subheader("7. Create math channels")
st.markdown(
    "- **Enable math channels** — adds **Differential (A - B)** and "
    "**Invert (A)** computed channels to the plot.  \n"
    "- **Window readouts** compute **edge frequency**, **duty cycle**, "
    "**logic levels** and **transition counts** for the currently viewed "
    "time window."
)

st.subheader("8. Decode a UART frame")
st.markdown(
    "UART is the fastest way to see a decode:\n"
    "1. **Enable decoding** under *Signal decoding (protocol analyzer)*.  \n"
    "2. Protocol → **UART / RS-232**.  \n"
    "3. **Decoder source** → the TX channel (there is a sample "
    "`uart_example.csv` in the repo).  \n"
    "4. Baud = **9600**, 8 data bits, no parity, 1 stop bit, idle HIGH.  \n"
    "5. Read the decoded frames: byte number, hex, decimal, ASCII, bit order "
    "and framing/parity status."
)

st.subheader("9. Decode SPI or I2C")
st.markdown(
    "Multi-channel decoders need their channels **visible** in the sidebar "
    "first:\n"
    "- **SPI**: clock (SCLK), master TX (MOSI), slave RX (MISO), chip select "
    "(SS/CS). Configure CPOL/CPHA, active level, bits per word.\n"
    "- **I2C**: SCL + SDA. The decoder prints the full transaction: START, "
    "address + R/W, ACK/NACK per byte, data bytes, STOP."

    "\n\nIf a required channel is missing, the decoder says so instead of "
    "guessing."
)

st.subheader("10. Decode high-level and analog signals")
st.markdown(
    "- **Manchester / Differential Manchester** — for M-Bus/encoder edges, "
    "with bit alignment handling.\n"
    "- **NRZ** — clocked NRZ with phase, bits-per-word and MSB-first options.\n"
    "- **PWM** — measures per-pulse period and duty directly from the waveform."
)

st.subheader("11. Export results")
st.markdown(
    "When a decode succeeds you get:\n"
    "- **Per-protocol CSV** of the decoded table(s).  \n"
    "- **Summary text log** of metrics and decode transcript.  \n"
    "- **Offline interactive HTML** chart of the visible window (Plotly "
    "embedded, no CDN needed).  \n"
    "- **Full-resolution window CSV** and a **ZIP** with everything above."
)

st.success(
    "The whole flow — import, view, zoom, math, decode, export — runs locally "
    f"with {APP_NAME}. No account, no license, no sign-up."
)

render_brand_footer()