"""An offline, rule-based provider so the demo runs with zero setup.

`python main.py --mock-email` uses this automatically when no API credential is
configured, so anyone can see the full pipeline work without keys or network. It
implements the same ``complete()`` surface as ``lumifie_core.LLMProvider`` and
returns rule-based structured results for each tool the agent forces.
"""

from __future__ import annotations

import re
from typing import Any

from lumifie_core import CompletionResult, ToolCall

from inbound_triage.contacts import extract_emails, extract_phones

_USAGE = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

_OOO = ("out of office", "on leave", "on vacation", "annual leave", "automatic reply")
_SPAM = ("unsubscribe", "viagra", "crypto giveaway", "click here to win", "won")
_REFERRAL = (
    "not the right person", "wrong person", "reach out to", "you should contact", "forward",
)
_OBJECTION = (
    "too expensive", "over budget", "already use", "already have",
    "not the right time", "no budget", "pricing", "not a priority",
)
_INTERESTED = ("interested", "sounds great", "book", "demo", "call", "love to", "tell me more")

_NAME_RE = re.compile(
    r"(?:contact|reach out to|talk to|speak with|forward .* to)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)


def _classify(text: str) -> dict[str, Any]:
    t = text.lower()
    if any(w in t for w in _OOO):
        intent, why = "OUT_OF_OFFICE", "auto-reply language detected"
    elif any(w in t for w in _SPAM):
        intent, why = "SPAM", "spam markers detected"
    elif any(w in t for w in _REFERRAL):
        intent, why = "NOT_THE_RIGHT_PERSON", "referral language detected"
    elif any(w in t for w in _OBJECTION):
        intent, why = "OBJECTION", "objection language detected"
    elif any(w in t for w in _INTERESTED):
        intent, why = "INTERESTED", "positive buying language detected"
    else:
        intent, why = "OBJECTION", "no clear signal; defaulting to objection handling"
    return {"intent": intent, "confidence": 0.7, "reasoning": f"[offline stub] {why}"}


def _contact(text: str) -> dict[str, Any]:
    m = _NAME_RE.search(text)
    return {
        "referred_name": m.group(1) if m else None,
        "referred_title": None,
        "emails": extract_emails(text),
        "phones": extract_phones(text),
        "note": "[offline stub] extracted via regex",
    }


def _rebuttal(_text: str) -> dict[str, Any]:
    body = (
        "Thanks for the candid reply — totally fair. A quick thought before you go: "
        "most teams in your position find the cost of the status quo outweighs the "
        "investment within a quarter. Open to a 15-minute look at the numbers?"
    )
    return {
        "body": body,
        "key_points": [
            "acknowledge the objection",
            "reframe around ROI",
            "low-commitment next step",
        ],
    }


class StubProvider:
    """Deterministic offline stand-in for LLMProvider."""

    supports_tools = True
    model = "stub:offline"

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        name = (kwargs.get("tool_choice") or {}).get("function", {}).get("name", "")
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if name == "classification":
            args = _classify(user_text)
        elif name == "contact":
            args = _contact(user_text)
        elif name == "rebuttal":
            args = _rebuttal(user_text)
        else:
            args = {}
        return CompletionResult(
            text=None,
            tool_calls=[ToolCall(id="stub", name=name or "stub", arguments=args)],
            finish_reason="tool_calls",
            usage=_USAGE,
        )


__all__ = ["StubProvider"]
