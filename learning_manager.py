from __future__ import annotations

import threading

import lily_paths
import safe_json

LEARNING_FILE = "learning.json"
_lock = threading.RLock()


def learning_path():
    return lily_paths.data_path(LEARNING_FILE)


def load_learning():
    """Load learning.json; a damaged file is preserved and recovered, never wiped."""
    data, status, note = safe_json.load_json_safe(learning_path(), dict, dict)
    if note:
        print("Learning:", note)
    return data


def save_learning(data):
    with _lock:
        safe_json.atomic_write_json(learning_path(), data, indent=4, ensure_ascii=False)


def learn(data, key, value):
    key = key.lower().strip()
    value = value.strip()

    with _lock:
        if key in data:
            data[key]["value"] = value
            data[key]["times_used"] = data[key].get("times_used", 0) + 1
            confidence = data[key].get("confidence", 0)
            data[key]["confidence"] = min(confidence + 10, 100)
        else:
            data[key] = {
                "value": value,
                "confidence": 50,
                "times_used": 1
            }
        save_learning(data)


def find_learning(data, key):
    key = key.lower().strip()
    return data.get(key)


def get_all_learning(data):
    return data
