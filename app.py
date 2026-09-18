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
    default_timestamp_mode,
    detect_transitions,
    estimate_logic_levels_and_thresholds,
    find_time_column,
    group_bits,
    prepare_time_axis,
    scan_differential_manchester,
)

from branding import get_build_label, page_setup, render_brand_footer
from debug_utils import (
    clear_debug_logs,
    collect_runtime_diagnostics,
    debug_log,
    export_debug_log,
    export_diagnostics_json,
    get_debug_logs,
    get_last_exception,
    record_app_state,
    record_exception,
)


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
.mso-version {
    display: inline-block; margin-left: 10px; padding: 2px 8px;
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.04em;
    color: #9db4d8; border: 1px solid var(--mso-border); border-radius: 6px;
    background: rgba(59,130,246,0.08); vertical-align: middle;
}
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

.mso-section {
    font-size: 0.68rem; letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--mso-muted); font-weight: 700; margin: 12px 0 2px;
    border-left: 3px solid var(--mso-accent); padding-left: 8px;
}
.mso-hint {
    font-size: 0.76rem; color: #9db4d8; border: 1px dashed var(--mso-border);
    border-radius: 8px; padding: 5px 10px; margin: 4px 0 2px;
    background: rgba(59,130,246,0.06);
}
</style>
"""


def inject_mso_theme() -> None:
    st.markdown(MSO_CSS, unsafe_allow_html=True)


def render_header() -> None:
    build_label = get_build_label()
    version_html = (
        f'<span class="mso-version">{build_label}</span>' if build_label else ""
    )
    st.markdown(
        f"""
        <div class="mso-header">
            <div class="mso-logo">&#9674;</div>
            <div class="mso-title">
                <div class="main">WaveLogic MSO — Multi-Channel Protocol Analyzer{version_html}</div>
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


@st.cache_data(show_spinner=False, max_entries=4)
def scan_differential_manchester_cached(
    time_s: np.ndarray,
    channel_a: np.ndarray,
    channel_b: np.ndarray,
    nominal_bit_us: float,
    alignment: str,
    preamble_count: int,
    holdoff_us: float,
) -> dict:
    """Run the multi-message scan once; selection then reuses cached output."""
    return scan_differential_manchester(
        time_s,
        channel_a,
        channel_b,
        nominal_bit_us,
        alignment,
        preamble_count,
        holdoff_us,
    )


# ============================================================
# MULTI-MESSAGE DIFFERENTIAL MANCHESTER PRESENTATION
# ============================================================
DIFFERENTIAL_THRESHOLD_NOTE = (
    "Threshold lines in this figure are a reference visualization. The scanner "
    "estimates logic thresholds per burst, so the plotted levels are not "
    "necessarily the exact thresholds used for candidate validation."
)

DIFFERENTIAL_BUDGET_NOTE = (
    "Scan stopped at the decoder-call safety limit. Messages shown were "
    "independently validated before the limit was reached; additional messages "
    "may exist."
)


def differential_budget_notice(scan_metrics: dict) -> str | None:
    """Return the incompleteness notice when the scan hit the call budget."""
    if (scan_metrics or {}).get("decoder_call_budget_hit"):
        return DIFFERENTIAL_BUDGET_NOTE
    return None


