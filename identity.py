"""Lily's identity: one source of truth for names, the identity prompt block,
identity-question matching, and an output guard.

Root causes this addresses (found in the audit):
  * identity lived in ONE weak sentence and four exact-match phrases, so any
    other wording ("Hi, who are you?") reached a model that only knew its own
    training identity;
  * the user's configured name never reached the prompt;
  * the persona sat at the very start of an unbounded prompt, so once the
    context filled up it was the first thing llama.cpp dropped.

The Qwen model underneath is an implementation detail: it is never named in
the persona and the prompt tells it not to claim another identity.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

import lily_config

DEFAULT_ASSISTANT = "Lily"
_REJECTED_ASSISTANT_NAMES = {"", "qwen", "jarvis", "assistant", "ai", "chatgpt", "gemini", "claude"}


def _clean(value) -> str:
    return str(value or "").strip()


def get_names(memory=None) -> Tuple[str, str]:
    """Return (assistant_name, user_name). The assistant is always Lily unless a
    sensible custom name is configured; the user name comes from settings, then
    config/api_keys.json, then the stored memory entry 'name'."""
    assistant = _clean(lily_config.get("assistant_name"))
    if assistant.lower() in _REJECTED_ASSISTANT_NAMES:
        assistant = ""
    user = _clean(lily_config.get("user_name"))
    if not (assistant and user):
        try:
            from memory import config_manager as _cm
            if not assistant:
                cand = _clean(_cm.get_assistant_name())
                assistant = "" if cand.lower() in _REJECTED_ASSISTANT_NAMES else cand
            if not user:
                user = _clean(_cm.get_user_name())
        except Exception:
            pass
    if not user and memory:
        entry = memory.get("name")
        if isinstance(entry, dict):
            user = _clean(entry.get("value"))
        elif entry:
            user = _clean(entry)
    return (assistant or DEFAULT_ASSISTANT), user


def identity_block(assistant: str, user: str) -> str:
    """The identity section of the system prompt (kept short for a small model)."""
    owner = "%s's" % user if user else "the user's"
    lines = [
        "You are %s, %s personal AI assistant. Your name is %s." % (assistant, owner, assistant),
        "You run locally and privately on %s computer." % (owner if user else "the user's"),
        "Always speak as %s. If asked who or what you are, answer that you are %s, %s personal AI assistant."
        % (assistant, assistant, owner),
        "Never say you are Qwen, ChatGPT, GPT, Alibaba, OpenAI or a generic \"AI language model\"; "
        "the language model under you is an internal detail. If asked which model you use, "
        "say only that you use a small local language model.",
    ]
    if user:
        lines.append("You are talking with %s. Use their name naturally and sparingly." % user)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Identity-question matching (deterministic, so the answer never depends on the model)
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    t = str(text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    t = t.replace("'", " ")
    return re.sub(r"\s+", " ", t).strip()


_NOT_DOING = r"(?!\s+(?:doing|up to|going|thinking|talking|saying|looking|wearing|having|eating|watching|reading|listening|getting|trying|planning|working|making|supposed|afraid|scared|worried|waiting|about))"

_P_WHO = re.compile(r"\bwho (?:are|r) (?:you|u)\b|\bwho (?:you|u) (?:are|r)\b|\bwho is this\b$")
_P_WHAT = re.compile(r"\bwhat (?:are|r) (?:you|u)\b" + _NOT_DOING + r"|\bwhat (?:you|u) (?:are|r)\b$")
_P_NAME = re.compile(r"\b(?:what is|what s|whats|what) your name\b|\bwhat do (?:people |they |i )?call you\b|"
                     r"\bwhat should i call you\b|\bhow should i (?:call|address) you\b|\bwho do i call you\b")
_P_ABOUT = re.compile(r"\b(?:tell me about|introduce|describe) (?:yourself|your self)\b")
_P_MODEL = re.compile(r"\b(?:what|which) (?:model|llm|language model|engine|ai)\b.*\b(?:you|your|are you|do you use)\b|"
                      r"\bwhat (?:model|llm) are you\b|\bare you based on\b|\bwhat are you running on\b|"
                      r"\bwhat are you built on\b|\bwhat powers you\b")
_P_ARE_YOU = re.compile(
    r"\bare (?:you|u) (?:really |actually |just )?"
    r"(?P<what>qwen|chatgpt|chat gpt|gpt|gpt 4|gpt4|openai|alibaba|gemini|claude|siri|alexa|cortana|jarvis|bard|llama|"
    r"an ai|a ai|ai|a robot|a bot|a chatbot|an assistant|a human|human|real|a real person|a person)\b")
_P_CREATOR = re.compile(r"\bwho (?:made|created|built|developed|trained|programmed|designed|owns) (?:you|u)\b|"
                        r"\bwho is your (?:creator|maker|developer|owner|author)\b|\bwho s your (?:creator|maker|developer|owner)\b")
_P_MY_NAME = re.compile(r"\b(?:what is|what s|whats|what) my name\b|\bwho am i\b|\bdo you (?:know|remember) my name\b|"
                        r"\bwhat do you call me\b|\bwhat s my name\b")

_MAX_WORDS = 18     # long messages that merely contain these words are normal chat, not identity questions
_MAX_CLAUSE_WORDS = 9
_FILLER = re.compile(
    r"^(?:(?:hi|hey|hello|yo|ok|okay|so|well|please|lily|um|uh|quick question|just curious|by the way|"
    r"can you (?:please )?tell me|could you (?:please )?tell me|would you tell me|i want to know|i would like to know|"
    r"i d like to know|i wanna know|do you mind telling me)\b ?)+")
_CLAUSE_SPLIT = re.compile(r"\b(?:and|also|then)\b")


def _clauses(t: str):
    for raw in _CLAUSE_SPLIT.split(t):
        clause = _FILLER.sub("", raw.strip()).strip()
        if clause and len(clause.split()) <= _MAX_CLAUSE_WORDS:
            yield clause


def match_identity_question(text: str, assistant: str, user: str) -> Optional[str]:
    """Return a canonical reply if the message asks who Lily is / what her name is /
    what the user's name is, else None.

    Each clause must START with the question (after polite fillers such as "hi" or
    "can you tell me"), so "explain who are you in the movie Fight Club" is normal chat."""
    t = _norm(text)
    if not t or len(t.split()) > _MAX_WORDS:
        return None
    parts = []
    asked_self = False
    asked_user = False
    for clause in _clauses(t):
        if _P_MY_NAME.match(clause):
            asked_user = True
            continue
        if asked_self:
            continue
        reply = _self_reply(clause, assistant)
        if reply:
            parts.append(reply)
            asked_self = True
    if asked_user and user:
        parts.append("Your name is %s." % user)
    if not parts:
        return None
    return " ".join(parts)


def _self_reply(t: str, assistant: str) -> Optional[str]:
    m = _P_ARE_YOU.match(t)
    if m:
        what = m.group("what")
        if what in ("an ai", "a ai", "ai", "a robot", "a bot", "a chatbot"):
            return "Yes, I'm %s, an AI assistant running locally on your computer." % assistant
        if what in ("a human", "human", "real", "a real person", "a person"):
            return "No, I'm not human. I'm %s, your personal AI assistant." % assistant
        if what == "an assistant":
            return "Yes, I'm %s, your personal AI assistant." % assistant
        return "No, I'm %s, your personal AI assistant." % assistant
    if _P_ABOUT.match(t):
        return ("I'm %s, your personal AI assistant. I run locally and privately on your computer; "
                "I can chat, remember things you tell me, and help with tasks like opening apps "
                "and checking your system." % assistant)
    if _P_MODEL.match(t):
        return ("I'm %s. I run locally on your computer and use a small local language model to think "
                "and talk, but I'm %s whichever model is under the hood." % (assistant, assistant))
    if _P_CREATOR.match(t):
        return ("I'm %s, your personal AI assistant, set up to run locally on your computer. "
                "I don't have more details about who built the pieces I'm made from." % assistant)
    if _P_NAME.match(t):
        return "My name is %s." % assistant
    if _P_WHO.match(t) or _P_WHAT.match(t):
        return "I'm %s, your personal AI assistant." % assistant
    return None


# ---------------------------------------------------------------------------
# Output guard (defence in depth: the prompt is the real fix)
# ---------------------------------------------------------------------------
_BAD_CLAIM = re.compile(r"(?i)\b(?:i am|i'm|i\u2019m|my name is|this is|you are talking to|you're talking to)\s+"
                        r"(?:qwen|chatgpt|gpt[- ]?\d*|openai|gemini|claude|llama|alibaba(?: cloud)?)\b")
_BAD_MAKER = re.compile(r"(?i)\b(?:created|developed|made|built|trained|designed)\s+by\s+"
                        r"(?:alibaba(?: cloud)?|openai|google|anthropic|meta|microsoft)\b")
_GENERIC_ID = re.compile(r"(?i)\b(?:i am|i'm|i\u2019m)\s+(?:just\s+)?(?:an?\s+)?"
                         r"(?:ai|artificial intelligence)\s*(?:language\s+)?(?:model|assistant|chatbot)\b")
_AS_AN_AI = re.compile(r"(?i)\bas an ai(?: language)?(?: model| assistant)?\s*,\s*")


def enforce_identity(answer: str, assistant: str) -> Tuple[str, bool]:
    """Rewrite sentences where the model claims to be someone else. Returns
    (text, changed). Sentences that already name the assistant are left alone."""
    if not answer:
        return answer, False
    canonical = "I'm %s, your personal AI assistant." % assistant
    changed = False
    out_lines = []
    used_canonical = False
    for line in answer.split("\n"):
        pieces = re.split(r"(?<=[.!?])\s+", line)
        kept = []
        for sent in pieces:
            if not sent:
                continue
            bad = bool(_BAD_CLAIM.search(sent) or _BAD_MAKER.search(sent))
            generic = bool(_GENERIC_ID.search(sent)) and assistant.lower() not in sent.lower()
            if bad or generic:
                changed = True
                if not used_canonical:
                    kept.append(canonical)
                    used_canonical = True
                continue
            fixed = _AS_AN_AI.sub("", sent)
            if fixed != sent:
                changed = True
                fixed = fixed[:1].upper() + fixed[1:] if fixed else fixed
            kept.append(fixed)
        out_lines.append(" ".join(kept))
    result = "\n".join(out_lines).strip()
    return (result if result else canonical), changed
