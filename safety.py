"""Safety classification and the single confirmation gate.

Audit findings addressed here:
  * confirmation was a global flag with no expiry, accepted "sure"/"right" and
    anything starting with "yes ", and could be answered by a remote dashboard
    user or a misheard voice command;
  * delete had no protected-path check (drive roots, C:\\Windows, Lily's own
    memory.json all got the same single yes/no);
  * nothing classified actions as read-only / reversible / destructive.

Tiers
    READ_ONLY    - reads information only
    REVERSIBLE   - easy to undo (launch app, open folder, volume, lock screen)
    DESTRUCTIVE  - needs explicit confirmation (delete, close app, shutdown,
                   change networking, run generated code ...)

Standard library only; Python 3.8 compatible.
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Callable, Optional, Tuple

import lily_config
import lily_log
import lily_paths

_log = lily_log.get_logger("safety")

READ_ONLY = "read_only"
REVERSIBLE = "reversible"
DESTRUCTIVE = "destructive"

TOOL_TIERS = {
    # read-only
    "system_info": READ_ONLY, "cpu_info": READ_ONLY, "memory_info": READ_ONLY, "disk_info": READ_ONLY,
    "battery_info": READ_ONLY, "network_info": READ_ONLY, "user_info": READ_ONLY, "datetime_info": READ_ONLY,
    "list_files": READ_ONLY, "search_files": READ_ONLY, "read_text_file": READ_ONLY,
    "get_folder_size": READ_ONLY, "list_backups": READ_ONLY, "list_processes": READ_ONLY,
    "take_screenshot": READ_ONLY,
    # reversible
    "launch_program": REVERSIBLE, "open_path": REVERSIBLE, "lock_computer": REVERSIBLE,
    "create_text_file": REVERSIBLE, "backup": REVERSIBLE, "open_url": REVERSIBLE,
    # destructive
    "delete_path": DESTRUCTIVE, "write_text_file": DESTRUCTIVE, "restart_computer": DESTRUCTIVE,
    "shutdown_computer": DESTRUCTIVE, "close_app": DESTRUCTIVE,
}

# computer_settings parses free text itself ("turn off wifi", "shut down"), so match by word
_DESTRUCTIVE_SETTING_WORDS = ("shutdown", "shut down", "restart", "reboot", "wifi", "wi-fi", "wi fi", "network",
                              "close", "kill", "sleep", "hibernate", "log off", "logoff", "sign out")
_DESTRUCTIVE_CODE_ACTIONS = {"run", "build", "execute", "auto_run"}


def tier_of_tool(name: str) -> str:
    return TOOL_TIERS.get(str(name), REVERSIBLE)


def classify_action(name: str, params: Optional[dict] = None) -> str:
    """Tier for a Mark-LIV action given its parameters."""
    params = params if isinstance(params, dict) else {}
    action = str(params.get("action", "") or "").lower().strip()
    if name in TOOL_TIERS:
        return TOOL_TIERS[name]
    if name == "computer_settings":
        return DESTRUCTIVE if any(w in action for w in _DESTRUCTIVE_SETTING_WORDS) else REVERSIBLE
    if name == "code_helper":
        return DESTRUCTIVE if action in _DESTRUCTIVE_CODE_ACTIONS else READ_ONLY
    if name == "dev_agent":
        return DESTRUCTIVE
    if name == "game_updater":
        shutdown = params.get("shutdown_when_done")
        return DESTRUCTIVE if shutdown in (True, "true", "True", "yes", 1) else REVERSIBLE
    if name == "file_controller":
        return DESTRUCTIVE if action in ("delete", "move", "write", "rename", "overwrite") else READ_ONLY
    if name in ("web_search", "weather_report", "youtube_video", "flight_finder"):
        return READ_ONLY
    return REVERSIBLE


# ---------------------------------------------------------------------------
# Protected paths / processes
# ---------------------------------------------------------------------------

def _n(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(str(path))))


def _inside(child: str, parent: str) -> bool:
    return child == parent or child.startswith(parent.rstrip("\\/") + os.sep)


def protected_reason(path: str, project_dir: Optional[str] = None) -> Optional[str]:
    """Return a human reason if `path` must never be deleted, else None."""
    if not str(path or "").strip():
        return "an empty path"
    p = _n(path)
    if os.path.dirname(p) == p or re.match(r"^[a-z]:[\\/]?$", p):
        return "a drive root"
    sysdirs = []
    for var in ("SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData"):
        v = os.environ.get(var)
        if v:
            sysdirs.append(_n(v))
    for d in sysdirs:
        if _inside(p, d):
            return "a Windows/system folder"
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if home:
        h = _n(home)
        if p == h or _inside(h, p):
            return "your user profile folder (or a folder that contains it)"
    proj = _n(project_dir or lily_paths.BASE_DIR)
    data = _n(lily_paths.data_dir())
    if _inside(proj, p) and p != proj:
        return "a folder that contains Lily"
    for guarded in {proj, data}:
        if _inside(p, guarded):
            rel = p[len(guarded):].lstrip("\\/")
            first = rel.split(os.sep)[0] if rel else ""
            if guarded == proj and first in ("backups", "logs", "screenshots"):
                continue
            return "part of Lily's own program or data"
    return None


PROTECTED_PROCESSES = {
    "system", "system idle process", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "lsm.exe", "svchost.exe", "dwm.exe", "explorer.exe", "taskhost.exe", "taskhostw.exe",
    "spoolsv.exe", "audiodg.exe", "conhost.exe", "python.exe", "pythonw.exe", "py.exe",
}


def protected_process(name: str) -> bool:
    n = str(name or "").lower().strip()
    if n and not n.endswith(".exe") and "." not in n:
        n += ".exe"
    own = os.path.basename(os.environ.get("LILY_SELF_EXE", "")).lower()
    return n in PROTECTED_PROCESSES or (bool(own) and n == own)


# ---------------------------------------------------------------------------
# Confirmation gate
# ---------------------------------------------------------------------------

def _norm_reply(text: str) -> str:
    t = re.sub(r"[^a-z0-9' ]+", " ", str(text or "").lower().replace("\u2019", "'"))
    return re.sub(r"\s+", " ", t).strip()


YES_LOCAL = {"yes", "y", "yes please", "confirm", "confirmed", "i confirm", "yes confirm", "yes i confirm", "yes do it"}
CONFIRM_VOICE = {"confirm", "confirmed", "i confirm", "yes confirm", "yes i confirm"}
CANCEL_WORDS = {"no", "n", "nope", "cancel", "stop", "never mind", "nevermind", "dont", "don't", "do not",
                "abort", "no thanks", "no thank you", "not now"}


class SafetyGate(object):
    """Holds at most ONE pending destructive action with a time limit."""

    def __init__(self, ttl_seconds: Optional[float] = None, clock: Callable[[], float] = time.monotonic):
        self._ttl_override = ttl_seconds
        self._clock = clock
        self._lock = threading.RLock()
        self._pending = None  # type: Optional[dict]

    def _ttl(self) -> float:
        if self._ttl_override is not None:
            return float(self._ttl_override)
        return lily_config.get_number("confirm_ttl_seconds", 60)

    def request(self, title: str, runner: Callable[[], str], detail: str = "") -> str:
        """Register an action and return the question to show the user."""
        ttl = self._ttl()
        with self._lock:
            self._pending = {"title": title, "runner": runner, "expires": self._clock() + ttl}
        _log.info("confirmation requested: %s (valid for %d s)", title, int(ttl))
        text = title.strip()
        if detail:
            text += " " + detail.strip()
        return "%s Type \"yes\" (or say \"confirm\") within %d seconds to go ahead, or \"no\" to cancel." % (
            text, int(ttl))

    def has_pending(self) -> bool:
        with self._lock:
            return self._pending is not None and self._clock() <= self._pending["expires"]

    def cancel(self) -> None:
        with self._lock:
            self._pending = None

    def handle_reply(self, text: str, origin: str = "local") -> Tuple[bool, Optional[str]]:
        """Returns (consumed, message). consumed=False means the message was not a
        reply to the pending question and should be processed normally (any
        unrelated message silently cancels the pending action)."""
        with self._lock:
            pending = self._pending
            if pending is None:
                return False, None
            n = _norm_reply(text)
            answered = n in YES_LOCAL or n in CANCEL_WORDS
            if self._clock() > pending["expires"]:
                self._pending = None
                _log.info("confirmation expired: %s", pending["title"])
                if answered:
                    return True, "That confirmation expired, so I did nothing."
                return False, None
            if n in CANCEL_WORDS:
                self._pending = None
                _log.info("cancelled by the user: %s", pending["title"])
                return True, "Okay, I cancelled that."
            if n not in YES_LOCAL:
                self._pending = None
                _log.info("pending request cancelled by an unrelated message: %s", pending["title"])
                return False, None
            if origin == "remote" and not lily_config.get_bool("allow_remote_confirmation", False):
                _log.warning("refused a remote confirmation for: %s", pending["title"])
                return True, ("For safety, confirmations must be given on this computer, not remotely. "
                              "I haven't done anything.")
            if origin == "voice" and n not in CONFIRM_VOICE:
                _log.info("voice reply was not the word 'confirm'; still waiting: %s", pending["title"])
                return True, "For safety, please say \"confirm\" (or type yes) so I'm sure I heard you correctly."
            runner = pending["runner"]
            self._pending = None
        _log.info("confirmed (%s): %s", origin, pending["title"])
        try:
            return True, str(runner())
        except Exception as exc:  # the action itself failed; Lily stays alive
            _log.exception("confirmed action failed: %s", pending["title"])
            return True, "I couldn't do that: %s" % exc


_gate = SafetyGate()


def get_gate() -> SafetyGate:
    return _gate
