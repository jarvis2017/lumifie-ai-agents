"""An offline, rule-based provider so the demo runs with zero setup.

``--source demo`` uses this automatically when no API credential is configured,
so anyone can see the full pipeline — including LLM-drafted follow-up emails —
without keys or network. It implements the same ``complete()`` surface as
``lumifie_core.LLMProvider`` and returns a deterministic structured email draft.
"""

from __future__ import annotations

from typing import Any

from lumifie_core import CompletionResult, ToolCall

_USAGE = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _draft(user_text: str) -> dict[str, Any]:
    target = "your account"
    for token in user_text.split():
        if token.startswith(("c-", "d-")):
            target = token.rstrip(".")
            break
    return {
        "subject": "Quick follow-up",
        "body": (
            "Hi there,\n\n"
            "I wanted to circle back on our recent conversation. I know things get "
            "busy, so no pressure at all — I'm here whenever the timing is right, and "
            "happy to answer any questions in the meantime.\n\n"
            f"Would a short call next week be useful to keep things moving on {target}?\n\n"
            "Best regards,\nThe Team\n\n[offline stub draft — review before sending]"
        ),
    }


class StubProvider:
    """Deterministic offline stand-in for LLMProvider (email drafts only)."""

    supports_tools = True
    model = "stub:offline"

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        choice = kwargs.get("tool_choice") or {}
        name = choice.get("function", {}).get("name", "") or "email_draft"
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        args = _draft(user_text)
        return CompletionResult(
            text=None,
            tool_calls=[ToolCall(id="stub", name=name, arguments=args)],
            finish_reason="tool_calls",
            usage=_USAGE,
        )


__all__ = ["StubProvider"]