def differential_message_summary(
    messages: list[dict],
    window_start_from_capture_us: float | None = None,
) -> pd.DataFrame:
    """Compact per-message summary built from the existing scanner result.

    ``Start_us``/``End_us`` are relative to the selected window start, matching
    the existing legacy frame-summary convention. When the window start offset
    is supplied, capture-relative columns are added so the exported artifact is
    unambiguous.
    """
    rows: list[dict] = []
    for index, message in enumerate(messages, start=1):
        start_us = float(message.get("frame_start_us", np.nan))
        end_us = float(message.get("frame_end_us", np.nan))
        structural = message.get("structural_validation") or {}
        row = {
            "Message": index,
            "Start_us": start_us,
            "End_us": end_us,
            "Duration_us": end_us - start_us,
            "DecodedBits": len(message.get("bits", [])),
            "PacketBits": len(message.get("packet_data_bits", [])),
            "Preamble": "PASS" if message.get("preamble_valid") else "FAIL",
            "Sync": "PASS" if message.get("sync_valid") else "FAIL",
            "Clock": "PASS" if message.get("clock_quality_pass") else "FAIL",
            "FittedBit_us": float(message.get("fitted_bit_us", np.nan)),
            "StructuralCoverage": float(
                structural.get("boundary_transition_coverage", np.nan)
            ),
            "LogicalStartSample": int(message.get("logical_frame_start_sample", -1)),
            "LogicalEndSample": int(message.get("logical_frame_end_sample", -1)),
        }
        if window_start_from_capture_us is not None:
            row["WindowStartFromCapture_us"] = window_start_from_capture_us
            row["StartFromCapture_us"] = window_start_from_capture_us + start_us
            row["EndFromCapture_us"] = window_start_from_capture_us + end_us
        rows.append(row)
    return pd.DataFrame(rows)


def differential_message_bits(messages: list[dict]) -> pd.DataFrame:
    """Decoded bitstream per message, for export without re-decoding."""
    rows = [
        {
            "Message": index,
            "DecodedBits": bits_to_string(message.get("bits", np.array([], dtype=int))),
        }
        for index, message in enumerate(messages, start=1)
    ]
    return pd.DataFrame(rows)


