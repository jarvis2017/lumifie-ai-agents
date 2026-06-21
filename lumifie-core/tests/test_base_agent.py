"""Tests for BaseAgent: token accounting and the structured() helper."""

from __future__ import annotations

import json
from typing import Any

from lumifie_core import BaseAgent, CoreSettings, chat
from lumifie_core.provider import CompletionResult, ToolCall


class _ToolProvider:
    supports_tools = True
    model = "claude-opus-4-8"

    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] = {}

    def complete(self, messages, **kwargs):
        self.last_kwargs = kwargs
        return CompletionResult(
            text=None,
            tool_calls=[ToolCall(id="c1", name="extract", arguments={"x": 1})],
            finish_reason="tool_calls",
            usage={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        )


class _JSONProvider:
    supports_tools = False
    model = "ollama/llama3.1"

    def complete(self, messages, **kwargs):
        self.last_kwargs = kwargs
        return CompletionResult(
            text=json.dumps({"x": 2}),
            finish_reason="stop",
            usage={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
        )


class _Agent(BaseAgent):
    name = "test-agent"

    def run(self, *args, **kwargs):
        return "ran"


def _settings():
    return CoreSettings()


def test_token_usage_accumulates():
    agent = _Agent(_ToolProvider(), _settings())
    agent.complete([chat.user("hi")])
    agent.complete([chat.user("again")])
    assert agent.token_usage["input_tokens"] == 20
    assert agent.token_usage["output_tokens"] == 8


def test_structured_uses_tool_when_supported():
    provider = _ToolProvider()
    agent = _Agent(provider, _settings())
    out = agent.structured(system="s", prompt="p", schema={"type": "object"}, tool_name="extract")
    assert out == {"x": 1}
    # Forced the specific tool.
    assert provider.last_kwargs["tool_choice"] == {"type": "function", "function": {"name": "extract"}}
    assert "tools" in provider.last_kwargs


def test_structured_uses_json_mode_when_no_tools():
    provider = _JSONProvider()
    agent = _Agent(provider, _settings())
    out = agent.structured(system="s", prompt="p", schema={"type": "object"}, tool_name="extract")
    assert out == {"x": 2}
    assert provider.last_kwargs["response_format"] == {"type": "json_object"}
    assert "tools" not in provider.last_kwargs


def test_parse_json_handles_garbage():
    assert chat.parse_json(None) == {}
    assert chat.parse_json("not json") == {}
    assert chat.parse_json('[1,2]') == {}  # not an object
    assert chat.parse_json('{"a": 1}') == {"a": 1}
