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

st.subheader("Overall workflow")
st.markdown(
    "1. Start WaveLogic MSO.  \n"
    "2. Upload/import a CSV capture.  \n"
    "3. Verify the detected time column and channels.  \n"
    "4. Select a protocol.  \n"
    "5. Configure that protocol.  \n"
    "6. Analyze / decode.  \n"
    "7. Inspect the waveform.  \n"
    "8. Inspect the decoded results.  \n"
    "9. Export results if required.  \n"
    "10. Use **Debug & Logs** when troubleshooting."
)

st.subheader("1. Use the sample capture")
with st.expander("No CSV handy? Use the sample", expanded=False):
    st.markdown(
        "Two-channel capture sample "
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
    "column** dropdown if needed, and set **CSV time unit** if the file is not "
    "in seconds.  \n"
    "- Use **Time-axis mode** to choose how time is handled (see step 5)."
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

st.subheader("5. Time axis and timestamp quality")
st.markdown(
    "- With clean, usable timestamps the capture can be used directly "
    "(**Use CSV timestamps directly**).  \n"
    "- Low-quality, quantized, duplicated or non-monotonic timestamps are "
    "detected automatically and default to **Reconstruct uniform timestamps**, "
    "which builds a uniform time axis from row order and the capture duration.  \n"
    "- Importantly, this only affects the *time axis* used for display and "
    "decoding. The underlying channel samples passed to the decoders remain the "
    "full-resolution waveform; exports keep both the original and applied "
    "timestamps."
)

st.subheader("6. View channels on the shared time axis")
st.markdown(
    "- **Show simultaneously** — tick the channels you want to draw.  \n"
    "- The plot uses a shared time axis with transparent overlays and a "
    "per-channel color from the palette.  \n"
    "- Display simplification is automatic for large files so the chart stays "
    "responsive (adjust with **Total plotted-point budget**); decoding and "
    "exports always use full resolution."
)

st.subheader("7. Zoom and cursor readouts")
st.markdown(
    "Use the Plotly mode bar: **box zoom**, **pan**, **home**. The crosshair "
    "tool updates the cursor readouts, which show per-channel values and time "
    "deltas at the current pointer position."
)

st.subheader("8. Create math channels")
st.markdown(
    "- **Add differential math channel** — adds a computed **Math A - Math B** "
    "trace to the plot.  \n"
    "- **Channel display controls** let you set **Display gain**, **Display "
    "offset (V)** and **Invert display** per channel. These affect display only; "
    "decoders always use raw voltage samples."
)

st.subheader("9. Decode a UART frame")
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

st.subheader("10. Decode SPI or I2C")
st.markdown(
    "Multi-channel decoders need their channels **visible** in the sidebar "
    "first:\n"
    "- **SPI**: clock (SCLK), master TX (MOSI), slave RX (MISO), chip select "
    "(SS/CS). Configure CPOL/CPHA, active level, bits per word.\n"
    "- **I2C**: SCL + SDA. The decoder prints the full transaction: START, "
    "address + R/W, ACK/NACK per byte, data bytes, STOP.\n\n"
    "If a required channel is missing, the decoder says so instead of guessing."
)

st.subheader("11. Differential Manchester")
st.markdown(
    "Differential Manchester has two explicit **Analysis mode** options. Pick "
    "the mode first, then the channels and timing."
)

st.markdown("**Step A — Select the protocol**")
st.markdown("Protocol → **Differential Manchester (legacy project)**.")

st.markdown("**Step B — Choose Analysis mode**")
st.markdown(
    "- **Multi-message / Burst Scan** *(default)* — recommended for captures "
    "that may contain one or more messages. It scans the selected window for "
    "independently validated messages and reports each one separately. You do "
    "**not** need to crop the capture to a single frame.  \n"
    "- **Single Frame** — use this when you have deliberately narrowed the "
    "window to one frame and want the legacy single-frame decoder for detailed "
    "analysis of that frame."
)

st.markdown("**Step C — Select Channel A / Channel B**")
st.markdown(
    "- Choose the two waveform channels that carry the differential pair.  \n"
    "- The UI may show a suggestion such as *Suggested differential pair: "
    "CH3(V) / CH4(V)* when two channels are clearly the most active. The "
    "suggestion is only a convenience and is **not** a guaranteed protocol "
    "identification — you can always choose the channels manually.  \n"
    "- Some captures use CH3/CH4; treat that as an example, not a rule."
)

st.markdown("**Step D — Timing configuration**")
st.markdown(
    "- **Nominal bit time (µs)** — expressed in microseconds; defaults to "
    "`12.8 µs`. Adjust it if the capture uses different timing.  \n"
    "- **Preamble bit count** (default 22), **Clock alignment**, and "
    "**Transition hold-off (µs)** are also available.  \n"
    "- `12.8 µs` is an empirical default for this workflow, **not** a universal "
    "Differential Manchester protocol specification."
)

st.markdown("**Step E — Read the results (Multi-message / Burst Scan)**")
st.markdown(
    "A successful scan shows the **Validated messages** count, a compact "
    "per-message summary table, a **Select message** dropdown, and the full "
    "detail for the selected message (status chips, metrics, decoded bits, "
    "packet bytes, pulse timing, frame summary, waveform figure and text "
    "summary).\n\n"
    "Only **independently validated** messages are presented as detected "
    "messages — not every region of electrical activity becomes a decoded "
    "message. If nothing is validated, the panel reports the scanner status, "
    "candidate regions, decoder calls and selected settings so you can adjust "
    "the channel pair or bit time."
)

st.markdown("**Single Frame — threshold controls**")
st.markdown(
    "In Single Frame mode you also get **Threshold mode** (Automatic / Manual) "
    "with LOW/HIGH threshold inputs, plus the timing controls above. Manual "
    "thresholds apply to Single Frame only."
)

st.warning(
    "Long window in Single Frame? If the app reports that the selected window "
    "spans too many half-bit cells, the window is too large for the single-frame "
    "decoder. This is intentional protection and your data is never silently "
    "cropped. Either narrow the **Window** controls to one frame, or switch "
    "**Analysis mode** to **Multi-message / Burst Scan**."
)

st.subheader("12. Decode NRZ and PWM")
st.markdown(
    "- **NRZ** — clocked NRZ with phase, bits-per-word and MSB-first options.\n"
    "- **PWM** — measures per-pulse period and duty directly from the waveform."
)

st.subheader("13. Export results")
st.markdown(
    "When a decode succeeds you get:\n"
    "- **Per-protocol CSV** of the decoded table(s).  \n"
    "- **Summary text log** of metrics and decode transcript.  \n"
    "- **Offline interactive HTML** chart of the visible window (Plotly "
    "embedded, no CDN needed).  \n"
    "- **Full-resolution window CSV** and a **ZIP** with everything above.  \n"
    "For Differential Manchester burst scans, message-level CSVs "
    "(`dm_messages_summary.csv`, `dm_messages_bits.csv`) are included too."
)

st.subheader("14. Debug & Logs")
st.markdown(
    "At the bottom of the page is an opt-in **Debug & Logs** section, **disabled "
    "by default**. Enable **Enable debug & diagnostic logs** to see application "
    "and runtime information, `analyzer_core` import diagnostics, imported-API "
    "verification, the current application state, the most recent exception, and "
    "the bounded recent log records.\n\n"
    "It also offers **Download debug log**, **Download diagnostics** (JSON) and "
    "**Clear debug log**. Diagnostics are observational only — no secrets, "
    "credentials, environment variables or uploaded waveform contents are shown "
    "or included in the downloads."
)

st.success(
    "The whole flow — import, view, zoom, math, decode, export and diagnose — "
    f"runs locally with {APP_NAME}. No account, no license, no sign-up."
)

render_brand_footer()