def differential_message_result(
    message: dict,
    signal_name: str,
    timestamp_quality: dict,
    time_axis_note: str,
    low_threshold: float,
    high_threshold: float,
    holdoff_us: float,
    index: int,
    total: int,
    window_start_from_capture_us: float,
) -> dict:
    """Shape one scanner message into the existing render_result contract."""
    frame_start_us = float(message.get("frame_start_us", np.nan))
    frame_end_us = float(message.get("frame_end_us", np.nan))
    summary = message["frame_summary"].copy()
    summary["Source"] = signal_name
    summary["Convention"] = "Legacy: midpoint transition = 0"
    summary["MessageIndex"] = index
    summary["MessageCount"] = total
    # Scan-relative times mirror the legacy frame-summary convention, while the
    # capture-relative columns avoid implying a false time origin.
    summary["LogicalFrameStart_us"] = frame_start_us
    summary["LogicalFrameEnd_us"] = frame_end_us
    summary["WindowStartFromCapture_us"] = window_start_from_capture_us
    summary["LogicalFrameStartFromCapture_us"] = window_start_from_capture_us + frame_start_us
    summary["LogicalFrameEndFromCapture_us"] = window_start_from_capture_us + frame_end_us
    summary["LogicalFrameStartSample"] = int(message.get("logical_frame_start_sample", -1))
    summary["LogicalFrameEndSample"] = int(message.get("logical_frame_end_sample", -1))
    summary["DecoderWindowStartSample"] = int(message.get("decoder_window_start_sample", -1))
    summary["DecoderWindowEndSample"] = int(message.get("decoder_window_end_sample", -1))
    structural = message.get("structural_validation") or {}
    summary["StructuralCoverage"] = float(
        structural.get("boundary_transition_coverage", np.nan)
    )
    summary["TimestampModeApplied"] = timestamp_quality["applied_mode"]
    summary["DecoderTimeAxis"] = time_axis_note
    summary["LowThreshold_V"] = low_threshold
    summary["HighThreshold_V"] = high_threshold
    summary["TransitionHoldoff_us"] = holdoff_us

    packet_string = bits_to_string(message["packet_data_bits"])
    packet_hex, _ = bits_to_hex(packet_string)
    byte_table = pd.DataFrame(
        bits_to_hex(packet_string)[1],
        columns=["ByteNumber", "Binary", "Hex", "Decimal", "CompleteByte"],
    )

    text = "\n".join([
        f"Message {index} of {total}",
        f"Source: {signal_name}",
        "Convention: legacy midpoint transition = 0",
        f"Decoder time axis: {time_axis_note}",
        f"Selected window start: {window_start_from_capture_us:.3f} µs from capture start",
        f"Logical frame start: {frame_start_us:.3f} µs from selected window start",
        f"Logical frame end: {frame_end_us:.3f} µs from selected window start",
        (
            "Logical frame start: "
            f"{window_start_from_capture_us + frame_start_us:.3f} µs from capture start"
        ),
        (
            "Logical frame end: "
            f"{window_start_from_capture_us + frame_end_us:.3f} µs from capture start"
        ),
        f"Clock fit pass: {message['clock_quality_pass']}",
        f"Preamble valid: {message['preamble_valid']}",
        f"Sync valid: {message['sync_valid']}",
        "",
        "Complete decoded bits:",
        bits_to_string(message["bits"]),
        "",
        "Packet bits:",
        group_bits(packet_string),
        "",
        "Packet HEX (MSB-first complete bytes):",
        packet_hex or "No complete bytes",
    ])

    detail_figure = None
    if len(message["bits"]) <= 300 and len(message["pulses"]) <= 1000:
        detail_figure = create_figure(
            message,
            signal_name,
            30_000,
            low_threshold,
            high_threshold,
        )
        # Crop the view to the logical frame boundaries reported by the decoder
        # (first/last decoded bit cell), which excludes the pre-roll lead-in and
        # trailing context that the decoder window includes.
        try:
            logical_start_us = float(message["frame_summary"]["FrameStart_us"].iloc[0])
            logical_end_us = float(message["frame_summary"]["FrameEnd_us"].iloc[0])
            detail_figure.update_xaxes(
                range=[logical_start_us, logical_end_us],
                title_text="Time relative to decoder window start (µs)",
            )
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    return {
        "protocol": f"Differential Manchester (message {index} of {total})",
        "metrics": [
            ("Message", f"{index} of {total}"),
            ("Decoded bits", str(len(message["bits"]))),
            ("Fitted bit time", f"{message['fitted_bit_us']:.4f} µs"),
            ("Preamble", "PASS" if message["preamble_valid"] else "FAIL"),
        ],
        "status": [
            ("Clock fit", message["clock_quality_pass"]),
            ("Preamble valid", message["preamble_valid"]),
            ("Sync valid", message["sync_valid"]),
        ],
        "tables": [
            ("Decoded bits", message["decoded"]),
            ("Packet bytes", byte_table),
            ("Pulse timing", message["pulses"]),
            ("Frame summary", summary),
        ],
        "text": text,
        "figure": detail_figure,
        "threshold_note": (
            DIFFERENTIAL_THRESHOLD_NOTE if detail_figure is not None else None
        ),
    }


# ============================================================
# OPTIONAL DECODER
# ============================================================
MULTI_MESSAGE_MODE = "Multi-message / Burst Scan"
SINGLE_FRAME_MODE = "Single Frame"

_TOO_MANY_HALF_BIT_CELLS_MARKER = "too many half-bit cells"


def _render_section_label(text: str) -> None:
    st.markdown(f'<div class="mso-section">{text}</div>', unsafe_allow_html=True)


