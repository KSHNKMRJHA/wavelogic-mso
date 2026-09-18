from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

def normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", str(name)).lower()

# ============================================================
# HELPERS
# ============================================================

def find_time_column(columns: list[str]) -> str | None:
    normalized = {normalize_name(c): c for c in columns}
    preferred = [
        "time(s)", "time", "times", "second", "seconds", "t(s)", "x",
    ]
    for candidate in preferred:
        key = normalize_name(candidate)
        if key in normalized:
            return normalized[key]
    for column in columns:
        key = normalize_name(column)
        if "time" in key:
            return column
    return None


def channel_candidates(df: pd.DataFrame, time_column: str) -> list[str]:
    channels: list[str] = []
    for column in df.columns:
        if column == time_column or str(column).lower().startswith("unnamed"):
            continue
        numeric = pd.to_numeric(df[column], errors="coerce")
        if numeric.notna().sum() >= max(10, int(0.10 * len(df))):
            channels.append(column)
    return channels


def load_csv(uploaded_file) -> tuple[pd.DataFrame, str, list[str]]:
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file)
    df.columns = [str(c).strip() for c in df.columns]
    time_column = find_time_column(list(df.columns))
    if time_column is None:
        raise ValueError(
            "No time column was detected. Use a column such as Time(s), Time, or T(s)."
        )
    channels = channel_candidates(df, time_column)
    if not channels:
        raise ValueError("No numeric waveform channel was detected in the CSV.")
    return df, time_column, channels


