from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib
import zipfile

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from analyzer_core import (
    analyze_timestamp_quality,
    bits_to_hex,
    bits_to_string,
    channel_candidates,
    create_figure,
    dataframe_csv_bytes,
    decode_i2c,
    decode_manchester,
    decode_nrz,
    decode_pwm,
    decode_spi,
    decode_uart,
    decode_waveform,
    detect_transitions,
    estimate_logic_levels_and_thresholds,
    find_time_column,
    group_bits,
    prepare_time_axis,
)

from branding import page_setup, render_brand_footer


st.set_page_config(
    page_title="WaveLogic MSO — Multi-Channel Protocol Analyzer",
    page_icon="📈",
    layout="wide",
)

COLORS = [
    "#FFD43B",
    "#4DABF7",
    "#FF6B6B",
    "#69DB7C",
    "#DA77F2",
    "#FFA94D",
    "#66D9E8",
    "#F783AC",
]

TIME_FACTORS = {
    "Seconds": 1.0,
    "Milliseconds": 1e-3,
    "Microseconds": 1e-6,
    "Nanoseconds": 1e-9,
}

PLOT_CONFIG = {
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True,
    "toImageButtonOptions": {
        "format": "png",
        "filename": "multi_channel_waveform",
        "scale": 2,
    },
}


# ============================================================
# CORPORATE MSO-STYLE THEME
# ============================================================
MSO_CSS = """
<style>
:root {
    --mso-bg: #0b1220;
    --mso-panel: #111a2e;
    --mso-panel-2: #16213a;
    --mso-border: #233252;
    --mso-accent: #3b82f6;
    --mso-accent-2: #6366f1;
    --mso-text: #dbe4f5;
    --mso-muted: #7f90b0;
    --mso-good: #22c55e;
    --mso-bad: #ef4444;
    --mso-warn: #f59e0b;
}

html, body, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1200px 500px at 20% -10%, rgba(59,130,246,0.12), transparent 60%),
        radial-gradient(1000px 420px at 85% -10%, rgba(99,102,241,0.10), transparent 60%),
        var(--mso-bg);
    color: var(--mso-text);
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { right: 2rem; }

.block-container { padding-top: 1.2rem; max-width: 1500px; }

h1, h2, h3 { color: #f1f5fb !important; letter-spacing: -0.01em; }
h1 { font-size: 1.55rem !important; font-weight: 700 !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0e1728 0%, #0a1220 100%);
    border-right: 1px solid var(--mso-border);
}
[data-testid="stSidebar"] hr { border-color: var(--mso-border); }

.mso-header {
    display: flex; align-items: center; gap: 14px;
    padding: 10px 18px; margin-bottom: 14px;
    border: 1px solid var(--mso-border);
    border-radius: 12px;
    background: linear-gradient(90deg, var(--mso-panel) 0%, #0d1730 100%);
    box-shadow: 0 4px 24px rgba(0,0,0,0.35);
}
.mso-logo {
    width: 42px; height: 42px; border-radius: 10px; flex: 0 0 auto;
    background: linear-gradient(135deg, var(--mso-accent), var(--mso-accent-2));
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; color: #fff;
}
.mso-title { flex: 1; }
.mso-title .main { font-size: 1.05rem; font-weight: 700; color: #f1f5fb; }
.mso-title .sub { font-size: 0.78rem; color: var(--mso-muted); }
.mso-badge {
    font-size: 0.7rem; letter-spacing: 0.08em; color: #c7d5f2;
    border: 1px solid var(--mso-border); border-radius: 999px;
    padding: 4px 10px; background: rgba(59,130,246,0.08); white-space: nowrap;
}

[data-testid="stMetric"] {
    background: var(--mso-panel);
    border: 1px solid var(--mso-border);
    border-radius: 10px;
    padding: 10px 14px;
}
[data-testid="stMetricValue"] { font-size: 1.25rem !important; color: #f1f5fb; }
[data-testid="stMetricLabel"] { font-size: 0.72rem; color: var(--mso-muted); }

.chip {
    display: inline-flex; align-items: center; gap: 7px;
    border-radius: 999px; padding: 6px 14px; margin: 2px 6px 2px 0;
    font-size: 0.78rem; font-weight: 600; border: 1px solid transparent;
}
.chip .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.chip.good { color: var(--mso-good); border-color: rgba(34,197,94,0.35); background: rgba(34,197,94,0.10); }
.chip.good .dot { background: var(--mso-good); }
.chip.bad  { color: var(--mso-bad); border-color: rgba(239,68,68,0.35); background: rgba(239,68,68,0.10); }
.chip.bad .dot  { background: var(--mso-bad); }
.chip.warn { color: var(--mso-warn); border-color: rgba(245,158,11,0.35); background: rgba(245,158,11,0.10); }
.chip.warn .dot { background: var(--mso-warn); }
.chip.neutral { color: var(--mso-muted); border-color: var(--mso-border); background: var(--mso-panel-2); }
.chip.neutral .dot { background: var(--mso-muted); }

.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--mso-border); }
.stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 6px 16px; color: var(--mso-muted); }
.stTabs [aria-selected="true"] { color: #fff; background: rgba(59,130,246,0.12); }

[data-testid="stExpander"] {
    border: 1px solid var(--mso-border) !important;
    border-radius: 10px !important;
    background: var(--mso-panel) !important;
}
[data-testid="stExpander"] summary { color: #dbe4f5; }

button[kind="primary"] {
    background: linear-gradient(135deg, var(--mso-accent), var(--mso-accent-2)) !important;
    border: none !important;
    border-radius: 8px !important;
}
code, pre {
    border-radius: 8px !important;
    background: #0a1122 !important;
    border: 1px solid var(--mso-border) !important;
}
[data-testid="stDataFrame"] { border: 1px solid var(--mso-border); border-radius: 10px; overflow: hidden; }
</style>
"""


