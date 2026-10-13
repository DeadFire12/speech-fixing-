"""Central path resolution for Lily.

Why this exists: several modules used bare relative file names such as
"memory.json". Those silently pointed at a *different* (empty) file whenever
Lily was started from another working directory (a shortcut, an IDE, pythonw).
Everything now resolves against the project folder instead.

Environment overrides (mainly for tests and portable installs):
    LILY_DATA_DIR    where memory.json / learning.json / state.json / goals.json live
    LILY_CONFIG_DIR  where config/local_settings.json lives
    LILY_LOG_DIR     where logs are written

Python 3.8 / Windows 7 compatible (standard library only).
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def data_dir() -> Path:
    override = os.environ.get("LILY_DATA_DIR")
    return Path(override) if override else BASE_DIR


def config_dir() -> Path:
    override = os.environ.get("LILY_CONFIG_DIR")
    return Path(override) if override else BASE_DIR / "config"


def log_dir() -> Path:
    override = os.environ.get("LILY_LOG_DIR")
    return Path(override) if override else BASE_DIR / "logs"


def data_path(name: str) -> str:
    return str(data_dir() / name)


def config_path(name: str) -> str:
    return str(config_dir() / name)


def log_path(name: str) -> str:
    return str(log_dir() / name)
