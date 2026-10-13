"""Lily settings (config/local_settings.json) with safe loading and defaults.

Resolution order for every setting: environment variable (LILY_<KEY>, where
noted) > config/local_settings.json > built-in default. Nothing in here is
machine specific: llama.cpp and the model are located from the settings file,
then by looking inside the project folder, then on PATH (see core/local_engine).
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict

import lily_paths
import safe_json

DEFAULTS = {
    # --- identity ---------------------------------------------------------
    "assistant_name": "Lily",
    "user_name": "",
    # --- local model ------------------------------------------------------
    "llama_path": "",
    "model_path": "",
    "threads": 3,
    "context": 2048,
    "timeout": 120,
    "max_tokens": 256,
    "chat_max_tokens": 128,
    "chat_template": "chatml",
    "no_conversation_flag": "auto",   # auto | on | off  (-no-cnv for newer llama-cli builds)
    "extra_llama_args": [],
    # --- voice ------------------------------------------------------------
    "voice_input_enabled": True,
    "tts_enabled": True,
    "tts_rate": 175,
    "tts_volume": 1.0,
    "stt_backend": "auto",            # auto | vosk | google | none
    "vosk_model_path": "",
    "mic_sample_rates": [None, 16000, 44100],
    "mic_calibration_seconds": 0.6,
    # Optional emergency override when Windows exposes the same microphone
    # under several host APIs. Set only to an input index verified by
    # mic_level_test.py; device indices can change after hardware changes.
    "mic_device_index": None,
    "wake_threshold": 0.5,
    "wake_cooldown_seconds": 2.0,
    "wake_pip_spec": ["onnxruntime==1.10.0", "openwakeword==0.5.1"],
    # --- safety -----------------------------------------------------------
    "confirm_ttl_seconds": 60,
    "allow_remote_confirmation": False,
    "shutdown_delay_seconds": 30,
    "dashboard_auto_firewall": False,
    # --- launching applications (app_launcher.py) -----------------------------
    "launch_allow_shells": False,         # allow opening cmd/powershell (still with no arguments)
    "launch_start_menu_typing": False,    # old fallback: type the name into the Start menu (types into the focused window)
    # --- logging ----------------------------------------------------------
    "log_level": "INFO",              # DEBUG | INFO | WARNING | ERROR
    "log_max_bytes": 1000000,
    "log_backup_count": 3,
}  # type: Dict[str, Any]

_lock = threading.RLock()
_cache = {"stamp": None, "data": None}  # type: dict
LAST_NOTE = ""


def settings_path() -> str:
    return lily_paths.config_path("local_settings.json")


def load() -> Dict[str, Any]:
    """Return the merged settings dict (defaults + file). Never raises."""
    global LAST_NOTE
    path = settings_path()
    with _lock:
        try:
            stamp = os.stat(path).st_mtime if os.path.exists(path) else None
        except OSError:
            stamp = None
        if _cache["data"] is not None and _cache["stamp"] == stamp and _cache.get("path") == path:
            return dict(_cache["data"])
        data, status, note = safe_json.load_json_safe(path, dict, dict)
        if note:
            LAST_NOTE = note
            try:
                print("Config:", note)
            except Exception:
                pass
        merged = dict(DEFAULTS)
        if isinstance(data, dict):
            merged.update(data)
        try:
            stamp = os.stat(path).st_mtime if os.path.exists(path) else None
        except OSError:
            stamp = None
        _cache.update({"stamp": stamp, "data": merged, "path": path})
        return dict(merged)


def get(key: str, default: Any = None) -> Any:
    value = load().get(key, DEFAULTS.get(key, default) if default is None else default)
    return value


def get_bool(key: str, default: bool = False) -> bool:
    v = load().get(key, default)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def get_number(key: str, default: float) -> float:
    try:
        return float(load().get(key, default))
    except (TypeError, ValueError):
        return float(default)


def save(key: str, value: Any) -> None:
    """Atomically update a single key, preserving everything else."""
    path = settings_path()
    with _lock:
        data, _status, _note = safe_json.load_json_safe(path, dict, dict)
        if not isinstance(data, dict):
            data = {}
        data[key] = value
        safe_json.atomic_write_json(path, data, indent=4)
        _cache["data"] = None


def invalidate() -> None:
    with _lock:
        _cache["data"] = None
