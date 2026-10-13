"""Microphone selection helpers (pure functions, easy to test).

Audit findings fixed here:
  * listen() only worked if a device was saved in config OR device index 9 happened
    to be a Realtek mic; otherwise it printed "using the system default" and then
    returned None without recording anything;
  * names saved by the UI picker can be longer than the 31-character names PyAudio's
    MME host API reports, and the old check only tested "saved in reported";
  * the wake-word loop ignored the chosen device entirely.

Selection order: configured device name -> optional name hints from settings ->
the operating system default (index None). Never a hard-coded index.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").lower()).strip()


def _find(names: Sequence[str], target: str) -> Optional[int]:
    t = _norm(target)
    if not t:
        return None
    normed = [_norm(n) for n in names]
    for i, n in enumerate(normed):                       # 1) exact
        if n == t:
            return i
    for i, n in enumerate(normed):                       # 2) saved name inside reported name
        if t in n:
            return i
    for i, n in enumerate(normed):                       # 3) reported name is a truncated form of saved name
        if len(n) >= 15 and t.startswith(n):
            return i
    for i, n in enumerate(normed):                       # 4) same name up to MME truncation
        if len(n) >= 15 and len(t) >= 15 and (n[:28] == t[:28]):
            return i
    return None


def resolve_input_index(names: Sequence[str], wanted: str = "",
                        hints: Iterable[str] = (), preferred_index=None) -> Tuple[Optional[int], str]:
    """Return (index_or_None, reason). None means 'use the system default device'.

    ``preferred_index`` is an advanced, local diagnostic override for duplicate
    Windows host-API names. It should only be set to an index verified by
    ``mic_level_test.py``; indices can change when audio devices are added.
    """
    if preferred_index not in (None, ""):
        try:
            idx = int(preferred_index)
            if 0 <= idx < len(names):
                return idx, "configured-index"
        except (TypeError, ValueError):
            pass
    if wanted:
        idx = _find(names, wanted)
        if idx is not None:
            return idx, "configured"
    for hint in hints or ():
        idx = _find(names, hint)
        if idx is not None:
            return idx, "hint"
    return None, ("configured-not-found" if wanted else "default")


def pyaudio_input_devices(pa) -> List[Tuple[int, str]]:
    """(index, name) of every input-capable PyAudio device."""
    found = []
    try:
        count = pa.get_device_count()
    except Exception:
        return found
    for i in range(count):
        try:
            info = pa.get_device_info_by_index(i)
        except Exception:
            continue
        if int(info.get("maxInputChannels", 0) or 0) > 0:
            found.append((i, str(info.get("name", ""))))
    return found


def resolve_pyaudio_index(pa, wanted: str = "", hints: Iterable[str] = (),
                          preferred_index=None) -> Tuple[Optional[int], str]:
    """Resolve an input device for the wake loop, honouring a verified override.

    Unlike ``resolve_input_index``, this function knows which raw PyAudio
    indices can accept input, so an override is accepted only for an input-capable
    device. That matters on Windows, where speakers and microphones share the
    same numeric index space.
    """
    devices = pyaudio_input_devices(pa)
    if preferred_index not in (None, ""):
        try:
            idx = int(preferred_index)
            if any(device_index == idx for device_index, _name in devices):
                return idx, "configured-index"
        except (TypeError, ValueError):
            pass
    names = [n for _i, n in devices]
    pos, reason = resolve_input_index(names, wanted, hints)
    if pos is None:
        return None, reason
    return devices[pos][0], reason