def inject_mso_theme() -> None:
    st.markdown(MSO_CSS, unsafe_allow_html=True)


def render_header() -> None:
    st.markdown(
        """
        <div class="mso-header">
            <div class="mso-logo">&#9674;</div>
            <div class="mso-title">
                <div class="main">WaveLogic MSO — Multi-Channel Protocol Analyzer</div>
                <div class="sub">CSV oscilloscope import &middot; universal signal decoding &middot; offline exports</div>
            </div>
            <div class="mso-badge">SCOPE + DECODE PACK</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# FILE AND DISPLAY HELPERS
# ============================================================
@st.cache_data(show_spinner=False, max_entries=3, ttl=3600)
def read_csv_cached(
    content: bytes,
    separator: str,
    skiprows: int,
) -> pd.DataFrame:
    """Cache parsing only; do not enable disk persistence."""
    frame = pd.read_csv(
        BytesIO(content),
        sep=separator,
        skiprows=skiprows,
        encoding="utf-8-sig",
    )

    frame.columns = [str(column).strip() for column in frame.columns]

    if frame.empty:
        raise ValueError("The CSV contains no data rows.")

    if not frame.columns.is_unique:
        raise ValueError("Column names must be unique after removing whitespace.")

    return frame


def display_envelope(
    x: np.ndarray,
    y: np.ndarray,
    budget: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Downsample for display only.

    Preserve bucket endpoints, extrema, and representative NaN gaps.
    Returned indices also allow hover data to retain original voltages.
    """
    n = len(x)

    if n <= budget:
        indices = np.arange(n)
        return x, y, indices

    bucket_count = max(1, budget // 6)
    edges = np.linspace(0, n, bucket_count + 1, dtype=int)

    selected: list[int] = []

    for left, right in zip(edges[:-1], edges[1:]):
        if right <= left:
            continue

        segment = y[left:right]
        valid = np.flatnonzero(np.isfinite(segment))
        missing = np.flatnonzero(~np.isfinite(segment))

        candidates = {left, right - 1}

        if len(valid):
            finite_values = segment[valid]
            candidates.add(left + int(valid[np.argmin(finite_values)]))
            candidates.add(left + int(valid[np.argmax(finite_values)]))

        if len(missing):
            candidates.add(left + int(missing[0]))
            candidates.add(left + int(missing[-1]))

        selected.extend(sorted(candidates))

    indices = np.asarray(selected, dtype=int)
    return x[indices], y[indices], indices


def make_scope_figure(
    time_us: np.ndarray,
    signals: dict[str, np.ndarray],
    settings: dict[str, dict],
    stacked: bool,
    total_budget: int,
    cursor_a: float | None,
    cursor_b: float | None,
    revision: str,
) -> go.Figure:
    names = list(signals)
    rows = len(names) if stacked else 1

    if stacked:
        figure = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=min(0.035, 0.20 / rows),
            subplot_titles=names,
        )
    else:
        figure = make_subplots(rows=1, cols=1)

    # Keep the overall display load bounded as channels are added.
    per_trace_budget = max(6, total_budget // len(names))

    for position, name in enumerate(names):
        row = position + 1 if stacked else 1
        options = settings[name]

        raw_voltage = signals[name]
        sign = -1.0 if options["invert"] else 1.0

        display_voltage = (
            raw_voltage * sign * options["gain"]
            + options["offset"]
        )

        display_time, display_y, indices = display_envelope(
            time_us,
            display_voltage,
            per_trace_budget,
        )

        figure.add_trace(
            go.Scattergl(
                x=display_time,
                y=display_y,
                customdata=raw_voltage[indices],
                name=name,
                mode="lines",
                connectgaps=False,
                line={
                    "color": options["color"],
                    "width": 1.3,
                },
                hovertemplate=(
                    "Time: %{x:.6f} µs"
                    "<br>Raw voltage: %{customdata:.6f} V"
                    "<br>Display value: %{y:.6f}"
                    "<extra>%{fullData.name}</extra>"
                ),
            ),
            row=row,
            col=1,
        )

    for row in range(1, rows + 1):
        figure.update_yaxes(
            title_text="Display V",
            showgrid=True,
            zeroline=True,
            row=row,
            col=1,
        )

        for value, color in (
            (cursor_a, "#FFFFFF"),
            (cursor_b, "#FF922B"),
        ):
            if value is not None:
                figure.add_vline(
                    x=value,
                    line_color=color,
                    line_dash="dash",
                    line_width=1,
                    row=row,
                    col=1,
                )

    figure.update_xaxes(
        showgrid=True,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        # Explicitly show the requested window.
        range=[float(time_us[0]), float(time_us[-1])],
    )

    figure.update_xaxes(
        title_text="Time from capture start (µs)",
        row=rows,
        col=1,
    )

    figure.update_layout(
        template="plotly_dark",
        height=max(540, min(1600, 230 * rows)) if stacked else 650,
        title="Multi-channel oscilloscope view",
        hovermode="x unified",
        dragmode="zoom",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
        },
        margin={"l": 65, "r": 25, "t": 100, "b": 60},
        uirevision=revision,
    )

    return figure


def build_zip(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    return buffer.getvalue()


# ============================================================
# OPTIONAL DECODER
# ============================================================
def render_decoder(
    time_s: np.ndarray,
    signals: dict[str, np.ndarray],
    capture_origin_s: float,
    timestamp_quality: dict,
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    st.subheader("Signal decoding (protocol analyzer)")

    enabled = st.checkbox(
        "Enable decoding",
        value=False,
        help=(
            "Waveform viewing does not require decoding. Enable a protocol, then "
            "select the channels it uses. Every channel a decoder needs must be "
            "checked under 'Visible channels' in the sidebar."
        ),
    )

    if not enabled:
        return files

    strict = len(time_s) > 1 and bool(np.all(np.diff(time_s) > 0))

    if not strict:
        st.warning(
            "Selected window timestamps are not strictly increasing (duplicates or "
            "resets). Protocol decoders require strictly increasing time, so a uniform "
            "time axis reconstructed across this window will be used for decoding. "
            "The scope view, statistics, and CSV export are not affected."
        )

    axis_choice = st.radio(
        "Decoder time axis",
        ["CSV timestamps", "Uniform reconstruction"],
        index=0 if strict else 1,
        horizontal=True,
        help=(
            "Uniform reconstruction assumes evenly spaced samples between the window's "
            "first and last timestamp. It is the safe choice when the CSV contains "
            "duplicate or non-monotonic timestamps."
        ),
    )

    if axis_choice == "Uniform reconstruction":
        decode_time = np.linspace(float(time_s[0]), float(time_s[-1]), len(time_s))
        time_axis_note = "uniform-reconstructed"
    else:
        decode_time = np.asarray(time_s, dtype=float)
        time_axis_note = "CSV timestamps"

    if not np.all(np.diff(decode_time) > 0):
        st.error("The decoder time axis is not strictly increasing. Nothing was decoded.")
        return files

    if len(decode_time) < 20:
        st.error("Select a window containing at least 20 samples for decoding.")
        return files

    st.caption(
        f"Decoding will run on the **{time_axis_note}** axis. "
        "Display gain/offset/inversion never affect decoding (raw voltages are used)."
    )

    protocol = st.selectbox(
        "Protocol",
        [
            "Differential Manchester (legacy project)",
            "Manchester (Biphase-L)",
            "UART / RS-232",
            "SPI (4-wire master view)",
            "I2C (7-bit)",
            "NRZ (clocked)",
            "PWM / pulse-width",
        ],
        help=(
            "Legacy Differential Manchester keeps the original project's convention "
            "(midpoint transition = 0). All other decoders use standard conventions. "
            "UART, Manchester, NRZ, and PWM need one source channel; SPI needs 4 and "
            "I2C needs 2. Required channels must be shown in the sidebar."
        ),
    )

    missing = [name for name in signals if not np.all(np.isfinite(signals[name]))]
    if missing:
        st.warning(
            "Channels with missing/nonfinite samples in this window: "
            + ", ".join(missing)
            + ". Decoders sample logic levels; keep the window centered on valid data."
        )

    def pick_channel(prompt: str, exclude: set[str] | None = None) -> str | None:
        options = [c for c in signals if c not in (exclude or set())]
        if not options:
            st.error(f"No channel is available for {prompt}.")
            return None
        return st.selectbox(prompt, options)

    def render_result(result: dict) -> None:
        st.markdown(f"#### {result['protocol']} decode result")

        status = result.get("status") or []
        if status:
            column_count = min(len(status), 6)
            columns = st.columns(column_count)
            for index, (label, ok) in enumerate(status[:column_count]):
                with columns[index % column_count]:
                    if isinstance(ok, bool):
                        tone = "good" if ok else "bad"
                        text_piece = f"{label}: {'PASS' if ok else 'FAIL'}"
                    else:
                        tone = "neutral"
                        text_piece = f"{label}: {ok}"
                    st.markdown(
                        f'<span class="chip {tone}"><span class="dot"></span>{text_piece}</span>',
                        unsafe_allow_html=True,
                    )

        metrics = result.get("metrics") or []
        if metrics:
            columns = st.columns(min(len(metrics), 6))
            for index, (label, value) in enumerate(metrics[:6]):
                with columns[index % len(columns)]:
                    st.metric(label, value)

        figure = result.get("figure")
        if figure is not None:
            st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)
            files["decoded_waveform.html"] = figure.to_html(
                full_html=True,
                include_plotlyjs=True,
                config=PLOT_CONFIG,
            ).encode("utf-8")

        tables = result.get("tables") or []
        if tables:
            tabs = st.tabs([name for name, _ in tables])
            for tab, (_, frame) in zip(tabs, tables):
                with tab:
                    st.dataframe(frame, width="stretch", hide_index=True)

        if result.get("text"):
            st.code(result["text"], language="text")

        for name, frame in tables:
            safe_name = (
                name.lower()
                .replace(" ", "_")
                .replace("/", "_")
                .replace("(", "")
                .replace(")", "")
            )
            files[f"{safe_name}.csv"] = dataframe_csv_bytes(frame)

        if result.get("text"):
            files["decoded_summary.txt"] = result["text"].encode("utf-8")

    result = None

    try:
        if protocol == "Differential Manchester (legacy project)":
            source = pick_channel("Decoder source")
            if source is None:
                return files
            voltage = np.asarray(signals[source], dtype=float)

            with st.expander("Legacy decoder configuration", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    nominal_bit_us = st.number_input(
                        "Nominal bit time (µs)",
                        min_value=0.001,
                        value=12.8,
                        step=0.1,
                        format="%.4f",
                    )
                    preamble_count = st.number_input(
                        "Preamble bit count",
                        min_value=1,
                        value=22,
                        step=1,
                    )
                with col2:
                    alignment = st.selectbox(
                        "Clock alignment",
                        [
                            "First transition is bit start",
                            "First transition is midpoint",
                        ],
                    )
                    holdoff_us = st.number_input(
                        "Transition hold-off (µs)",
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        format="%.4f",
                    )
                with col3:
                    threshold_mode = st.radio(
                        "Threshold mode",
                        ["Automatic", "Manual"],
                    )
                    levels = estimate_logic_levels_and_thresholds(voltage)
                    if threshold_mode == "Automatic":
                        low_threshold = float(levels["low_threshold"])
                        high_threshold = float(levels["high_threshold"])
                    else:
                        low_threshold = st.number_input(
                            "LOW threshold (V)",
                            value=float(levels["low_threshold"]),
                            step=0.05,
                            format="%.5f",
                        )
                        high_threshold = st.number_input(
                            "HIGH threshold (V)",
                            value=float(levels["high_threshold"]),
                            step=0.05,
                            format="%.5f",
                        )

            logic, indices, transition_times = detect_transitions(
                decode_time,
                voltage,
                low_threshold,
                high_threshold,
                holdoff_us,
            )
            decoded = decode_waveform(
                decode_time,
                voltage,
                logic,
                indices,
                transition_times,
                nominal_bit_us,
                alignment,
                int(preamble_count),
            )

            summary = decoded["frame_summary"].copy()
            summary["Source"] = source
            summary["Convention"] = "Legacy: midpoint transition = 0"
            summary["TimestampModeApplied"] = timestamp_quality["applied_mode"]
            summary["WindowStartFromCapture_us"] = (
                float(decode_time[0]) - capture_origin_s
            ) * 1e6
            summary["LowThreshold_V"] = low_threshold
            summary["HighThreshold_V"] = high_threshold
            summary["TransitionHoldoff_us"] = holdoff_us
            summary["DecoderTimeAxis"] = time_axis_note

            packet_string = bits_to_string(decoded["packet_data_bits"])
            packet_hex, _ = bits_to_hex(packet_string)
            byte_table = pd.DataFrame(
                bits_to_hex(packet_string)[1],
                columns=["ByteNumber", "Binary", "Hex", "Decimal", "CompleteByte"],
            )

            text = "\n".join([
                f"Source: {source}",
                "Convention: legacy midpoint transition = 0",
                f"Decoder time axis: {time_axis_note}",
                f"Clock fit pass: {decoded['clock_quality_pass']}",
                f"Preamble valid: {decoded['preamble_valid']}",
                f"Sync valid: {decoded['sync_valid']}",
                "",
                "Complete decoded bits:",
                bits_to_string(decoded["bits"]),
                "",
                "Packet bits:",
                group_bits(packet_string),
                "",
                "Packet HEX (MSB-first complete bytes):",
                packet_hex or "No complete bytes",
            ])

            detail_figure = None
            if len(decoded["bits"]) <= 300 and len(decoded["pulses"]) <= 1000:
                detail_figure = create_figure(
                    decoded,
                    source,
                    30_000,
                    low_threshold,
                    high_threshold,
                )

            result = {
                "protocol": "Legacy Differential Manchester",
                "metrics": [
                    ("Decoded bits", str(len(decoded["bits"]))),
                    ("Fitted bit time", f"{decoded['fitted_bit_us']:.4f} µs"),
                    ("Preamble", "PASS" if decoded["preamble_valid"] else "FAIL"),
                    ("Sync", "PASS" if decoded["sync_valid"] else "FAIL"),
                ],
                "status": [
                    ("Clock fit", decoded["clock_quality_pass"]),
                    ("Preamble valid", decoded["preamble_valid"]),
                    ("Sync valid", decoded["sync_valid"]),
                ],
                "tables": [
                    ("Decoded bits", decoded["decoded"]),
                    ("Packet bytes", byte_table),
                    ("Pulse timing", decoded["pulses"]),
                    ("Frame summary", summary),
                ],
                "text": text,
                "figure": detail_figure,
            }

        elif protocol == "Manchester (Biphase-L)":
            source = pick_channel("Decoder source")
            if source is None:
                return files
            voltage = np.asarray(signals[source], dtype=float)
            levels = estimate_logic_levels_and_thresholds(voltage)
            with st.expander("Manchester configuration", expanded=True):
                col1, col2 = st.columns(2)
                nominal_bit_us = col1.number_input(
                    "Nominal bit time (µs)",
                    min_value=0.001,
                    value=25.0,
                    step=0.1,
                    format="%.4f",
                )
                convention = col2.selectbox(
                    "Midpoint convention",
                    ["LOW->HIGH = 1", "LOW->HIGH = 0"],
                    help="IEEE convention is LOW->HIGH = 1.",
                )
            result = decode_manchester(
                decode_time,
                voltage,
                float(levels["low_threshold"]),
                float(levels["high_threshold"]),
                nominal_bit_us,
                mid_low_high_is_one=(convention == "LOW->HIGH = 1"),
            )

        elif protocol == "UART / RS-232":
            source = pick_channel("Decoder source")
            if source is None:
                return files
            voltage = np.asarray(signals[source], dtype=float)
            with st.expander("UART configuration", expanded=True):
                col1, col2, col3 = st.columns(3)
                baud = col1.number_input(
                    "Baud rate",
                    min_value=1.0,
                    value=9600.0,
                    step=100.0,
                    format="%g",
                )
                data_bits = col2.selectbox("Data bits", [5, 6, 7, 8, 9], index=3)
                parity = col3.selectbox("Parity", ["none", "even", "odd"])
                col4, col5, col6 = st.columns(3)
                stop_bits = col4.selectbox("Stop bits", [1.0, 1.5, 2.0])
                idle = col5.selectbox("Idle level", ["HIGH", "LOW"])
                bit_order = col6.selectbox(
                    "Bit order",
                    ["LSB first (typical)", "MSB first"],
                )
            levels = estimate_logic_levels_and_thresholds(voltage)
            result = decode_uart(
                decode_time,
                voltage,
                float(levels["low_threshold"]),
                float(levels["high_threshold"]),
                baud,
                int(data_bits),
                parity,
                float(stop_bits),
                idle,
                invert=False,
                lsb_first=(bit_order == "LSB first (typical)"),
            )

        elif protocol == "SPI (4-wire master view)":
            skip: set[str] = set()
            clk_ch = pick_channel("SPI clock (SCLK)", skip)
            if clk_ch is None:
                return files
            skip.add(clk_ch)
            mosi_ch = pick_channel("Master TX (MOSI)", skip)
            if mosi_ch is None:
                return files
            skip.add(mosi_ch)
            miso_ch = pick_channel("Slave RX (MISO)", skip)
            if miso_ch is None:
                return files
            skip.add(miso_ch)
            cs_ch = pick_channel("Chip select (SS/CS)", skip)
            if cs_ch is None:
                return files
            with st.expander("SPI configuration", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                cpol = col1.selectbox(
                    "CPOL",
                    [0, 1],
                    help="Clock idle level; 0 = idles LOW.",
                )
                cpha = col2.selectbox(
                    "CPHA",
                    [0, 1],
                    help="0 = sample on leading edge, 1 = on trailing edge.",
                )
                cs_active = col3.selectbox("CS active", ["LOW", "HIGH"])
                bits_per_word = col4.number_input(
                    "Bits per word",
                    min_value=1,
                    max_value=32,
                    value=8,
                    step=8,
                )
                col5, col6 = st.columns(2)
                bit_order = col5.selectbox(
                    "Bit order",
                    ["MSB first (typical)", "LSB first"],
                )
                merge_gap = col6.number_input(
                    "Merge CS gaps (µs)",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    format="%.3f",
                )
            result = decode_spi(
                decode_time,
                signals[clk_ch],
                signals[mosi_ch],
                signals[miso_ch],
                signals[cs_ch],
                int(cpol),
                int(cpha),
                cs_active,
                int(bits_per_word),
                bit_order == "MSB first (typical)",
                float(merge_gap),
            )

        elif protocol == "I2C (7-bit)":
            scl_ch = pick_channel("SCL clock")
            if scl_ch is None:
                return files
            sda_ch = pick_channel("SDA data", {scl_ch})
            if sda_ch is None:
                return files
            result = decode_i2c(decode_time, signals[scl_ch], signals[sda_ch])

        elif protocol == "NRZ (clocked)":
            source = pick_channel("Decoder source")
            if source is None:
                return files
            voltage = np.asarray(signals[source], dtype=float)
            with st.expander("NRZ configuration", expanded=True):
                col1, col2, col3 = st.columns(3)
                bit_time_us = col1.number_input(
                    "Bit time (µs)",
                    min_value=0.001,
                    value=1.0,
                    step=0.1,
                    format="%.6f",
                )
                phase = col2.number_input(
                    "Sample phase (fraction of bit)",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.5,
                    step=0.05,
                    format="%.2f",
                )
                bits_word = col3.selectbox("Bits per word", [8, 16, 24, 32])
                col4, col5 = st.columns(2)
                bit_order = col4.selectbox(
                    "Bit order",
                    ["MSB first (typical)", "LSB first"],
                )
            levels = estimate_logic_levels_and_thresholds(voltage)
            result = decode_nrz(
                decode_time,
                voltage,
                float(levels["low_threshold"]),
                float(levels["high_threshold"]),
                bit_time_us,
                float(phase),
                int(bits_word),
                bit_order == "LSB first",
            )

        elif protocol == "PWM / pulse-width":
            source = pick_channel("Decoder source")
            if source is None:
                return files
            voltage = np.asarray(signals[source], dtype=float)
            with st.expander("PWM configuration", expanded=True):
                min_pulse_us = st.number_input(
                    "Minimum pulse width (µs)",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    format="%.3f",
                )
            levels = estimate_logic_levels_and_thresholds(voltage)
            result = decode_pwm(
                decode_time,
                voltage,
                float(levels["low_threshold"]),
                float(levels["high_threshold"]),
                float(min_pulse_us),
            )

    except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
        st.error(f"Decoder could not analyze this window: {exc}")
        return files

    if result is None:
        return files

    render_result(result)
    return files


# MAIN APPLICATION
# ============================================================
def main() -> None:
    inject_mso_theme()
    render_header()

    st.caption(
        "CSV-based oscilloscope viewer: simultaneous channels, differential math, "
        "shared time axis, cursors, and a built-in multi-protocol decoder pack."
    )

    uploaded = st.file_uploader(
        "Upload oscilloscope CSV",
        type=["csv"],
    )

    with st.sidebar:
        st.header("CSV import")

        separator_name = st.selectbox(
            "Delimiter",
            ["Comma", "Semicolon", "Tab"],
        )

        separator = {
            "Comma": ",",
            "Semicolon": ";",
            "Tab": "\t",
        }[separator_name]

        skiprows = st.number_input(
            "Metadata rows before header",
            min_value=0,
            value=0,
            step=1,
        )

        st.caption(
            "Input voltage columns are assumed to be in volts. "
            "Convert other units before importing."
        )

    if uploaded is None:
        st.info(
            "Upload a CSV containing one time column and one or more numeric channels."
        )
        st.code(
            "Time(s),CH1,CH2,CH3\n"
            "0.000000,0.0,3.3,1.20\n"
            "0.000001,3.3,0.0,1.25\n"
            "0.000002,3.3,0.0,1.30",
            language="text",
        )
        render_brand_footer()
        return

    content = uploaded.getvalue()
    file_id = hashlib.sha256(content).hexdigest()[:16]

    try:
        raw_df = read_csv_cached(
            content,
            separator,
            int(skiprows),
        )
    except (ValueError, pd.errors.ParserError, UnicodeError) as exc:
        st.error(f"CSV import failed: {exc}")
        st.info("Check the delimiter, metadata row count, and UTF-8 encoding.")
        return

    with st.sidebar:
        detected_time = find_time_column(list(raw_df.columns))

        time_column = st.selectbox(
            "Time column",
            list(raw_df.columns),
            index=(
                list(raw_df.columns).index(detected_time)
                if detected_time is not None
                else 0
            ),
        )

        time_unit = st.selectbox(
            "CSV time unit",
            list(TIME_FACTORS),
            index=0,
        )

        timestamp_mode = st.radio(
            "Time-axis mode",
            [
                "Use CSV timestamps directly",
                "Reconstruct uniform timestamps",
            ],
            help=(
                "Reconstruction is explicit because it assumes uniformly "
                "sampled rows and trustworthy first/last timestamps."
            ),
        )

    original_time = pd.to_numeric(
        raw_df[time_column],
        errors="coerce",
    ).to_numpy(dtype=float) * TIME_FACTORS[time_unit]

    if len(original_time) < 2:
        st.error("At least two timestamped rows are required.")
        return

    if not np.all(np.isfinite(original_time)):
        st.error(
            "The time column contains missing or nonnumeric values. "
            "Correct the CSV or import settings. Rows are not silently dropped."
        )
        return

    input_quality = analyze_timestamp_quality(original_time)

    try:
        # Crucially, prepare ONE time axis for the full CSV row order,
        # before selecting channels or handling missing voltage values.
        time_s, quality = prepare_time_axis(
            original_time,
            timestamp_mode,
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    if time_s[-1] <= time_s[0]:
        st.error("Capture duration must be positive.")
        return

    if quality["reconstruction_applied"]:
        st.warning(
            "Time has been reconstructed uniformly from row order and "
            "first-to-last duration. This does not recover actual jitter, "
            "missing acquisitions, or time resets. Use only when uniform "
            "sampling and the endpoint duration are known to be valid."
        )
    elif input_quality["duplicate_ratio"] > 0:
        st.warning(
            "Duplicate timestamps are retained for viewing. "
            "The decoder requires strictly increasing time."
        )

    with st.expander("Timestamp diagnosis and CSV preview"):
        diagnostic = {
            "Rows": input_quality["total_rows"],
            "Unique timestamps": input_quality["unique_timestamps"],
            "Duplicate ratio": input_quality["duplicate_ratio"],
            "Backward steps": input_quality["non_monotonic_steps"],
            "Original duration (s)": input_quality["duration_s"],
            "Applied mode": quality["applied_mode"],
        }

        st.json(diagnostic)
        st.dataframe(
            raw_df.head(20),
            width="stretch",
            hide_index=True,
        )

    available = channel_candidates(raw_df, time_column)

    if not available:
        st.error(
            "No numeric waveform channels were found. "
            "Check the delimiter, header, and numeric formatting."
        )
        return

    with st.sidebar:
        st.header("Visible channels")

        selected = st.multiselect(
            "Show simultaneously",
            available,
            default=available[:min(4, len(available))],
        )

        math_enabled = st.checkbox(
            "Add differential math channel",
            value=False,
            disabled=len(available) < 2,
        )

        math_a = None
        math_b = None

        if math_enabled:
            math_a = st.selectbox("Math A", available)

            math_b = st.selectbox(
                "Math B",
                [name for name in available if name != math_a],
            )

        view = st.radio(
            "Chart layout",
            ["Overlay", "Stacked / shared time"],
        )

        total_budget = st.number_input(
            "Total plotted-point budget",
            min_value=1000,
            max_value=500_000,
            value=80_000,
            step=1000,
            help=(
                "Display only. CSV exports, statistics, and decoding use "
                "full-resolution samples from the selected window."
            ),
        )

    signals: dict[str, np.ndarray] = {}

    for name in selected:
        values = pd.to_numeric(
            raw_df[name],
            errors="coerce",
        ).to_numpy(dtype=float)

        signals[name] = np.where(np.isfinite(values), values, np.nan)

    if math_enabled and math_a is not None and math_b is not None:
        a = pd.to_numeric(
            raw_df[math_a],
            errors="coerce",
        ).to_numpy(dtype=float)

        b = pd.to_numeric(
            raw_df[math_b],
            errors="coerce",
        ).to_numpy(dtype=float)

        with np.errstate(invalid="ignore", over="ignore"):
            differential = a - b

        math_name = f"MATH: {math_a} - {math_b}"

        while math_name in signals:
            math_name += " [math]"

        signals[math_name] = np.where(
            np.isfinite(differential),
            differential,
            np.nan,
        )

    if not signals:
        st.info("Select at least one channel or enable a math channel.")
        return

    capture_origin_s = float(time_s[0])
    relative_us = (time_s - capture_origin_s) * 1e6
    duration_us = float(relative_us[-1])

    with st.sidebar:
        st.header("Window")

        start_us = st.number_input(
            "Start from capture origin (µs)",
            min_value=0.0,
            max_value=duration_us,
            value=0.0,
            step=duration_us / 1000.0,
            format="%.6f",
        )

        end_us = st.number_input(
            "End from capture origin (µs)",
            min_value=0.0,
            max_value=duration_us,
            value=duration_us,
            step=duration_us / 1000.0,
            format="%.6f",
        )

    if start_us >= end_us:
        st.error("Window start must be less than window end.")
        return

    mask = (
        (relative_us >= start_us)
        & (relative_us <= end_us)
    )

    if np.count_nonzero(mask) < 2:
        st.warning("The selected window contains fewer than two samples.")
        return

    window_time_s = time_s[mask]
    window_time_us = relative_us[mask]
    window_signals = {
        name: values[mask]
        for name, values in signals.items()
    }

    settings: dict[str, dict] = {}

    with st.sidebar:
        st.header("Channel display controls")
        st.caption(
            "Display value = raw voltage × gain × polarity + offset. "
            "These settings do not modify exported raw data or decoder input."
        )

        for index, name in enumerate(signals):
            widget_id = hashlib.sha256(
                f"{file_id}:{name}".encode("utf-8")
            ).hexdigest()[:16]

            with st.expander(name):
                settings[name] = {
                    "color": st.color_picker(
                        "Color",
                        COLORS[index % len(COLORS)],
                        key=f"color_{widget_id}",
                    ),
                    "gain": st.number_input(
                        "Display gain",
                        min_value=0.001,
                        max_value=1000.0,
                        value=1.0,
                        step=0.1,
                        key=f"gain_{widget_id}",
                    ),
                    "offset": st.number_input(
                        "Display offset (V)",
                        value=0.0,
                        step=0.5,
                        key=f"offset_{widget_id}",
                    ),
                    "invert": st.checkbox(
                        "Invert display",
                        value=False,
                        key=f"invert_{widget_id}",
                    ),
                }

    metrics = st.columns(4)
    metrics[0].metric("Visible traces", len(signals))
    metrics[1].metric("Window samples", f"{len(window_time_s):,}")
    metrics[2].metric(
        "Sampled window span",
        f"{window_time_us[-1] - window_time_us[0]:.3f} µs",
    )

    positive_steps = np.diff(time_s)
    positive_steps = positive_steps[positive_steps > 0]

    if len(positive_steps):
        metrics[3].metric(
            "Median positive Δt",
            f"{np.median(positive_steps) * 1e6:.6f} µs",
        )

    cursor_a = None
    cursor_b = None

    with st.expander("Time cursors", expanded=False):
        cursors_enabled = st.checkbox("Show cursors A and B")

        if cursors_enabled:
            col_a, col_b, col_delta, col_frequency = st.columns(4)

            lower = float(window_time_us[0])
            upper = float(window_time_us[-1])
            span = upper - lower

            with col_a:
                cursor_a = st.number_input(
                    "Cursor A (µs)",
                    min_value=lower,
                    max_value=upper,
                    value=lower + span * 0.25,
                    step=span / 1000.0,
                    format="%.6f",
                )

            with col_b:
                cursor_b = st.number_input(
                    "Cursor B (µs)",
                    min_value=lower,
                    max_value=upper,
                    value=lower + span * 0.75,
                    step=span / 1000.0,
                    format="%.6f",
                )

            delta_us = abs(cursor_b - cursor_a)
            col_delta.metric("|B − A|", f"{delta_us:.6f} µs")

            col_frequency.metric(
                "1 / Δt",
                f"{1e6 / delta_us:,.3f} Hz" if delta_us > 0 else "—",
            )

            st.caption(
                "1/Δt is a reciprocal cursor interval, not automatic frequency "
                "detection. Cursor positions are entered numerically."
            )

    revision = (
        f"{file_id}:{time_column}:{time_unit}:{timestamp_mode}:"
        f"{start_us}:{end_us}:{view}:{list(signals)}"
    )

    figure = make_scope_figure(
        window_time_us,
        window_signals,
        settings,
        stacked=view == "Stacked / shared time",
        total_budget=int(total_budget),
        cursor_a=cursor_a,
        cursor_b=cursor_b,
        revision=revision,
    )

    st.plotly_chart(
        figure,
        width="stretch",
        config=PLOT_CONFIG,
    )

    st.caption(
        "Scroll to zoom; use the toolbar to switch to pan. "
        "Click legend entries to hide/show traces; double-click to isolate one. "
        "For finer detail, narrow the Window controls: browser-only zoom does "
        "not fetch additional samples from the display-downsampled trace. "
        "Display rendering may simplify very short gaps."
    )

    statistics = []

    for name, values in window_signals.items():
        valid = values[np.isfinite(values)]

        statistics.append({
            "Channel": name,
            "Valid samples": len(valid),
            "Missing samples": len(values) - len(valid),
            "Min_V": float(np.min(valid)) if len(valid) else np.nan,
            "Max_V": float(np.max(valid)) if len(valid) else np.nan,
            "PeakToPeak_V": float(np.ptp(valid)) if len(valid) else np.nan,
            "Mean_V": float(np.mean(valid)) if len(valid) else np.nan,
            "RMS_V": (
                float(np.sqrt(np.mean(np.square(valid))))
                if len(valid) else np.nan
            ),
        })

    statistics_df = pd.DataFrame(statistics)

    with st.expander("Full-resolution window statistics"):
        st.caption(
            "Statistics use raw voltage samples, not display gain/offset. "
            "Mean and RMS are sample-weighted, not time-weighted."
        )
        st.dataframe(
            statistics_df,
            width="stretch",
            hide_index=True,
        )

    # Keep the original and applied timestamp axes in the raw export.
    export_frame = pd.DataFrame({
        "OriginalCSVTime_s": original_time[mask],
        "AppliedTime_s": window_time_s,
        "TimeFromCaptureStart_us": window_time_us,
    })

    for name, values in window_signals.items():
        export_frame[f"Signal_V::{name}"] = values

    files = {
        "scope.html": figure.to_html(
            full_html=True,
            include_plotlyjs=True,
            config=PLOT_CONFIG,
        ).encode("utf-8"),
        "window_waveforms.csv": dataframe_csv_bytes(export_frame),
        "window_statistics.csv": dataframe_csv_bytes(statistics_df),
        "display_settings.csv": dataframe_csv_bytes(
            pd.DataFrame.from_dict(
                settings,
                orient="index",
            ).rename_axis("Channel").reset_index()
        ),
    }

    files.update(
        render_decoder(
            window_time_s,
            window_signals,
            capture_origin_s,
            quality,
        )
    )

    base_name = Path(uploaded.name).stem

    st.subheader("Download")

    col1, col2, col3 = st.columns(3)

    col1.download_button(
        "Offline interactive chart",
        data=files["scope.html"],
        file_name=f"{base_name}_scope.html",
        mime="text/html",
    )

    col2.download_button(
        "Full-resolution window CSV",
        data=files["window_waveforms.csv"],
        file_name=f"{base_name}_window.csv",
        mime="text/csv",
    )

    col3.download_button(
        "All available results ZIP",
        data=build_zip(files),
        file_name=f"{base_name}_analysis.zip",
        mime="application/zip",
    )

    st.caption(
        "The HTML chart embeds Plotly and does not require a CDN. "
        "It contains the displayed/downsampled traces; the window CSV contains "
        "full-resolution selected samples. Treat downloaded files as capture data."
    )

    render_brand_footer()


if __name__ == "__main__":
    main()