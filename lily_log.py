"""Structured, persistent logging for Lily.

* One rotating file (logs/lily.log, 1 MB x 3 backups by default) next to the program.
* Every line: timestamp with milliseconds | level | component | thread | message,
  and a full traceback for errors.
* Uncaught exceptions - in the main thread or any worker thread - are written to the log
  before anything else happens, so a crash always leaves evidence.
* Never raises: if the log folder is not writable Lily keeps running and warnings go to the
  console instead.
* Privacy: the logs record WHAT happened (events, errors, safety decisions, sizes), not what
  you said. Message text is never written.

Settings (config/local_settings.json): log_level (DEBUG|INFO|WARNING|ERROR, default INFO),
log_max_bytes (default 1000000), log_backup_count (default 3).
Standard library only; Python 3.8 / Windows 7 compatible.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
from typing import Optional

import lily_paths

ROOT_NAME = "lily"
LOG_FILE_NAME = "lily.log"
FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(threadName)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Without a handler, Python prints WARNING+ records to stderr ("last resort"). Until
# setup_logging() runs, stay quiet instead.
logging.getLogger(ROOT_NAME).addHandler(logging.NullHandler())
logging.raiseExceptions = False   # a logging problem (e.g. file locked on Windows) must never crash Lily

_lock = threading.RLock()
_state = {"path": None, "hooks": False, "orig_excepthook": None, "orig_thread_hook": None}


def get_logger(component: str = "") -> logging.Logger:
    """Logger for a component, e.g. get_logger('runtime') -> 'lily.runtime'."""
    return logging.getLogger("%s.%s" % (ROOT_NAME, component) if component else ROOT_NAME)


def _level(value) -> int:
    name = str(value or "INFO").strip().upper()
    return {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "WARN": logging.WARNING,
            "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}.get(name, logging.INFO)


def _our_handlers():
    return [h for h in get_logger().handlers if getattr(h, "_lily_handler", False)]


def log_path() -> Optional[str]:
    """Path of the active log file, or None when file logging is not active."""
    return _state["path"]


def shutdown_logging() -> None:
    """Flush and close Lily's handlers (safe to call repeatedly)."""
    with _lock:
        root = get_logger()
        for handler in _our_handlers():
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
            root.removeHandler(handler)
        _state["path"] = None


def setup_logging(path: Optional[str] = None, level=None) -> Optional[str]:
    """Start file logging. Idempotent: calling it again with the same file changes nothing
    (no duplicate handlers); a different file replaces the old handler.

    Returns the log file path, or None if the file could not be opened (a console handler
    for WARNING+ is installed instead). Never raises."""
    import lily_config
    try:
        settings = lily_config.load()
    except Exception:
        settings = {}
    wanted = os.path.abspath(path or lily_paths.log_path(LOG_FILE_NAME))
    lvl = _level(level if level is not None else settings.get("log_level"))
    with _lock:
        root = get_logger()
        root.setLevel(lvl)
        root.propagate = False
        if _state["path"] == wanted and _our_handlers():
            for h in _our_handlers():
                h.setLevel(lvl)
            return wanted
        shutdown_logging()
        try:
            folder = os.path.dirname(wanted)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder, exist_ok=True)
            try:
                max_bytes = int(float(settings.get("log_max_bytes", 1000000)))
                backups = int(float(settings.get("log_backup_count", 3)))
            except (TypeError, ValueError):
                max_bytes, backups = 1000000, 3
            handler = logging.handlers.RotatingFileHandler(
                wanted, maxBytes=max(10000, max_bytes), backupCount=max(0, backups), encoding="utf-8", delay=True)
            handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
            handler.setLevel(lvl)
            handler._lily_handler = True
            root.addHandler(handler)
            # open the file now so a permission problem shows up here, not on the first message
            handler.acquire()
            try:
                handler.stream = handler._open()
            finally:
                handler.release()
            _state["path"] = wanted
            return wanted
        except Exception as exc:
            fallback = logging.StreamHandler(sys.stderr)
            fallback.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
            fallback.setLevel(max(lvl, logging.WARNING))
            fallback._lily_handler = True
            root.addHandler(fallback)
            _state["path"] = None
            root.warning("File logging is unavailable (%s); messages go to the console instead.", exc)
            return None


def install_excepthooks() -> None:
    """Log uncaught exceptions (main thread and worker threads), then run the previous hook."""
    with _lock:
        if _state["hooks"]:
            return
        _state["hooks"] = True
        _state["orig_excepthook"] = sys.excepthook
        _state["orig_thread_hook"] = getattr(threading, "excepthook", None)

    def _main_hook(exc_type, exc, tb):
        try:
            if not issubclass(exc_type, KeyboardInterrupt):
                get_logger("crash").critical("Unhandled exception in the main thread", exc_info=(exc_type, exc, tb))
        finally:
            (_state["orig_excepthook"] or sys.__excepthook__)(exc_type, exc, tb)

    sys.excepthook = _main_hook

    if _state["orig_thread_hook"] is not None:      # threading.excepthook exists from Python 3.8
        def _thread_hook(args):
            try:
                if args.exc_type is not SystemExit:
                    name = getattr(args.thread, "name", "?")
                    get_logger("crash").critical("Unhandled exception in thread %s", name,
                                                 exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            finally:
                _state["orig_thread_hook"](args)
        threading.excepthook = _thread_hook


def remove_excepthooks() -> None:
    """Restore the previous hooks (used by tests)."""
    with _lock:
        if not _state["hooks"]:
            return
        sys.excepthook = _state["orig_excepthook"] or sys.__excepthook__
        if _state["orig_thread_hook"] is not None:
            threading.excepthook = _state["orig_thread_hook"]
        _state["hooks"] = False


def flush() -> None:
    for handler in _our_handlers():
        try:
            handler.flush()
        except Exception:
            pass
