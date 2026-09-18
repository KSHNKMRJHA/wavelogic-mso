"""Observational debug/logging helpers for WaveLogic MSO.

This module is import-safe without a Streamlit runtime (so tests and tooling can
use it) and is strictly observational: it never modifies decoder logic,
protocol behavior, timestamp handling, application data, or configuration.

Per-session logs/state live in ``st.session_state`` when a Streamlit runtime is
present; otherwise a bounded module-level fallback is used.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import sys
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

MAX_LOG_RECORDS = 200
ANALYZER_CORE_MODULE = "analyzer_core"
UNAVAILABLE = "Unavailable"

_SESSION_LOG_KEY = "_wavelogic_debug_log"
_SESSION_STATE_KEY = "_wavelogic_app_state"
_SESSION_EXCEPTION_KEY = "_wavelogic_last_exception"

_REPO_ROOT = Path(__file__).resolve().parent
_APP_PATH = _REPO_ROOT / "app.py"

_FALLBACK_LOGS: deque = deque(maxlen=MAX_LOG_RECORDS)
_FALLBACK_STATE: dict = {}
_FALLBACK_EXCEPTION: dict = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _session_state():
    """Return ``st.session_state`` only when a live Streamlit runtime exists."""
    try:
        import streamlit as st
    except Exception:
        return None
    try:
        from streamlit.runtime import exists as _runtime_exists

        if not _runtime_exists():
            return None
    except Exception:
        return None
    try:
        return st.session_state
    except Exception:
        return None


def _get_or_create(key, factory, fallback):
    state = _session_state()
    if state is not None:
        try:
            return state[key]
        except Exception:
            try:
                value = factory()
                state[key] = value
                return value
            except Exception:
                return fallback
    return fallback


def _log_buffer() -> deque:
    return _get_or_create(
        _SESSION_LOG_KEY,
        lambda: deque(maxlen=MAX_LOG_RECORDS),
        _FALLBACK_LOGS,
    )


def _state_container() -> dict:
    return _get_or_create(_SESSION_STATE_KEY, dict, _FALLBACK_STATE)


def _exception_container() -> dict:
    return _get_or_create(_SESSION_EXCEPTION_KEY, dict, _FALLBACK_EXCEPTION)


def debug_log(message, level: str = "INFO") -> dict:
    """Append one bounded diagnostic record and return it. Never raises."""
    record = {
        "timestamp": _now_iso(),
        "level": str(level).upper() or "INFO",
        "message": str(message),
    }
    try:
        _log_buffer().append(record)
    except Exception:
        pass
    return record


def get_debug_logs() -> list[dict]:
    """Return the current bounded log records, oldest first."""
    try:
        return list(_log_buffer())
    except Exception:
        return []


def clear_debug_logs() -> None:
    """Empty the current bounded log buffer."""
    try:
        _log_buffer().clear()
    except Exception:
        pass


def record_app_state(**fields) -> dict:
    """Merge safe, non-secret application state fields for display."""
    try:
        container = _state_container()
        container.update(fields)
        return dict(container)
    except Exception:
        return {}


def get_app_state() -> dict:
    try:
        return dict(_state_container())
    except Exception:
        return {}


def record_exception(exc: BaseException) -> dict:
    """Store the most recent exception (type/message/traceback) safely."""
    info = {
        "timestamp": _now_iso(),
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }
    try:
        container = _exception_container()
        container.clear()
        container.update(info)
    except Exception:
        pass
    return info


def get_last_exception() -> dict:
    try:
        return dict(_exception_container())
    except Exception:
        return {}


def discover_analyzer_core_symbols(app_path=None) -> tuple[str, ...]:
    """Return the exact names ``app.py`` imports from ``analyzer_core``.

    Inspected dynamically from source so the debug view can never drift from
    the real import list. Returns an empty tuple if discovery fails.
    """
    path = Path(app_path) if app_path is not None else _APP_PATH
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return ()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == ANALYZER_CORE_MODULE:
            return tuple(alias.name for alias in node.names)
    return ()


def verify_imported_symbols(symbols=None) -> list[dict]:
    """Return ``[{symbol, available}]`` for the analyzer_core import list."""
    names = tuple(symbols) if symbols is not None else discover_analyzer_core_symbols()
    try:
        import importlib

        module = importlib.import_module(ANALYZER_CORE_MODULE)
    except Exception as exc:  # pragma: no cover - defensive
        return [
            {"symbol": name, "available": False, "note": f"{type(exc).__name__}"}
            for name in names
        ]
    return [{"symbol": name, "available": bool(hasattr(module, name))} for name in names]


def test_exact_named_import(symbols=None) -> dict:
    """Execute the exact ``from analyzer_core import (...)`` used by app.py."""
    names = tuple(symbols) if symbols is not None else discover_analyzer_core_symbols()
    result = {
        "ok": False,
        "symbol_count": len(names),
        "exception_type": None,
        "exception_message": None,
        "traceback": None,
    }
    if not names:
        result["exception_type"] = "Unavailable"
        result["exception_message"] = "No analyzer_core symbols were discovered."
        return result
    try:
        namespace: dict = {}
        statement = "from analyzer_core import (" + ", ".join(names) + ")"
        exec(compile(statement, "<analyzer_core-named-import>", "exec"), namespace)
        result["ok"] = True
    except Exception as exc:
        result["exception_type"] = type(exc).__name__
        result["exception_message"] = str(exc)
        result["traceback"] = traceback.format_exc()
    return result


def _analyzer_core_file_info() -> dict:
    info = {"module": ANALYZER_CORE_MODULE, "file": UNAVAILABLE, "sha256_12": UNAVAILABLE,
            "size_bytes": UNAVAILABLE, "has_default_timestamp_mode": UNAVAILABLE}
    try:
        import importlib

        module = importlib.import_module(ANALYZER_CORE_MODULE)
        info["has_default_timestamp_mode"] = bool(
            hasattr(module, "default_timestamp_mode")
        )
        module_file = getattr(module, "__file__", None)
        if module_file:
            info["file"] = str(module_file)
            try:
                data = Path(module_file).read_bytes()
                info["sha256_12"] = hashlib.sha256(data).hexdigest()[:12]
                info["size_bytes"] = len(data)
            except Exception:
                pass
    except Exception as exc:
        info["file"] = f"{UNAVAILABLE}: {type(exc).__name__}: {exc}"
    return info


def _streamlit_version() -> str:
    try:
        import streamlit

        return str(getattr(streamlit, "__version__", UNAVAILABLE))
    except Exception:
        return UNAVAILABLE


def collect_runtime_diagnostics(include_import_test: bool = True) -> dict:
    """Collect safe, non-secret diagnostics. Missing values become 'Unavailable'."""
    diagnostics: dict = {
        "application": {
            "build_label": UNAVAILABLE,
            "app_file": str(_APP_PATH),
            "python_version": sys.version.split()[0],
            "python_full_version": sys.version.replace("\n", " "),
            "streamlit_version": _streamlit_version(),
        },
        "runtime": {
            "cwd": UNAVAILABLE,
            "executable": UNAVAILABLE,
            "platform": UNAVAILABLE,
            "machine": UNAVAILABLE,
            "pid": UNAVAILABLE,
            "sys_path": [],
        },
        "analyzer_core": _analyzer_core_file_info(),
        "imported_symbols": verify_imported_symbols(),
        "exact_named_import": UNAVAILABLE,
        "app_state": get_app_state(),
        "last_exception": get_last_exception() or UNAVAILABLE,
        "log_record_count": len(get_debug_logs()),
    }

    try:
        from branding import get_build_label

        diagnostics["application"]["build_label"] = get_build_label() or UNAVAILABLE
    except Exception:
        pass

    runtime = diagnostics["runtime"]
    try:
        runtime["cwd"] = os.getcwd()
    except Exception:
        pass
    try:
        runtime["executable"] = sys.executable
    except Exception:
        pass
    try:
        runtime["platform"] = platform.platform()
    except Exception:
        pass
    try:
        runtime["machine"] = platform.machine()
    except Exception:
        pass
    try:
        runtime["pid"] = os.getpid()
    except Exception:
        pass
    try:
        runtime["sys_path"] = list(sys.path)
    except Exception:
        pass

    if include_import_test:
        diagnostics["exact_named_import"] = test_exact_named_import()

    return diagnostics


def format_debug_log(logs=None, limit: int | None = None) -> str:
    """Render log records as ``timestamp [LEVEL] message`` lines."""
    records = get_debug_logs() if logs is None else list(logs)
    if limit is not None and limit >= 0:
        records = records[-limit:]
    lines = [f"{r.get('timestamp', '')} [{r.get('level', '')}] {r.get('message', '')}"
             for r in records]
    return "\n".join(lines)


def export_debug_log(logs=None) -> str:
    """Return a downloadable plain-text debug log."""
    records = get_debug_logs() if logs is None else list(logs)
    header = (
        "WaveLogic MSO debug log\n"
        f"Generated: {_now_iso()}\n"
        f"Records: {len(records)} (bounded to {MAX_LOG_RECORDS})\n"
        "Note: observational only. Contains no secrets or uploaded waveform data.\n"
        + "-" * 60
    )
    body = format_debug_log(records) or "No debug records."
    return f"{header}\n{body}\n"


def export_diagnostics_json(diagnostics=None) -> str:
    """Return safe diagnostics as pretty JSON (no secrets, no waveform data)."""
    data = collect_runtime_diagnostics() if diagnostics is None else diagnostics
    try:
        return json.dumps(data, indent=2, default=str, sort_keys=True)
    except Exception as exc:  # pragma: no cover - defensive
        return json.dumps(
            {"error": f"{type(exc).__name__}: {exc}"}, indent=2, sort_keys=True
        )
