import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import app
from app import (
    MULTI_MESSAGE_MODE,
    SINGLE_FRAME_MODE,
    is_too_many_half_bit_cells_error,
    suggest_differential_pair,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
APP_TREE = ast.parse(APP_SOURCE)

DM_BRANCH_START = 'if protocol == "Differential Manchester (legacy project)":'
DM_BRANCH_END = 'elif protocol == "Manchester (Biphase-L)":'


def _functions_by_name():
    return {
        node.name: node
        for node in APP_TREE.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _dm_branch_source() -> str:
    start = APP_SOURCE.index(DM_BRANCH_START)
    end = APP_SOURCE.index(DM_BRANCH_END)
    return APP_SOURCE[start:end]


class DecoderRoutingTests(unittest.TestCase):
    """Multi-message must use the scanner; single-frame uses decode_waveform."""

    def test_multi_message_path_does_not_call_legacy_decoder(self):
        functions = _functions_by_name()
        self.assertIn("render_multi_message_scan", functions)
        called = _called_names(functions["render_multi_message_scan"])
        self.assertNotIn("decode_waveform", called)
        self.assertIn("scan_differential_manchester_cached", called)

    def test_single_frame_path_still_calls_legacy_decoder(self):
        # decode_waveform lives in render_decoder (single-frame path only).
        functions = _functions_by_name()
        self.assertIn("render_decoder", functions)
        self.assertIn("decode_waveform", _called_names(functions["render_decoder"]))

    def test_multi_message_dispatch_uses_scanner_helper(self):
        branch = _dm_branch_source()
        self.assertIn("scan_differential_manchester_cached", APP_SOURCE)
        self.assertIn("render_multi_message_scan(", branch)

    def test_decoder_is_invoked_exactly_once_at_module_call_level(self):
        # decode_waveform is imported once and called once, in the single-frame
        # path only.
        self.assertEqual(APP_SOURCE.count("decode_waveform("), 1)


class DifferentialManchesterUiLayoutTests(unittest.TestCase):
    """The DM workflow order: analysis mode -> channels -> timing -> results."""

    def setUp(self):
        self.branch = _dm_branch_source()

    def test_analysis_mode_precedes_channels(self):
        self.assertLess(
            self.branch.index('"Analysis mode"'),
            self.branch.index('"Channel A"'),
        )

    def test_channels_precede_legacy_threshold_controls(self):
        threshold_index = self.branch.index('"Threshold mode"')
        self.assertLess(self.branch.index('"Channel A"'), threshold_index)
        self.assertLess(self.branch.index('"Channel B"'), threshold_index)

    def test_multi_message_is_the_default_mode(self):
        options_index = self.branch.index(
            "[MULTI_MESSAGE_MODE, SINGLE_FRAME_MODE]"
        )
        self.assertGreater(options_index, -1)
        self.assertIn("index=0", self.branch[options_index:options_index + 200])

    def test_old_checkbox_workflow_is_removed(self):
        self.assertNotIn("Detect multiple messages (multi-burst scan)", APP_SOURCE)
        self.assertNotIn("Paired decoder channel", APP_SOURCE)

    def test_default_mode_constants(self):
        self.assertEqual(MULTI_MESSAGE_MODE, "Multi-message / Burst Scan")
        self.assertEqual(SINGLE_FRAME_MODE, "Single Frame")


class ChannelSuggestionTests(unittest.TestCase):
    def test_suggests_active_pair_when_ch3_ch4_dominate(self):
        rng = np.random.default_rng(1234)
        n = 5000
        signals = {
            "CH1(V)": np.zeros(n),
            "CH2(V)": np.full(n, -0.32),
            "CH3(V)": rng.normal(0.0, 0.05, n),
            "CH4(V)": rng.normal(0.0, 0.05, n),
        }
        first, second, hint = suggest_differential_pair(signals)
        self.assertEqual({first, second}, {"CH3(V)", "CH4(V)"})
        self.assertIn("Suggested differential pair:", hint)
        self.assertIn("CH3(V)", hint)
        self.assertIn("CH4(V)", hint)

    def test_returns_nothing_for_a_single_channel(self):
        first, second, hint = suggest_differential_pair({"CH1(V)": np.zeros(100)})
        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertIsNone(hint)

    def test_returns_nothing_when_channels_are_similar(self):
        rng = np.random.default_rng(7)
        n = 4000
        signals = {
            "A": rng.normal(0, 1.0, n),
            "B": rng.normal(0, 1.0, n),
            "C": rng.normal(0, 0.9, n),
        }
        first, second, hint = suggest_differential_pair(signals)
        self.assertIsNone(first)
        self.assertIsNone(hint)

    def test_suggestion_does_not_claim_a_confidence_score(self):
        signals = {"A": np.zeros(100), "B": np.zeros(100), "C": np.zeros(100)}
        signals["B"] = np.linspace(0, 1, 100)
        signals["C"] = np.linspace(0, 1, 100)
        _, _, hint = suggest_differential_pair(signals)
        if hint is not None:
            self.assertNotIn("confidence", hint.lower())


class LongWindowGuidanceTests(unittest.TestCase):
    def test_detects_half_bit_cell_overflow_error(self):
        exc = ValueError(
            "The selected window spans too many half-bit cells. Select one frame "
            "or check the bit time and CSV time units."
        )
        self.assertTrue(is_too_many_half_bit_cells_error(exc))

    def test_ignores_unrelated_value_errors(self):
        self.assertFalse(
            is_too_many_half_bit_cells_error(ValueError("LOW threshold must be below"))
        )

    def test_guidance_recommends_mode_switch_or_narrowing(self):
        self.assertIn("Single-frame decoder cannot process this entire window.", APP_SOURCE)
        self.assertIn("Multi-message / Burst Scan", APP_SOURCE)
        self.assertIn("narrow the Window controls to one frame", APP_SOURCE)

    def test_long_window_handling_is_wired_into_single_frame_path(self):
        branch = _dm_branch_source()
        self.assertIn("is_too_many_half_bit_cells_error(exc)", branch)
        self.assertIn("render_long_window_guidance(", branch)


class HistoricalCaptureRegressionTests(unittest.TestCase):
    """Guarded: only runs when the local (git-ignored) capture is present."""

    CAPTURE = REPO_ROOT / "sample_latest" / "lpmwink1.7ms0.csv"

    @unittest.skipUnless(CAPTURE.exists(), "sample capture not available locally")
    def test_lpmwink_capture_still_validates_two_messages(self):
        from analyzer_core import scan_differential_manchester

        frame = pd.read_csv(
            self.CAPTURE,
            usecols=["Time(s)", "CH3(V)", "CH4(V)"],
        )
        time_s = pd.to_numeric(frame["Time(s)"], errors="coerce").to_numpy(float)
        decode_time = np.linspace(float(time_s[0]), float(time_s[-1]), len(time_s))
        result = scan_differential_manchester(
            decode_time,
            pd.to_numeric(frame["CH3(V)"], errors="coerce").to_numpy(float),
            pd.to_numeric(frame["CH4(V)"], errors="coerce").to_numpy(float),
            nominal_bit_time_us=12.8,
            alignment="First transition is bit start",
            preamble_count=22,
            transition_holdoff_us=0.0,
        )
        self.assertEqual(result["message_count"], 2)
        self.assertEqual(result["status"], "validated")


if __name__ == "__main__":
    unittest.main()
