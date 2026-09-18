import unittest

import numpy as np

from analyzer_core import scan_differential_manchester
from app import (
    DIFFERENTIAL_BUDGET_NOTE,
    DIFFERENTIAL_THRESHOLD_NOTE,
    differential_budget_notice,
    differential_message_bits,
    differential_message_result,
    differential_message_summary,
)
from tests.test_differential_orchestration import (
    _build_waveform_from_transition_grid,
    _intended_transition_grid,
)

KNOWN_GOOD_BITS = [1] * 22 + [0] + [1, 0, 1, 1, 0, 0, 1, 0]


def _two_burst_waveform(
    gap_us: float = 1000.0,
    bit_time_us: float = 12.8,
    samples_per_us: float = 10.0,
    amplitude: float = 3.3,
) -> tuple[np.ndarray, np.ndarray]:
    grid = _intended_transition_grid(KNOWN_GOOD_BITS)
    half_us = bit_time_us / 2.0
    frame_span_us = max(grid) * half_us
    lead_us = 4 * bit_time_us
    total_us = lead_us + frame_span_us + gap_us + frame_span_us + 4 * bit_time_us
    sample_count = int(total_us * samples_per_us)
    time_s = np.arange(sample_count) / samples_per_us * 1e-6

    first = lead_us
    second = lead_us + frame_span_us + gap_us
    transition_us = np.asarray(sorted(
        [first + point * half_us for point in grid]
        + [second + point * half_us for point in grid]
    ))

    voltage = np.zeros(sample_count)
    state = 0.0
    cursor = 0
    for index, sample_us in enumerate(time_s * 1e6):
        while cursor < len(transition_us) and sample_us >= transition_us[cursor]:
            state = amplitude - state
            cursor += 1
        voltage[index] = state
    return time_s, voltage


