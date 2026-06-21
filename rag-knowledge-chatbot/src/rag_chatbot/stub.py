"""An offline, rule-based provider so the chatbot runs with zero setup.

When no API credential is configured, the factory selects this provider so
`rag-chatbot ask` / `rag-chatbot demo` work fully offline on the demo dataset. It
implements the same ``complete()`` surface as ``lumifie_core.LLMProvider``.

For the ``answer`` tool it composes a grounded reply by quoting the top retrieved
passage(s) straight out of the numbered context the agent built into the prompt,
and reports the citation numbers it used — so the demo produces a real, cited
answer without any model.
"""

from __future__ import annotations

import re
from typing import Any

from lumifie_core import CompletionResult, ToolCall

_USAGE = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

# Matches "[n] (source: …)\n<passage text>" blocks in the agent's prompt.
_PASSAGE_RE = re.compile(
    r"\[(\d+)\]\s*\(source:[^)]*\)\n(.*?)(?=\n\n\[\d+\]|\n\nAnswer the question|\Z)",
    re.DOTALL,
)
_MAX_QUOTE = 320


def _parse_passages(prompt: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in _PASSAGE_RE.finditer(prompt):
        out.append((int(m.group(1)), " ".join(m.group(2).split())))
    return out


def _answer(prompt: str) -> dict[str, Any]:
    passages = _parse_passages(prompt)
    if not passages:
        return {"answer": "I don't have enough information to answer that.", "cited": []}

    # Quote the top one or two passages and cite them inline.
    used = passages[:2]
    parts: list[str] = []
    for n, text in used:
        quote = text if len(text) <= _MAX_QUOTE else text[:_MAX_QUOTE].rstrip() + "…"
        parts.append(f"{quote} [{n}]")
    answer = (
        "Based on the provided documents: "
        + " ".join(parts)
    )
    return {"answer": answer, "cited": [n for n, _ in used]}


class StubProvider:
    """Deterministic offline stand-in for LLMProvider."""

    supports_tools = True
    model = "stub:offline"

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        name = (kwargs.get("tool_choice") or {}).get("function", {}).get("name", "")
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if name == "answer":
            args = _answer(user_text)
        else:
            args = {}
        return CompletionResult(
            text=None,
            tool_calls=[ToolCall(id="stub", name=name or "stub", arguments=args)],
            finish_reason="tool_calls",
            usage=_USAGE,
        )


__all__ = ["StubProvider"]