def make_signal(
    df: pd.DataFrame,
    time_column: str,
    channel_a: str,
    mode: str,
    channel_b: str | None,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Return samples in original CSV row order. Do not discard duplicate times."""
    working = pd.DataFrame()
    working["time"] = pd.to_numeric(df[time_column], errors="coerce")
    working["a"] = pd.to_numeric(df[channel_a], errors="coerce")

    if mode == "Single channel":
        working = working.dropna(subset=["time", "a"])
        voltage = working["a"].to_numpy(dtype=float)
        signal_name = channel_a
    else:
        if channel_b is None or channel_b == channel_a:
            raise ValueError("Select two different channels for a differential signal.")
        working["b"] = pd.to_numeric(df[channel_b], errors="coerce")
        working = working.dropna(subset=["time", "a", "b"])
        if mode == "Channel A - Channel B":
            voltage = (working["a"] - working["b"]).to_numpy(dtype=float)
            signal_name = f"{channel_a} - {channel_b}"
        else:
            voltage = (working["b"] - working["a"]).to_numpy(dtype=float)
            signal_name = f"{channel_b} - {channel_a}"

    time_s = working["time"].to_numpy(dtype=float)
    if len(time_s) < 20:
        raise ValueError("Too few valid samples remain after cleaning selected columns.")
    return time_s, voltage, signal_name


def analyze_timestamp_quality(time_s: np.ndarray) -> dict:
    """Identify rounded, duplicated, non-monotonic, or otherwise weak timestamps."""
    time_s = np.asarray(time_s, dtype=float)
    total = len(time_s)
    unique_count = int(np.unique(time_s).size)
    duplicate_ratio = 1.0 - unique_count / max(total, 1)
    delta = np.diff(time_s)
    positive = delta[delta > 0]
    non_monotonic_count = int(np.sum(delta < 0))
    repeated_count = int(np.sum(delta == 0))
    duration_s = float(time_s[-1] - time_s[0])
    expected_dt_s = duration_s / (total - 1) if total > 1 and duration_s > 0 else np.nan
    median_positive_dt_s = float(np.median(positive)) if len(positive) else np.nan
    largest_positive_dt_s = float(np.max(positive)) if len(positive) else np.nan
    coarse_ratio = (
        median_positive_dt_s / expected_dt_s
        if np.isfinite(expected_dt_s) and expected_dt_s > 0 and np.isfinite(median_positive_dt_s)
        else np.inf
    )

    reasons = []
    if duplicate_ratio >= 0.05:
        reasons.append(f"{duplicate_ratio:.1%} of rows repeat an existing timestamp")
    if non_monotonic_count > 0:
        reasons.append(f"{non_monotonic_count} timestamp steps move backwards")
    if coarse_ratio >= 5.0:
        reasons.append("positive timestamp resolution is coarse relative to row count")
    if duration_s <= 0:
        reasons.append("capture duration is not positive")

    low_precision = bool(reasons)
    return {
        "total_rows": total,
        "unique_timestamps": unique_count,
        "duplicate_ratio": duplicate_ratio,
        "repeated_steps": repeated_count,
        "non_monotonic_steps": non_monotonic_count,
        "duration_s": duration_s,
        "expected_dt_s": expected_dt_s,
        "median_positive_dt_s": median_positive_dt_s,
        "largest_positive_dt_s": largest_positive_dt_s,
        "coarse_ratio": coarse_ratio,
        "low_precision": low_precision,
        "reasons": reasons,
    }


def prepare_time_axis(
    original_time_s: np.ndarray,
    requested_mode: str,
) -> tuple[np.ndarray, dict]:
    """Use CSV time directly or reconstruct uniform time from row order and duration."""
    quality = analyze_timestamp_quality(original_time_s)
    if requested_mode == "Automatic":
        applied_mode = "Reconstruct uniform timestamps" if quality["low_precision"] else "Use CSV timestamps directly"
    else:
        applied_mode = requested_mode

    if applied_mode == "Reconstruct uniform timestamps":
        if quality["duration_s"] <= 0:
            raise ValueError("Uniform time reconstruction requires a positive first-to-last capture duration.")
        analysis_time_s = np.linspace(
            float(original_time_s[0]), float(original_time_s[-1]), len(original_time_s)
        )
    else:
        if quality["non_monotonic_steps"] > 0:
            raise ValueError(
                "CSV timestamps move backwards. Select 'Reconstruct uniform timestamps' or correct the CSV."
            )
        # Retain duplicate rows. Direct mode is allowed, but repeated values will be warned.
        analysis_time_s = np.asarray(original_time_s, dtype=float)

    quality["requested_mode"] = requested_mode
    quality["applied_mode"] = applied_mode
    quality["reconstruction_applied"] = applied_mode == "Reconstruct uniform timestamps"
    return analysis_time_s, quality


def default_timestamp_mode(quality: dict) -> str:
    """Return the safe default for the UI time-axis radio.

    Captures with low-precision timestamps (duplicates/resets/coarse
    resolution) default to uniform reconstruction so the scope view and the
    decoder share the same time axis. Clean captures keep direct CSV time.
    """
    if isinstance(quality, dict) and quality.get("low_precision"):
        return "Reconstruct uniform timestamps"
    return "Use CSV timestamps directly"


def minmax_envelope_downsample(
    time_us: np.ndarray,
    voltage: np.ndarray,
    max_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Preserve first/minimum/maximum/last points in each display bucket."""
    n = len(time_us)
    if n <= max_points:
        return time_us, voltage
    bucket_count = max(1, max_points // 4)
    edges = np.linspace(0, n, bucket_count + 1, dtype=int)
    selected: list[int] = []
    for left, right in zip(edges[:-1], edges[1:]):
        if right <= left:
            continue
        segment = voltage[left:right]
        candidates = [
            left,
            left + int(np.argmin(segment)),
            left + int(np.argmax(segment)),
            right - 1,
        ]
        selected.extend(sorted(set(candidates)))
    index = np.asarray(sorted(set(selected)), dtype=int)
    return time_us[index], voltage[index]


def estimate_logic_levels_and_thresholds(voltage: np.ndarray) -> dict:
    """Estimate stable LOW/HIGH levels and 30%/70% Schmitt thresholds."""
    clean = np.asarray(voltage, dtype=float)
    clean = clean[np.isfinite(clean)]
    if len(clean) < 20:
        raise ValueError("Too few valid samples for automatic threshold estimation.")

    lower_limit = float(np.percentile(clean, 1.0))
    upper_limit = float(np.percentile(clean, 99.0))
    clipped = clean[(clean >= lower_limit) & (clean <= upper_limit)]
    if len(clipped) < 20:
        raise ValueError("Too few samples remain after removing voltage outliers.")

    low_center = float(np.percentile(clipped, 20.0))
    high_center = float(np.percentile(clipped, 80.0))
    for _ in range(30):
        low_distance = np.abs(clipped - low_center)
        high_distance = np.abs(clipped - high_center)
        low_cluster = clipped[low_distance <= high_distance]
        high_cluster = clipped[high_distance < low_distance]
        if len(low_cluster) == 0 or len(high_cluster) == 0:
            raise ValueError("The waveform could not be separated into LOW and HIGH levels.")
        new_low = float(np.median(low_cluster))
        new_high = float(np.median(high_cluster))
        change = max(abs(new_low - low_center), abs(new_high - high_center))
        low_center, high_center = new_low, new_high
        if change < 1e-6:
            break

    if low_center > high_center:
        low_center, high_center = high_center, low_center
        low_cluster, high_cluster = high_cluster, low_cluster
    span = high_center - low_center
    if span <= 1e-9:
        raise ValueError("No distinct LOW and HIGH voltage levels were detected.")

    return {
        "estimated_low_level": low_center,
        "estimated_high_level": high_center,
        "voltage_span": span,
        "low_threshold": low_center + 0.30 * span,
        "high_threshold": low_center + 0.70 * span,
        "low_noise": float(np.std(low_cluster)),
        "high_noise": float(np.std(high_cluster)),
    }


def detect_transitions(
    time_s: np.ndarray,
    voltage: np.ndarray,
    low_threshold: float,
    high_threshold: float,
    minimum_separation_us: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Schmitt-trigger conversion with optional transition hold-off.

    Hold-off is NOT pulse-width qualification or a complete glitch filter.
    During hold-off, the previous accepted logic state is retained.
    """
    time_s = np.asarray(time_s, dtype=float)
    voltage = np.asarray(voltage, dtype=float)

    if time_s.ndim != 1 or voltage.ndim != 1:
        raise ValueError("Time and voltage must be one-dimensional arrays.")

    if len(time_s) != len(voltage) or len(time_s) < 20:
        raise ValueError("At least 20 matching time/voltage samples are required.")

    if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(voltage)):
        raise ValueError("Selected decoder samples contain missing or infinite values.")

    if np.any(np.diff(time_s) <= 0):
        raise ValueError(
            "Decoding requires strictly increasing timestamps. "
            "Correct the CSV or explicitly select uniform reconstruction."
        )

    if not np.isfinite(low_threshold) or not np.isfinite(high_threshold):
        raise ValueError("Thresholds must be finite.")

    if low_threshold >= high_threshold:
        raise ValueError("LOW threshold must be below HIGH threshold.")

    if minimum_separation_us < 0:
        raise ValueError("Transition hold-off cannot be negative.")

    minimum_s = minimum_separation_us * 1e-6

    # If the capture begins inside the hysteresis band, the initial state
    # is ambiguous; use its position relative to the threshold midpoint.
    state = bool(voltage[0] >= (low_threshold + high_threshold) / 2.0)

    logic = np.empty(len(voltage), dtype=bool)
    logic[0] = state

    kept: list[int] = []
    last_transition_s = -np.inf

    for i in range(1, len(voltage)):
        candidate = state

        if not state and voltage[i] >= high_threshold:
            candidate = True
        elif state and voltage[i] <= low_threshold:
            candidate = False

        if (
            candidate != state
            and time_s[i] - last_transition_s >= minimum_s
        ):
            state = candidate
            kept.append(i)
            last_transition_s = time_s[i]

        logic[i] = state

    indices = np.asarray(kept, dtype=int)

    if len(indices) < 4:
        raise ValueError(
            "Fewer than four transitions were detected. Check the source, "
            "thresholds, selected frame, and transition hold-off."
        )

    return logic, indices, time_s[indices]


def decode_waveform(
    time_s: np.ndarray,
    voltage: np.ndarray,
    logic: np.ndarray,
    transition_indices: np.ndarray,
    transition_times_s: np.ndarray,
    nominal_bit_time_us: float,
    alignment: str,
    preamble_count: int,
) -> dict:
    """
    Decode using the existing project-specific convention:
        transition at midpoint = 0
        no transition at midpoint = 1

    This preserves the original project's convention. It is not a
    general-purpose standard Differential Manchester decoder.
    """
    time_s = np.asarray(time_s, dtype=float)
    voltage = np.asarray(voltage, dtype=float)
    logic = np.asarray(logic, dtype=bool)
    transition_indices = np.asarray(transition_indices, dtype=int)
    transition_times_s = np.asarray(transition_times_s, dtype=float)

    # --------------------------------------------------------
    # Input validation
    # --------------------------------------------------------
    if time_s.ndim != 1 or voltage.ndim != 1 or logic.ndim != 1:
        raise ValueError("Time, voltage, and logic must be one-dimensional.")

    if len(time_s) < 20:
        raise ValueError("At least 20 samples are required for decoding.")

    if len(voltage) != len(time_s) or len(logic) != len(time_s):
        raise ValueError("Time, voltage, and logic lengths must match.")

    if not np.all(np.isfinite(time_s)):
        raise ValueError("Time contains missing or infinite values.")

    if not np.all(np.isfinite(voltage)):
        raise ValueError("Voltage contains missing or infinite values.")

    if np.any(np.diff(time_s) <= 0):
        raise ValueError("Decoding requires strictly increasing timestamps.")

    if (
        transition_indices.ndim != 1
        or transition_times_s.ndim != 1
        or len(transition_indices) != len(transition_times_s)
        or len(transition_times_s) < 4
    ):
        raise ValueError("At least four matching transitions are required.")

    if (
        np.any(transition_indices < 0)
        or np.any(transition_indices >= len(time_s))
        or np.any(np.diff(transition_indices) <= 0)
    ):
        raise ValueError("Transition indices are invalid or out of order.")

    if (
        not np.all(np.isfinite(transition_times_s))
        or np.any(np.diff(transition_times_s) <= 0)
    ):
        raise ValueError("Transition times must be finite and increasing.")

    if not np.isfinite(nominal_bit_time_us) or nominal_bit_time_us <= 0:
        raise ValueError("Nominal bit time must be positive.")

    allowed_alignments = (
        "First transition is bit start",
        "First transition is midpoint",
    )

    if alignment not in allowed_alignments:
        raise ValueError("Unknown clock alignment.")

    preamble_count = int(preamble_count)

    if preamble_count < 1:
        raise ValueError("Preamble bit count must be at least one.")

    # --------------------------------------------------------
    # Recover a half-bit timing grid
    # --------------------------------------------------------
    nominal_half_s = nominal_bit_time_us * 1e-6 / 2.0
    grid_numbers = [0]

    for delta in np.diff(transition_times_s):
        ratio = float(delta / nominal_half_s)

        if not np.isfinite(ratio) or ratio <= 0:
            raise ValueError("Invalid transition timing.")

        # Preserve long gaps rather than compressing them into
        # a maximum of three half-bit cells.
        steps = max(1, int(round(ratio)))
        next_grid = grid_numbers[-1] + steps

        if next_grid > 200_000:
            raise ValueError(
                "The selected window spans too many half-bit cells. "
                "Select one frame or check the bit time and CSV time units."
            )

        grid_numbers.append(next_grid)

    grid_numbers = np.asarray(grid_numbers, dtype=int)

    matrix = np.column_stack([
        np.ones(len(grid_numbers)),
        grid_numbers,
    ])

    # Fit relative time to reduce numerical problems when the
    # original CSV has a large absolute timestamp origin.
    fit_origin_s = float(transition_times_s[0])
    relative_transition_s = transition_times_s - fit_origin_s

    relative_intercept_s, fitted_half_s = np.linalg.lstsq(
        matrix,
        relative_transition_s,
        rcond=None,
    )[0]

    relative_intercept_s = float(relative_intercept_s)
    fitted_half_s = float(fitted_half_s)

    if not np.isfinite(fitted_half_s) or fitted_half_s <= 0:
        raise ValueError("Clock fitting did not produce a positive period.")

    fitted_bit_s = 2.0 * fitted_half_s
    fitted_bit_us = fitted_bit_s * 1e6

    fitted_relative_transition_s = (
        relative_intercept_s + grid_numbers * fitted_half_s
    )

    fit_error_us = (
        relative_transition_s - fitted_relative_transition_s
    ) * 1e6

    max_fit_error_us = float(np.max(np.abs(fit_error_us)))
    rms_fit_error_us = float(
        np.sqrt(np.mean(np.square(fit_error_us)))
    )

    bit_time_error_percent = float(
        100.0
        * abs(fitted_bit_us - nominal_bit_time_us)
        / nominal_bit_time_us
    )

    # Preserve the original project's timing quality limits.
    clock_quality_pass = bool(
        bit_time_error_percent <= 10.0
        and max_fit_error_us <= 1.2
        and rms_fit_error_us <= 0.6
    )

    transition_grid_set = set(int(x) for x in grid_numbers)

    # --------------------------------------------------------
    # Build bit cells for the selected alignment
    # --------------------------------------------------------
    last_grid = int(grid_numbers[-1])

    if alignment == "First transition is bit start":
        start_grids = np.arange(0, last_grid + 1, 2, dtype=int)
        mid_grids = start_grids + 1

        complete_grid = mid_grids <= last_grid
        start_grids = start_grids[complete_grid]
        mid_grids = mid_grids[complete_grid]
    else:
        mid_grids = np.arange(0, last_grid + 1, 2, dtype=int)
        start_grids = mid_grids - 1

    # These times are relative to fit_origin_s.
    start_relative_s = (
        relative_intercept_s + start_grids * fitted_half_s
    )
    mid_relative_s = (
        relative_intercept_s + mid_grids * fitted_half_s
    )
    end_relative_s = start_relative_s + fitted_bit_s

    capture_start_relative_s = float(time_s[0] - fit_origin_s)
    capture_end_relative_s = float(time_s[-1] - fit_origin_s)

    # Report only cells fully inside the captured window.
    valid = (
        (start_relative_s >= capture_start_relative_s)
        & (end_relative_s <= capture_end_relative_s)
    )

    start_grids = start_grids[valid]
    mid_grids = mid_grids[valid]
    start_relative_s = start_relative_s[valid]
    mid_relative_s = mid_relative_s[valid]
    end_relative_s = end_relative_s[valid]

    if len(start_grids) == 0:
        raise ValueError(
            "No complete bit cells fit inside the selected window. "
            "Select a wider window or check bit time and alignment."
        )

    start_flags = np.asarray(
        [int(grid) in transition_grid_set for grid in start_grids],
        dtype=bool,
    )

    midpoint_flags = np.asarray(
        [int(grid) in transition_grid_set for grid in mid_grids],
        dtype=bool,
    )

    # Existing project convention, deliberately unchanged.
    bits = np.where(midpoint_flags, 0, 1).astype(int)

    # --------------------------------------------------------
    # Convert all reported times to selected-window-relative µs
    # --------------------------------------------------------
    t0 = float(time_s[0])

    time_us = (time_s - t0) * 1e6
    transition_us = (transition_times_s - t0) * 1e6

    start_us = (
        start_relative_s - capture_start_relative_s
    ) * 1e6
    mid_us = (
        mid_relative_s - capture_start_relative_s
    ) * 1e6
    end_us = (
        end_relative_s - capture_start_relative_s
    ) * 1e6

    bit_numbers = np.arange(1, len(bits) + 1)
    first_half_us = mid_us - start_us
    second_half_us = end_us - mid_us
    bit_duration_us = end_us - start_us

    # --------------------------------------------------------
    # Existing project framing assumptions
    # --------------------------------------------------------
    sections = np.full(len(bits), "PACKET_DATA", dtype=object)

    preamble_available = min(preamble_count, len(bits))
    sections[:preamble_available] = "PREAMBLE"

    sync_index = (
        preamble_count if len(bits) > preamble_count else None
    )

    if sync_index is not None:
        sections[sync_index] = "BYTE_SYNC"

    preamble_bits = bits[:preamble_available]

    preamble_valid = bool(
        len(preamble_bits) == preamble_count
        and np.all(preamble_bits == 1)
    )

    sync_bit = (
        int(bits[sync_index]) if sync_index is not None else None
    )
    sync_valid = bool(sync_bit == 0) if sync_bit is not None else False

    data_start_index = preamble_count + 1
    packet_data_bits = bits[data_start_index:]

    # --------------------------------------------------------
    # Decoded bit table
    # --------------------------------------------------------
    decoded = pd.DataFrame({
        "BitNumber": bit_numbers,
        "DecodedBit": bits,
        "DecodedBit_Inverted": 1 - bits,
        "FrameSection": sections,
        "Start_us": start_us,
        "Midpoint_us": mid_us,
        "End_us": end_us,
        "FirstHalfDuration_us": first_half_us,
        "SecondHalfDuration_us": second_half_us,
        "TotalBitDuration_us": bit_duration_us,
        "TransitionAtStart": start_flags.astype(int),
        "TransitionAtMidpoint": midpoint_flags.astype(int),
    })

    # Only intervals between detected transitions are listed.
    # Initial and final partial pulses are not included.
    pulse_start_us = transition_us[:-1]
    pulse_end_us = transition_us[1:]
    pulse_width_us = pulse_end_us - pulse_start_us

    pulse_high = logic[transition_indices[:-1]]

    pulses = pd.DataFrame({
        "PulseNumber": np.arange(1, len(pulse_width_us) + 1),
        "Level": np.where(pulse_high, "HIGH", "LOW"),
        "Start_us": pulse_start_us,
        "End_us": pulse_end_us,
        "PulseWidth_us": pulse_width_us,
    })

    frame_summary = pd.DataFrame({
        "FrameStart_us": [float(start_us[0])],
        "FrameEnd_us": [float(end_us[-1])],
        "CompleteFrameDuration_us": [
            float(end_us[-1] - start_us[0])
        ],
        "FirstTransition_us": [float(transition_us[0])],
        "LastTransition_us": [float(transition_us[-1])],
        "ActiveTransitionDuration_us": [
            float(transition_us[-1] - transition_us[0])
        ],
        "DecodedBitCount": [len(bits)],
        "DecodedZeroCount": [int(np.sum(bits == 0))],
        "DecodedOneCount": [int(np.sum(bits == 1))],
        "AverageBitDuration_us": [float(np.mean(bit_duration_us))],
        "FittedBitDuration_us": [float(fitted_bit_us)],
        "FittedHalfBitDuration_us": [float(fitted_half_s * 1e6)],
        "MaximumClockFitError_us": [max_fit_error_us],
        "RMSClockFitError_us": [rms_fit_error_us],
        "BitTimeError_percent": [bit_time_error_percent],
        "ClockQualityPass": [clock_quality_pass],
        "PreambleBitCountConfigured": [preamble_count],
        "PreambleValid": [preamble_valid],
        "SyncBit": [sync_bit],
        "SyncValid": [sync_valid],
    })

    # Keep the keys expected by app.py and create_figure().
    return {
        "time_us": time_us,
        "voltage": voltage,
        "transition_us": transition_us,
        "bits": bits,
        "start_us": start_us,
        "mid_us": mid_us,
        "end_us": end_us,
        "start_flags": start_flags,
        "midpoint_flags": midpoint_flags,
        "sections": sections,
        "decoded": decoded,
        "pulses": pulses,
        "frame_summary": frame_summary,
        "preamble_bits": preamble_bits,
        "preamble_valid": preamble_valid,
        "sync_bit": sync_bit,
        "sync_valid": sync_valid,
        "packet_data_bits": packet_data_bits,
        "fitted_bit_us": float(fitted_bit_us),
        "max_fit_error_us": max_fit_error_us,
        "rms_fit_error_us": rms_fit_error_us,
        "bit_time_error_percent": bit_time_error_percent,
        "clock_quality_pass": clock_quality_pass,
    }

def create_figure(
    result: dict,
    signal_name: str,
    max_points: int,
    low_threshold: float,
    high_threshold: float,
) -> go.Figure:
    time_us = result["time_us"]
    voltage = result["voltage"]
    display_time_us, display_voltage = minmax_envelope_downsample(
        time_us, voltage, max_points
    )

    v_min = float(np.min(voltage))
    v_max = float(np.max(voltage))
    span = max(v_max - v_min, 1.0)
    bit_y = v_max + 0.12 * span
    timing_y = v_max + 0.24 * span
    number_y = v_max + 0.36 * span
    plot_top = v_max + 0.48 * span

    decoded = result["decoded"]
    pulses = result["pulses"]
    pulse_mid = (pulses["Start_us"].to_numpy() + pulses["End_us"].to_numpy()) / 2.0
    pulse_high = pulses["Level"].to_numpy() == "HIGH"
    pulse_y = np.where(pulse_high, v_max - 0.10 * span, v_min + 0.10 * span)
    pulse_text = [
        f"{'H' if level == 'HIGH' else 'L'} {width:.3f} us"
        for level, width in zip(pulses["Level"], pulses["PulseWidth_us"])
    ]

    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=display_time_us,
        y=display_voltage,
        mode="lines",
        name=signal_name,
        line=dict(color="#155EEF", width=1),
        hovertemplate="Time: %{x:.3f} us<br>Voltage: %{y:.4f} V<extra></extra>",
    ))
    fig.add_hline(
        y=low_threshold, line_width=1, line_dash="dash", line_color="#F79009",
        annotation_text=f"LOW threshold = {low_threshold:.3f} V",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=high_threshold, line_width=1, line_dash="dash", line_color="#D92D20",
        annotation_text=f"HIGH threshold = {high_threshold:.3f} V",
        annotation_position="top right",
    )
    fig.add_trace(go.Scatter(
        x=pulse_mid,
        y=pulse_y,
        mode="text",
        name="HIGH/LOW pulse width",
        text=pulse_text,
        textfont=dict(size=9, color="#6941C6"),
        customdata=pulses[["PulseNumber", "Start_us", "End_us", "PulseWidth_us", "Level"]],
        hovertemplate=(
            "Pulse %{customdata[0]}<br>Level: %{customdata[4]}<br>"
            "Start: %{customdata[1]:.3f} us<br>End: %{customdata[2]:.3f} us<br>"
            "Width: %{customdata[3]:.3f} us<extra></extra>"
        ),
    ))
    colors = ["#d62728" if bit == 0 else "#15803d" for bit in result["bits"]]
    custom = np.column_stack([
        decoded["BitNumber"], decoded["Start_us"], decoded["Midpoint_us"],
        decoded["End_us"], decoded["TotalBitDuration_us"],
        decoded["TransitionAtStart"], decoded["TransitionAtMidpoint"],
        decoded["FrameSection"],
    ])
    fig.add_trace(go.Scatter(
        x=result["mid_us"],
        y=np.full(len(result["bits"]), bit_y),
        mode="text",
        name="Decoded bits",
        text=[str(x) for x in result["bits"]],
        textfont=dict(size=17, color=colors),
        customdata=custom,
        hovertemplate=(
            "Bit %{customdata[0]}<br>Decoded: %{text}<br>"
            "Start: %{customdata[1]:.3f} us<br>Midpoint: %{customdata[2]:.3f} us<br>"
            "End: %{customdata[3]:.3f} us<br>Total: %{customdata[4]:.3f} us<br>"
            "Transition at start: %{customdata[5]}<br>"
            "Transition at midpoint: %{customdata[6]}<br>"
            "Section: %{customdata[7]}<extra></extra>"
        ),
    ))
    fig.add_trace(go.Scatter(
        x=result["mid_us"], y=np.full(len(result["bits"]), timing_y),
        mode="text", name="Bit duration",
        text=[f"{x:.3f} us" for x in decoded["TotalBitDuration_us"]],
        textfont=dict(size=9, color="#7F56D9"), hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=result["mid_us"], y=np.full(len(result["bits"]), number_y),
        mode="text", name="Bit numbers",
        text=[f"B{n}" for n in decoded["BitNumber"]],
        textfont=dict(size=9, color="#475467"), hoverinfo="skip",
    ))

    shapes = []
    for x in result["start_us"]:
        shapes.append(dict(
            type="line", x0=float(x), x1=float(x), y0=v_min, y1=plot_top,
            line=dict(color="rgba(220,38,38,0.32)", width=1, dash="dot"),
        ))
    for x in result["mid_us"]:
        shapes.append(dict(
            type="line", x0=float(x), x1=float(x), y0=v_min, y1=v_max + 0.05 * span,
            line=dict(color="rgba(22,163,74,0.22)", width=1, dash="dash"),
        ))

    fig.update_layout(
        title=f"Differential Manchester Decoded Waveform: {signal_name}",
        xaxis_title="Time from selected capture start (us)",
        yaxis_title="Voltage (V)",
        height=760,
        margin=dict(l=70, r=40, t=80, b=80),
        template="plotly_white",
        hovermode="closest",
        dragmode="pan",
        shapes=shapes,
        legend=dict(orientation="h"),
    )
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.08))
    fig.update_yaxes(range=[v_min - 0.08 * span, plot_top])
    return fig


def bits_to_string(bits: np.ndarray) -> str:
    return "".join(str(int(x)) for x in bits)


def group_bits(bit_string: str, width: int = 8) -> str:
    return " ".join(bit_string[i:i + width] for i in range(0, len(bit_string), width))


def dataframe_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def bits_to_hex(bit_string: str) -> tuple[str, list[dict]]:
    """Convert complete 8-bit groups to two-digit hexadecimal values."""
    byte_details: list[dict] = []
    hex_values: list[str] = []

    for start in range(0, len(bit_string), 8):
        group = bit_string[start:start + 8]
        if len(group) != 8:
            byte_details.append({
                "ByteNumber": len(byte_details) + 1,
                "Binary": group,
                "Hex": "INCOMPLETE",
                "Decimal": np.nan,
                "CompleteByte": 0,
            })
            continue

        decimal_value = int(group, 2)
        hex_value = f"{decimal_value:02X}"
        hex_values.append(hex_value)
        byte_details.append({
            "ByteNumber": len(byte_details) + 1,
            "Binary": group,
            "Hex": f"0x{hex_value}",
            "Decimal": decimal_value,
            "CompleteByte": 1,
        })

    return " ".join(hex_values), byte_details


# ============================================================
# MSO-STYLE PROTOCOL DECODERS
# ============================================================

def channel_logic(
    signal: np.ndarray,
    low_threshold: float | None = None,
    high_threshold: float | None = None,
) -> np.ndarray:
    """Schmitt-triggered 0/1 sample sequence (protocol decoders sample it later)."""
    sig = np.asarray(signal, dtype=float)
    if len(sig) < 1:
        raise ValueError("Empty channel cannot be converted to logic levels.")

    if low_threshold is None or high_threshold is None:
        levels = estimate_logic_levels_and_thresholds(sig)
        low_threshold = float(levels["low_threshold"])
        high_threshold = float(levels["high_threshold"])

    logic = np.empty(len(sig), dtype=bool)
    stable = int(sig[0] >= (low_threshold + high_threshold) / 2.0)

    for i, value in enumerate(sig):
        if value >= high_threshold:
            stable = 1
        elif value <= low_threshold:
            stable = 0
        logic[i] = bool(stable)

    return logic


def transitions_of(logic: np.ndarray) -> np.ndarray:
    """Indices (>=1) where the boolean sample sequence changes state."""
    diff = np.diff(np.asarray(logic, dtype=np.int8))
    return np.flatnonzero(diff != 0) + 1


def _sample_nearest(
    times: np.ndarray,
    values: np.ndarray,
    query_times: np.ndarray,
) -> np.ndarray:
    """Value at the sample whose timestamp is closest to each query time."""
    times = np.asarray(times, dtype=float)
    values = np.asarray(values)
    qt = np.asarray(query_times, dtype=float)

    i = np.searchsorted(times, qt, side="right")
    previous = np.clip(i - 1, 0, len(times) - 1)
    following = np.clip(i, 0, len(times) - 1)
    closer = np.where(
        np.abs(times[previous] - qt) <= np.abs(times[following] - qt),
        previous,
        following,
    )
    return values[closer]


def _sample_before(
    times: np.ndarray,
    values: np.ndarray,
    query_times: np.ndarray,
) -> np.ndarray:
    """Value at the last sample at or before each query time."""
    times = np.asarray(times, dtype=float)
    i = np.searchsorted(times, np.asarray(query_times), side="right")
    i = np.clip(i - 1, 0, len(times) - 1)
    return np.asarray(values)[i]


def _decode_guards(
    time_s: np.ndarray,
    samples: np.ndarray,
    minimum: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    time_s = np.asarray(time_s, dtype=float)
    samples = np.asarray(samples, dtype=float)
    if time_s.ndim != 1 or samples.ndim != 1 or len(time_s) != len(samples):
        raise ValueError("Time and signal must be one-dimensional and equal length.")
    if len(time_s) < minimum:
        raise ValueError(f"At least {minimum} samples are required for decoding.")
    if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(samples)):
        raise ValueError("Capture contains missing or infinite values.")
    if np.any(np.diff(time_s) <= 0):
        raise ValueError(
            "Decoding requires strictly increasing timestamps. "
            "Select 'Uniform reconstruction' on the decoder time axis or correct the CSV."
        )
    return time_s, samples


def _clock_fit(
    transition_times_s: np.ndarray,
    nominal_period_s: float,
) -> dict:
    """Shared linear clock fit for transition-grid decoders (Manchester family)."""
    nominal_half_s = nominal_period_s / 2.0
    grid_numbers = [0]
    for delta in np.diff(transition_times_s):
        ratio = float(delta / nominal_half_s)
        if not np.isfinite(ratio) or ratio <= 0:
            raise ValueError("Invalid transition timing.")
        steps = max(1, int(round(ratio)))
        grid_numbers.append(grid_numbers[-1] + steps)

    grid_numbers = np.asarray(grid_numbers, dtype=int)
    matrix = np.column_stack([np.ones(len(grid_numbers)), grid_numbers])
    origin = float(transition_times_s[0])
    relative = transition_times_s - origin
    intercept, fitted_half_s = np.linalg.lstsq(matrix, relative, rcond=None)[0]
    intercept = float(intercept)
    fitted_half_s = float(fitted_half_s)
    if not np.isfinite(fitted_half_s) or fitted_half_s <= 0:
        raise ValueError("Clock fitting did not produce a positive period.")

    fitted = intercept + grid_numbers * fitted_half_s
    error_us = (relative - fitted) * 1e6
    fitted_bit_s = 2.0 * fitted_half_s
    return {
        "grid_numbers": grid_numbers,
        "fitted_half_s": fitted_half_s,
        "fitted_bit_us": fitted_bit_s * 1e6,
        "t0_s": origin,
        "max_err_us": float(np.max(np.abs(error_us))),
        "rms_err_us": float(np.sqrt(np.mean(np.square(error_us)))),
        "bit_error_percent": float(
            100.0 * abs(fitted_bit_s - nominal_period_s) / nominal_period_s
        ),
    }


# ------------------------------------------------------------
# Standard Manchester (Biphase-L)
# ------------------------------------------------------------
def decode_manchester(
    time_s: np.ndarray,
    voltage: np.ndarray,
    low_threshold: float,
    high_threshold: float,
    nominal_bit_us: float,
    mid_low_high_is_one: bool = True,
) -> dict:
    """Standard Biphase-L / IEEE 802.3 Manchester: midpoint transition always present."""
    time_s, voltage = _decode_guards(time_s, voltage)

    if not np.isfinite(low_threshold) or not np.isfinite(high_threshold):
        raise ValueError("Thresholds must be finite.")
    if low_threshold >= high_threshold:
        raise ValueError("LOW threshold must be below HIGH threshold.")
    if not np.isfinite(nominal_bit_us) or nominal_bit_us <= 0:
        raise ValueError("Nominal bit time must be positive.")

    logic = channel_logic(voltage, low_threshold, high_threshold)
    transition_idx = transitions_of(logic)
    if len(transition_idx) < 4:
        raise ValueError(
            "Fewer than four transitions detected. Check the source, thresholds, "
            "and whether the signal is Manchester-encoded."
        )

    transition_times_s = time_s[transition_idx]
    fit = _clock_fit(transition_times_s, nominal_bit_us * 1e-6)

    direction: dict[int, bool] = {}
    for grid, edge in zip(
        fit["grid_numbers"].tolist(),
        transition_idx.tolist(),
    ):
        direction[int(grid)] = bool(logic[edge])

    last_grid = int(fit["grid_numbers"][-1])
    # In standard Manchester the FIRST transition is a midpoint of the first bit.
    # Midpoint transitions land on even relative grid numbers; boundary edges (if
    # present) land on odd numbers. Bit cells span [mid-1, mid+1].
    mid_grids = np.arange(0, last_grid + 1, 2, dtype=int)
    start_grids = mid_grids - 1

    complete = mid_grids + 1 <= last_grid
    start_grids = start_grids[complete]
    mid_grids = mid_grids[complete]

    start_relative_s = fit["t0_s"] + (start_grids - fit["grid_numbers"][0]) * fit["fitted_half_s"]
    mid_relative_s = fit["t0_s"] + (mid_grids - fit["grid_numbers"][0]) * fit["fitted_half_s"]

    within_window = (
        (start_relative_s >= float(time_s[0]))
        & (mid_relative_s <= float(time_s[-1]))
    )
    start_grids = start_grids[within_window]
    mid_grids = mid_grids[within_window]

    if len(start_grids) == 0:
        raise ValueError("No complete Manchester bit cells fit inside the window.")

    bits_list: list[int] = []
    valid_list: list[bool] = []
    mid_rising_list: list[int] = []

    for mid_grid in mid_grids.tolist():
        present = int(mid_grid) in direction
        if present:
            rising = direction[int(mid_grid)]
            bit = 1 if rising == mid_low_high_is_one else 0
        else:
            rising = 0
            bit = -1
        bits_list.append(bit)
        valid_list.append(present)
        mid_rising_list.append(int(rising))

    bits = np.asarray(bits_list, dtype=int)
    valid = np.asarray(valid_list, dtype=bool)

    t0 = float(time_s[0])
    start_us = (start_relative_s - t0) * 1e6
    mid_us = (mid_relative_s - t0) * 1e6
    end_us = start_us + fit["fitted_bit_us"]

    decoded = pd.DataFrame({
        "BitNumber": np.arange(1, len(bits) + 1),
        "DecodedBit": np.where(valid, bits, -1),
        "Valid": valid,
        "MidpointDirection": mid_rising_list,
        "Start_us": start_us,
        "Midpoint_us": mid_us,
        "End_us": end_us,
        "BitDuration_us": end_us - start_us,
    })

    bit_string = "".join(str(int(b)) for b in bits[valid])
    byte_table = pd.DataFrame(
        bits_to_hex(bit_string)[1],
        columns=["ByteNumber", "Binary", "Hex", "Decimal", "CompleteByte"],
    )

    clock_pass = bool(
        fit["bit_error_percent"] <= 10.0
        and fit["max_err_us"] <= 1.2
        and fit["rms_err_us"] <= 0.6
    )

    summary = pd.DataFrame({
        "DecodedBitCount": [int(len(bits))],
        "ValidBitCount": [int(np.sum(valid))],
        "InvalidMidpointCount": [int(np.sum(~valid))],
        "FittedBitDuration_us": [fit["fitted_bit_us"]],
        "MaximumClockFitError_us": [fit["max_err_us"]],
        "RMSClockFitError_us": [fit["rms_err_us"]],
        "BitTimeError_percent": [fit["bit_error_percent"]],
        "ClockQualityPass": [clock_pass],
        "Convention": ["Midpoint low->high = 1" if mid_low_high_is_one else "Midpoint low->high = 0"],
    })

    text = (
        "Manchester (Biphase-L) decoder\n"
        f"Convention: midpoint {'low->high = 1, high->low = 0' if mid_low_high_is_one else 'low->high = 0, high->low = 1'}\n"
        f"Clock fit pass: {clock_pass}\n"
        f"Valid bits: {int(np.sum(valid))}/{len(bits)}\n"
        "\nComplete decoded bits:\n"
        + bits_to_string(bits[valid])
        + "\n\nByte groups (MSB-first):\n"
        + group_bits(bits_to_string(bits[valid]))
    )

    return {
        "protocol": "Manchester (Biphase-L)",
        "metrics": [
            ("Bits", str(len(bits))),
            ("Valid", f"{int(np.sum(valid))}/{len(bits)}"),
            ("Fitted bit time", f"{fit['fitted_bit_us']:.4f} µs"),
            ("Clock fit err", f"{fit['rms_err_us']:.4f} µs"),
        ],
        "status": [
            ("Clock quality", clock_pass),
            ("All midpoints valid", bool(np.all(valid))),
        ],
        "tables": [
            ("Decoded bits", decoded),
            ("Bytes (MSB-first)", byte_table),
            ("Frame summary", summary),
        ],
        "text": text,
        "figure": None,
    }


# ------------------------------------------------------------
# UART / RS-232 async serial
# ------------------------------------------------------------
def decode_uart(
    time_s: np.ndarray,
    voltage: np.ndarray,
    low_threshold: float,
    high_threshold: float,
    baud: float,
    data_bits: int = 8,
    parity: str = "none",
    stop_bits: float = 1.0,
    idle: str = "HIGH",
    invert: bool = False,
    lsb_first: bool = True,
) -> dict:
    time_s, voltage = _decode_guards(time_s, voltage)
    if baud <= 0:
        raise ValueError("Baud rate must be positive.")
    if data_bits < 5 or data_bits > 9:
        raise ValueError("Data bits must be between 5 and 9.")
    if parity not in ("none", "even", "odd"):
        raise ValueError("Parity must be none, even, or odd.")

    logic = channel_logic(voltage, low_threshold, high_threshold)
    if invert:
        logic = ~logic

    idle_high = idle == "HIGH"
    bit_s = 1.0 / baud
    parity_bits = 1 if parity != "none" else 0
    frame_s = bit_s * (data_bits + parity_bits + stop_bits)

    logic_int = logic.astype(np.int8)
    trans = np.flatnonzero(np.diff(logic_int) < 0) + 1

    rows: list[dict] = []
    grid_rows: list[dict] = []
    capture_start = float(time_s[0])
    capture_end = float(time_s[-1])
    frame_end_guard = -np.inf
    frame_errors = 0
    parity_errors = 0
    bytes_read = 0

    for edge in trans:
        t0 = float(time_s[edge])
        if t0 < frame_end_guard:
            continue

        frame_end = t0 + frame_s + 0.5 * bit_s
        if frame_end > capture_end:
            break

        data_times = t0 + (1.5 + np.arange(data_bits)) * bit_s
        sampled = _sample_nearest(time_s, logic_int, data_times)
        sampled = sampled.astype(int)

        if lsb_first:
            value = int(np.sum(sampled << np.arange(data_bits)))
        else:
            value = int(np.sum(sampled << np.arange(data_bits - 1, -1, -1)))

        errors: list[str] = []

        # Bit slots: start [0,1), data [1, 1+data_bits), parity, then stop bits.
        stop_time = t0 + (1.0 + data_bits + parity_bits + stop_bits / 2.0) * bit_s
        parity_time = t0 + (1.0 + data_bits + parity_bits / 2.0) * bit_s if parity_bits else None
        stop_sample = int(_sample_nearest(time_s, logic_int, np.array([stop_time]))[0])
        if (stop_sample == 1) != idle_high:
            errors.append("framing")
            frame_errors += 1

        if parity_bits:
            parity_value = int(
                _sample_nearest(time_s, logic_int, np.array([parity_time]))[0]
            )
            ones = int(np.sum(sampled))
            if parity == "even":
                ok = (ones + parity_value) % 2 == 0
            else:
                ok = (ones + parity_value) % 2 == 1
            if not ok:
                errors.append("parity")
                parity_errors += 1

        role_names = ["Start"]
        role_names += [f"D{i}" for i in range(data_bits)]
        if parity_bits:
            role_names.append("Parity")
        role_names.append("Stop")

        sample_times = [t0]
        sample_times += data_times.tolist()
        if parity_bits:
            sample_times.append(parity_time)
        sample_times.append(stop_time)

        sample_levels = [
            int(_sample_nearest(time_s, logic_int, np.array([st]))[0])
            for st in sample_times
        ]

        for role, stt, level in zip(role_names, sample_times, sample_levels):
            grid_rows.append({
                "Frame": bytes_read + 1,
                "Role": role,
                "Time_us": (stt - capture_start) * 1e6,
                "Level": int(level),
            })

        rows.append({
            "ByteNumber": bytes_read + 1,
            "Hex": f"0x{value:02X}",
            "Decimal": value,
            "Char": chr(value) if 32 <= value <= 126 else ".",
            "BitOrder": "LSB first" if lsb_first else "MSB first",
            "Status": ", ".join(errors) if errors else "OK",
        })
        bytes_read += 1
        frame_end_guard = frame_end

    if bytes_read == 0:
        raise ValueError(
            "No UART start bits were found. Check the source signal, idle level, "
            "invert option, baud rate, and thresholds."
        )

    bytes_df = pd.DataFrame(rows)
    grid_df = pd.DataFrame(grid_rows)

    active_us = (
        bytes_read * frame_s
    ) * 1e6

    text = (
        "UART / RS-232 decoder\n"
        f"Baud: {baud:g}  Data bits: {data_bits}  Parity: {parity}  Stop: {stop_bits:g}\n"
        f"Idle: {idle}  Invert: {invert}  Bit order: {'LSB' if lsb_first else 'MSB'} first\n"
        f"Bytes decoded: {bytes_read}  Framing errors: {frame_errors}  Parity errors: {parity_errors}\n"
        "\nDecoded bytes:\n"
        + " ".join(f"{row['Hex']}:{row['Char']}" for row in rows)
    )

    return {
        "protocol": "UART / RS-232",
        "metrics": [
            ("Bytes", str(bytes_read)),
            ("Baud", f"{baud:g}"),
            ("Framing errors", str(frame_errors)),
            ("Parity errors", str(parity_errors)),
        ],
        "status": [
            ("Framing clean", frame_errors == 0),
            ("Parity correct", parity_errors == 0),
        ],
        "tables": [
            ("Decoded bytes", bytes_df),
            ("Bit sampling grid", grid_df),
        ],
        "text": text,
        "figure": None,
    }


# ------------------------------------------------------------
# NRZ synchronous (clocked) bit stream
# ------------------------------------------------------------
def decode_nrz(
    time_s: np.ndarray,
    voltage: np.ndarray,
    low_threshold: float,
    high_threshold: float,
    bit_time_us: float,
    phase_ratio: float = 0.5,
    bits_per_word: int = 8,
    lsb_first: bool = False,
) -> dict:
    time_s, voltage = _decode_guards(time_s, voltage)
    if bit_time_us <= 0:
        raise ValueError("Bit time must be positive.")
    if phase_ratio < 0.0 or phase_ratio > 1.0:
        raise ValueError("Phase ratio must be between 0 and 1.")

    logic = channel_logic(voltage, low_threshold, high_threshold)
    logic_int = logic.astype(np.int8)
    bit_s = bit_time_us * 1e-6

    first = float(time_s[0])
    last = float(time_s[-1])
    count = int((last - first) / bit_s)
    if count < bits_per_word:
        raise ValueError(
            "Captured window is shorter than one NRZ word. Increase the window "
            "or reduce bit time."
        )

    sample_times = first + (np.arange(count) + phase_ratio) * bit_s
    bits = _sample_nearest(time_s, logic_int, sample_times).astype(int)

    word_rows: list[dict] = []
    bit_rows: list[dict] = []

    word_count = count // bits_per_word
    for w in range(word_count):
        segment = bits[w * bits_per_word: (w + 1) * bits_per_word]
        if lsb_first:
            value = int(np.sum(segment << np.arange(bits_per_word)))
        else:
            value = int(np.sum(segment << np.arange(bits_per_word - 1, -1, -1)))
        word_rows.append({
            "WordNumber": w + 1,
            "Binary": bits_to_string(segment),
            "Hex": f"0x{value:02X}",
            "Decimal": value,
            "Char": chr(value) if 32 <= value <= 126 else ".",
            "BitOrder": "LSB first" if lsb_first else "MSB first",
        })

    remainder = bits[word_count * bits_per_word:]
    if len(remainder) > 0:
        word_rows.append({
            "WordNumber": word_count + 1,
            "Binary": bits_to_string(remainder),
            "Hex": "INCOMPLETE",
            "Decimal": np.nan,
            "Char": "—",
            "BitOrder": "partial",
        })

    for k, bit in enumerate(bits, start=1):
        bit_rows.append({
            "BitNumber": k,
            "Bit": int(bit),
            "Time_us": (sample_times[k - 1] - first) * 1e6,
        })

    text = (
        "NRZ synchronous (clocked) decoder\n"
        f"Bit time: {bit_time_us:.6f} µs  Phase: {phase_ratio:.2f}  "
        f"Words: {bits_per_word} bits  Order: {'LSB' if lsb_first else 'MSB'} first\n"
        "Bits: " + bits_to_string(bits)
    )

    return {
        "protocol": "NRZ (clocked)",
        "metrics": [
            ("Bits", str(len(bits))),
            ("Words", str(len([w for w in word_rows if w['BitOrder'] != 'partial']))),
            ("Bit time (µs)", f"{bit_time_us:.6f}"),
            ("Phase", f"{phase_ratio:.2f}"),
        ],
        "status": [
            ("Window sampled", bool(len(bits) >= 8)),
        ],
        "tables": [
            ("Words", pd.DataFrame(word_rows)),
            ("Bit stream", pd.DataFrame(bit_rows)),
        ],
        "text": text,
        "figure": None,
    }


# ------------------------------------------------------------
# PWM / pulse-width measurement
# ------------------------------------------------------------
def decode_pwm(
    time_s: np.ndarray,
    voltage: np.ndarray,
    low_threshold: float,
    high_threshold: float,
    min_pulse_us: float = 0.0,
) -> dict:
    time_s, voltage = _decode_guards(time_s, voltage)
    if min_pulse_us < 0:
        raise ValueError("Minimum pulse width cannot be negative.")

    logic = channel_logic(voltage, low_threshold, high_threshold)
    edges = transitions_of(logic)
    if len(edges) < 2:
        raise ValueError(
            "Fewer than two transitions were detected. Check the source and thresholds."
        )

    edge_times = time_s[edges]
    start = float(time_s[0])

    rows: list[dict] = []
    min_s = min_pulse_us * 1e-6
    pulses = 0

    for i in range(len(edge_times) - 1):
        t_a = float(edge_times[i])
        t_b = float(edge_times[i + 1])
        if t_b - t_a + 1e-12 < min_s:
            continue
        level = bool(logic[edges[i]])
        rows.append({
            "PulseNumber": len(rows) + 1,
            "Level": "HIGH" if level else "LOW",
            "Start_us": (t_a - start) * 1e6,
            "End_us": (t_b - start) * 1e6,
            "Width_us": (t_b - t_a) * 1e6,
        })
        pulses += 1

    if not rows:
        raise ValueError("No valid pulses after applying the minimum width filter.")

    pulse_df = pd.DataFrame(rows)
    high = pulse_df[pulse_df["Level"] == "HIGH"]
    low = pulse_df[pulse_df["Level"] == "LOW"]

    periods: list[float] = []
    for i in range(len(rows) - 1):
        if rows[i]["Level"] == "HIGH":
            next_same = [r for r in rows[i + 1:] if r["Level"] == "HIGH"]
            if next_same:
                periods.append(next_same[0]["Start_us"] - rows[i]["Start_us"])

    periods_np = np.asarray(periods, dtype=float)
    high_widths = high["Width_us"].to_numpy(dtype=float)
    low_widths = low["Width_us"].to_numpy(dtype=float)
    low_widths = low_widths[~np.isnan(low_widths)]

    summary = pd.DataFrame({
        "Metric": [
            "Valid pulses",
            "HIGH pulse count",
            "LOW pulse count",
            "Mean period (µs)",
            "Frequency (kHz)",
            "Mean duty cycle",
            "Min HIGH width (µs)",
            "Max HIGH width (µs)",
        ],
        "Value": [
            str(pulses),
            str(len(high)),
            str(len(low)),
            f"{float(np.mean(periods)):.4f}" if len(periods_np) else "—",
            f"{1000.0 / float(np.mean(periods)):.4f}" if len(periods_np) else "—",
            f"{float(np.mean(high_widths) / np.mean(periods)):.3%}" if len(periods_np) and len(high_widths) else "—",
            f"{float(np.min(high_widths)):.4f}" if len(high_widths) else "—",
            f"{float(np.max(high_widths)):.4f}" if len(high_widths) else "—",
        ],
    })

    text = (
        "PWM / pulse-width decoder\n"
        f"Pulses: {pulses}\n"
        + summary.to_string(index=False)
    )

    return {
        "protocol": "PWM / pulse-width",
        "metrics": [
            ("Pulses", str(pulses)),
            ("HIGH pulses", str(len(high))),
            ("LOW pulses", str(len(low))),
            (
                "Mean frequency",
                f"{1000.0 / float(np.mean(periods)):.4f} kHz" if len(periods_np) else "—",
            ),
        ],
        "status": [
            ("Pulse widths above minimum", True),
        ],
        "tables": [
            ("Pulses", pulse_df),
            ("Summary", summary),
        ],
        "text": text,
        "figure": None,
    }


# ------------------------------------------------------------
# SPI (master view, 4-wire)
# ------------------------------------------------------------
def decode_spi(
    time_s: np.ndarray,
    clock: np.ndarray,
    mosi: np.ndarray,
    miso: np.ndarray,
    chip_select: np.ndarray,
    cpol: int = 0,
    cpha: int = 0,
    cs_active: str = "LOW",
    bits_per_word: int = 8,
    msb_first: bool = True,
    merge_gap_us: float = 0.0,
) -> dict:
    time_s, _ = _decode_guards(time_s, clock)
    for name, channel in (("clock", clock), ("MOSI", mosi), ("MISO", miso), ("CS", chip_select)):
        if len(channel) != len(time_s):
            raise ValueError(f"SPI {name} channel length must match the time axis.")
        if not np.all(np.isfinite(channel)):
            raise ValueError(f"SPI {name} channel contains missing or infinite values.")
    if cpol not in (0, 1) or cpha not in (0, 1):
        raise ValueError("CPOL and CPHA must be 0 or 1.")
    if cs_active not in ("LOW", "HIGH"):
        raise ValueError("CS active level must be LOW or HIGH.")
    if bits_per_word < 1 or bits_per_word > 32:
        raise ValueError("Bits per word must be between 1 and 32.")

    l_clk = channel_logic(clock).astype(np.int8)
    l_mosi = channel_logic(mosi).astype(np.int8)
    l_miso = channel_logic(miso).astype(np.int8)
    l_cs = channel_logic(chip_select).astype(np.int8)

    active_level = 0 if cs_active == "LOW" else 1
    active_mask = l_cs == active_level
    active_idx = np.flatnonzero(active_mask)
    if len(active_idx) == 0:
        raise ValueError(
            f"No interval where {cs_active}-active chip select is held. "
            "Check the CS channel selection and active level."
        )

    median_dt = float(np.median(np.diff(time_s))) if len(time_s) > 1 else 0.0
    if not np.isfinite(median_dt) or median_dt <= 0:
        raise ValueError("Time axis has zero or non-finite spacing.")
    merge_samples = max(1, int(round(merge_gap_us * 1e-6 / median_dt)))

    runs: list[tuple[int, int]] = []
    segment_start = int(active_idx[0])
    segment_end = int(active_idx[0])
    for x in active_idx[1:]:
        x = int(x)
        if x - 1 <= segment_end + merge_samples:
            segment_end = x
        else:
            runs.append((segment_start, segment_end))
            segment_start, segment_end = x, x
    runs.append((segment_start, segment_end))

    leading_value = (cpol == 0)

    word_rows: list[dict] = []
    latch_rows: list[dict] = []
    frame_number = 0
    words_per_frame: list[int] = []

    for frame_number, (i0, i1) in enumerate(runs, start=1):
        sub_time = time_s[i0:i1 + 1]
        sub_clk = l_clk[i0:i1 + 1]
        clock_edges = transitions_of(sub_clk)
        frame_bits_mosi: list[int] = []
        frame_bits_miso: list[int] = []
        words_in_frame = 0

        for j in clock_edges:
            val = bool(sub_clk[j])
            edge_is_leading = (val == leading_value)
            latch = edge_is_leading if cpha == 0 else (not edge_is_leading)
            if not latch:
                continue

            t_edge = float(sub_time[j])
            mosi_bit = int(_sample_nearest(time_s, l_mosi, np.array([t_edge]))[0])
            miso_bit = int(_sample_nearest(time_s, l_miso, np.array([t_edge]))[0])
            frame_bits_mosi.append(mosi_bit)
            frame_bits_miso.append(miso_bit)

            latch_rows.append({
                "Frame": frame_number,
                "LatchNumber": len(frame_bits_mosi),
                "Time_us": (t_edge - float(time_s[0])) * 1e6,
                "MOSI_bit": mosi_bit,
                "MISO_bit": miso_bit,
            })

            if len(frame_bits_mosi) == bits_per_word:
                mos_arr = np.asarray(frame_bits_mosi, dtype=int)
                mis_arr = np.asarray(frame_bits_miso, dtype=int)
                shift = (
                    np.arange(bits_per_word - 1, -1, -1)
                    if msb_first
                    else np.arange(bits_per_word)
                )
                word_mosi = int(np.sum(mos_arr << shift))
                word_miso = int(np.sum(mis_arr << shift))
                word_rows.append({
                    "Frame": frame_number,
                    "WordInFrame": words_in_frame + 1,
                    "MOSI_Binary": bits_to_string(mos_arr),
                    "MOSI_Hex": f"0x{word_mosi:0{max(2, (bits_per_word + 3) // 4)}X}",
                    "MOSI_Decimal": word_mosi,
                    "MISO_Binary": bits_to_string(mis_arr),
                    "MISO_Hex": f"0x{word_miso:0{max(2, (bits_per_word + 3) // 4)}X}",
                    "MISO_Decimal": word_miso,
                })
                words_in_frame += 1
                frame_bits_mosi = []
                frame_bits_miso = []

        if frame_bits_mosi:
            word_rows.append({
                "Frame": frame_number,
                "WordInFrame": words_in_frame + 1,
                "MOSI_Binary": bits_to_string(np.asarray(frame_bits_mosi, dtype=int)),
                "MOSI_Hex": "TRAILING",
                "MOSI_Decimal": np.nan,
                "MISO_Binary": bits_to_string(np.asarray(frame_bits_miso, dtype=int)),
                "MISO_Hex": "TRAILING",
                "MISO_Decimal": np.nan,
            })

        words_per_frame.append(words_in_frame)

    if not word_rows:
        raise ValueError("No complete SPI words were latched. Check CPOL/CPHA, CS level, and channels.")

    word_df = pd.DataFrame(word_rows)
    latch_df = pd.DataFrame(latch_rows)

    text = (
        "SPI decoder (master view)\n"
        f"CPOL={cpol} CPHA={cpha}  CS active: {cs_active}  "
        f"Words: {bits_per_word} bits  Order: {'MSB' if msb_first else 'LSB'} first\n"
        f"Frames: {len(runs)}\n"
        f"Words: {len([r for r in word_rows if str(r['MOSI_Hex']) != 'TRAILING'])} (trailing bits in "
        f"{len([r for r in word_rows if str(r['MOSI_Hex']) == 'TRAILING'])} frames)\n"
        "\nMOSI bytes:\n"
        + " ".join(r["MOSI_Hex"] for r in word_rows if str(r["MOSI_Hex"]) != "TRAILING")
        + "\nMISO bytes:\n"
        + " ".join(r["MISO_Hex"] for r in word_rows if str(r["MISO_Hex"]) != "TRAILING")
    )

    return {
        "protocol": "SPI",
        "metrics": [
            ("Frames", str(len(runs))),
            ("Words", str(len([r for r in word_rows if str(r['MOSI_Hex']) != 'TRAILING']))),
            (
                "Trailing partial",
                str(len([r for r in word_rows if str(r['MOSI_Hex']) == 'TRAILING'])),
            ),
            ("Words/frame", str(max(words_per_frame)) if words_per_frame else "—"),
        ],
        "status": [
            ("CS active intervals found", True),
            ("Words latched", bool(len(word_rows) > 0)),
        ],
        "tables": [
            ("Words (MOSI/MISO)", word_df),
            ("Clock latch edges", latch_df),
        ],
        "text": text,
        "figure": None,
    }


# ------------------------------------------------------------
# I2C (7-bit addressing)
# ------------------------------------------------------------
def decode_i2c(
    time_s: np.ndarray,
    scl: np.ndarray,
    sda: np.ndarray,
) -> dict:
    time_s, _ = _decode_guards(time_s, scl)
    if len(scl) != len(time_s) or len(sda) != len(time_s):
        raise ValueError("SCL and SDA channel lengths must match the time axis.")
    if not np.all(np.isfinite(scl)) or not np.all(np.isfinite(sda)):
        raise ValueError("SCL/SDA contain missing or infinite values.")

    l_scl = channel_logic(scl).astype(np.int8)
    l_sda = channel_logic(sda).astype(np.int8)

    scl_rising = np.flatnonzero(np.diff(l_scl) > 0) + 1
    sda_edges = np.flatnonzero(np.diff(l_sda) != 0) + 1

    starts: list[int] = []
    stops: list[int] = []

    for edge_index in sda_edges:
        t_edge = float(time_s[edge_index])
        scl_high = bool(
            _sample_before(time_s, l_scl, np.array([t_edge]))[0]
        )
        if not scl_high:
            continue
        if l_sda[edge_index] == 1:
            stops.append(int(edge_index))
        else:
            starts.append(int(edge_index))

    if not starts:
        raise ValueError(
            "No I2C START condition detected (SDA falling while SCL high). "
            "Check SCL/SDA wiring and thresholds."
        )

    transcript: list[dict] = []
    message_index = 0
    nack_errors = 0
    bytes_count = 0

    for start_index in starts:
        following_stop = [s for s in stops if s > start_index]
        following_start = [s for s in starts if s > start_index]
        end_index_candidates = [len(time_s) - 1]
        if following_stop:
            end_index_candidates.append(min(following_stop))
        if following_start:
            end_index_candidates.append(min(following_start))
        end_index = min(end_index_candidates)

        start_time = float(time_s[start_index])
        transcript.append({
            "Index": len(transcript) + 1,
            "Event": "START",
            "Value": "S",
            "Time_us": (start_time - float(time_s[0])) * 1e6,
            "Notes": f"Message {message_index + 1} begins",
        })
        message_index += 1

        rising_in = [int(r) for r in scl_rising if start_index < int(r) < end_index]
        bit_values = [int(l_sda[r]) for r in rising_in]

        chunk = 0
        while len(bit_values) >= 9:
            frame_bits = bit_values[:8]
            ack = bit_values[8]
            bit_values = bit_values[9:]
            value = int("".join(str(b) for b in frame_bits), 2)

            role = "DATA"
            notes = ""
            if chunk == 0 and message_index >= 1:
                address = (value >> 1) & 0x7F
                rw = value & 1
                role = "ADDRESS"
                notes = (
                    f"7-bit addr 0x{address:02X}, write"
                    if rw == 0
                    else f"7-bit addr 0x{address:02X}, read"
                )
            if ack == 0:
                notes = notes + (" - ACK" if notes else "ACK")
            else:
                notes = notes + (" - NACK" if notes else "NACK")
                nack_errors += 1
            bytes_count += 1

            transcript.append({
                "Index": len(transcript) + 1,
                "Event": role,
                "Value": f"0x{value:02X}",
                "Time_us": None,
                "Notes": notes,
            })
            chunk += 1

        if bit_values:
            transcript.append({
                "Index": len(transcript) + 1,
                "Event": "PARTIAL",
                "Value": "".join(str(b) for b in bit_values),
                "Time_us": None,
                "Notes": f"{len(bit_values)} bits before bus end / STOP",
            })

        if following_stop and end_index == min(following_stop):
            stop_time = float(time_s[end_index])
            transcript.append({
                "Index": len(transcript) + 1,
                "Event": "STOP",
                "Value": "P",
                "Time_us": (stop_time - float(time_s[0])) * 1e6,
                "Notes": f"Message {message_index} ends",
            })
        else:
            transcript.append({
                "Index": len(transcript) + 1,
                "Event": "BUS_ACTIVE",
                "Value": "-",
                "Time_us": None,
                "Notes": "Bus terminates inside the capture window (no STOP seen)",
            })

    transcript_df = pd.DataFrame(transcript)
    messages = message_index

    text = (
        "I2C decoder (7-bit addressing)\n"
        f"Messages: {messages}  Address/data bytes: {bytes_count}  NACKs: {nack_errors}\n"
        "Event meanings: S = START, P = STOP, ADDRESS byte = 7-bit address + R/W bit\n"
        "\n" + transcript_df.to_string(index=False)
    )

    return {
        "protocol": "I2C",
        "metrics": [
            ("Messages", str(messages)),
            ("Bytes", str(bytes_count)),
            ("NACK errors", str(nack_errors)),
            ("START/STOP", f"{len(starts)}/{len(stops)}"),
        ],
        "status": [
            ("START detected", True),
            ("All ACK", nack_errors == 0),
        ],
        "tables": [
            ("Bus transcript", transcript_df),
        ],
        "text": text,
        "figure": None,
    }


def validate_differential_manchester_structure(
    result: dict,
    observed_transition_times_s: np.ndarray | None = None,
    decoder_window_start_s: float = 0.0,
    boundary_tolerance_us: float = 1.0,
    # Structural safety threshold derived from the Phase 0.8 characterization:
    # known-good frames showed ~96-99% boundary support while a sparse
    # reconstruction-artifact candidate showed ~28%. This is an independent
    # waveform-evidence guard, NOT a Differential Manchester protocol rule.
    min_boundary_transition_coverage: float = 0.90,
    # Conservative structural-density guard against decoder-grid false
    # positives (sparse transitions rounded into many fitted bit cells).
    # This is NOT a protocol frame-length requirement.
    min_transition_count: int = 20,
) -> dict:
    """Validate waveform structure independently of decoder status flags."""
    bits = np.asarray(result.get("bits", []), dtype=int)
    decoded = result.get("decoded")
    observed = np.asarray(
        observed_transition_times_s if observed_transition_times_s is not None else [],
        dtype=float,
    )

    if not isinstance(decoded, pd.DataFrame) or "Start_us" not in decoded:
        return {
            "accepted": False,
            "boundary_transition_coverage": 0.0,
            "transition_count": int(len(observed)),
            "reason": "decoded boundary table is missing",
        }

    if len(observed) == 0 or not np.all(np.isfinite(observed)):
        return {
            "accepted": False,
            "boundary_transition_coverage": 0.0,
            "transition_count": int(len(observed)),
            "reason": "independent waveform transitions are missing",
        }

    expected = (
        float(decoder_window_start_s)
        + decoded["Start_us"].to_numpy(dtype=float) * 1e-6
    )
    tolerance_s = boundary_tolerance_us * 1e-6
    supported = np.asarray([
        bool(np.any(np.abs(observed - boundary) <= tolerance_s))
        for boundary in expected
    ])
    coverage = float(np.mean(supported)) if len(supported) else 0.0
    reasons: list[str] = []

    if len(bits) < 1:
        reasons.append("no decoded bits")
    if len(observed) < min_transition_count:
        reasons.append("too few waveform transitions")
    if coverage < min_boundary_transition_coverage:
        reasons.append("insufficient boundary-transition coverage")

    return {
        "accepted": not reasons,
        "boundary_transition_coverage": coverage,
        "supported_boundary_count": int(np.sum(supported)),
        "boundary_count": int(len(expected)),
        "transition_count": int(len(observed)),
        "decoded_bit_count": int(len(bits)),
        "reason": "; ".join(reasons),
    }


def _local_timing_is_plausible(
    transition_times_s: np.ndarray,
    nominal_bit_time_us: float,
) -> tuple[bool, float | None]:
    """Cheap screening of observed transition spacing before full decoding.

    ``nominal_bit_time_us`` is an empirical timing prior used ONLY to center a
    wide plausibility band. It is not a hard-coded protocol timing value and
    this screen does not accept or reject a frame on its own; the existing
    decoder remains authoritative for timing fit.
    """
    gaps = np.diff(np.asarray(transition_times_s, dtype=float))
    positive = gaps[gaps > 0]
    if len(positive) == 0:
        return False, None

    median_gap_us = float(np.median(positive) * 1e6)
    candidates = (median_gap_us, 2.0 * median_gap_us)
    lower = 0.5 * nominal_bit_time_us
    upper = 2.5 * nominal_bit_time_us
    plausible = [value for value in candidates if lower <= value <= upper]
    return bool(plausible), min(plausible, key=lambda value: abs(value - nominal_bit_time_us)) if plausible else None


def cluster_differential_candidates(
    candidates: list[dict],
) -> list[dict]:
    """Collapse overlapping channel/offset detections to one representative."""
    ordered = sorted(
        candidates,
        key=lambda item: (
            float(item.get("frame_start_us", np.inf)),
            float(item.get("frame_end_us", np.inf)),
        ),
    )
    clusters: list[list[dict]] = []

    for candidate in ordered:
        if not clusters:
            clusters.append([candidate])
            continue

        current = clusters[-1]
        current_end = max(float(item["frame_end_us"]) for item in current)
        start = float(candidate["frame_start_us"])
        if start <= current_end:
            current.append(candidate)
        else:
            clusters.append([candidate])

    representatives: list[dict] = []
    for cluster in clusters:
        def bit_count(item: dict) -> int:
            bits = item.get("bits", [])
            return len(bits) if hasattr(bits, "__len__") else int(bits or 0)

        representative = min(
            cluster,
            key=lambda item: (
                not bool(item.get("structural_validation", {}).get("accepted", False)),
                float(item.get("rms_fit_error_us", np.inf)),
                float(item.get("max_fit_error_us", np.inf)),
                -bit_count(item),
            ),
        )
        representatives.append(representative)

    return representatives


def _paired_activity_regions(
    time_s: np.ndarray,
    transition_times: list[np.ndarray],
    activity_gap_us: float,
    minimum_transition_count: int,
) -> list[tuple[int, int]]:
    gap_s = activity_gap_us * 1e-6
    channel_regions: list[list[tuple[float, float, int]]] = []

    for events in transition_times:
        if len(events) == 0:
            channel_regions.append([])
            continue

        regions: list[tuple[float, float, int]] = []
        start = end = float(events[0])
        count = 1
        for event in events[1:]:
            event = float(event)
            if event - end <= gap_s:
                end = event
                count += 1
            else:
                if count >= minimum_transition_count:
                    regions.append((start, end, count))
                start = end = event
                count = 1
        if count >= minimum_transition_count:
            regions.append((start, end, count))
        channel_regions.append(regions)

    if len(channel_regions) < 2:
        return []

    paired: list[tuple[float, float, int]] = []
    for left_start, left_end, left_count in channel_regions[0]:
        for right_start, right_end, right_count in channel_regions[1]:
            overlap = min(left_end, right_end) - max(left_start, right_start)
            gap = max(0.0, max(left_start, right_start) - min(left_end, right_end))
            if overlap >= 0.0 or gap <= gap_s:
                paired.append((
                    min(left_start, right_start),
                    max(left_end, right_end),
                    left_count + right_count,
                ))

    paired.sort()
    merged: list[tuple[float, float, int]] = []
    for start, end, count in paired:
        if merged and start <= merged[-1][1] + gap_s:
            old_start, old_end, old_count = merged[-1]
            merged[-1] = (old_start, max(old_end, end), old_count + count)
        else:
            merged.append((start, end, count))

    return [
        (
            max(0, int(np.searchsorted(time_s, start, side="left")) - 1),
            min(len(time_s) - 1, int(np.searchsorted(time_s, end, side="right"))),
        )
        for start, end, _ in merged
    ]


def _voltage_activity_regions(
    time_s: np.ndarray,
    voltage: np.ndarray,
    amplitude_floor_v: float = 0.15,
    close_gap_us: float = 250.0,
    minimum_duration_us: float = 200.0,
) -> list[tuple[float, float]]:
    """Find coarse active voltage envelopes for paired-channel prefiltering."""
    baseline = float(np.median(voltage))
    active = np.abs(voltage - baseline) >= amplitude_floor_v
    indices = np.flatnonzero(active)
    if len(indices) == 0:
        return []

    sample_dt = float(np.median(np.diff(time_s)))
    close_samples = max(1, int(round(close_gap_us * 1e-6 / sample_dt)))
    minimum_duration_s = minimum_duration_us * 1e-6
    regions: list[tuple[float, float]] = []
    start = end = int(indices[0])

    for index in indices[1:]:
        index = int(index)
        if index <= end + close_samples:
            end = index
            continue
        if time_s[end] - time_s[start] >= minimum_duration_s:
            regions.append((float(time_s[start]), float(time_s[end])))
        start = end = index

    if time_s[end] - time_s[start] >= minimum_duration_s:
        regions.append((float(time_s[start]), float(time_s[end])))
    return regions


def _paired_voltage_activity_regions(
    time_s: np.ndarray,
    channels: list[np.ndarray],
    pairing_gap_us: float,
    padding_us: float = 500.0,
) -> list[tuple[int, int]]:
    channel_regions = [
        _voltage_activity_regions(time_s, channel)
        for channel in channels
    ]
    gap_s = pairing_gap_us * 1e-6
    paired: list[tuple[float, float]] = []
    for left_start, left_end in channel_regions[0]:
        for right_start, right_end in channel_regions[1]:
            overlap = min(left_end, right_end) - max(left_start, right_start)
            gap = max(0.0, max(left_start, right_start) - min(left_end, right_end))
            if overlap >= 0.0 or gap <= gap_s:
                paired.append((min(left_start, right_start), max(left_end, right_end)))

    paired.sort()
    merged: list[tuple[float, float]] = []
    for start, end in paired:
        if merged and start <= merged[-1][1] + gap_s:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    padding_s = padding_us * 1e-6
    end_padding_s = min(padding_s, 100e-6)
    return [
        (
            max(
                0,
                int(np.searchsorted(time_s, start - padding_s, side="left")) - 1,
            ),
            min(
                len(time_s) - 1,
                int(np.searchsorted(time_s, end + end_padding_s, side="right")),
            ),
        )
        for start, end in merged
    ]


def scan_differential_manchester(
    time_s: np.ndarray,
    channel_a: np.ndarray,
    channel_b: np.ndarray,
    nominal_bit_time_us: float = 12.8,
    alignment: str = "First transition is bit start",
    preamble_count: int = 22,
    transition_holdoff_us: float = 0.0,
    # Decoder-window context required before the logical first transition so the
    # existing decoder can construct complete leading bit cells. This is an
    # orchestration requirement, NOT part of the protocol timing.
    pre_roll_us: float = 30.0,
    activity_gap_us: float = 500.0,
    max_starts_per_region: int = 128,
    # Pathological-capture guard only: generous global ceiling on expensive
    # decoder calls for one invocation. Normal captures never reach it; if it
    # is reached, already-validated results are returned unchanged.
    max_decoder_calls: int = 10_000,
) -> dict:
    """Conservatively scan paired channels using the existing DM decoder."""
    time_s = np.asarray(time_s, dtype=float)
    channel_a = np.asarray(channel_a, dtype=float)
    channel_b = np.asarray(channel_b, dtype=float)

    if (
        time_s.ndim != 1
        or channel_a.ndim != 1
        or channel_b.ndim != 1
        or len(time_s) != len(channel_a)
        or len(time_s) != len(channel_b)
    ):
        raise ValueError("Time and paired channels must be matching one-dimensional arrays.")
    if len(time_s) < 20 or not np.all(np.isfinite(time_s)):
        raise ValueError("At least 20 finite time samples are required.")
    if np.any(np.diff(time_s) <= 0):
        raise ValueError("Differential Manchester scanning requires strictly increasing time.")

    channels = [channel_a, channel_b]
    transition_data: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for channel in channels:
        try:
            levels = estimate_logic_levels_and_thresholds(channel)
            logic, indices, times = detect_transitions(
                time_s,
                channel,
                levels["low_threshold"],
                levels["high_threshold"],
                transition_holdoff_us,
            )
        except ValueError:
            return {
                "protocol": "Differential Manchester",
                "status": "no_validated_messages",
                "message_count": 0,
                "messages": [],
                "metrics": {
                    "candidate_region_count": 0,
                    "decoder_calls": 0,
                    "rejected_candidates": 0,
                },
            }
        transition_data.append((logic, indices, times))

    event_regions = _paired_activity_regions(
        time_s,
        [item[2] for item in transition_data],
        activity_gap_us,
        minimum_transition_count=20,
    )
    voltage_regions = _paired_voltage_activity_regions(
        time_s,
        channels,
        pairing_gap_us=activity_gap_us,
    )
    if not event_regions:
        regions = voltage_regions
    elif voltage_regions and len(event_regions) > max(8, 2 * len(voltage_regions)):
        regions = voltage_regions
    else:
        regions = event_regions
    region_padding_s = max(pre_roll_us * 3e-6, 100e-6)
    regions = [
        (
            max(0, int(np.searchsorted(
                time_s,
                time_s[start] - region_padding_s,
                side="left",
            ))),
            min(len(time_s) - 1, int(np.searchsorted(
                time_s,
                time_s[end] + region_padding_s,
                side="right",
            ))),
        )
        for start, end in regions
    ]
    accepted: list[dict] = []
    rejected_count = 0
    timing_prefilter_rejections = 0
    decoder_calls = 0
    decoder_call_budget_hit = False

    for region_start, region_end in regions:
        if decoder_call_budget_hit:
            break
        for channel_index, channel in enumerate(channels):
            if decoder_call_budget_hit:
                break
            region_time = time_s[region_start:region_end + 1]
            region_voltage = channel[region_start:region_end + 1]
            try:
                region_levels = estimate_logic_levels_and_thresholds(region_voltage)
                region_logic, local_indices, local_times = detect_transitions(
                    region_time,
                    region_voltage,
                    region_levels["low_threshold"],
                    region_levels["high_threshold"],
                    transition_holdoff_us,
                )
            except ValueError:
                continue
            if len(local_indices) < 4:
                continue

            if len(local_indices) <= max_starts_per_region:
                starts = local_indices
            else:
                positions = np.linspace(
                    0,
                    len(local_indices) - 1,
                    max_starts_per_region,
                    dtype=int,
                )
                starts = local_indices[positions]
            for start_index in starts:
                if decoder_calls >= max_decoder_calls:
                    decoder_call_budget_hit = True
                    break
                start_index = int(start_index)
                pre_roll_start = max(
                    region_start,
                    int(np.searchsorted(
                        time_s,
                        time_s[region_start + start_index]
                        - pre_roll_us * 1e-6,
                        side="left",
                    )),
                )
                candidate_indices = local_indices[local_indices >= start_index]
                candidate_times = local_times[local_indices >= start_index]
                if len(candidate_indices) < 4:
                    continue
                timing_ok, local_timing_us = _local_timing_is_plausible(
                    candidate_times,
                    nominal_bit_time_us,
                )
                if not timing_ok:
                    timing_prefilter_rejections += 1
                    continue

                relative_indices = (
                    region_start + candidate_indices - pre_roll_start
                )
                candidate_time = time_s[pre_roll_start:region_end + 1]
                candidate_voltage = channel[pre_roll_start:region_end + 1]
                logic_start = pre_roll_start - region_start
                candidate_logic = region_logic[logic_start:]
                decoder_calls += 1

                try:
                    result = decode_waveform(
                        candidate_time,
                        candidate_voltage,
                        candidate_logic,
                        relative_indices,
                        candidate_times,
                        nominal_bit_time_us,
                        alignment,
                        preamble_count,
                    )
                except (ValueError, ArithmeticError, np.linalg.LinAlgError):
                    rejected_count += 1
                    continue

                structural = validate_differential_manchester_structure(
                    result,
                    observed_transition_times_s=candidate_times,
                    decoder_window_start_s=float(candidate_time[0]),
                )
                if not (
                    result["preamble_valid"]
                    and result["sync_valid"]
                    and result["clock_quality_pass"]
                    and structural["accepted"]
                ):
                    rejected_count += 1
                    continue

                summary = result["frame_summary"].iloc[0]
                decoder_window_start = float(candidate_time[0])
                frame_start = decoder_window_start + float(summary["FrameStart_us"]) * 1e-6
                frame_end = decoder_window_start + float(summary["FrameEnd_us"]) * 1e-6
                accepted.append({
                    **result,
                    "source_channel_index": channel_index,
                    "frame_start_us": (frame_start - time_s[0]) * 1e6,
                    "frame_end_us": (frame_end - time_s[0]) * 1e6,
                    "decoder_window_start_sample": pre_roll_start,
                    "decoder_window_end_sample": region_end,
                    "logical_frame_start_sample": int(np.searchsorted(time_s, frame_start)),
                    "logical_frame_end_sample": int(np.searchsorted(time_s, frame_end)),
                    "structural_validation": structural,
                    "local_timing_us": local_timing_us,
                    "rms_fit_error_us": result["rms_fit_error_us"],
                    "max_fit_error_us": result["max_fit_error_us"],
                })

    representatives = cluster_differential_candidates(accepted)
    status = "validated" if representatives else "no_validated_messages"
    return {
        "protocol": "Differential Manchester",
        "status": status,
        "message_count": len(representatives),
        "messages": representatives,
        "metrics": {
            "candidate_region_count": len(regions),
            "decoder_calls": decoder_calls,
            "rejected_candidates": rejected_count,
            "timing_prefilter_rejections": timing_prefilter_rejections,
            "decoder_call_budget_hit": decoder_call_budget_hit,
        },
    }





