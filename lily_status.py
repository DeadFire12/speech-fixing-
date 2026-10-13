"""Quick health/status report for Lily.

    py Lily.py --status          from a command prompt (works whether or not Lily is running)
    status                       typed into Lily (running instance)

What it reports: version, whether a Lily session is running (PID, start time, uptime),
model/llama.cpp state, voice input mode and which voice parts are installed, tool/action/plugin
counts, memory file health, the log file and recent errors.

It is deliberately cheap and READ-ONLY: it never starts the model, never opens the microphone,
and never repairs or moves a damaged file (it only reports it).

Uptime: a running Lily records its start time in logs/status.json. A stale record whose process
no longer exists is reported as "did not shut down cleanly" instead of a fake uptime.
Standard library only; Python 3.8 / Windows 7 compatible.
"""
from __future__ import annotations

import importlib.util
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, Optional

import lily_config
import lily_log
import lily_paths
import lily_version
import safe_json

STATUS_FILE = "status.json"
_run = subprocess.run          # replaced in tests
_START = {"ts": None, "mode": None}
_COUNTS = {}                   # registered by the GUI: {"tools": n, "actions": n, "plugins": n}


# ---------------------------------------------------------------------------
# session record (logs/status.json)
# ---------------------------------------------------------------------------

def status_path() -> str:
    return lily_paths.log_path(STATUS_FILE)


def _write_record(record: dict) -> None:
    try:
        safe_json.atomic_write_json(status_path(), record, indent=2, keep_backup=False)
    except Exception:
        pass                      # status reporting must never break Lily


def read_record() -> Optional[dict]:
    path = status_path()
    if not os.path.exists(path):
        return None
    data, status, _note = safe_json.load_json_safe(path, dict, dict, repair=False)
    return data if status == safe_json.OK and isinstance(data, dict) and data else None


def mark_started(mode: str) -> None:
    """Called once by Lily.py when a session begins (mode: gui | console | dashboard)."""
    _START["ts"], _START["mode"] = time.time(), mode
    _write_record({"version": lily_version.__version__, "pid": os.getpid(), "mode": mode,
                   "started": _START["ts"], "running": True, "stopped": None, "clean_exit": None,
                   "counts": dict(_COUNTS)})


def mark_stopped() -> None:
    """Called on a clean shutdown. Only touches the record that belongs to this process."""
    if _START["ts"] is None:
        return
    rec = read_record()
    if rec and rec.get("pid") == os.getpid():
        rec.update({"running": False, "stopped": time.time(), "clean_exit": True})
        _write_record(rec)


def set_component_counts(tools: int, actions: int, plugins: int) -> None:
    _COUNTS.update({"tools": int(tools), "actions": int(actions), "plugins": int(plugins)})
    rec = read_record()
    if _START["ts"] is not None and rec and rec.get("pid") == os.getpid():
        rec["counts"] = dict(_COUNTS)
        _write_record(rec)


def _decode(data) -> str:
    if not isinstance(data, bytes):
        return str(data)
    for enc in ("mbcs", "utf-8", "cp1252"):      # tasklist writes the console's ANSI code page
        try:
            return data.decode(enc, errors="ignore")
        except LookupError:
            continue
    return data.decode("latin-1", errors="ignore")


