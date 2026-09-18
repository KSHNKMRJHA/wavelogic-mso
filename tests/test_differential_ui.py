import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import app
from app import (
    DIFFERENTIAL_PAIR_MODE,
    MULTI_MESSAGE_MODE,
    SINGLE_FRAME_MODE,
    SINGLE_SIGNAL_MODE,
    differential_from_pair,
    is_too_many_half_bit_cells_error,
    resolve_decoder_signals,
    suggest_differential_pair,
    suggest_single_signal,
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
    """DM workflow order: analysis mode -> signal source -> timing -> results."""

    def setUp(self):
        self.branch = _dm_branch_source()

    def test_analysis_mode_precedes_signal_source(self):
        self.assertLess(
            self.branch.index('"Analysis mode"'),
            self.branch.index('"Decoder Signal Source"'),
        )

    def test_signal_source_precedes_legacy_threshold_controls(self):
        threshold_index = self.branch.index('"Threshold mode"')
        self.assertLess(self.branch.index('"Decode signal"'), threshold_index)
        self.assertLess(self.branch.index('"Positive (+)"'), threshold_index)

    def test_multi_message_is_the_default_mode(self):
        options_index = self.branch.index(
            "[MULTI_MESSAGE_MODE, SINGLE_FRAME_MODE]"
        )
        self.assertGreater(options_index, -1)
        self.assertIn("index=0", self.branch[options_index:options_index + 200])

    def test_single_signal_is_the_default_source_mode(self):
        options_index = self.branch.index(
            "[SINGLE_SIGNAL_MODE, DIFFERENTIAL_PAIR_MODE]"
        )
        self.assertGreater(options_index, -1)
        self.assertIn("index=0", self.branch[options_index:options_index + 200])

    def test_old_channel_workflow_is_removed(self):
        self.assertNotIn("Detect multiple messages (multi-burst scan)", APP_SOURCE)
        self.assertNotIn("Paired decoder channel", APP_SOURCE)
        self.assertNotIn('"Channel A"', APP_SOURCE)
        self.assertNotIn('"Channel B"', APP_SOURCE)

    def test_default_mode_constants(self):
        self.assertEqual(MULTI_MESSAGE_MODE, "Multi-message / Burst Scan")
        self.assertEqual(SINGLE_FRAME_MODE, "Single Frame")
        self.assertEqual(SINGLE_SIGNAL_MODE, "Single / derived signal")
        self.assertEqual(DIFFERENTIAL_PAIR_MODE, "Differential pair")


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


def _source_mode_if() -> ast.If | None:
    """The UI ``if source_mode == SINGLE_SIGNAL_MODE:`` statement in app.py.

    ``resolve_decoder_signals`` has a structurally similar branch, so the UI
    statement is identified by the widgets it renders.
    """
    for node in ast.walk(APP_TREE):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            left = node.test.left
            if not (isinstance(left, ast.Name) and left.id == "source_mode"):
                continue
            segment = ast.get_source_segment(APP_SOURCE, node) or ""
            if '"Decode signal"' in segment and '"Positive (+)"' in segment:
                return node
    return None


class SourceControlExposureTests(unittest.TestCase):
    """Single mode must not render pair controls, and vice versa."""

    def setUp(self):
        node = _source_mode_if()
        self.assertIsNotNone(node, "source_mode branch not found in app.py")
        self.single_src = "\n".join(
            segment for segment in
            (ast.get_source_segment(APP_SOURCE, stmt) for stmt in node.body)
            if segment
        )
        self.pair_src = "\n".join(
            segment for segment in
            (ast.get_source_segment(APP_SOURCE, stmt) for stmt in node.orelse)
            if segment
        )

    def test_single_mode_exposes_decode_signal_only(self):
        self.assertIn('"Decode signal"', self.single_src)
        self.assertNotIn('"Positive (+)"', self.single_src)
        self.assertNotIn('"Negative', self.single_src)

    def test_pair_mode_exposes_positive_and_negative(self):
        self.assertIn('"Positive (+)"', self.pair_src)
        self.assertIn('"Negative', self.pair_src)
        self.assertNotIn('"Decode signal"', self.pair_src)
        self.assertIn("Derived signal:", self.pair_src)

    def test_pair_suggestion_only_in_pair_mode(self):
        self.assertIn("suggest_differential_pair(", self.pair_src)
        self.assertNotIn("suggest_differential_pair(", self.single_src)


class DecoderSignalResolutionTests(unittest.TestCase):
    """The decoder always resolves to ONE logical waveform."""

    def setUp(self):
        rng = np.random.default_rng(99)
        n = 4000
        self.ch3 = rng.normal(0.0, 0.05, n)
        self.ch4 = rng.normal(0.0, 0.05, n)
        self.math = self.ch3 - self.ch4
        self.signals = {
            "CH1(V)": np.zeros(n),
            "CH2(V)": np.full(n, -0.3),
            "CH3(V)": self.ch3,
            "CH4(V)": self.ch4,
            "MATH: CH3 - CH4": self.math,
        }

    def test_single_physical_channel_selection(self):
        resolved = resolve_decoder_signals(
            self.signals, SINGLE_SIGNAL_MODE, single_name="CH3(V)"
        )
        self.assertEqual(resolved["label"], "CH3(V)")
        self.assertFalse(resolved["is_pair"])
        np.testing.assert_array_equal(resolved["single_signal"], self.ch3)
        # Single mode feeds the same waveform to both scanner inputs.
        np.testing.assert_array_equal(resolved["primary"], resolved["secondary"])

    def test_single_derived_math_channel_selection(self):
        resolved = resolve_decoder_signals(
            self.signals, SINGLE_SIGNAL_MODE, single_name="MATH: CH3 - CH4"
        )
        self.assertEqual(resolved["label"], "MATH: CH3 - CH4")
        np.testing.assert_allclose(resolved["single_signal"], self.math)

    def test_differential_pair_selection_builds_derived_signal(self):
        resolved = resolve_decoder_signals(
            self.signals,
            DIFFERENTIAL_PAIR_MODE,
            positive_name="CH3(V)",
            negative_name="CH4(V)",
        )
        self.assertTrue(resolved["is_pair"])
        self.assertEqual(resolved["label"], "CH3(V) \u2212 CH4(V)")
        np.testing.assert_array_equal(resolved["primary"], self.ch3)
        np.testing.assert_array_equal(resolved["secondary"], self.ch4)
        np.testing.assert_allclose(resolved["single_signal"], self.math)

    def test_unknown_names_fall_back_safely(self):
        resolved = resolve_decoder_signals(
            self.signals, SINGLE_SIGNAL_MODE, single_name="does-not-exist"
        )
        self.assertIn(resolved["label"], self.signals)

    def test_pair_with_single_signal_does_not_crash(self):
        resolved = resolve_decoder_signals(
            {"CH1(V)": self.ch3},
            DIFFERENTIAL_PAIR_MODE,
            positive_name="CH1(V)",
            negative_name="CH1(V)",
        )
        self.assertEqual(resolved["negative"], "CH1(V)")

    def test_differential_from_pair_drops_non_finite_pairs(self):
        a = np.array([1.0, np.nan, 3.0])
        b = np.array([0.5, 1.0, np.nan])
        derived = differential_from_pair(a, b)
        self.assertEqual(derived[0], 0.5)
        self.assertTrue(np.isnan(derived[1]))
        self.assertTrue(np.isnan(derived[2]))

    def test_suggest_single_signal_prefers_most_active(self):
        self.assertEqual(suggest_single_signal(self.signals), "MATH: CH3 - CH4")

    def test_suggest_single_signal_handles_empty(self):
        self.assertIsNone(suggest_single_signal({}))


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
    """Guarded: only runs when the local (git-ignored) captures are present.

    Pair-mode results are the validated historical baseline; the single-signal
    self-paired check proves the new source abstraction still routes through the
    same unchanged scanner.
    """

    CAPTURES = REPO_ROOT / "sample_latest"
    EXPECTED = {
        "lpmwink1.7ms0.csv": ("CH3(V)", "CH4(V)", 2),
        "wink 2 resp0.csv": ("CH3(V)", "CH4(V)", 2),
        "stm32wink150ms0.csv": ("CH3(V)", "CH4(V)", 4),
        "ackn0.csv": ("CH1(V)", "CH3(V)", 1),
        "RigolDS0.csv": ("CH1(V)", "CH3(V)", 1),
        "wnk0.csv": ("CH3(V)", "CH4(V)", 0),
        "stm32_wink1s0.csv": ("CH3(V)", "CH4(V)", 0),
        "wink_1s0.csv": ("CH3(V)", "CH4(V)", 0),
    }

    def _decode_time(self, frame):
        time_s = pd.to_numeric(frame["Time(s)"], errors="coerce").to_numpy(float)
        return np.linspace(float(time_s[0]), float(time_s[-1]), len(time_s))

    def test_historical_capture_counts_unchanged(self):
        from analyzer_core import scan_differential_manchester

        checked = 0
        for name, (positive, negative, expected) in self.EXPECTED.items():
            path = self.CAPTURES / name
            if not path.exists():
                continue
            checked += 1
            with self.subTest(capture=name):
                frame = pd.read_csv(path, usecols=["Time(s)", positive, negative])
                result = scan_differential_manchester(
                    self._decode_time(frame),
                    pd.to_numeric(frame[positive], errors="coerce").to_numpy(float),
                    pd.to_numeric(frame[negative], errors="coerce").to_numpy(float),
                    nominal_bit_time_us=12.8,
                    alignment="First transition is bit start",
                    preamble_count=22,
                    transition_holdoff_us=0.0,
                )
                self.assertEqual(result["message_count"], expected)
        if checked == 0:
            self.skipTest("no sample captures available locally")

    def test_single_signal_self_paired_scan_matches_pair_result(self):
        from analyzer_core import scan_differential_manchester

        path = self.CAPTURES / "lpmwink1.7ms0.csv"
        if not path.exists():
            self.skipTest("sample capture not available locally")
        frame = pd.read_csv(path, usecols=["Time(s)", "CH3(V)"])
        signal = pd.to_numeric(frame["CH3(V)"], errors="coerce").to_numpy(float)
        result = scan_differential_manchester(
            self._decode_time(frame),
            signal,
            signal,
            nominal_bit_time_us=12.8,
            alignment="First transition is bit start",
            preamble_count=22,
            transition_holdoff_us=0.0,
        )
        self.assertEqual(result["message_count"], 2)
        self.assertEqual(result["status"], "validated")


if __name__ == "__main__":
    unittest.main()
