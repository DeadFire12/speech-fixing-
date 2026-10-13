"""Practical desktop commands that were missing (audit Part 4C), kept out of the
giant process_text() so they stay small and testable.

Commands (all Windows 7 safe: tasklist/taskkill/webbrowser only):
    status / health check               READ_ONLY (version, model, voice, tools, uptime, log)
    list processes / what's running     READ_ONLY
    open <website or url>               REVERSIBLE
    close <app> / kill <app>            DESTRUCTIVE -> asks for confirmation first
    cancel shutdown / cancel restart    cancels a scheduled shutdown (shutdown /a)

handle() returns the reply text, or None when the message is not one of these
(so normal processing continues).
"""
from __future__ import annotations

import re
import webbrowser
from typing import Optional

import safety
import system_actions
import system_tools

_open_browser = webbrowser.open  # replaced in tests

_STATUS = re.compile(r"^(?:please )?(?:show |give me |what is |what s )?(?:the )?(?:lily )?"
                     r"(?:status|health|health check|system status|status report)$")
_CANCEL_POWER = re.compile(r"^(?:please )?(?:cancel|abort|stop) (?:the )?(?:pending |scheduled )?"
                           r"(?:shutdown|shut down|restart|reboot)$")
_LIST_PROC = re.compile(
    r"^(?:please )?(?:list|show)(?: me)?(?: all| the| my)?(?: running)? (?:processes|programs|apps|applications|tasks)$|"
    r"^what(?: is| s|s| are) running(?: right now| on my computer)?$|^what programs are running$|"
    r"^running (?:processes|programs|apps)$|^what is using (?:my )?(?:memory|ram)$|^top processes$")
_CLOSE = re.compile(
    r"^(?:please )?(?P<verb>force close|force quit|kill|terminate|close|quit|end)"
    r"(?: the)?(?: (?:app|program|application|process|window))? (?P<name>[a-z0-9][a-z0-9 ._-]{1,38})$")
_OPEN = re.compile(r"^(?:please )?(?:open|go to|visit|browse to|take me to)(?: the)?"
                   r"(?: (?:website|site|url|link|web page|webpage))? (?P<url>\S+)$", re.IGNORECASE)
_TLDS = {"com", "org", "net", "io", "edu", "gov", "co", "uk", "de", "fr", "es", "it", "nl", "ru", "jp", "cn",
         "in", "au", "ca", "app", "dev", "info", "me", "tv", "ai", "gg", "xyz", "us", "eu", "ch", "se", "no",
         "fi", "pl", "br", "mx", "tr", "ir"}
_NOT_APPS = {"it", "this", "that", "everything", "all", "them", "window", "tab", "door", "conversation",
             "chat", "session", "the", "up", "down", "lily", "yourself", "you"}


def _norm(text: str) -> str:
    t = re.sub(r"[^a-z0-9' ._-]+", " ", str(text or "").lower().replace("\u2019", "'"))
    t = t.replace("'", " ")
    return re.sub(r"\s+", " ", t).strip(" .")


def _as_url(token: str) -> Optional[str]:
    tok = token.strip().strip("<>\"'").rstrip(".,!?")
    if re.match(r"^https?://\S+\.\S+", tok, re.IGNORECASE):
        return tok
    m = re.match(r"^(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)*\.([a-z]{2,10}))(/\S*)?$", tok, re.IGNORECASE)
    if m and m.group(2).lower() in _TLDS:
        return "https://" + tok
    return None


def handle(text: str, origin: str = "local", gate=None) -> Optional[str]:
    gate = gate or safety.get_gate()
    n = _norm(text)
    if not n:
        return None

    if _STATUS.match(n):
        try:
            import lily_status
            return lily_status.format_status(lily_status.collect(in_process=True, deep=False))
        except Exception as exc:
            return "I couldn't build the status report: %s" % exc

    if _CANCEL_POWER.match(n):
        return system_actions.cancel_power()

    if _LIST_PROC.match(n):
        try:
            return system_tools.format_process_list(system_tools.top_by_memory(12))
        except Exception as exc:
            return "I couldn't read the process list: %s" % exc

    m = _CLOSE.match(n)
    if m:
        verb, name = m.group("verb"), m.group("name").strip()
        if name in _NOT_APPS:
            return None
        force = verb in ("force close", "force quit", "kill", "terminate")
        try:
            matches = system_tools.find_matches(name)
        except Exception:
            matches = []
        if not matches:
            # "close the door" must stay normal chat; an explicit kill/force request deserves an answer
            return ("I couldn't find a running program called %s." % name) if force else None
        if len(matches) > 1:
            return "I found several programs that match (%s). Please tell me the exact name." % ", ".join(matches[:5])
        image = matches[0]
        if safety.protected_process(image):
            return "I won't close %s, because Windows (or Lily) needs it to keep running." % image
        detail = "This forces it to stop and unsaved work will be lost." if force else \
                 "Unsaved work in it may be lost."
        return gate.request("Close %s?" % image, lambda i=image, f=force: system_tools.close_process(i, f)[1],
                            detail=detail)

    m = _OPEN.match(str(text or "").strip())
    if m:
        url = _as_url(m.group("url"))
        if url:
            try:
                _open_browser(url)
            except Exception as exc:
                return "I couldn't open your browser: %s" % exc
            return "Opening %s in your browser." % url
    return None
