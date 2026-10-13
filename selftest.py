"""Lily Self Test.

Run:   python Lily.py --selftest            (full, includes a live model call)
       python Lily.py --selftest --quick    (no live model call)
       python Lily.py --selftest --audio    (also opens the microphone briefly and speaks a phrase)

Statuses
    PASS      works
    WARNING   works with a limitation, or an optional part is not fully available
    FAIL      a core part is broken (exit code 1)
    SKIPPED   not applicable / optional and not installed

A missing OPTIONAL component (wake word, offline speech model, PyQt5, TTS ...) never
produces FAIL: Lily degrades to text mode and the report says so.

The test never touches your real memory.json: the memory round-trip runs in a
temporary folder, and data files are only inspected (never repaired) here.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import platform
import sys
import tempfile
import time
import traceback
from typing import Callable, List, Tuple

PASS, WARNING, FAIL, SKIPPED = "PASS", "WARNING", "FAIL", "SKIPPED"
Result = Tuple[str, str, str]  # (name, status, message)


class _quiet(object):
    """Silence stdout AND stderr (the deliberately broken probes print tracebacks)."""

    def __enter__(self):
        self._a = contextlib.redirect_stdout(io.StringIO())
        self._b = contextlib.redirect_stderr(io.StringIO())
        self._a.__enter__()
        self._b.__enter__()
        return self

    def __exit__(self, *exc):
        self._b.__exit__(*exc)
        self._a.__exit__(*exc)
        return False


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError, AttributeError):
        return name in sys.modules


# ---------------------------------------------------------------------------
def check_python() -> Result:
    v = sys.version_info
    where = "%s %s" % (platform.system(), platform.release())
    detail = "Python %d.%d.%d on %s" % (v[0], v[1], v[2], where)
    if v < (3, 7):
        return "Python runtime", FAIL, detail + " - Lily needs Python 3.8 (3.7 at minimum)."
    if (v[0], v[1]) != (3, 8):
        return "Python runtime", WARNING, detail + " - the Windows 7 build is meant for Python 3.8.x."
    return "Python runtime", PASS, detail


def check_logging() -> Result:
    import lily_log
    path = lily_log.setup_logging()
    if not path:
        return "Logging", WARNING, "the log file cannot be written - messages go to the console instead (check the logs folder)"
    lily_log.get_logger("selftest").info("self-test logging probe")
    lily_log.flush()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            ok = "self-test logging probe" in fh.read()
    except OSError as exc:
        return "Logging", WARNING, "the log file was created but cannot be read back: %s" % exc
    if not ok:
        return "Logging", WARNING, "the log file exists but the test line was not written"
    return "Logging", PASS, "writing to %s" % path


def check_config() -> Result:
    import lily_config
    import lily_paths
    path = lily_config.settings_path()
    if not os.path.exists(path):
        return "Configuration", WARNING, "no %s - using defaults (assistant 'Lily')" % path
    s = lily_config.load()
    note = lily_config.LAST_NOTE
    msg = "settings read from %s; assistant=%s, user=%s" % (
        os.path.relpath(path, str(lily_paths.BASE_DIR)), s.get("assistant_name"), s.get("user_name") or "(not set)")
    if note:
        return "Configuration", WARNING, msg + " | " + note
    return "Configuration", PASS, msg


def check_data_files() -> Result:
    import lily_paths
    import safe_json
    problems, found = [], 0
    for name, kind in (("memory.json", dict), ("learning.json", dict), ("state.json", dict), ("goals.json", list)):
        path = lily_paths.data_path(name)
        if not os.path.exists(path):
            continue
        found += 1
        _data, status, note = safe_json.load_json_safe(path, kind, kind, repair=False)
        if status not in (safe_json.OK,):
            problems.append("%s: %s" % (name, note or status))
    if problems:
        return "Data files", WARNING, "damaged (Lily will preserve and recover them on start-up): " + "; ".join(problems)
    return "Data files", PASS, "%d data file(s) readable; folder: %s" % (found, lily_paths.data_dir())


def check_memory_roundtrip() -> Result:
    import memory_manager as mm
    old = os.environ.get("LILY_DATA_DIR")
    tmp = tempfile.mkdtemp(prefix="lily-selftest-")
    os.environ["LILY_DATA_DIR"] = tmp
    try:
        with _quiet():
            mem = mm.load_memory()
            mm.remember(mem, "selftest color", "green")
            reloaded = mm.load_memory()
            assert "selftest color" in reloaded, "saved entry did not survive a reload"
            assert mm.search_memory(reloaded, "green"), "search did not find the entry"
            mm.remember(reloaded, "selftest color", "blue")
            assert mm.load_memory()["selftest color"]["value"] == "blue", "update was not saved"
            assert mm.forget_memory(reloaded, "selftest color"), "delete failed"
            assert "selftest color" not in mm.load_memory(), "deleted entry came back"
            # corruption must be survivable and must preserve the original bytes
            mm.remember(mm.load_memory(), "keep me", "x")
            path = mm.memory_path()
            good = open(path, "rb").read()
            open(path, "wb").write(good[: len(good) // 2])
            damaged = mm.load_memory()
            kept = [f for f in os.listdir(tmp) if ".corrupt-" in f]
            assert kept, "damaged file was not preserved"
        return "Memory system", PASS, "create/save/reload/search/update/delete and damaged-file recovery work (temporary folder)"
    except AssertionError as exc:
        return "Memory system", FAIL, str(exc)
    finally:
        if old is None:
            os.environ.pop("LILY_DATA_DIR", None)
        else:
            os.environ["LILY_DATA_DIR"] = old


def check_identity_prompt() -> Result:
    import identity
    import prompt_manager
    a, u = identity.get_names()
    sections = prompt_manager.build_system_sections(a, u, "Be warm and helpful.", "", "", "")
    turns = [("question %d" % i, "answer " * 40) for i in range(60)]
    prompt, info = prompt_manager.build_chat_prompt(sections, turns, "hello", 2048, 192)
    if not prompt.startswith("<|im_start|>system"):
        return "Identity & prompt", FAIL, "the system block is not first in the prompt"
    if a not in prompt.split("<|im_end|>")[0]:
        return "Identity & prompt", FAIL, "the assistant name is missing from the system block"
    if info["estimated_tokens"] > 2048 - 192:
        return "Identity & prompt", FAIL, "the prompt exceeds the context budget"
    reply = identity.match_identity_question("Hi, who are you?", a, u)
    if not reply or a not in reply:
        return "Identity & prompt", FAIL, "identity questions are not answered as %s" % a
    return "Identity & prompt", PASS, "persona first, fits %d/%d tokens with %d of %d history turns; assistant=%s user=%s" % (
        info["estimated_tokens"], info["budget"], info["turns_included"], info["turns_available"], a, u or "(not set)")


def check_local_model(quick: bool) -> List[Result]:
    from core import local_engine as le
    import identity
    import prompt_manager
    d = le.diagnose()
    out = []  # type: List[Result]
    if not d["llama_found"]:
        return [("Local model", FAIL, "llama.cpp not found at '%s'. Set llama_path in config/local_settings.json "
                                      "or put llama-cli.exe in the 'llama' folder." % d["llama_path"])]
    if not d["model_found"]:
        return [("Local model", FAIL, "GGUF model not found at '%s'. Set model_path in config/local_settings.json "
                                      "or put a .gguf file in the 'models' folder." % d["model_path"])]
    if quick:
        return [("Local model", PASS, "llama.cpp and model files found (live test skipped: --quick)")]
    a, u = identity.get_names()
    s = le.get_settings()
    sections = prompt_manager.build_system_sections(a, u, "", "", "", "")
    q = "Say your name and what you are, in one short sentence."
    prompt, _ = prompt_manager.build_chat_prompt(sections, [], q, s["context"], 96, prompt_manager.get_profile(s["chat_template"]))
    t0 = time.time()
    try:
        raw = le.generate(prompt, max_tokens=48, timeout=max(60, s["timeout"]))
    except le.EngineTimeout:
        return [("Local model", FAIL, "no answer within the time limit - the model is too slow or hung")]
    except le.EngineError as exc:
        return [("Local model", FAIL, "engine error: %s" % exc)]
    secs = time.time() - t0
    if not raw.strip():
        return [("Local model", WARNING, "the model returned an empty answer after %.1fs (check the model file / -no-cnv)" % secs)]
    out.append(("Local model", PASS, "answered in %.1fs: %r" % (secs, raw[:70])))
    low = raw.lower()
    if "qwen" in low or "alibaba" in low:
        out.append(("Model identity", WARNING, "the raw model said %r - Lily's identity guard rewrites this, but the "
                                               "prompt did not fully hold" % raw[:80]))
    elif a.lower() in low:
        out.append(("Model identity", PASS, "the model speaks as %s without being corrected" % a))
    else:
        out.append(("Model identity", WARNING, "the model did not state the name %s (small models can ignore the "
                                               "persona; identity questions are still answered directly)" % a))
    return out


def check_plugins() -> List[Result]:
    from pathlib import Path
    out = []  # type: List[Result]
    try:
        from lily_action_hub import LilyActionHub
        with _quiet():
            hub = LilyActionHub()
        n_tools, n_actions = len(hub.lily_tools.tools), len(hub.actions.names())
        rejected = [r for r in getattr(hub.actions, "_all_records", []) if not r.valid]
        msg = "%d Lily tools, %d actions, %d plugin(s)" % (n_tools, n_actions, len(hub.plugin_ui()))
        if rejected:
            out.append(("Plugin discovery", WARNING, msg + "; rejected: " + ", ".join(r.file for r in rejected)))
        else:
            out.append(("Plugin discovery", PASS, msg))
    except Exception as exc:
        out.append(("Plugin discovery", FAIL, "%s: %s" % (type(exc).__name__, exc)))
        return out
    # isolation probe: a broken action and a raising/hanging one must not take Lily down
    tmp = Path(tempfile.mkdtemp(prefix="lily-plugin-probe-"))
    (tmp / "broken_import.py").write_text("raise RuntimeError('broken at import')\n")
    (tmp / "raises.py").write_text("def run(parameters=None, **kw):\n    raise ValueError('boom')\nTOOL={'name':'raises','description':'d','handler':run}\n")
    (tmp / "hangs.py").write_text("import time\ndef run(parameters=None, **kw):\n    time.sleep(30)\nTOOL={'name':'hangs','description':'d','handler':run}\n")
    try:
        from core import action_loader, safe_call
        with _quiet():
            reg = action_loader.discover_actions(tmp, reserved_names=set())
            r1 = reg.run("raises", {})
            old = dict(safe_call.TIMEOUTS)
            safe_call.TIMEOUTS["hangs"] = 1.0
            try:
                t0 = time.time()
                r2 = reg.run("hangs", {})
                waited = time.time() - t0
            finally:
                safe_call.TIMEOUTS.clear()
                safe_call.TIMEOUTS.update(old)
        if "failed" in r1 and "stopped waiting" in r2 and waited < 10:
            out.append(("Plugin isolation", PASS, "a broken, a raising and a hanging action were all contained"))
        else:
            out.append(("Plugin isolation", FAIL, "unexpected results: %r / %r" % (r1, r2)))
    except Exception as exc:
        out.append(("Plugin isolation", FAIL, "%s: %s" % (type(exc).__name__, exc)))
    return out


def check_tts(audio: bool) -> Result:
    import voice_manager as vm
    st = vm.tts_status()
    if not st["available"]:
        return "Speech output (TTS)", WARNING, "unavailable (%s) - Lily continues in text mode" % st["reason"]
    if audio:
        ok = vm.speak("Lily self test.", timeout=30)
        return ("Speech output (TTS)", PASS, "spoke a test phrase") if ok else (
            "Speech output (TTS)", WARNING, "pyttsx3 is installed but speaking failed - text mode still works")
    try:
        vm._pyttsx3.init()
        return "Speech output (TTS)", PASS, "pyttsx3 engine can be created (run with --audio to hear it)"
    except Exception as exc:
        return "Speech output (TTS)", WARNING, "pyttsx3 is installed but could not start: %s" % exc


def check_microphone(audio: bool) -> Result:
    import audio_input
    import voice_manager as vm
    if not vm.AUDIO_AVAILABLE:
        return "Microphone", WARNING, "audio libraries not available (%s) - voice input is off, text mode works" % vm.AUDIO_IMPORT_ERROR
    try:
        names = list(vm.sr.Microphone.list_microphone_names())
    except Exception as exc:
        return "Microphone", WARNING, "could not list microphones: %s" % exc
    if not names:
        return "Microphone", WARNING, "no input devices found - voice input unavailable, text mode works"
    import lily_config
    wanted = vm._configured_device()
    idx, reason = audio_input.resolve_input_index(
        names, wanted, lily_config.get("mic_name_hints") or [],
        preferred_index=lily_config.get("mic_device_index"))
    label = names[idx] if idx is not None else "the system default device"
    msg = "%d device(s); will use %s (%s)" % (len(names), label, reason)
    if reason == "configured-not-found":
        return "Microphone", WARNING, msg + " - the saved microphone '%s' is not present" % wanted
    if audio:
        try:
            pa = vm.pyaudio.PyAudio()
            kw = dict(format=vm.pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
            if idx is not None:
                kw["input_device_index"] = idx
            stream = pa.open(**kw)
            stream.read(1024, exception_on_overflow=False)
            stream.close()
            pa.terminate()
            msg += "; opened and read it successfully"
        except Exception as exc:
            return "Microphone", WARNING, msg + "; but opening it failed: %s" % exc
    return "Microphone", PASS, msg


def check_stt() -> Result:
    import lily_config
    import voice_manager as vm
    backend = str(lily_config.get("stt_backend") or "auto").lower()
    if backend == "none":
        return "Speech recognition", SKIPPED, "disabled in settings"
    if not vm.AUDIO_AVAILABLE:
        return "Speech recognition", SKIPPED, "audio libraries not available"
    if vm._vosk_ready():
        return "Speech recognition", PASS, "offline model (Vosk) configured - no internet needed"
    return "Speech recognition", WARNING, ("uses Google's online service (needs internet). For fully offline voice input set "
                                           "vosk_model_path in config/local_settings.json")


def check_wake_word() -> Result:
    from core import wake_word
    if not wake_word.is_installed():
        return "Wake word", SKIPPED, "optional: openwakeword is not installed (push-to-talk / manual voice / typing still work)"
    if not wake_word.is_ready():
        return "Wake word", WARNING, "openwakeword is installed but its model files are missing (use the Wake Word setup button once)"
    return "Wake word", PASS, "openwakeword and the 'hey_jarvis' model are present"


def check_gui() -> Result:
    if not _has_module("PyQt5"):
        return "GUI", WARNING, "PyQt5 is not installed - use the console: python Lily.py --console"
    return "GUI", PASS, "PyQt5 is installed (the HUD itself can only be verified by launching it)"


def check_safety() -> Result:
    import safety
    gate = safety.get_gate()
    assert safety.tier_of_tool("delete_path") == safety.DESTRUCTIVE
    if safety.protected_reason(os.path.abspath(os.sep)) is None:
        return "Safety gate", FAIL, "a drive root is not protected from deletion"
    result = []
    gate.request("probe?", lambda: result.append(1) or "ran")
    consumed, _ = gate.handle_reply("sure", "local")          # must NOT confirm
    if result:
        return "Safety gate", FAIL, "a loose 'sure' confirmed a destructive action"
    return "Safety gate", PASS, "destructive actions need an explicit, local, time-limited confirmation; protected paths are refused"


def check_offline() -> Result:
    import lily_config
    import voice_manager as vm
    if vm.AUDIO_AVAILABLE and not vm._vosk_ready() and str(lily_config.get("stt_backend") or "auto").lower() != "none":
        return "Offline operation", WARNING, "chat, memory, tools and speech output work offline; voice input recognition is online until an offline model is configured"
    if not vm.AUDIO_AVAILABLE:
        return "Offline operation", PASS, "chat, memory and tools need no internet (voice packages are not installed)"
    return "Offline operation", PASS, "chat, memory, tools, speech and voice input need no internet"


def check_dependencies() -> Result:
    required = ["json", "threading", "subprocess"]
    optional = {"PyQt5": "HUD", "pyttsx3": "speech output", "speech_recognition": "voice input", "pyaudiowpatch": "microphone",
                "psutil": "system info", "pyautogui": "keyboard/mouse actions", "send2trash": "Recycle Bin deletes",
                "numpy": "wake word", "openwakeword": "wake word", "onnxruntime": "wake word", "fastapi": "remote dashboard",
                "uvicorn": "remote dashboard", "cryptography": "remote dashboard",
                "websockets": "remote dashboard", "pydantic": "remote dashboard", "sounddevice": "HUD device pickers"}
    missing = ["%s (%s)" % (m, why) for m, why in optional.items() if not _has_module(m)]
    notes = []
    try:
        from importlib import metadata
        if _has_module("pydantic") and int(metadata.version("pydantic").split(".")[0]) >= 2:
            notes.append("pydantic %s is installed: its Rust core may not load on Windows 7 - the dashboard file "
                         "requirements-dashboard.txt pins pydantic<2" % metadata.version("pydantic"))
    except Exception:
        pass
    if missing or notes:
        text = ("not installed: " + ", ".join(missing)) if missing else ""
        if notes:
            text += ("; " if text else "") + "; ".join(notes)
        text += " (see INSTALL-WIN7.md section 3b)" if missing else ""
        return "Optional packages", WARNING, text
    return "Optional packages", PASS, "all optional packages are installed"


# ---------------------------------------------------------------------------
def run_checks(quick: bool = False, audio: bool = False) -> List[Result]:
    plan = [
        ("Python runtime", check_python), ("Logging", check_logging), ("Configuration", check_config),
        ("Data files", check_data_files),
        ("Memory system", check_memory_roundtrip), ("Identity & prompt", check_identity_prompt),
        ("Local model", lambda: check_local_model(quick)), ("Plugin discovery", check_plugins),
        ("TTS", lambda: check_tts(audio)), ("Microphone", lambda: check_microphone(audio)),
        ("Speech recognition", check_stt), ("Wake word", check_wake_word), ("GUI", check_gui),
        ("Safety gate", check_safety), ("Offline", check_offline), ("Packages", check_dependencies),
    ]
    results = []  # type: List[Result]
    for label, fn in plan:
        try:
            res = fn()
        except Exception as exc:  # a broken check must never stop the report
            tb = traceback.format_exc().strip().splitlines()[-1]
            res = (label, FAIL, "the check itself crashed: %s (%s)" % (exc, tb))
        results.extend(res if isinstance(res, list) else [res])
    return results


def format_report(results: List[Result]) -> str:
    width = max(len(r[0]) for r in results)
    import lily_version
    lines = ["", "Lily Self Test (%s)" % lily_version.version_string(), ""]
    for name, status, msg in results:
        lines.append("[%s] %s - %s" % (status.ljust(7), name.ljust(width), msg))
    counts = dict((s, sum(1 for r in results if r[1] == s)) for s in (PASS, WARNING, FAIL, SKIPPED))
    lines += ["", "Summary: %d PASS, %d WARNING, %d FAIL, %d SKIPPED" % (counts[PASS], counts[WARNING], counts[FAIL], counts[SKIPPED])]
    lines.append("Result: " + ("NOT HEALTHY - fix the FAIL items above." if counts[FAIL] else
                               ("OK with warnings - optional parts are limited; Lily still works." if counts[WARNING] else "ALL GOOD")))
    return "\n".join(lines)


def main(quick: bool = False, audio: bool = False) -> int:
    results = run_checks(quick=quick, audio=audio)
    print(format_report(results))
    try:
        import lily_paths
        import safe_json
        safe_json.atomic_write_json(lily_paths.log_path("selftest.json"),
                                    [{"check": n, "status": s, "message": m} for n, s, m in results],
                                    keep_backup=False)
    except Exception:
        pass
    try:
        from core import local_engine
        local_engine.shutdown()
        import voice_manager
        voice_manager.shutdown()
    except Exception:
        pass
    return 1 if any(r[1] == FAIL for r in results) else 0


if __name__ == "__main__":
    q = "--quick" in sys.argv
    a = "--audio" in sys.argv
    raise SystemExit(main(quick=q, audio=a))
