import unittest

import numpy as np

from analyzer_core import (
    analyze_timestamp_quality,
    default_timestamp_mode,
    prepare_time_axis,
)

DIRECT = "Use CSV timestamps directly"
RECONSTRUCT = "Reconstruct uniform timestamps"


class DefaultTimestampModeTests(unittest.TestCase):
    def test_low_precision_capture_defaults_to_reconstruction(self):
        quality = {"low_precision": True, "duplicate_ratio": 0.8}
        self.assertEqual(default_timestamp_mode(quality), RECONSTRUCT)

    def test_clean_capture_defaults_to_direct_timestamps(self):
        quality = {"low_precision": False, "duplicate_ratio": 0.0}
        self.assertEqual(default_timestamp_mode(quality), DIRECT)

    def test_missing_flag_defaults_to_direct_timestamps(self):
        self.assertEqual(default_timestamp_mode({}), DIRECT)
        self.assertEqual(default_timestamp_mode(None), DIRECT)

    def test_duplicated_timestamps_route_to_reconstruction(self):
        base = np.linspace(0.0, 1.0, 500)
        duplicated = np.repeat(base, 2)  # 50% duplicate ratio
        quality = analyze_timestamp_quality(duplicated)
        self.assertTrue(quality["low_precision"])
        self.assertEqual(default_timestamp_mode(quality), RECONSTRUCT)

    def test_strictly_increasing_timestamps_route_to_direct(self):
        clean = np.linspace(0.0, 1.0, 1000)
        quality = analyze_timestamp_quality(clean)
        self.assertFalse(quality["low_precision"])
        self.assertEqual(default_timestamp_mode(quality), DIRECT)

    def test_print_quantized_grid_default_axis_is_strictly_increasing(self):
        # The failure signature of stm32wink150ms0.csv: a uniform grid whose
        # printed (rounded) timestamps carry heavy duplicates. The default
        # mode must be accepted by prepare_time_axis and yield a strictly
        # increasing axis with preserved length and endpoints.
        true_grid = np.linspace(-0.03182, 1.4682, 200_000)
        quantized = np.round(true_grid, 4)
        quality = analyze_timestamp_quality(quantized)
        self.assertTrue(quality["low_precision"])
        mode = default_timestamp_mode(quality)
        self.assertEqual(mode, RECONSTRUCT)
        axis, applied = prepare_time_axis(quantized, mode)
        self.assertEqual(applied["applied_mode"], RECONSTRUCT)
        self.assertEqual(len(axis), len(quantized))
        self.assertAlmostEqual(float(axis[0]), float(quantized[0]))
        self.assertAlmostEqual(float(axis[-1]), float(quantized[-1]))
        self.assertTrue(bool(np.all(np.diff(axis) > 0)))

    def test_returned_mode_is_a_valid_prepare_time_axis_mode(self):
        for quality in ({"low_precision": True}, {"low_precision": False}):
            self.assertIn(
                default_timestamp_mode(quality),
                (DIRECT, RECONSTRUCT),
            )


if __name__ == "__main__":
    unittest.main()