def suggest_differential_pair(
    signals: dict[str, np.ndarray],
    max_samples: int = 50_000,
) -> tuple[str | None, str | None, str | None]:
    """Suggest the most plausibly active two-channel pair for burst scanning.

    UI hint only — ranks channels by robust voltage spread over the current
    window and returns the top two when they clearly dominate the rest. It never
    overrides the user's manual Channel A / Channel B selection and is not a
    confidence score.
    """
    spreads: dict[str, float] = {}
    for name, values in signals.items():
        try:
            array = np.asarray(values, dtype=float)
            if array.size == 0:
                continue
            step = max(1, array.size // max_samples)
            sample = array[::step]
            finite = sample[np.isfinite(sample)]
            if finite.size < 20:
                continue
            spreads[name] = float(np.std(finite))
        except Exception:
            continue

    if len(spreads) < 2:
        return None, None, None

    ranked = sorted(spreads.items(), key=lambda item: item[1], reverse=True)
    (first_name, first_value), (second_name, second_value) = ranked[0], ranked[1]
    if first_value <= 0 or second_value <= 0:
        return None, None, None

    others = [value for _, value in ranked[2:] if value > 0]
    dominant = (not others) or (second_value > 2.0 * max(others))
    if not dominant:
        return None, None, None

    return first_name, second_name, f"Suggested differential pair: {first_name} / {second_name}"


def is_too_many_half_bit_cells_error(exc: BaseException) -> bool:
    """True when the legacy decoder failed because the window is too long."""
    return _TOO_MANY_HALF_BIT_CELLS_MARKER in str(exc).lower()


def safe_logic_levels(voltage: np.ndarray) -> dict | None:
    """Estimate levels without raising, for optional reference lines."""
    try:
        return estimate_logic_levels_and_thresholds(voltage)
    except ValueError:
        return None


def render_long_window_guidance(
    sample_count: int,
    duration_us: float,
    nominal_bit_us: float,
) -> None:
    """Actionable guidance when the single-frame decoder rejects a long window."""
    st.warning("Single-frame decoder cannot process this entire window.")
    columns = st.columns(3)
    columns[0].metric("Window samples", f"{int(sample_count):,}")
    columns[1].metric("Window duration", f"{float(duration_us):.3f} µs")
    columns[2].metric("Nominal bit time", f"{float(nominal_bit_us):.4f} µs")
    st.info(
        "Either narrow the Window controls to one frame, or switch Analysis "
        "Mode to Multi-message / Burst Scan."
    )


def render_multi_message_scan(
    files: dict[str, bytes],
    decode_time: np.ndarray,
    channel_a_voltage: np.ndarray,
    channel_b_voltage: np.ndarray,
    channel_a_name: str,
    channel_b_name: str,
    nominal_bit_us: float,
    alignment: str,
    preamble_count: int,
    holdoff_us: float,
    timestamp_quality: dict,
    time_axis_note: str,
    capture_origin_s: float,
    render_result,
) -> dict[str, bytes]:
    """Burst-scan workflow: locate, validate, summarise and present messages.

    Candidate discovery and validation are delegated entirely to the existing
    paired-channel scanner; the legacy decoder is never applied to the whole
    capture here.
    """
    window_duration_us = (
        float(decode_time[-1] - decode_time[0]) * 1e6 if len(decode_time) else 0.0
    )

    debug_log(
        f"Burst scan start: A={channel_a_name} B={channel_b_name} "
        f"bit_time_us={nominal_bit_us} preamble={int(preamble_count)} "
        f"samples={len(decode_time)} window_us={window_duration_us:.3f}"
    )

    scan_result = scan_differential_manchester_cached(
        decode_time,
        channel_a_voltage,
        channel_b_voltage,
        nominal_bit_us,
        alignment,
        int(preamble_count),
        holdoff_us,
    )

    messages = scan_result.get("messages", [])
    message_count = int(scan_result.get("message_count", len(messages)))
    scan_metrics = scan_result.get("metrics", {})
    status = scan_result.get("status", "unknown")

    debug_log(
        f"Burst scan end: status={status} messages={message_count} "
        f"decoder_calls={scan_metrics.get('decoder_calls')}"
    )
    record_app_state(
        multi_message_status=status,
        multi_message_count=message_count,
        multi_message_candidate_regions=scan_metrics.get("candidate_region_count"),
        multi_message_decoder_calls=scan_metrics.get("decoder_calls"),
    )

    _render_section_label("Result")
    st.markdown("#### Differential Manchester — Burst Scan")
    st.metric("Validated messages", message_count)

    budget_notice = differential_budget_notice(scan_metrics)
    if budget_notice:
        st.warning(budget_notice)

    if message_count == 0:
        st.warning(
            "No independently validated Differential Manchester messages "
            "were found."
        )
        st.dataframe(
            _diagnostics_frame([
                ("Scanner status", status),
                ("Candidate regions", scan_metrics.get("candidate_region_count", "n/a")),
                ("Decoder calls", scan_metrics.get("decoder_calls", "n/a")),
                (
                    "Decoder-call budget hit",
                    scan_metrics.get("decoder_call_budget_hit", "n/a"),
                ),
                ("Channel A", channel_a_name),
                ("Channel B", channel_b_name),
                ("Nominal bit time (µs)", f"{nominal_bit_us:.4f}"),
                ("Window duration (µs)", f"{window_duration_us:.3f}"),
            ]),
            width="stretch",
            hide_index=True,
        )
        st.info("Check the channel pair, bit time, and selected capture window.")
        return files

    window_start_from_capture_us = (
        float(decode_time[0]) - capture_origin_s
    ) * 1e6

    summary_df = differential_message_summary(
        messages,
        window_start_from_capture_us=window_start_from_capture_us,
    )
    st.dataframe(summary_df, width="stretch", hide_index=True)
    st.caption(
        "Start_us/End_us are relative to the selected window start. Each "
        "message is independently validated by the scanner."
    )
    files["dm_messages_summary.csv"] = dataframe_csv_bytes(summary_df)
    files["dm_messages_bits.csv"] = dataframe_csv_bytes(
        differential_message_bits(messages)
    )

    labels = [f"Message {number}" for number in range(1, len(messages) + 1)]
    selected_label = st.selectbox("Select message", labels, key="dm_message_select")
    selected_index = int(selected_label.split()[-1])

    # Reference threshold lines reuse already-available levels; never required.
    levels = safe_logic_levels(channel_a_voltage) or safe_logic_levels(
        channel_b_voltage
    )
    if levels is None:
        reference_low = float("nan")
        reference_high = float("nan")
    else:
        reference_low = float(levels["low_threshold"])
        reference_high = float(levels["high_threshold"])

    detail_result = differential_message_result(
        messages[selected_index - 1],
        channel_a_name,
        timestamp_quality,
        time_axis_note,
        reference_low,
        reference_high,
        holdoff_us,
        selected_index,
        message_count,
        window_start_from_capture_us,
    )
    if detail_result.get("threshold_note"):
        st.caption(detail_result["threshold_note"])
    render_result(detail_result)
    return files


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

    debug_log(f"Protocol selected: {protocol} (time axis: {time_axis_note})")
    record_app_state(protocol=protocol, decoder_time_axis=time_axis_note)

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
            channel_names = list(signals)
            suggested_a, suggested_b, suggestion_hint = suggest_differential_pair(
                signals
            )

            default_a = suggested_a if suggested_a in signals else channel_names[0]
            if len(channel_names) > 1:
                default_b = (
                    suggested_b
                    if suggested_b in signals and suggested_b != default_a
                    else next(
                        (name for name in channel_names if name != default_a),
                        default_a,
                    )
                )
            else:
                default_b = default_a

            _render_section_label("Analysis mode")
            analysis_mode = st.radio(
                "Analysis mode",
                [MULTI_MESSAGE_MODE, SINGLE_FRAME_MODE],
                index=0,
                horizontal=True,
                key="dm_analysis_mode",
                help=(
                    "Burst Scan uses the paired-channel scanner to locate and "
                    "independently validate every message in the window. Single "
                    "Frame runs the legacy decoder on one frame."
                ),
            )

            _render_section_label("Channels")
            channel_col_a, channel_col_b = st.columns(2)
            with channel_col_a:
                channel_a = st.selectbox(
                    "Channel A",
                    channel_names,
                    index=channel_names.index(default_a),
                    key="dm_channel_a",
                    help="Primary decoder channel.",
                )
            with channel_col_b:
                channel_b = st.selectbox(
                    "Channel B",
                    channel_names,
                    index=channel_names.index(default_b),
                    key="dm_channel_b",
                    help="Second channel correlated by the burst scanner.",
                )
            if suggestion_hint:
                st.markdown(
                    f'<div class="mso-hint">{suggestion_hint}</div>',
                    unsafe_allow_html=True,
                )

            _render_section_label("Timing configuration")
            timing_cols = st.columns(4)
            with timing_cols[0]:
                nominal_bit_us = st.number_input(
                    "Nominal bit time (µs)",
                    min_value=0.001,
                    value=12.8,
                    step=0.1,
                    format="%.4f",
                    key="dm_bit_time",
                )
            with timing_cols[1]:
                preamble_count = st.number_input(
                    "Preamble bit count",
                    min_value=1,
                    value=22,
                    step=1,
                    key="dm_preamble",
                )
            with timing_cols[2]:
                alignment = st.selectbox(
                    "Clock alignment",
                    [
                        "First transition is bit start",
                        "First transition is midpoint",
                    ],
                    key="dm_alignment",
                )
            with timing_cols[3]:
                holdoff_us = st.number_input(
                    "Transition hold-off (µs)",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    format="%.4f",
                    key="dm_holdoff",
                )

            voltage = np.asarray(signals[channel_a], dtype=float)
            paired_voltage = np.asarray(signals[channel_b], dtype=float)
            source = channel_a
            window_duration_us = (
                float(decode_time[-1] - decode_time[0]) * 1e6
                if len(decode_time)
                else 0.0
            )

            debug_log(
                f"Differential Manchester: mode={analysis_mode} "
                f"channel_a={channel_a} channel_b={channel_b} "
                f"bit_time_us={float(nominal_bit_us)} samples={len(decode_time)} "
                f"window_us={window_duration_us:.3f}"
            )
            record_app_state(
                analysis_mode=analysis_mode,
                decoder_source=channel_a,
                decoder_paired_channel=channel_b,
                nominal_bit_time_us=float(nominal_bit_us),
                window_samples=len(decode_time),
                window_duration_us=round(window_duration_us, 6),
            )

            if analysis_mode == MULTI_MESSAGE_MODE:
                return render_multi_message_scan(
                    files,
                    decode_time,
                    voltage,
                    paired_voltage,
                    channel_a,
                    channel_b,
                    float(nominal_bit_us),
                    alignment,
                    int(preamble_count),
                    float(holdoff_us),
                    timestamp_quality,
                    time_axis_note,
                    capture_origin_s,
                    render_result,
                )

            _render_section_label("Single-frame configuration")
            threshold_mode = st.radio(
                "Threshold mode",
                ["Automatic", "Manual"],
                key="dm_threshold_mode",
            )
            levels = estimate_logic_levels_and_thresholds(voltage)
            if threshold_mode == "Automatic":
                low_threshold = float(levels["low_threshold"])
                high_threshold = float(levels["high_threshold"])
            else:
                threshold_cols = st.columns(2)
                with threshold_cols[0]:
                    low_threshold = st.number_input(
                        "LOW threshold (V)",
                        value=float(levels["low_threshold"]),
                        step=0.05,
                        format="%.5f",
                        key="dm_low_threshold",
                    )
                with threshold_cols[1]:
                    high_threshold = st.number_input(
                        "HIGH threshold (V)",
                        value=float(levels["high_threshold"]),
                        step=0.05,
                        format="%.5f",
                        key="dm_high_threshold",
                    )

            try:
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
            except ValueError as exc:
                if is_too_many_half_bit_cells_error(exc):
                    debug_log(
                        f"Single-frame long-window failure: {type(exc).__name__}: {exc}",
                        "ERROR",
                    )
                    record_exception(exc)
                    render_long_window_guidance(
                        sample_count=len(decode_time),
                        duration_us=window_duration_us,
                        nominal_bit_us=float(nominal_bit_us),
                    )
                    return files
                raise

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
        debug_log(f"Decoder exception: {type(exc).__name__}: {exc}", "ERROR")
        record_exception(exc)
        st.error(f"Decoder could not analyze this window: {exc}")
        return files

    if result is None:
        return files

    render_result(result)
    return files


# DEBUG & LOGS
# ============================================================
def _diagnostics_frame(rows: list[tuple[str, object]]) -> pd.DataFrame:
    """Build an Arrow-safe two-column table (values rendered as text)."""
    return pd.DataFrame(
        [(str(field), str(value)) for field, value in rows],
        columns=["Field", "Value"],
    )


def render_debug_section() -> None:
    """Bottom-of-page, opt-in Debug & Logs view.

    Observational only: never modifies application state or behaviour. Shown
    last so it can also expose diagnostics when earlier processing raised.
    """
    st.divider()
    st.subheader("Debug & Logs")

    enabled = st.toggle(
        "Enable debug & diagnostic logs",
        value=False,
        key="wavelogic_debug_enabled",
        help="Show technical runtime information and recent application logs.",
    )

    if not enabled:
        return

    st.caption(
        "Technical diagnostics for troubleshooting. Never shows secrets, "
        "credentials, environment variables, or uploaded file contents."
    )

    try:
        diagnostics = collect_runtime_diagnostics()
    except Exception as exc:  # pragma: no cover - defensive
        debug_log(f"Diagnostics collection failed: {type(exc).__name__}: {exc}", "ERROR")
        diagnostics = {"error": f"{type(exc).__name__}: {exc}"}

    application = diagnostics.get("application", {}) or {}
    runtime = diagnostics.get("runtime", {}) or {}
    core = diagnostics.get("analyzer_core", {}) or {}

    st.markdown("**Application**")
    st.dataframe(
        _diagnostics_frame([
            ("Build label", application.get("build_label", "Unavailable")),
            ("App file", application.get("app_file", "Unavailable")),
            ("Python", application.get("python_version", "Unavailable")),
            ("Streamlit", application.get("streamlit_version", "Unavailable")),
        ]),
        width="stretch",
        hide_index=True,
    )

    st.markdown("**Runtime**")
    st.dataframe(
        _diagnostics_frame([
            ("Working directory", runtime.get("cwd", "Unavailable")),
            ("Executable", runtime.get("executable", "Unavailable")),
            ("Platform", runtime.get("platform", "Unavailable")),
            ("Machine", runtime.get("machine", "Unavailable")),
            ("Process id", runtime.get("pid", "Unavailable")),
        ]),
        width="stretch",
        hide_index=True,
    )

    sys_path = runtime.get("sys_path") or []
    with st.expander("sys.path", expanded=False):
        st.code("\n".join(str(item) for item in sys_path) or "Unavailable", language="text")

    st.markdown("**analyzer_core import diagnostics**")
    st.dataframe(
        _diagnostics_frame([
            ("Module", core.get("module", "Unavailable")),
            ("File", core.get("file", "Unavailable")),
            ("SHA-256 (first 12)", core.get("sha256_12", "Unavailable")),
            ("Size (bytes)", core.get("size_bytes", "Unavailable")),
            (
                "has default_timestamp_mode",
                core.get("has_default_timestamp_mode", "Unavailable"),
            ),
        ]),
        width="stretch",
        hide_index=True,
    )

    st.markdown("**Imported API verification**")
    symbols = diagnostics.get("imported_symbols") or []
    if symbols:
        st.dataframe(
            pd.DataFrame(
                [
                    {"Symbol": item.get("symbol", ""), "Available": item.get("available", False)}
                    for item in symbols
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Symbol list unavailable.")

    exact = diagnostics.get("exact_named_import")
    if isinstance(exact, dict):
        if exact.get("ok"):
            st.success(f"Exact analyzer_core named import: OK ({exact.get('symbol_count')} symbols)")
        else:
            st.error(
                "Exact analyzer_core named import: FAILED — "
                f"{exact.get('exception_type')}: {exact.get('exception_message')}"
            )
            if exact.get("traceback"):
                st.code(exact["traceback"], language="text")
    elif exact:
        st.write(exact)

    st.markdown("**Application state**")
    state = diagnostics.get("app_state") or {}
    if state:
        st.dataframe(
            _diagnostics_frame([(str(k), v) for k, v in state.items()]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No application state captured this run.")

    last_error = get_last_exception()
    if last_error:
        st.markdown("**Last exception**")
        st.dataframe(
            _diagnostics_frame([
                ("Time", last_error.get("timestamp", "Unavailable")),
                ("Type", last_error.get("type", "Unavailable")),
                ("Message", last_error.get("message", "Unavailable")),
            ]),
            width="stretch",
            hide_index=True,
        )
        with st.expander("Traceback", expanded=False):
            st.code(last_error.get("traceback", "Unavailable"), language="text")

    st.markdown("**Recent log records**")
    records = get_debug_logs()
    if records:
        st.dataframe(
            pd.DataFrame(records)[["timestamp", "level", "message"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No log records yet.")

    download_a, download_b, download_c = st.columns(3)
    download_a.download_button(
        "Download debug log",
        data=export_debug_log(records).encode("utf-8"),
        file_name="wavelogic_debug_log.txt",
        mime="text/plain",
    )
    download_b.download_button(
        "Download diagnostics",
        data=export_diagnostics_json(diagnostics).encode("utf-8"),
        file_name="wavelogic_diagnostics.json",
        mime="application/json",
    )
    download_c.button(
        "Clear debug log",
        key="wavelogic_clear_debug_log",
        on_click=clear_debug_logs,
    )


# MAIN APPLICATION
# ============================================================
def main() -> None:
    try:
        _run_app()
    finally:
        render_debug_section()


def _run_app() -> None:
    debug_log("Application run started")
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
        debug_log(f"CSV import failed: {type(exc).__name__}: {exc}", "ERROR")
        record_exception(exc)
        st.error(f"CSV import failed: {exc}")
        st.info("Check the delimiter, metadata row count, and UTF-8 encoding.")
        return

    debug_log(f"CSV loaded: {uploaded.name} rows={len(raw_df)} columns={list(raw_df.columns)}")
    record_app_state(
        file_name=uploaded.name,
        file_rows=len(raw_df),
        file_columns=", ".join(str(column) for column in raw_df.columns),
    )

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

    with st.sidebar:
        timestamp_options = [
            "Use CSV timestamps directly",
            "Reconstruct uniform timestamps",
        ]
        timestamp_mode = st.radio(
            "Time-axis mode",
            timestamp_options,
            index=timestamp_options.index(
                default_timestamp_mode(input_quality)
            ),
            help=(
                "Reconstruction is explicit because it assumes uniformly "
                "sampled rows and trustworthy first/last timestamps. "
                "Captures with duplicate or coarse timestamps default to "
                "reconstruction so the scope view and the decoder share "
                "the same time axis."
            ),
        )

    try:
        # Crucially, prepare ONE time axis for the full CSV row order,
        # before selecting channels or handling missing voltage values.
        time_s, quality = prepare_time_axis(
            original_time,
            timestamp_mode,
        )
    except ValueError as exc:
        debug_log(f"Timestamp preparation failed: {type(exc).__name__}: {exc}", "ERROR")
        record_exception(exc)
        st.error(str(exc))
        return

    debug_log(
        f"Timestamp analysis: mode={quality['applied_mode']} "
        f"duplicates={input_quality['duplicate_ratio']:.3f} "
        f"backward_steps={input_quality['non_monotonic_steps']}"
    )
    record_app_state(
        time_column=time_column,
        time_unit=time_unit,
        timestamp_mode=quality["applied_mode"],
        timestamp_reconstruction=quality["reconstruction_applied"],
    )

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

    debug_log(f"Export artifacts generated: {len(files)} file(s)")

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