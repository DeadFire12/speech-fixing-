from __future__ import annotations
import json
import os
import shutil
import threading
from datetime import datetime

import lily_paths
import safe_json

MEMORY_FILE = "memory.json"

# One lock for every read-modify-write of the memory dict (GUI, voice and
# dashboard threads can all trigger remember/forget).
_memory_lock = threading.RLock()
LAST_LOAD_NOTE = ""


def memory_path():
    """Absolute path of memory.json (anchored to the project / LILY_DATA_DIR,
    never to the current working directory)."""
    return lily_paths.data_path(MEMORY_FILE)




# =========================================
# TIME
# =========================================

def now():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )



# =========================================
# CATEGORY DETECTION
# =========================================

def detect_category(key):

    key = key.lower().strip()


    if key.startswith("favorite"):

        return "preferences"


    if key.startswith("explanation"):

        return "preferences"


    if key.startswith("like"):

        return "likes"


    if key.startswith("dislike"):

        return "history"


    if key.startswith("used to like"):

        return "history"


    if key in [

        "name",
        "age",
        "birthday",
        "location"

    ]:

        return "personal"


    return "general"



# =========================================
# IMPORTANCE
# =========================================

def detect_importance(key):

    key = key.lower()


    important = [

        "name",
        "birthday",
        "location",
        "favorite game",
        "favorite color"

    ]


    if key in important:

        return "high"


    return "normal"



# =========================================
# LOAD MEMORY
# =========================================

def load_memory():
    """Load memory.json without ever destroying it.

    A damaged file is moved aside (never deleted), then restored from the last
    good backup or salvaged entry-by-entry. See safe_json.py.
    """
    global LAST_LOAD_NOTE
    data, status, note = safe_json.load_json_safe(memory_path(), dict, dict)
    LAST_LOAD_NOTE = note
    if note:
        print("Memory:", note)

    upgraded = {}
    for key, value in data.items():
        if isinstance(value, dict):
            upgraded[key] = value
        else:
            upgraded[key] = {
                "value": str(value),
                "created": now(),
                "updated": now(),
                "category": detect_category(key),
                "confirmed": True,
                "confidence": 100,
                "importance": detect_importance(key)
            }
    return upgraded


# =========================================
# SAVE MEMORY
# =========================================

def save_memory(memory):
    """Atomic save (temp file + replace); the previous good file is kept as
    memory.json.bak so one bad write can never wipe everything."""
    with _memory_lock:
        safe_json.atomic_write_json(
            memory_path(), memory, indent=4, ensure_ascii=False, sort_keys=True
        )


# =========================================
# SEARCH MEMORY
# =========================================

def search_memory(memory, query):
    """Return {key: entry} whose key or value contains the query text."""
    q = str(query).lower().strip()
    if not q:
        return {}
    found = {}
    for key, entry in memory.items():
        value = entry.get("value", "") if isinstance(entry, dict) else str(entry)
        if q in str(key).lower() or q in str(value).lower():
            found[key] = entry
    return found


# =========================================
# NORMALIZE KEY
# =========================================

def normalize_key(key):

    return key.lower().strip()



# =========================================
# REMEMBER
# =========================================

def remember(memory, key, value):
    with _memory_lock:
        return _remember_unlocked(memory, key, value)


def _remember_unlocked(memory, key, value):

    key = normalize_key(key)

    value = value.strip()

    current = now()



    if key in memory:


        old_value = memory[key].get(
            "value",
            ""
        )


        if old_value.lower() == value.lower():

            return



        created = memory[key].get(
            "created",
            current
        )


    else:

        created = current



    memory[key] = {


        "value": value,


        "created": created,


        "updated": current,


        "category":
            detect_category(key),


        "confirmed":
            True,


        "confidence":
            100,


        "importance":
            detect_importance(key)

    }



    save_memory(memory)



# =========================================
# FIND MEMORY
# =========================================

def find_memory(memory, key):

    key = normalize_key(key)

    return memory.get(key)



# =========================================
# DELETE MEMORY
# =========================================

def forget_memory(memory, key):

    key = normalize_key(key)

    with _memory_lock:
        if key in memory:
            del memory[key]
            save_memory(memory)
            return True

    return False



# =========================================
# DELETE ALL
# =========================================

def forget_all(memory):
    with _memory_lock:
        # explicit user request, but still keep a timestamped safety copy
        try:
            if os.path.exists(memory_path()):
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copyfile(memory_path(), memory_path() + ".before-forget-" + stamp)
        except OSError:
            pass
        memory.clear()
        save_memory(memory)



# =========================================
# CATEGORY SEARCH
# =========================================

def get_memories_by_category(memory, category):

    results = {}


    for key, data in memory.items():

        if data.get("category") == category:

            results[key] = data



    return results



# =========================================
# ALL CATEGORIES
# =========================================

def get_all_categories(memory):

    categories = set()


    for data in memory.values():

        categories.add(

            data.get(
                "category",
                "general"
            )

        )


    return list(categories)