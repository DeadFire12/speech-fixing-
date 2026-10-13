"""Guarded implementations of the destructive system actions.

Replaces the inline os.remove / shutil.rmtree / os.system("shutdown /s /t 0")
code that used to live inside lily_runtime. Callers must reach these through
the SafetyGate (safety.py); these functions still re-check protected paths.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import lily_config
import lily_log
import safety

_log = lily_log.get_logger("system")

IS_WINDOWS = sys.platform.startswith("win")
_run = subprocess.run  # replaced in tests


def _send2trash():
    try:
        import send2trash  # type: ignore
        return send2trash.send2trash
    except Exception:
        return None


def delete_path(path: str) -> str:
    """Delete a file or folder: Recycle Bin when possible, never a protected path."""
    reason = safety.protected_reason(path)
    if reason:
        _log.warning("refused to delete a protected path (%s): %s", reason, path)
        return "I won't delete that, because it is %s." % reason
    if not os.path.exists(path):
        return "That file or folder no longer exists."
    trash = _send2trash()
    try:
        if trash is not None:
            trash(path)
            _log.info("moved to the Recycle Bin: %s", path)
            return "Moved %s to the Recycle Bin. You can restore it from there." % path
        if os.path.isfile(path):
            os.remove(path)
            return "Deleted %s permanently (Recycle Bin support isn't installed)." % path
        shutil.rmtree(path)
        return "Deleted the folder %s permanently (Recycle Bin support isn't installed)." % path
    except Exception as exc:
        _log.exception("delete failed: %s", path)
        return "I couldn't delete that: %s" % exc


def power_action(kind: str) -> str:
    """Schedule shutdown/restart with a cancel window instead of instantly."""
    if kind not in ("shutdown", "restart"):
        return "Unknown power action."
    if not IS_WINDOWS:
        return "Power actions are only supported on Windows."
    delay = int(lily_config.get_number("shutdown_delay_seconds", 30))
    delay = max(5, min(delay, 600))
    flag = "/s" if kind == "shutdown" else "/r"
    try:
        result = _run(["shutdown", flag, "/t", str(delay)], capture_output=True, timeout=15)
    except Exception as exc:
        return "I couldn't schedule that: %s" % exc
    if getattr(result, "returncode", 1) != 0:
        return "Windows refused the request (code %s)." % getattr(result, "returncode", "?")
    _log.warning("%s scheduled in %d seconds", kind, delay)
    verb = "shut down" if kind == "shutdown" else "restart"
    return "Okay. Your computer will %s in %d seconds. Say \"cancel shutdown\" to stop it." % (verb, delay)


def cancel_power() -> str:
    if not IS_WINDOWS:
        return "Power actions are only supported on Windows."
    try:
        result = _run(["shutdown", "/a"], capture_output=True, timeout=15)
    except Exception as exc:
        return "I couldn't cancel it: %s" % exc
    if getattr(result, "returncode", 1) == 0:
        _log.info("pending shutdown/restart cancelled")
        return "Done. I cancelled the pending shutdown/restart."
    return "There was no shutdown or restart in progress."
