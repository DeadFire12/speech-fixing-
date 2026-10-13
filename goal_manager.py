from __future__ import annotations

import threading

import lily_paths
import safe_json

GOAL_FILE = "goals.json"
_lock = threading.RLock()


def goals_path():
    return lily_paths.data_path(GOAL_FILE)


def load_goals():
    """Load goals.json. A missing or damaged file never crashes start-up."""
    data, status, note = safe_json.load_json_safe(goals_path(), list, list)
    if note:
        print("Goals:", note)
    return [g for g in data if isinstance(g, dict) and "task" in g]


def save_goals(goals):
    with _lock:
        safe_json.atomic_write_json(goals_path(), goals, indent=4)


def add_goal(goals, text):
    with _lock:
        goals.append({
            "task": text,
            "completed": False
        })
        save_goals(goals)


def complete_goal(goals, task):
    task = task.lower().strip()
    with _lock:
        for goal in goals:
            if goal["task"].lower().strip() == task:
                goal["completed"] = True
                save_goals(goals)  # previously never persisted
                return True
    return False


def get_goals(goals):
    return goals
