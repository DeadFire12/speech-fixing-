"""Safe application launching: no shell, no arguments, validated names, paths and URLs.

Why this exists (found in review of 1.1.0): `computer_manager.launch_program` and
`actions/open_app.py` handed the user's text to `subprocess.Popen(..., shell=True)`. A blocklist of
characters cannot make that safe - `cmd /c shutdown /s /t 0` contains none of the "dangerous"
characters yet runs a shutdown. `open_app` had four such sinks (shell launch, `start <name>`, a typed
Start-menu search and a fuzzy alias match).

This module is now the ONLY way those features start something. It accepts exactly three kinds of
input and rejects everything else before any process is created:

  name  a plain application name ("notepad", "Visual Studio Code"): letters, digits, spaces, dots,
        hyphens, underscores, plus signs and brackets only; no switches; resolved to a real file via
        PATH, the Windows "App Paths" registry key, or a Start-menu shortcut, then started as
        Popen([file]) - no shell, no arguments.
  path  an absolute path to an existing .exe or .lnk (no UNC paths, no "..", no %VARIABLES%).
  document  an absolute path to an existing document or folder; it is opened with its default
        application (like double-clicking it). Scripts, installers and registry files are refused.
  url   an http:// or https:// address, opened through the browser (never through a shell).

Never launched, even by name: command shells and script hosts (cmd, powershell, wscript, ...), and
system-administration tools (shutdown, taskkill, reg, format, diskpart, schtasks, net, wmic ...).
Shells can be allowed explicitly with `launch_allow_shells: true`; they still start with no arguments.

Standard library only (winreg is imported lazily on Windows); Python 3.8 / Windows 7 compatible.
"""
from __future__ import annotations

import ntpath
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from collections import namedtuple
from typing import List, Optional, Tuple

import lily_config
import lily_log
import lily_paths

_log = lily_log.get_logger("launcher")

IS_WINDOWS = sys.platform.startswith("win")

# Hooks the tests replace; production code never touches them.
_popen = subprocess.Popen
_startfile = getattr(os, "startfile", None)
_open_url_fn = webbrowser.open
_isfile = os.path.isfile
_isdir = os.path.isdir
_which = shutil.which

LaunchResult = namedtuple("LaunchResult", "success message kind target")

# A plain name: starts with a letter/digit, then letters, digits, space . _ + ( ) -
NAME_RE = re.compile(r"^\w[\w ._+()\-]{0,63}$")
# "notepad -x", "app /c": a switch-looking token. (A hyphen INSIDE a word is fine: "7-Zip".)
SWITCH_RE = re.compile(r"(?:^|\s)[/\-]{1,2}\w")

ALLOWED_PATH_EXTENSIONS = (".exe", ".lnk")
# .cmd/.bat are only accepted when PATH resolution finds one of these well-known launcher shims
TRUSTED_SHIMS = frozenset(["code"])
ALLOWED_URIS = frozenset(["ms-settings:"])      # fixed URIs that come from the alias table, exact match only

SHELLS = frozenset(["cmd", "powershell", "pwsh", "powershell_ise", "bash", "sh", "zsh", "wsl", "command"])
NEVER = frozenset([
    "shutdown", "logoff", "taskkill", "tskill", "reg", "regedit", "format", "diskpart", "bcdedit", "schtasks",
    "sc", "net", "net1", "netsh", "wmic", "mshta", "wscript", "cscript", "rundll32", "regsvr32", "certutil",
    "bitsadmin", "msiexec", "takeown", "icacls", "cacls", "cipher", "vssadmin", "wevtutil", "runas", "forfiles",
    "at", "psexec", "sdelete", "fsutil", "dism", "sfc", "chkdsk", "convert", "assoc", "ftype", "start",
])

