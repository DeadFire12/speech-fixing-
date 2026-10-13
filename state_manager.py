from __future__ import annotations

import threading

import lily_paths
import safe_json

STATE_FILE = "state.json"
_lock = threading.RLock()

DEFAULT_STATE = {
    "mood": "happy",
    "activity": "idle",
    "last_action": None
}


def state_path():
    return lily_paths.data_path(STATE_FILE)


def load_state():
    """Load state.json. A missing or damaged file never crashes start-up."""
    data, status, note = safe_json.load_json_safe(state_path(), lambda: dict(DEFAULT_STATE), dict)
    if note:
        print("State:", note)
    if not data:
        data = dict(DEFAULT_STATE)
    return data


def save_state(state):
    with _lock:
        safe_json.atomic_write_json(state_path(), state, indent=4)


def set_state(state, key, value):
    with _lock:
        state[key] = value
        save_state(state)


def get_state(state, key):
    return state.get(key)


def get_all_state(state):
    return state
