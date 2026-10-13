"""Atomic, recoverable JSON persistence.

Problems this fixes (all verified in the audit):
  * save used open(path, "w") -> a crash mid-write left a truncated file;
  * load returned {} on ANY error, and the next save then overwrote the
    damaged file with that empty dict -> every stored memory silently lost;
  * state.json / goals.json had no error handling at all (corruption crashed
    start-up).

Behaviour now:
  * atomic_write_json(): serialise first, write to a temp file in the same
    folder, flush + fsync, keep the previous good file as "<name>.bak", then
    os.replace(). A failure at any point leaves the old file untouched.
  * load_json_safe(): if the file is damaged it is MOVED (never deleted) to
    "<name>.corrupt-<timestamp>", then recovery is attempted from "<name>.bak"
    and finally by salvaging the complete entries from the damaged text.
    The original bytes are therefore always preserved.

Standard library only; Python 3.8 compatible.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional, Tuple

_locks = {}  # type: dict
_locks_guard = threading.Lock()
_mode = threading.local()   # read-only mode is per THREAD, so a status check never blocks another thread's saves

OK = "ok"
MISSING = "missing"
RECOVERED_BACKUP = "recovered_backup"
RECOVERED_SALVAGE = "recovered_salvage"
RESET = "reset_default"


class read_only(object):
    """Context manager: inside it, THIS thread never repairs, moves or writes any JSON file.

    Used by the status report so that looking at Lily's health can never change it: a damaged
    file is reported (and defaults are returned) instead of being quarantined/recovered, and
    writes are skipped. Other threads are unaffected."""

    def __enter__(self):
        _mode.depth = getattr(_mode, "depth", 0) + 1
        return self

    def __exit__(self, *exc):
        _mode.depth = max(0, getattr(_mode, "depth", 1) - 1)
        return False


def is_read_only() -> bool:
    return getattr(_mode, "depth", 0) > 0


def get_lock(path: str) -> "threading.RLock":
    key = os.path.normcase(os.path.abspath(str(path)))
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


def _read_text(path: str) -> Tuple[str, bool]:
    """Return (text, clean_utf8). Invalid bytes are replaced and flagged."""
    with open(path, "rb") as fh:       # closed immediately: an open handle can block os.replace on Windows
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig"), True
    except UnicodeDecodeError:
        return raw.decode("utf-8-sig", errors="replace"), False


def _type_ok(data: Any, expected_type) -> bool:
    return expected_type is None or isinstance(data, expected_type)


def salvage_json(text: str, expected_type) -> Any:
    """Recover every *complete* top-level entry from truncated/damaged JSON.

    Returns a dict (for objects) or list (for arrays); empty when nothing is
    recoverable. Never raises; whatever was parsed before the damage is kept.
    """
    dec = json.JSONDecoder()
    s = text.lstrip("\ufeff")
    n = len(s)
    empty = [] if expected_type is list else {}

    def skip_ws(k):
        while k < n and s[k] in " \t\r\n":
            k += 1
        return k

    i = skip_ws(0)
    if i >= n:
        return empty
    out_dict = {}
    out_list = []
    first = s[i]
    try:
        if first == "{" and expected_type is not list:
            i += 1
            while True:
                i = skip_ws(i)
                if i >= n or s[i] == "}":
                    break
                key, i = dec.raw_decode(s, i)
                if not isinstance(key, str):
                    break
                i = skip_ws(i)
                if i >= n or s[i] != ":":
                    break
                i = skip_ws(i + 1)
                value, i = dec.raw_decode(s, i)
                out_dict[key] = value
                i = skip_ws(i)
                if i < n and s[i] == ",":
                    i += 1
            return out_dict
        if first == "[" and expected_type is not dict:
            i += 1
            while True:
                i = skip_ws(i)
                if i >= n or s[i] == "]":
                    break
                value, i = dec.raw_decode(s, i)
                out_list.append(value)
                i = skip_ws(i)
                if i < n and s[i] == ",":
                    i += 1
            return out_list
    except Exception:
        pass
    if first == "[" and expected_type is not dict:
        return out_list
    if first == "{" and expected_type is not list:
        return out_dict
    return empty


def _quarantine(path: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = "%s.corrupt-%s" % (path, stamp)
    k = 1
    while os.path.exists(target):
        k += 1
        target = "%s.corrupt-%s-%d" % (path, stamp, k)
    os.replace(path, target)
    return target


def load_json_safe(path: str, default_factory: Callable[[], Any],
                   expected_type=None, repair: bool = True) -> Tuple[Any, str, str]:
    """Load JSON. Returns (data, status, note).

    status is one of OK / MISSING / RECOVERED_BACKUP / RECOVERED_SALVAGE / RESET.
    note is a human-readable explanation (empty when status is OK/MISSING).
    """
    path = str(path)
    if is_read_only():
        repair = False
    with get_lock(path):
        if not os.path.exists(path):
            return default_factory(), MISSING, ""
        try:
            text, clean = _read_text(path)
            data = json.loads(text)
            if clean and _type_ok(data, expected_type):
                return data, OK, ""
            problem = "wrong data type" if clean else "invalid UTF-8"
        except (ValueError, OSError) as exc:
            if isinstance(exc, OSError):  # unreadable (locked/permissions): do not touch it
                return default_factory(), MISSING, "could not read %s: %s" % (os.path.basename(path), exc)
            problem = str(exc)
            text = ""
            try:
                text = _read_text(path)[0]
            except OSError:
                pass
        if not repair:
            return default_factory(), RESET, "damaged file left in place: %s" % problem
        try:
            damaged_text = _read_text(path)[0]
        except OSError:
            damaged_text = ""
        moved = _quarantine(path)
        base = os.path.basename(path)
        note = "%s was damaged (%s); original preserved as %s" % (base, problem, os.path.basename(moved))
        # Two sources of recovery, merged so the most data survives:
        #  * the last known good copy (.bak) - complete, but one save behind;
        #  * complete entries salvaged from the damaged text - newer, but possibly partial.
        backup_data = None
        bak = path + ".bak"
        if os.path.exists(bak):
            try:
                candidate = json.loads(_read_text(bak)[0])
                if _type_ok(candidate, expected_type):
                    backup_data = candidate
            except Exception:
                backup_data = None
        salvaged = salvage_json(damaged_text, expected_type)

        if backup_data is not None:
            if isinstance(backup_data, dict) and isinstance(salvaged, dict):
                merged = dict(backup_data)
                merged.update(salvaged)               # salvaged entries are complete and newer
            elif isinstance(backup_data, list) and isinstance(salvaged, list) and len(salvaged) > len(backup_data):
                merged = salvaged
            else:
                merged = backup_data
            atomic_write_json(path, merged, keep_backup=False)
            extra = " (+ %d newer entr%s salvaged)" % (len(salvaged), "y" if len(salvaged) == 1 else "ies") \
                if salvaged and isinstance(salvaged, dict) else ""
            return merged, RECOVERED_BACKUP, note + "; restored from the last good backup" + extra
        if salvaged:
            atomic_write_json(path, salvaged, keep_backup=False)
            return salvaged, RECOVERED_SALVAGE, note + "; recovered %d entr%s" % (
                len(salvaged), "y" if len(salvaged) == 1 else "ies")
        return default_factory(), RESET, note + "; nothing could be recovered, starting empty"

def atomic_write_json(path: str, data: Any, indent: int = 4, ensure_ascii: bool = False,
                      sort_keys: bool = False, keep_backup: bool = True) -> None:
    """Serialise, then replace the file atomically. Never leaves a partial file."""
    path = str(path)
    if is_read_only():
        return                       # read-only mode (status report): never write
    payload = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
    folder = os.path.dirname(os.path.abspath(path))
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
    with get_lock(path):
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            if keep_backup and os.path.exists(path):
                try:
                    json.loads(_read_text(path)[0])  # only back up a file that is itself valid
                    shutil.copyfile(path, path + ".bak")
                except Exception:
                    pass
            last_exc = None
            for attempt in range(6):  # antivirus/indexers can briefly lock files on Windows
                try:
                    os.replace(tmp, path)
                    last_exc = None
                    break
                except PermissionError as exc:
                    last_exc = exc
                    time.sleep(0.05 * (attempt + 1))
            if last_exc is not None:
                raise last_exc
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