class MessagePresentationTests(unittest.TestCase):
    def test_single_message_presentation_is_compact_and_complete(self):
        time_s, voltage = _build_waveform_from_transition_grid(
            _intended_transition_grid(KNOWN_GOOD_BITS)
        )
        scan_result = scan_differential_manchester(time_s, voltage, voltage.copy())

        self.assertEqual(scan_result["status"], "validated")
        self.assertEqual(scan_result["message_count"], 1)
        messages = scan_result["messages"]

        summary = differential_message_summary(messages)
        self.assertEqual(len(summary), 1)
        row = summary.iloc[0]
        self.assertEqual(int(row["Message"]), 1)
        self.assertGreater(row["End_us"], row["Start_us"])
        self.assertEqual(int(row["DecodedBits"]), len(KNOWN_GOOD_BITS))
        self.assertEqual(row["Preamble"], "PASS")
        self.assertEqual(row["Sync"], "PASS")
        self.assertEqual(row["Clock"], "PASS")

        detail = differential_message_result(
            messages[0],
            signal_name="CH3",
            timestamp_quality={"applied_mode": "Use CSV timestamps directly"},
            time_axis_note="CSV timestamps",
            low_threshold=0.9,
            high_threshold=2.4,
            holdoff_us=0.0,
            index=1,
            total=1,
            window_start_from_capture_us=123.456,
        )
        self.assertIn("message 1 of 1", detail["protocol"].lower())
        frame_summary = detail["tables"][3][1]
        self.assertAlmostEqual(
            float(frame_summary["WindowStartFromCapture_us"].iloc[0]),
            123.456,
            places=6,
        )
        self.assertAlmostEqual(
            float(frame_summary["LogicalFrameStartFromCapture_us"].iloc[0]),
            123.456 + float(messages[0]["frame_start_us"]),
            places=6,
        )
        self.assertEqual(len(detail["tables"]), 4)
        self.assertIn("Logical frame start", detail["text"])
        self.assertIsNotNone(detail["figure"])
        self.assertEqual(detail["threshold_note"], DIFFERENTIAL_THRESHOLD_NOTE)

        # The figure must be cropped to the logical frame boundaries rather than
        # showing the full decoder window (which includes pre-roll context).
        figure_range = detail["figure"].layout.xaxis.range
        logical_start = float(frame_summary["FrameStart_us"].iloc[0])
        logical_end = float(frame_summary["FrameEnd_us"].iloc[0])
        self.assertAlmostEqual(float(figure_range[0]), logical_start, places=6)
        self.assertAlmostEqual(float(figure_range[1]), logical_end, places=6)
        self.assertGreater(logical_start, float(messages[0]["time_us"][0]))
        self.assertLess(logical_end, float(messages[0]["time_us"][-1]))

    def test_multi_message_summary_and_selection(self):
        time_s, voltage = _two_burst_waveform()
        scan_result = scan_differential_manchester(time_s, voltage, voltage.copy())

        self.assertEqual(scan_result["message_count"], 2)
        messages = scan_result["messages"]
        summary = differential_message_summary(messages)
        self.assertEqual(len(summary), 2)
        self.assertEqual(list(summary["Message"]), [1, 2])

        labels = [f"Message {n}" for n in range(1, len(messages) + 1)]
        selected_index = int(labels[1].split()[-1])
        self.assertEqual(selected_index, 2)

        selected_message = messages[selected_index - 1]
        detail = differential_message_result(
            selected_message,
            signal_name="CH3",
            timestamp_quality={"applied_mode": "Use CSV timestamps directly"},
            time_axis_note="CSV timestamps",
            low_threshold=0.9,
            high_threshold=2.4,
            holdoff_us=0.0,
            index=selected_index,
            total=len(messages),
            window_start_from_capture_us=0.0,
        )
        self.assertIn("message 2 of 2", detail["protocol"].lower())
        frame_summary = detail["tables"][3][1]
        self.assertEqual(int(frame_summary["MessageIndex"].iloc[0]), 2)
        self.assertAlmostEqual(
            float(frame_summary["LogicalFrameStart_us"].iloc[0]),
            float(selected_message["frame_start_us"]),
            places=6,
        )
        self.assertAlmostEqual(
            float(frame_summary["LogicalFrameEnd_us"].iloc[0]),
            float(selected_message["frame_end_us"]),
            places=6,
        )

        bits_table = differential_message_bits(messages)
        self.assertEqual(len(bits_table), 2)
        self.assertEqual(bits_table["DecodedBits"].iloc[0], bits_table["DecodedBits"].iloc[1])

    def test_logical_offsets_are_separate_from_decoder_window(self):
        time_s, voltage = _build_waveform_from_transition_grid(
            _intended_transition_grid(KNOWN_GOOD_BITS)
        )
        scan_result = scan_differential_manchester(time_s, voltage, voltage.copy())
        message = scan_result["messages"][0]

        self.assertLess(
            message["decoder_window_start_sample"],
            message["logical_frame_start_sample"],
        )
        self.assertLess(
            message["logical_frame_start_sample"],
            message["logical_frame_end_sample"],
        )

    def test_empty_message_list_is_handled(self):
        summary = differential_message_summary([])
        bits = differential_message_bits([])

        self.assertEqual(len(summary), 0)
        self.assertEqual(len(bits), 0)

    def test_budget_notice_applies_to_completed_and_empty_scans(self):
        # The notice is derived only from the budget flag, so it is shown for a
        # budget-limited scan regardless of how many messages were validated.
        self.assertEqual(
            differential_budget_notice({"decoder_call_budget_hit": True}),
            DIFFERENTIAL_BUDGET_NOTE,
        )
        self.assertEqual(
            differential_budget_notice(
                {"decoder_call_budget_hit": True, "candidate_region_count": 24}
            ),
            DIFFERENTIAL_BUDGET_NOTE,
        )
        self.assertIsNone(differential_budget_notice({"decoder_call_budget_hit": False}))
        self.assertIsNone(differential_budget_notice({}))
        self.assertIsNone(differential_budget_notice(None))


if __name__ == "__main__":
    unittest.main()
