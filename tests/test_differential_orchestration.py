import unittest

import numpy as np
import pandas as pd

from analyzer_core import (
    cluster_differential_candidates,
    decode_waveform,
    detect_transitions,
    estimate_logic_levels_and_thresholds,
    scan_differential_manchester,
    validate_differential_manchester_structure,
)


def _result(bit_count: int, start_flags: int, transition_count: int) -> dict:
    flags = np.zeros(bit_count, dtype=bool)
    flags[:start_flags] = True
    decoded = pd.DataFrame({
        "TransitionAtStart": flags.astype(int),
        "Start_us": np.arange(bit_count, dtype=float),
    })
    return {
        "bits": np.ones(bit_count, dtype=int),
        "decoded": decoded,
        "transition_us": np.arange(transition_count, dtype=float),
        "preamble_valid": True,
        "sync_valid": True,
        "clock_quality_pass": True,
    }


def _intended_transition_grid(bits: list[int]) -> list[int]:
    """Convert intended bit cells to the project's Differential Manchester grid."""
    grid = 0
    points: list[int] = []
    for bit in bits:
        points.append(grid)
        if bit == 0:
            points.append(grid + 1)
        grid += 2
    points.append(grid)
    return points


def _build_waveform_from_transition_grid(
    grid_points: list[int],
    bit_time_us: float = 12.8,
    samples_per_us: float = 10.0,
    amplitude: float = 3.3,
    lead_bits: int = 4,
    tail_bits: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a compact deterministic waveform whose edges sit on a chosen grid."""
    half_us = bit_time_us / 2.0
    lead_us = lead_bits * bit_time_us
    transition_us = lead_us + np.asarray(grid_points, dtype=float) * half_us
    total_us = lead_us + float(max(grid_points)) * half_us + tail_bits * bit_time_us
    sample_count = int(total_us * samples_per_us)
    time_s = np.arange(sample_count) / samples_per_us * 1e-6

    voltage = np.zeros(sample_count)
    state = 0.0
    cursor = 0
    for index, sample_us in enumerate(time_s * 1e6):
        while cursor < len(transition_us) and sample_us >= transition_us[cursor]:
            state = amplitude - state
            cursor += 1
        voltage[index] = state
    return time_s, voltage


def _legacy_decode(time_s: np.ndarray, voltage: np.ndarray) -> dict:
    levels = estimate_logic_levels_and_thresholds(voltage)
    logic, indices, transition_times = detect_transitions(
        time_s,
        voltage,
        levels["low_threshold"],
        levels["high_threshold"],
        0.0,
    )
    return decode_waveform(
        time_s,
        voltage,
        logic,
        indices,
        transition_times,
        12.8,
        "First transition is bit start",
        22,
    )


class DifferentialOrchestrationTests(unittest.TestCase):
    def test_rejects_sparse_p14_like_structure(self):
        result = _result(bit_count=47, start_flags=13, transition_count=18)

        validation = validate_differential_manchester_structure(
            result,
            observed_transition_times_s=np.arange(13, dtype=float) * 1e-6,
        )

        self.assertFalse(validation["accepted"])
        self.assertLess(validation["boundary_transition_coverage"], 0.90)

    def test_accepts_known_good_structure(self):
        result = _result(bit_count=153, start_flags=151, transition_count=235)

        validation = validate_differential_manchester_structure(
            result,
            observed_transition_times_s=np.arange(151, dtype=float) * 1e-6,
        )

        self.assertTrue(validation["accepted"])
        self.assertGreaterEqual(validation["boundary_transition_coverage"], 0.90)

    def test_decoder_flags_cannot_fake_raw_transition_coverage(self):
        result = _result(bit_count=47, start_flags=47, transition_count=18)

        validation = validate_differential_manchester_structure(
            result,
            observed_transition_times_s=np.arange(13, dtype=float) * 1e-6,
        )

        self.assertFalse(validation["accepted"])
        self.assertLess(validation["boundary_transition_coverage"], 0.90)

    def test_clusters_overlapping_channel_and_offset_hits(self):
        candidates = [
            {
                "frame_start_us": 100.0,
                "frame_end_us": 200.0,
                "channel": "CH3",
                "rms_fit_error_us": 0.4,
                "max_fit_error_us": 0.8,
                "bits": 120,
            },
            {
                "frame_start_us": 100.02,
                "frame_end_us": 200.02,
                "channel": "CH4",
                "rms_fit_error_us": 0.2,
                "max_fit_error_us": 0.5,
                "bits": 121,
            },
            {
                "frame_start_us": 500.0,
                "frame_end_us": 600.0,
                "channel": "CH3",
                "rms_fit_error_us": 0.3,
                "max_fit_error_us": 0.7,
                "bits": 100,
            },
        ]

        clustered = cluster_differential_candidates(candidates)

        self.assertEqual(len(clustered), 2)
        self.assertEqual(clustered[0]["channel"], "CH4")

    def test_does_not_merge_adjacent_non_overlapping_frames(self):
        candidates = [
            {
                "frame_start_us": 0.0,
                "frame_end_us": 100.0,
                "rms_fit_error_us": 0.1,
                "max_fit_error_us": 0.2,
                "bits": np.ones(10, dtype=int),
            },
            {
                "frame_start_us": 150.0,
                "frame_end_us": 250.0,
                "rms_fit_error_us": 0.1,
                "max_fit_error_us": 0.2,
                "bits": np.ones(10, dtype=int),
            },
        ]

        self.assertEqual(len(cluster_differential_candidates(candidates)), 2)

    def test_cluster_preserves_logical_offsets(self):
        candidate = {
            "frame_start_us": 100.0,
            "frame_end_us": 200.0,
            "logical_frame_start_sample": 10,
            "logical_frame_end_sample": 20,
            "decoder_window_start_sample": 5,
            "decoder_window_end_sample": 25,
            "rms_fit_error_us": 0.1,
            "max_fit_error_us": 0.2,
            "bits": np.ones(10, dtype=int),
        }

        result = cluster_differential_candidates([candidate])[0]

        self.assertEqual(result["logical_frame_start_sample"], 10)
        self.assertEqual(result["logical_frame_end_sample"], 20)

    def test_scanner_handles_unusable_paired_channel(self):
        time_s = np.linspace(0.0, 1e-3, 100)
        signal = np.where(np.arange(100) % 2, 3.3, 0.0)

        result = scan_differential_manchester(
            time_s,
            signal,
            np.zeros_like(signal),
        )

        self.assertEqual(result["status"], "no_validated_messages")
        self.assertEqual(result["message_count"], 0)

    def test_scanner_accepts_compact_known_good_waveform(self):
        bits = [1] * 22 + [0] + [1, 0, 1, 1, 0, 0, 1, 0]
        time_s, voltage = _build_waveform_from_transition_grid(
            _intended_transition_grid(bits)
        )

        result = scan_differential_manchester(time_s, voltage, voltage.copy())

        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["message_count"], 1)
        message = result["messages"][0]
        self.assertListEqual(list(message["bits"]), bits)
        self.assertLess(message["frame_start_us"], message["frame_end_us"])
        self.assertGreaterEqual(message["logical_frame_start_sample"], 0)
        self.assertLess(
            message["decoder_window_start_sample"],
            message["logical_frame_start_sample"],
        )

    def test_scanner_rejects_sparse_transition_candidate(self):
        # Sparse edges on a coarse grid plus one mid-grid edge so the existing
        # decoder reports valid preamble/sync/clock. The scanner must still
        # reject it because raw waveform evidence does not support the decoded
        # boundaries. This mirrors the decoder-grid false-positive mechanism.
        grid_points = list(range(0, 45, 4)) + [45, 48, 52, 56, 60]
        time_s, voltage = _build_waveform_from_transition_grid(grid_points)

        legacy = _legacy_decode(time_s, voltage)
        self.assertTrue(legacy["preamble_valid"])
        self.assertTrue(legacy["sync_valid"])
        self.assertTrue(legacy["clock_quality_pass"])

        result = scan_differential_manchester(time_s, voltage, voltage.copy())

        self.assertEqual(result["status"], "no_validated_messages")
        self.assertEqual(result["message_count"], 0)

    def test_single_message_invariant_legacy_matches_orchestration(self):
        bits = [1] * 22 + [0] + [1, 0, 1, 1, 0, 0, 1, 0]
        time_s, voltage = _build_waveform_from_transition_grid(
            _intended_transition_grid(bits)
        )

        legacy = _legacy_decode(time_s, voltage)
        result = scan_differential_manchester(time_s, voltage, voltage.copy())
        message = result["messages"][0]

        self.assertListEqual(list(message["bits"]), list(legacy["bits"]))
        self.assertEqual(len(message["bits"]), len(legacy["bits"]))
        for key in ("preamble_valid", "sync_valid", "clock_quality_pass"):
            self.assertEqual(message[key], legacy[key], key)
        legacy_start = float(legacy["frame_summary"]["FrameStart_us"].iloc[0])
        legacy_end = float(legacy["frame_summary"]["FrameEnd_us"].iloc[0])
        self.assertAlmostEqual(message["frame_start_us"], legacy_start, places=6)
        self.assertAlmostEqual(message["frame_end_us"], legacy_end, places=6)


if __name__ == "__main__":
    unittest.main()
