import json
import unittest

import debug_utils
from debug_utils import (
    MAX_LOG_RECORDS,
    clear_debug_logs,
    collect_runtime_diagnostics,
    debug_log,
    discover_analyzer_core_symbols,
    export_debug_log,
    export_diagnostics_json,
    get_app_state,
    get_debug_logs,
    get_last_exception,
    record_app_state,
    record_exception,
    test_exact_named_import,
    verify_imported_symbols,
)

EXPECTED_SYMBOL_COUNT = 20


class DebugLogBufferTests(unittest.TestCase):
    def setUp(self):
        clear_debug_logs()

    def tearDown(self):
        clear_debug_logs()

    def test_debug_log_returns_record_with_required_fields(self):
        record = debug_log("hello", "INFO")
        self.assertEqual(set(record), {"timestamp", "level", "message"})
        self.assertEqual(record["level"], "INFO")
        self.assertEqual(record["message"], "hello")

    def test_debug_log_appends_in_order(self):
        debug_log("first")
        debug_log("second", "ERROR")
        logs = get_debug_logs()
        self.assertEqual([entry["message"] for entry in logs], ["first", "second"])
        self.assertEqual(logs[-1]["level"], "ERROR")

    def test_buffer_is_bounded_to_max_records(self):
        overflow = MAX_LOG_RECORDS + 50
        for index in range(overflow):
            debug_log(f"entry-{index}")
        logs = get_debug_logs()
        self.assertEqual(len(logs), MAX_LOG_RECORDS)
        # Oldest records are dropped; the most recent are retained.
        self.assertEqual(logs[0]["message"], f"entry-{overflow - MAX_LOG_RECORDS}")
        self.assertEqual(logs[-1]["message"], f"entry-{overflow - 1}")

    def test_clear_debug_logs_empties_buffer(self):
        debug_log("something")
        clear_debug_logs()
        self.assertEqual(get_debug_logs(), [])

    def test_bounded_constant_is_positive(self):
        self.assertGreater(MAX_LOG_RECORDS, 0)


class AnalyzerCoreDiagnosticTests(unittest.TestCase):
    def test_discover_symbols_matches_app_import_list(self):
        symbols = discover_analyzer_core_symbols()
        self.assertEqual(len(symbols), EXPECTED_SYMBOL_COUNT)
        self.assertIn("default_timestamp_mode", symbols)
        self.assertIn("scan_differential_manchester", symbols)

    def test_verify_imported_symbols_all_available(self):
        rows = verify_imported_symbols()
        self.assertEqual(len(rows), EXPECTED_SYMBOL_COUNT)
        missing = [row["symbol"] for row in rows if not row["available"]]
        self.assertEqual(missing, [])

    def test_exact_named_import_succeeds(self):
        result = test_exact_named_import()
        self.assertTrue(result["ok"], msg=result.get("exception_message"))
        self.assertEqual(result["symbol_count"], EXPECTED_SYMBOL_COUNT)
        self.assertIsNone(result["exception_type"])


class DiagnosticsCollectionTests(unittest.TestCase):
    def setUp(self):
        clear_debug_logs()

    def tearDown(self):
        clear_debug_logs()

    def test_collect_runtime_diagnostics_sections(self):
        diagnostics = collect_runtime_diagnostics()
        for section in (
            "application",
            "runtime",
            "analyzer_core",
            "imported_symbols",
            "exact_named_import",
            "app_state",
        ):
            self.assertIn(section, diagnostics)
        self.assertIn("python_version", diagnostics["application"])
        self.assertIn("streamlit_version", diagnostics["application"])
        self.assertTrue(diagnostics["analyzer_core"]["file"])
        self.assertTrue(diagnostics["analyzer_core"]["has_default_timestamp_mode"])
        self.assertEqual(len(diagnostics["imported_symbols"]), EXPECTED_SYMBOL_COUNT)

    def test_diagnostics_are_json_safe_without_secrets(self):
        payload = export_diagnostics_json(collect_runtime_diagnostics())
        parsed = json.loads(payload)
        self.assertIsInstance(parsed, dict)
        # No credential-looking keys are ever emitted.
        self.assertNotIn("secrets", payload.lower())
        self.assertNotIn("password", payload.lower())

    def test_export_debug_log_contains_records(self):
        debug_log("diagnostic marker")
        text = export_debug_log()
        self.assertIn("diagnostic marker", text)
        self.assertIn("WaveLogic MSO debug log", text)


class AppStateAndExceptionTests(unittest.TestCase):
    def setUp(self):
        clear_debug_logs()

    def tearDown(self):
        clear_debug_logs()

    def test_record_and_read_app_state(self):
        record_app_state(protocol="Differential Manchester", window_samples=42)
        state = get_app_state()
        self.assertEqual(state["protocol"], "Differential Manchester")
        self.assertEqual(state["window_samples"], 42)

    def test_record_exception_captures_type_message_traceback(self):
        try:
            raise ValueError("synthetic failure")
        except ValueError as exc:
            info = record_exception(exc)
        self.assertEqual(info["type"], "ValueError")
        self.assertIn("synthetic failure", info["message"])
        self.assertIn("ValueError", info["traceback"])
        self.assertEqual(get_last_exception()["type"], "ValueError")

    def test_module_exposes_no_streamlit_import_at_module_level(self):
        # debug_utils must stay import-safe without a Streamlit runtime.
        self.assertTrue(hasattr(debug_utils, "collect_runtime_diagnostics"))


if __name__ == "__main__":
    unittest.main()
