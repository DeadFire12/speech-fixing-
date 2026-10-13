"""The one place Lily's version is defined.

Everything that shows a version (the --version command, --status, the self-test header, the
log file banner, the GUI start-up line) reads it from here. Bump it here only.

Versioning: MAJOR.MINOR.PATCH
    1.0.0  first stabilised release (audit repairs, self-test, regression suite)
    1.1.0  adds file logging, the --version command and the --status command
    1.1.1  safety repair: memory clearing goes through the safety gate, no shell in application launching,
           no hard-coded form of address, explicit optional-dependency files
    1.1.2  Windows SAPI speech isolation and Qt5 mouse-event compatibility
    1.1.3  press-and-hold push-to-talk and microphone signal diagnostics
"""
from __future__ import annotations

import platform
import sys

__version__ = "1.1.3"
VERSION_INFO = tuple(int(part) for part in __version__.split("."))
RELEASE_NAME = "Lily local (Windows 7 / Python 3.8 build)"


def version_string() -> str:
    """Short form: 'Lily 1.1.0'."""
    return "Lily %s" % __version__


def runtime_summary() -> str:
    """'Python 3.8.10 | Windows-7-6.1.7601-SP1' - never raises."""
    try:
        py = "Python %d.%d.%d" % sys.version_info[:3]
        return "%s | %s" % (py, platform.platform())
    except Exception:
        return "Python %s" % sys.version.split()[0]


def version_banner() -> str:
    """What `Lily.py --version` prints."""
    return "%s\n%s\n%s" % (version_string(), RELEASE_NAME, runtime_summary())