def pid_alive(pid) -> Optional[bool]:
    """True/False, or None when it cannot be determined.

    Windows: tasklist (a long-standing Windows 7 tool). os.kill(pid, 0) is NOT used there:
    on Windows os.kill terminates the process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        try:
            result = _run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
                          capture_output=True, timeout=15)
        except Exception:
            return None
        return ('"%d"' % pid) in _decode(result.stdout)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return None


def format_duration(seconds) -> str:
    s = max(0, int(seconds))
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, sec = divmod(rem, 60)
    if d:
        return "%dd %dh %02dm" % (d, h, m)
    if h:
        return "%dh %02dm %02ds" % (h, m, sec)
    if m:
        return "%dm %02ds" % (m, sec)
    return "%ds" % sec


def _when(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"


def session_info(in_process: bool = False, now: Optional[float] = None) -> Dict:
    now = time.time() if now is None else now
    if in_process and _START["ts"] is not None:
        return {"state": "running", "pid": os.getpid(), "mode": _START["mode"], "started": _START["ts"],
                "uptime": now - _START["ts"]}
    rec = read_record()
    if rec is None:
        return {"state": "unknown" if in_process else "never"}
    started = rec.get("started")
    if rec.get("running"):
        alive = pid_alive(rec.get("pid"))
        if alive is False:
            return {"state": "crashed", "pid": rec.get("pid"), "mode": rec.get("mode"), "started": started}
        info = {"state": "running", "pid": rec.get("pid"), "mode": rec.get("mode"), "started": started}
        if started:
            info["uptime"] = now - float(started)
        if alive is None:
            info["unverified"] = True
        return info
    info = {"state": "stopped", "clean": bool(rec.get("clean_exit")), "mode": rec.get("mode"),
            "stopped": rec.get("stopped"), "started": started}
    if started and rec.get("stopped"):
        info["last_uptime"] = float(rec["stopped"]) - float(started)
    return info


# ---------------------------------------------------------------------------
# log file health
# ---------------------------------------------------------------------------
_ERR_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d{3} \| (ERROR|CRITICAL)\s")


def count_recent_errors(path: Optional[str], hours: float = 24.0, now: Optional[float] = None) -> Optional[int]:
    """ERROR/CRITICAL lines in the last `hours` hours, read from the tail of the log. None if no log."""
    if not path or not os.path.exists(path):
        return None
    now = time.time() if now is None else now
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 262144))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    count = 0
    for line in tail.splitlines():
        m = _ERR_LINE.match(line)
        if not m:
            continue
        try:
            when = time.mktime(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timetuple())
        except ValueError:
            continue
        if now - when <= hours * 3600:
            count += 1
    return count


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------

def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError, AttributeError):
        return name in sys.modules


def _read_api_flag(name: str) -> bool:
    """Read-only look at config/api_keys.json (the normal getters would repair a damaged file)."""
    try:
        from memory import config_manager as cm
        path = str(cm.CONFIG_FILE)
        if not os.path.exists(path):
            return False
        data, status, _n = safe_json.load_json_safe(path, dict, dict, repair=False)
        return bool(data.get(name)) if status == safe_json.OK else False
    except Exception:
        return False


def _model_info() -> Dict:
    from core import local_engine as le
    s = le.get_settings()
    llama_ok = bool(s["llama_path"]) and os.path.isfile(s["llama_path"])
    model_ok = bool(s["model_path"]) and os.path.isfile(s["model_path"])
    info = {"llama_found": llama_ok, "model_found": model_ok, "context": s["context"],
            "template": s["chat_template"], "llama_path": s["llama_path"], "model_path": s["model_path"]}
    if model_ok:
        info["model_name"] = os.path.basename(s["model_path"])
        try:
            info["model_mb"] = int(os.path.getsize(s["model_path"]) / (1024 * 1024))
        except OSError:
            info["model_mb"] = None
    return info


def _voice_info() -> Dict:
    settings = lily_config.load()
    if not settings.get("voice_input_enabled", True):
        mode = "disabled"
    elif _read_api_flag("wake_word_enabled"):
        mode = "wake word"
    elif _read_api_flag("push_to_talk_enabled"):
        mode = "push to talk"
    else:
        mode = "manual"
    backend = str(settings.get("stt_backend") or "auto").lower()
    vosk_dir = str(settings.get("vosk_model_path") or "").strip()
    offline = bool(vosk_dir) and os.path.isdir(vosk_dir) and _has_module("vosk")
    wake_installed = wake_ready = False
    try:
        from core import wake_word
        wake_installed, wake_ready = bool(wake_word.is_installed()), bool(wake_word.is_ready())
    except Exception:
        pass
    return {"mode": mode, "tts": _has_module("pyttsx3") and bool(settings.get("tts_enabled", True)),
            "tts_enabled": bool(settings.get("tts_enabled", True)),
            "mic_libs": _has_module("speech_recognition") and (_has_module("pyaudiowpatch") or _has_module("pyaudio")),
            "stt": "none" if backend == "none" else ("offline (Vosk)" if offline and backend in ("auto", "vosk")
                                                      else "Google (needs internet)"),
            "wake_installed": wake_installed, "wake_ready": wake_ready}


def _tool_counts(deep: bool) -> Dict:
    if _COUNTS:
        return dict(_COUNTS)
    counts = {}
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if deep:
                from lily_action_hub import LilyActionHub
                hub = LilyActionHub()
                counts = {"tools": len(hub.lily_tools.tools), "actions": len(hub.actions.names()),
                          "plugins": len(hub.plugin_ui())}
            else:
                from tool_registry import create_tool_manager
                counts = {"tools": len(create_tool_manager().tools), "actions": None, "plugins": None}
    except Exception:
        counts = {}
    return counts


def _memory_info() -> Dict:
    path = lily_paths.data_path("memory.json")
    if not os.path.exists(path):
        return {"state": "none"}
    data, status, note = safe_json.load_json_safe(path, dict, dict, repair=False)
    if status == safe_json.OK:
        return {"state": "ok", "entries": len(data)}
    return {"state": "damaged", "note": note}


def collect(in_process: bool = False, deep: bool = False) -> Dict:
    """Gather the status as a dict. Read-only and quick (no model call, no microphone).

    The whole collection runs in safe_json's read-only mode for this thread: nothing is
    repaired, moved or written, even when the plugin loader reads the configuration."""
    with safe_json.read_only():
        return _collect(in_process, deep)


def _collect(in_process: bool, deep: bool) -> Dict:
    path = lily_log.log_path() or lily_paths.log_path(lily_log.LOG_FILE_NAME)
    info = {
        "version": lily_version.__version__,
        "runtime": lily_version.runtime_summary(),
        "session": session_info(in_process=in_process),
        "model": _model_info(),
        "voice": _voice_info(),
        "tools": _tool_counts(deep),
        "memory": _memory_info(),
        "log": {"path": path, "exists": os.path.exists(path),
                "size_kb": (os.path.getsize(path) // 1024) if os.path.exists(path) else 0,
                "errors_24h": count_recent_errors(path)},
    }
    problems = []
    if not (info["model"]["llama_found"] and info["model"]["model_found"]):
        problems.append("chat model unavailable (tools still work)")
    if info["memory"]["state"] == "damaged":
        problems.append("memory.json is damaged (it will be preserved and recovered on the next start)")
    if info["session"]["state"] == "crashed":
        problems.append("the last session did not shut down cleanly")
    if (info["log"]["errors_24h"] or 0) > 0:
        problems.append("%d error(s) in the log in the last 24 hours" % info["log"]["errors_24h"])
    info["problems"] = problems
    info["overall"] = "OK" if not problems else "DEGRADED"
    return info


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------

def _yes(flag) -> str:
    return "yes" if flag else "no"


def format_status(info: Dict) -> str:
    s, m, v, t, mem, lg = info["session"], info["model"], info["voice"], info["tools"], info["memory"], info["log"]
    lines = ["%s - status" % lily_version.version_string(),
             "Overall: %s" % info["overall"] + ("" if not info["problems"] else " - " + "; ".join(info["problems"]))]
    state = s.get("state")
    if state == "running":
        text = "running (%s), PID %s" % (s.get("mode") or "?", s.get("pid"))
        if s.get("started"):
            text += ", started %s, uptime %s" % (_when(s["started"]), format_duration(s.get("uptime", 0)))
        if s.get("unverified"):
            text += " (could not verify the process)"
    elif state == "crashed":
        text = "not running - the last session (PID %s, started %s) did not shut down cleanly" % (
            s.get("pid"), _when(s.get("started")))
    elif state == "stopped":
        text = "not running - last session ended %s%s" % (
            "normally" if s.get("clean") else "unexpectedly",
            (" after " + format_duration(s["last_uptime"])) if s.get("last_uptime") is not None else "")
    elif state == "unknown":
        text = "no session record (Lily was not started with Lily.py)"
    else:
        text = "no session has been recorded yet"
    lines.append("Session: " + text)
    if m["llama_found"] and m["model_found"]:
        size = (", %s MB" % m["model_mb"]) if m.get("model_mb") else ""
        lines.append("Model:   ready - %s%s, context %s, template %s (not loaded until you chat)" % (
            m.get("model_name", "?"), size, m["context"], m["template"]))
    else:
        missing = []
        if not m["llama_found"]:
            missing.append("llama.cpp not found at '%s'" % m["llama_path"])
        if not m["model_found"]:
            missing.append("GGUF model not found at '%s'" % m["model_path"])
        lines.append("Model:   UNAVAILABLE - " + "; ".join(missing))
    lines.append("Voice:   input mode %s | speech output %s | microphone libraries %s | recognition %s | wake word %s" % (
        v["mode"], "installed" if v["tts"] else ("off in settings" if not v["tts_enabled"] else "not installed"),
        "installed" if v["mic_libs"] else "not installed", v["stt"],
        "ready" if v["wake_ready"] else ("installed, models missing" if v["wake_installed"] else "not installed")))
    if t:
        lines.append("Tools:   %s Lily tools, %s actions, %s plugin(s)" % (
            t.get("tools", "?"), t.get("actions") if t.get("actions") is not None else "n/a",
            t.get("plugins") if t.get("plugins") is not None else "n/a"))
    else:
        lines.append("Tools:   count unavailable")
    if mem["state"] == "ok":
        lines.append("Memory:  %d entries (memory.json readable)" % mem["entries"])
    elif mem["state"] == "none":
        lines.append("Memory:  no memory file yet")
    else:
        lines.append("Memory:  DAMAGED - " + str(mem.get("note", "")))
    err = lg["errors_24h"]
    lines.append("Log:     %s (%s KB), %s" % (
        lg["path"], lg["size_kb"], "no log written yet" if err is None else "%d error(s) in the last 24h" % err))
    lines.append(info["runtime"])
    return "\n".join(lines)


def main() -> int:
    """`Lily.py --status`."""
    print(format_status(collect(in_process=False, deep=True)))
    return 0
