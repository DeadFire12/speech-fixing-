"""Structured conversation history.

Replaces the old single string that was trimmed with split("\\n")[-300:], which
cut conversations in the middle of an answer and let the prompt grow past the
model's context window. History is now a list of whole turns, trimmed by turn
and by a token budget (see prompt_manager).
"""
from __future__ import annotations

import threading
from typing import List, Tuple

MAX_STORED_TURNS = 60


class Conversation(object):
    def __init__(self, max_turns: int = MAX_STORED_TURNS):
        self._turns = []  # type: List[Tuple[str, str]]
        self._max = max_turns
        self._lock = threading.RLock()

    def add(self, user: str, assistant: str) -> None:
        with self._lock:
            self._turns.append((str(user), str(assistant)))
            if len(self._turns) > self._max:
                del self._turns[: len(self._turns) - self._max]

    def turns(self) -> List[Tuple[str, str]]:
        with self._lock:
            return list(self._turns)

    def clear(self) -> None:
        with self._lock:
            self._turns = []

    def __len__(self) -> int:
        with self._lock:
            return len(self._turns)