# Script / installer / registry file types that opening through the shell would EXECUTE.
DANGEROUS_OPEN_EXTENSIONS = frozenset([
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta",
    ".msi", ".msp", ".reg", ".scr", ".pif", ".jar", ".cpl", ".gadget", ".application",
])

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _pathmod():
    return ntpath if IS_WINDOWS else os.path


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def safe_web_url(text) -> Optional[str]:
    """The URL if it is a plain http(s) address, else None. Never raises.

    Rejected: any other scheme (file:, javascript:, ms-msdt:, ftp: ...), whitespace/control
    characters, quotes, angle brackets, backticks, backslashes, user-info tricks
    (https://good.com@evil.com), and anything that does not START with http:// or https://
    (so it can never be mistaken for a browser command-line option)."""
    t = str(text or "").strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        t = t[1:-1].strip()
    if not t or len(t) > 2000:
        return None
    if re.search(r"[\s\x00-\x1f\x7f\"'<>`^|\\]", t):
        return None
    m = re.match(r"^(https?)://([^/?#]+)([/?#].*)?$", t, re.IGNORECASE)
    if not m:
        return None
    host = m.group(2)
    if "@" in host:
        return None
    hostname = re.sub(r":\d{1,5}$", "", host)
    if not re.match(r"^(localhost|[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+)$", hostname):
        return None
    return t


def safe_argument(text) -> bool:
    """True if `text` can be passed as ONE argument to a .cmd/.bat launcher without cmd.exe
    interpreting any part of it (used for the project folder handed to VS Code)."""
    t = str(text or "")
    return bool(t) and len(t) <= 400 and not re.search(r"[&|<>^%!\"'`;\r\n\x00]", t)


def _stem(name: str) -> str:
    s = re.sub(r"\s+", " ", str(name).strip().lower())
    return s[:-4] if s.endswith(".exe") else s


def _blocked_name(name: str) -> Optional[str]:
    """Reason a plain name must not be launched, or None."""
    stem = _stem(name)
    squashed = stem.replace(" ", "")
    for candidate in (stem, squashed, os.path.splitext(stem)[0]):
        if candidate in NEVER:
            return "'%s' is a system-administration tool, so I don't launch it" % name
    for candidate in (stem, squashed, os.path.splitext(stem)[0]):
        if candidate in SHELLS and not lily_config.get_bool("launch_allow_shells", False):
            return ("'%s' is a command shell. For safety I don't open shells (set launch_allow_shells to true "
                    "in config/local_settings.json if you really want that)" % name)
    return None


