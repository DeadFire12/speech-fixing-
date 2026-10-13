"""Unified action/plugin bridge for Lily + Mark-LIV.

Lily's original deterministic tools stay authoritative for overlapping names.
Mark-LIV actions are then available through the same hub, and Mark-LIV plugins
remain available through the original plugin registry.
"""
from __future__ import annotations

import threading
from pathlib import Path

import safety
from tool_registry import create_tool_manager

from core.action_loader import ActionRegistry, discover_actions
from core.plugin_loader import PluginRegistry, discover_plugins


class LilyActionHub:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent)
        self.lily_tools = create_tool_manager()
        try:
            self.actions = discover_actions(self.base_dir / "actions", reserved_names=set(self.lily_tools.tools))
        except Exception as e:
            print("[Hub] action discovery failed:", e)
            self.actions = ActionRegistry({}, print)
        try:
            self.plugins = discover_plugins(self.base_dir / "plugins", self.actions.names() | set(self.lily_tools.tools))
        except Exception as e:
            print("[Hub] plugin discovery failed:", e)
            self.plugins = PluginRegistry({}, print)
        self._lock = threading.RLock()

    def action_ui(self):
        """Return active Mark-LIV action declarations in the UI-friendly shape."""
        out = []
        for item in self.actions.get_tool_declarations():
            row = dict(item)
            row["source"] = "Mark-LIV"
            row["valid"] = True
            out.append(row)
        return out

    def list_all(self):
        out = []
        for x in self.lily_tools.list_tools():
            out.append({"name": x["name"], "description": x["description"], "source": "Lily", "valid": True,
                        "safety": safety.tier_of_tool(x["name"])})
        for row in self.action_ui():
            row["safety"] = safety.classify_action(row.get("name", ""), {})
            out.append(row)
        for x in self.plugins.list_for_ui():
            y = dict(x)
            y["source"] = "Plugin"
            out.append(y)
        return out

    def plugin_ui(self):
        return self.plugins.list_for_ui()

    def plugin_settings(self):
        return self.plugins.settings_schemas()

    def run_mark(self, name, params):
        """Run a Mark-LIV action. DESTRUCTIVE ones are not run directly: the caller gets a
        confirmation question and the action only runs after the user confirms (safety.py)."""
        params = params or {}
        if safety.classify_action(name, params) == safety.DESTRUCTIVE:
            summary = ", ".join("%s=%s" % (k, str(v)[:40]) for k, v in list(params.items())[:3])
            return safety.get_gate().request(
                "Run '%s'%s?" % (name, (" (" + summary + ")") if summary else ""),
                lambda n=name, p=dict(params): self._run_mark_now(n, p),
                detail="This can change or remove things on your computer.")
        return self._run_mark_now(name, params)

    def _run_mark_now(self, name, params):
        with self._lock:
            return self.actions.run(name, params or {}, ctx={"assistant": "Lily", "local_mode": True})

    def run_plugin(self, name, params=None, player=None):
        with self._lock:
            return self.plugins.run(name, params or {}, player=player, session_memory=None)

    def run(self, name, *args, **kwargs):
        if name in self.lily_tools.tools:
            return self.lily_tools.run(name, *args, **kwargs)
        params = kwargs.get("parameters") or (args[0] if args and isinstance(args[0], dict) else {})
        if self.actions.has(name):
            result = self.run_mark(name, params)
        else:
            result = self.run_plugin(name, params)
        return {"success": True, "result": result}


ACTION_ALIASES = {
    # Mark-LIV-specific routes. Lily's own generic file/app/search tools keep
    # priority for ambiguous commands such as "search my files" or "open X".
    "web_search": ["web search ", "search the web ", "search online ", "look up online "],
    "weather_report": ["weather in ", "forecast for ", "temperature in "],
    "youtube_video": ["youtube ", "play on youtube ", "play a video on youtube "],
    "browser_control": ["browser control ", "use the browser ", "browse "],
    "computer_control": ["click ", "type on screen ", "press key ", "hotkey ", "scroll "],
    "computer_settings": ["volume ", "brightness ", "mute ", "wifi ", "fullscreen ", "lock screen"],
    "code_helper": ["write code ", "fix code ", "debug code ", "optimize code "],
    "dev_agent": ["build a project ", "create a project ", "generate a project"],
    "desktop_control": ["organize desktop ", "set wallpaper ", "desktop control "],
    "flight_finder": ["find flights ", "flights from ", "book flight"],
    "send_message": ["send message ", "send a message ", "send whatsapp ", "whatsapp "],
}



def simple_route(text):
    t = (text or "").strip()
    low = t.lower()
    for name, aliases in ACTION_ALIASES.items():
        for alias in aliases:
            if low.startswith(alias):
                rest = t[len(alias):].strip()
                if name == "open_app":
                    return name, {"app_name": rest}
                if name == "web_search":
                    return name, {"query": rest}
                if name == "weather_report":
                    return name, {"city": rest}
                if name == "youtube_video":
                    return name, {"action": "play", "query": rest}
                if name == "reminder":
                    return None, None
                if name == "computer_settings":
                    # its own parser needs the whole phrase ("volume 40"), not just the tail ("40")
                    return name, {"action": t}
                return name, {"action": rest or t}
    return None, None
