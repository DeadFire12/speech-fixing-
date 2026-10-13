from __future__ import annotations
import os
import shutil
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BACKUP_DIR = os.path.join(
    BASE_DIR,
    "backups"
)


FILES_TO_BACKUP = [
    "memory.json",
    "state.json",
    "goals.json",
    "learning.json"
]


def create_backup():

    os.makedirs(
        BACKUP_DIR,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    backup_folder = os.path.join(
        BACKUP_DIR,
        timestamp
    )

    os.makedirs(
        backup_folder,
        exist_ok=True
    )

    copied = []

    for filename in FILES_TO_BACKUP:

        source = os.path.join(
            BASE_DIR,
            filename
        )

        if os.path.exists(source):

            destination = os.path.join(
                backup_folder,
                filename
            )

            shutil.copy2(
                source,
                destination
            )

            copied.append(filename)

    return backup_folder, copied


def list_backups():

    if not os.path.exists(BACKUP_DIR):
        return []

    backups = []

    for name in os.listdir(BACKUP_DIR):

        path = os.path.join(
            BACKUP_DIR,
            name
        )

        if os.path.isdir(path):
            backups.append(name)

    backups.sort(
        reverse=True
    )

    return backups