def classify(text) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (kind, value, error). kind is 'url', 'uri', 'path' or 'name'; on rejection kind and
    value are None and error says why. No process is ever started here."""
    raw = str(text or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].strip()
    if not raw:
        return None, None, "No application name was given."
    if len(raw) > 2000:
        return None, None, "That is far too long to be an application name."
    if _CONTROL_RE.search(raw):
        return None, None, "That contains control characters, so I won't launch it."

    # --- web addresses and other URI schemes (but not "C:\..." drive paths) ---
    if _SCHEME_RE.match(raw) and not _DRIVE_RE.match(raw) and not re.match(r"^[A-Za-z]:$", raw):
        if raw.lower() in ALLOWED_URIS:
            return "uri", raw.lower(), None
        scheme = raw.split(":", 1)[0].lower()
        if scheme in ("http", "https"):
            url = safe_web_url(raw)
            if url:
                return "url", url, None
            return None, None, "That web address isn't valid or safe to open."
        return None, None, "I only open http and https web addresses, not '%s:' links." % scheme

    # --- command-line options ("cmd /c shutdown /s", "app.exe --flag"): never accepted, whatever the rest is ---
    if SWITCH_RE.search(raw):
        return None, None, "That looks like it has command-line options. I only open programs by name, without options."

    # --- paths ---
    if "\\" in raw or "/" in raw or _DRIVE_RE.match(raw):
        pm = _pathmod()
        if raw.startswith("\\\\") or raw.startswith("//"):
            return None, None, "Network (UNC) paths aren't launched."
        if "%" in raw or "$" in raw or "`" in raw:
            return None, None, "Paths with variables or special characters aren't launched."
        if not pm.isabs(raw) or (IS_WINDOWS and not _DRIVE_RE.match(raw)):
            return None, None, "Give the full path starting at the drive (for example C:\\Program Files\\...)."
        parts = re.split(r"[\\/]+", raw)
        if ".." in parts:
            return None, None, "Paths containing '..' aren't launched."
        if re.search(r"\s[A-Za-z]:[\\/]", raw):
            return None, None, "That looks like a program followed by more paths or options, which I don't accept."
        norm = pm.normpath(raw)
        ext = pm.splitext(norm)[1].lower()
        if ext in ALLOWED_PATH_EXTENSIONS:                      # a program or a shortcut
            blocked = _blocked_name(pm.splitext(pm.basename(norm))[0])
            if blocked:
                return None, None, blocked + "."
            if not _isfile(norm):
                return None, None, "I couldn't find that file."
            return "path", norm, None
        if ext in DANGEROUS_OPEN_EXTENSIONS:                    # scripts, installers, registry files ...
            return None, None, ("I won't run '%s' script or installer files. Say 'open <app name>' to start a "
                                "program." % ext)
        if _isfile(norm) or _isdir(norm):                       # a document or a folder
            return "document", norm, None
        return None, None, "I couldn't find that file or folder."

    # --- plain names ---
    if not NAME_RE.match(raw):
        return None, None, ("'%s' doesn't look like an application name. I only accept letters, digits, spaces, "
                            "dots, hyphens and brackets, and never commands or options." % raw[:40])
    if SWITCH_RE.search(raw):
        return None, None, "That looks like it has command-line options. I only open programs by name, without options."
    blocked = _blocked_name(raw)
    if blocked:
        return None, None, blocked + "."
    return "name", raw, None


# ---------------------------------------------------------------------------
# resolving a plain name to a real file (no shell involved)
# ---------------------------------------------------------------------------

def _in_untrusted_dir(path: str) -> bool:
    """Windows searches the current directory first; ignore hits there or in Lily's own folder.
    A result with no directory part at all cannot be trusted either."""
    try:
        pm = _pathmod()
        folder = pm.dirname(path)
        if not folder:
            return True
        folder = pm.normcase(pm.realpath(folder))
        return folder in (pm.normcase(pm.realpath(os.getcwd())),
                          pm.normcase(pm.realpath(str(lily_paths.BASE_DIR))))
    except Exception:
        return False


def _registry_lookup(name: str) -> Optional[str]:
    """App Paths registry key: the same table the Windows `start` command uses."""
    if not IS_WINDOWS:
        return None
    try:
        import winreg
    except ImportError:
        return None
    exe = name if name.lower().endswith(".exe") else name + ".exe"
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + exe
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _kind = winreg.QueryValueEx(key, None)
        except OSError:
            continue
        value = os.path.expandvars(str(value).strip().strip('"'))
        if value.lower().endswith(".exe") and _isfile(value):
            return value
    return None


def _start_menu_dirs() -> List[str]:
    dirs = []
    for var in ("ProgramData", "APPDATA"):
        base = os.environ.get(var)
        if base:
            dirs.append(os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs"))
    return dirs


def _start_menu_lookup(name: str) -> Optional[str]:
    """A shortcut (.lnk) in the Start menu whose name matches: exact first, then a prefix/contains match."""
    if not IS_WINDOWS:
        return None
    wanted = re.sub(r"\s+", " ", name.lower().strip())
    best = None   # (rank, length, path)
    seen = 0
    for root in _start_menu_dirs():
        for dirpath, _dirs, files in os.walk(root):
            if dirpath[len(root):].count(os.sep) > 3:
                continue
            for fname in files:
                seen += 1
                if seen > 4000:
                    break
                if not fname.lower().endswith(".lnk"):
                    continue
                stem = re.sub(r"\s+", " ", fname[:-4].lower())
                if any(bad in stem for bad in ("uninstall", "remove", "setup")):
                    continue
                if stem == wanted:
                    rank = 0
                elif len(wanted) >= 4 and (stem.startswith(wanted) or wanted in stem):
                    rank = 1
                else:
                    continue
                cand = (rank, len(stem), os.path.join(dirpath, fname))
                if best is None or cand < best:
                    best = cand
    return best[2] if best else None


def resolve_name(name: str) -> Tuple[Optional[str], str]:
    """Find the file for a validated plain name. Returns (path_or_None, how_it_was_found)."""
    base = str(name).strip()
    candidates = [base] if os.path.splitext(base)[1].lower() in (".exe", ".com") else [base, base + ".exe"]
    for cand in candidates:
        found = _which(cand)
        if found and not _in_untrusted_dir(found):
            ext = os.path.splitext(found)[1].lower()
            if ext in (".exe", ".com", ".lnk"):
                return found, "PATH"
            if ext in (".cmd", ".bat") and _stem(base) in TRUSTED_SHIMS:
                return found, "PATH (trusted launcher)"
    for cand in candidates:
        found = _registry_lookup(cand)
        if found:
            return found, "App Paths"
    found = _start_menu_lookup(base)
    if found:
        return found, "Start menu"
    return None, ""


# ---------------------------------------------------------------------------
# starting things
# ---------------------------------------------------------------------------

def _start_file(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".lnk":
        if _startfile is None:
            raise OSError("opening shortcuts is only supported on Windows")
        _startfile(path)                      # ShellExecute on a shortcut: runs its target, nothing else
        return
    _popen([path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
           cwd=os.path.dirname(path) or None, shell=False)


def launch_application(text) -> LaunchResult:
    """Validate and start an application, path or URL. Never raises; never uses a shell."""
    kind, value, error = classify(text)
    if error:
        _log.warning("refused to launch %r: %s", str(text)[:80], error)
        return LaunchResult(False, error, None, None)
    try:
        if kind == "url":
            _open_url_fn(value)
            _log.info("opened a web address in the browser")
            return LaunchResult(True, "Opening %s in your browser." % value, "url", value)
        if kind == "uri":
            if _startfile is None:
                return LaunchResult(False, "That is only available on Windows 8 or newer.", "uri", value)
            _startfile(value)
            return LaunchResult(True, "Opened %s." % value, "uri", value)
        if kind == "path":
            _start_file(value)
            _log.info("launched %s", value)
            return LaunchResult(True, "Started %s." % os.path.basename(value), "path", value)
        if kind == "document":
            if _startfile is None:
                return LaunchResult(False, "Opening documents is only supported on Windows.", "document", value)
            _startfile(value)                 # default application, like double-clicking; no shell, no arguments
            _log.info("opened %s", value)
            return LaunchResult(True, "Opened %s." % (os.path.basename(value.rstrip("\\/")) or value), "document", value)
        path, how = resolve_name(value)
        if not path:
            return LaunchResult(False, "I couldn't find an app called %s." % value, "name", None)
        _start_file(path)
        _log.info("launched %s (found via %s)", path, how)
        return LaunchResult(True, "Started %s." % value, "name", path)
    except Exception as exc:
        _log.exception("launching %r failed", str(text)[:80])
        return LaunchResult(False, "I couldn't start that: %s" % exc, kind, value)


def is_plain_name(text) -> bool:
    return classify(text)[0] == "name"


def start_menu_typing_enabled() -> bool:
    """The old keystroke fallback (typing the name into the Start menu and pressing Enter) is OFF by
    default: it types into whatever window has focus. Shortcuts are found directly instead."""
    return lily_config.get_bool("launch_start_menu_typing", False)
