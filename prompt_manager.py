"""Prompt assembly for the local model.

One system block (identity first), whole-turn history, and a token budget that
guarantees the persona is never pushed out of the model's context window.

The chat template is a profile (ChatML for Qwen today) so another GGUF family
can be supported by adding a profile, without touching the runtime.
"""
from __future__ import annotations

import re
import textwrap
from typing import Dict, List, Optional, Tuple

import identity

PROFILES = {
    "chatml": {
        "name": "chatml",
        "system": "<|im_start|>system\n{content}<|im_end|>\n",
        "user": "<|im_start|>user\n{content}<|im_end|>\n",
        "assistant": "<|im_start|>assistant\n{content}<|im_end|>\n",
        "assistant_open": "<|im_start|>assistant\n",
        "stop": ["<|im_end|>", "<|im_start|>"],
    },
}


def get_profile(name: str = "chatml") -> Dict:
    return PROFILES.get(str(name or "chatml").lower(), PROFILES["chatml"])


def estimate_tokens(text: str) -> int:
    """Deliberately conservative (~3 chars/token) so we under-fill the context."""
    return int(len(text) / 3.0) + 1


def strip_template_tokens(text: str) -> str:
    return re.sub(r"<\|im_(?:start|end)\|>", "", str(text or ""))


# ---------------------------------------------------------------------------
# System block
# ---------------------------------------------------------------------------

def _norm_value(value: str) -> str:
    return re.sub(r"[\s\.\!\?]+$", "", str(value or "").strip().lower())


def build_learning_text(learning: Optional[dict]) -> str:
    """'Learned information' lines, de-duplicated (the old code repeated whole
    blocks when learning.json held near-duplicate entries). The simple/detailed
    explanation preferences are handled by the response-style block instead."""
    if not learning:
        return ""
    seen = set()
    lines = []
    for _key, data in learning.items():
        value = str((data or {}).get("value", "")).strip()
        norm = _norm_value(value)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        if "prefer simple explanations" in norm or "prefer detailed explanations" in norm:
            continue
        lines.append("- " + value)
    if not lines:
        return ""
    return "Things you have learned about the user:\n" + "\n".join(lines)


def summarize_memory(memory: Optional[dict], max_items: int = 8, max_chars: int = 600) -> str:
    """A short, bounded summary of stored memories for the prompt."""
    if not memory:
        return ""
    rows = []
    for key, entry in memory.items():
        if isinstance(entry, dict):
            value = str(entry.get("value", "")).strip()
            importance = 0 if entry.get("importance") == "high" else 1
            category = 0 if entry.get("category") in ("personal", "preferences") else 1
            updated = str(entry.get("updated", ""))
        else:
            value, importance, category, updated = str(entry).strip(), 1, 1, ""
        if not value:
            continue
        rows.append((importance, category, _invert(updated), str(key), value))
    rows.sort()
    out, used = [], 0
    for _i, _c, _u, key, value in rows[:max_items]:
        line = "- %s: %s" % (key, value[:120])
        if used + len(line) > max_chars:
            break
        out.append(line)
        used += len(line) + 1
    if not out:
        return ""
    return "Things the user has asked you to remember:\n" + "\n".join(out)


def _invert(stamp: str) -> str:
    # newest first when sorted ascending
    return "".join(chr(255 - ord(c)) if ord(c) < 256 else c for c in stamp)


def build_system_sections(assistant: str, user: str, persona_text: str = "",
                          style_text: str = "", learning_text: str = "",
                          memory_text: str = "") -> List[Tuple[str, str, bool]]:
    """Ordered (name, text, required) sections. Required ones are never dropped."""
    persona = textwrap.dedent(str(persona_text or "")).strip()
    # the persona file's own first sentence would repeat the identity block
    persona = re.sub(r"(?im)^you are [^\n]*personal ai assistant\.?\s*$", "", persona).strip()
    sections = [
        ("identity", identity.identity_block(assistant, user), True),
        ("persona", persona, True),
        ("style", textwrap.dedent(str(style_text or "")).strip(), False),
        ("memory", memory_text.strip(), False),
        ("learning", learning_text.strip(), False),
    ]
    return [(n, t, r) for n, t, r in sections if t]


def build_chat_prompt(sections: List[Tuple[str, str, bool]], turns: List[Tuple[str, str]],
                      user_text: str, context_tokens: int, reserve_tokens: int,
                      profile: Optional[Dict] = None) -> Tuple[str, Dict]:
    """Assemble system + history + user turn so the estimate fits the context.

    Order of sacrifice when space runs out: oldest history turns first, then
    optional system sections (learning, memory, style). The identity and persona
    sections are never dropped. Returns (prompt, info).
    """
    profile = profile or get_profile("chatml")
    budget = max(256, int(context_tokens) - int(reserve_tokens))
    user_part = profile["user"].format(content=strip_template_tokens(user_text).strip())
    tail = profile["assistant_open"]

    secs = list(sections)
    dropped = []

    def system_text(ss):
        return profile["system"].format(content="\n\n".join(t for _n, t, _r in ss) + "\n")

    fixed = lambda ss: estimate_tokens(system_text(ss)) + estimate_tokens(user_part) + estimate_tokens(tail)
    while fixed(secs) > budget:
        # drop the last optional section, scanning from the end
        for idx in range(len(secs) - 1, -1, -1):
            if not secs[idx][2]:
                dropped.append(secs[idx][0])
                del secs[idx]
                break
        else:
            break  # only required sections remain

    remaining = budget - fixed(secs)
    history = []
    used_turns = 0
    for u, a in reversed(turns):
        block = (profile["user"].format(content=strip_template_tokens(u).strip()) +
                 profile["assistant"].format(content=strip_template_tokens(a).strip()))
        cost = estimate_tokens(block)
        if cost > remaining:
            break
        history.append(block)
        remaining -= cost
        used_turns += 1
    history.reverse()

    prompt = system_text(secs) + "".join(history) + user_part + tail
    info = {
        "estimated_tokens": estimate_tokens(prompt),
        "budget": budget,
        "turns_included": used_turns,
        "turns_available": len(turns),
        "sections": [n for n, _t, _r in secs],
        "sections_dropped": dropped,
    }
    return prompt, info
