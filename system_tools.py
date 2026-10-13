"""Process inspection helpers built only on Windows 7 tools (tasklist/taskkill).

No PowerShell, no newer APIs. psutil is not required.
"""
from __future__ import annotations

import csv
import io
import re
import subprocess
import sys

import lily_log
from typing import Callable, List, Optional, Tuple

_run = subprocess.run  # replaced in tests
_log = lily_log.get_logger("system")
IS_WINDOWS = sys.platform.startswith("win")


def parse_tasklist_csv(text: str) -> List[Tuple[str, int, int]]:
    """Parse `tasklist /FO CSV /NH` output into (image_name, pid, mem_kb)."""
    rows = []
    for rec in csv.reader(io.StringIO(text or "")):
        if len(rec) < 5 or not rec[0].strip():
            continue
        try:
            pid = int(rec[1])
        except ValueError:
            continue
        mem = re.sub(r"[^\d]", "", rec[4])
        rows.append((rec[0].strip(), pid, int(mem) if mem else 0))
    return rows


def _decode(data) -> str:
    if not isinstance(data, bytes):
        return str(data)
    for enc in ("mbcs", "utf-8", "cp1252"):  # tasklist writes the console's ANSI code page
        try:
            return data.decode(enc, errors="ignore")
        except LookupError:
            continue
    return data.decode("latin-1", errors="ignore")


def running_processes() -> List[Tuple[str, int, int]]:
    if not IS_WINDOWS:
        return []
    result = _run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, timeout=20)
    return parse_tasklist_csv(_decode(result.stdout))


def top_by_memory(limit: int = 12) -> List[Tuple[str, int, int]]:
    merged = {}
    for name, _pid, mem in running_processes():
        merged[name] = merged.get(name, 0) + mem
    merged.pop("System Idle Process", None)
    merged.pop("System", None)
    ranked = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [(n, 0, m) for n, m in ranked]


def format_process_list(rows: List[Tuple[str, int, int]]) -> str:
    if not rows:
        return "I couldn't read the process list on this system."
    lines = ["These programs are using the most memory:"]
    for name, _pid, mem in rows:
        lines.append("- %s: %.0f MB" % (name, mem / 1024.0))
    return "\n".join(lines)


def _exe_name(name: str) -> str:
    n = str(name or "").strip().strip('"')
    n = re.sub(r"\s+", " ", n)
    return n if n.lower().endswith(".exe") else n + ".exe"


def find_matches(name: str, procs: Optional[List[Tuple[str, int, int]]] = None) -> List[str]:
    """Distinct image names matching what the user said ("chrome" -> chrome.exe)."""
    wanted = re.sub(r"[^a-z0-9]", "", str(name or "").lower().replace(".exe", ""))
    if len(wanted) < 2:
        return []
    procs = running_processes() if procs is None else procs
    exact, partial = [], []
    for image, _pid, _mem in procs:
        key = re.sub(r"[^a-z0-9]", "", image.lower().replace(".exe", ""))
        if key == wanted:
            exact.append(image)
        elif wanted in key and len(wanted) >= 4:
            partial.append(image)
    seen, out = set(), []
    for image in (exact or partial):
        if image.lower() not in seen:
            seen.add(image.lower())
            out.append(image)
    return out


def close_process(image: str, force: bool = False) -> Tuple[bool, str]:
    """taskkill by image name. Without /F the program may ask to save its work."""
    if not IS_WINDOWS:
        return False, "Closing programs is only supported on Windows."
    cmd = ["taskkill", "/IM", _exe_name(image)] + (["/F"] if force else [])
    result = _run(cmd, capture_output=True, timeout=20)
    _log.info("taskkill %s -> exit code %s", " ".join(cmd[1:]), result.returncode)
    if result.returncode == 0:
        return True, "I asked %s to close%s." % (image, " (forced)" if force else "")
    return False, ("%s didn't close. It may be waiting for you to save, or need a forced close." % image)
