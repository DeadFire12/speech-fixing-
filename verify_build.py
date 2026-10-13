"""Offline integrity checker for the merged Lily + Mark-LIV build.

Run on the target Windows machine with Python 3.8:
    py verify_build.py

This script does not contact a cloud API and does not require an API key.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "Lily.py", "main.py", "ui.py", "lily_runtime.py", "lily_gui.py",
    "lily_action_hub.py", "core/local_engine.py", "core/avatar.py",
    "core/face_model.obj", "actions", "plugins", "dashboard/server.py",
    "memory.json", "goals.json", "learning.json", "state.json",
    "config/local_settings.json", "config/api_keys.json",
]


def fail(msg):
    print("FAIL:", msg)
    return False


def main():
    ok = True
    print("LILY + MARK-LIV LOCAL BUILD CHECK")
    print("Root:", ROOT)
    print("Python:", sys.version.replace("\n", " "))

    if sys.version_info[:2] != (3, 8):
        print("WARN: This package was prepared for Python 3.8.x.")

    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            ok = fail("Missing required path: " + rel) and ok

    # Static Python syntax check.
    py_files = [p for p in ROOT.rglob("*.py") if "original_sources" not in p.parts and "__pycache__" not in p.parts]
    syntax_errors = []
    for p in py_files:
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
        except Exception as e:
            syntax_errors.append((p, e))
    print("Python files checked:", len(py_files))
    if syntax_errors:
        ok = False
        for p, e in syntax_errors:
            print("FAIL: syntax", p, e)
    else:
        print("OK: all merged Python files parse")

    # Local-only config check.
    cfg = json.loads((ROOT / "config" / "api_keys.json").read_text(encoding="utf-8"))
    forbidden_keys = [k for k in cfg if "api" in k.lower() and "local" not in k.lower()]
    if forbidden_keys:
        ok = False
        print("FAIL: cloud-style key fields present:", forbidden_keys)
    else:
        print("OK: config contains no API key field")

    # Local engine paths and tuning.
    settings = json.loads((ROOT / "config" / "local_settings.json").read_text(encoding="utf-8"))
    print("Local threads:", settings.get("threads"))
    print("Local model:", settings.get("model_path"))
    print("Local llama:", settings.get("llama_path"))
    if int(settings.get("threads", 0)) != 3:
        print("WARN: expected tested Win7 default thread count 3")

    # UI source guard: no accidental PyQt6 import remains in adapted files.
    ui_text = (ROOT / "ui.py").read_text(encoding="utf-8", errors="replace")
    avatar_text = (ROOT / "core" / "avatar.py").read_text(encoding="utf-8", errors="replace")
    if "PyQt6" in ui_text or "PyQt6" in avatar_text:
        ok = False
        print("FAIL: PyQt6 reference remains in adapted UI/avatar")
    else:
        print("OK: adapted UI/avatar use PyQt5")

    # Secret-pattern scan over shipped runtime/config files (original_sources is
    # intentionally excluded because it is an audit copy, not an active config).
    secret_patterns = [
        re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    ]
    secret_hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or "original_sources" in p.parts or "__pycache__" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(rx.search(text) for rx in secret_patterns):
            secret_hits.append(p)
    if secret_hits:
        ok = False
        print("FAIL: possible secret material in:", secret_hits)
    else:
        print("OK: no common API-key patterns found")

    # Import core non-UI bridge and count discovered tools/actions.
    try:
        from lily_action_hub import LilyActionHub
        hub = LilyActionHub(ROOT)
        print("Lily deterministic tools:", len(hub.lily_tools.tools))
        print("Mark-LIV actions active:", len(hub.action_ui()))
        print("Plugins active:", len([x for x in hub.plugin_ui() if x.get("valid")]))
        if len(hub.lily_tools.tools) < 20 or len(hub.action_ui()) < 10:
            print("WARN: unusually low discovered capability count")
    except Exception as e:
        ok = False
        print("FAIL: action/plugin bridge import:", type(e).__name__, e)

    try:
        import core.local_engine  # noqa: F401
        import core.gemini       # noqa: F401
        import lily_runtime      # noqa: F401
        import dashboard.server  # noqa: F401
        print("OK: local engine, Gemini-shim, Lily runtime, dashboard imports")
    except Exception as e:
        ok = False
        print("FAIL: core imports:", type(e).__name__, e)

    try:
        import PyQt5  # noqa: F401
        import ui as _ui  # noqa: F401
        print("OK: PyQt5 is installed and ui.py imports")
    except Exception as e:
        print("WARN: PyQt5/UI runtime check not available here:", type(e).__name__, e)
        print("      Install a Win7-compatible PyQt5 5.15.x build on the target laptop.")

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
