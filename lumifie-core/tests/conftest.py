"""Fixtures and fakes for lumifie_core tests (no network, no API keys)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def make_response(
    *,
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    model: str = "test-model",
) -> SimpleNamespace:
    """Build a litellm-shaped (OpenAI) response object for the provider to normalize."""
    tc_objs = [
        SimpleNamespace(
            id=tc["id"],
            type="function",
            function=SimpleNamespace(name=tc["name"], arguments=tc["arguments"]),
        )
        for tc in (tool_calls or [])
    ]
    message = SimpleNamespace(content=content, role="assistant", tool_calls=tc_objs or None)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


class RecordingCompletion:
    """A fake litellm.completion that records calls and returns scripted responses."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._responses.pop(0) if self._responses else make_response(content="ok")
