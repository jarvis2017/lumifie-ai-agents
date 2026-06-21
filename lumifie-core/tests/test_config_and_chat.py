"""Tests for CoreSettings env loading and chat helpers."""

from __future__ import annotations

import json

from lumifie_core import chat
from lumifie_core.config import CoreSettings
from lumifie_core.provider import CompletionResult, ToolCall


def test_from_env_defaults(monkeypatch):
    for var in (
        "LITELLM_MODEL",
        "LUMIFIE_MAX_TOKENS",
        "LUMIFIE_TEMPERATURE",
        "LUMIFIE_REASONING_EFFORT",
        "LUMIFIE_MAX_RETRIES",
        "LUMIFIE_LOG_LEVEL",
    ):
        monkeypatch.delenv(var, raising=False)
    s = CoreSettings.from_env()
    assert s.model == "claude"
    assert s.max_tokens == 8000
    assert s.temperature is None
    assert s.max_retries == 4


def test_from_env_reads_litellm_model(monkeypatch):
    monkeypatch.setenv("LITELLM_MODEL", "ollama/llama3.1")
    monkeypatch.setenv("LUMIFIE_MAX_TOKENS", "4096")
    s = CoreSettings.from_env()
    assert s.model == "ollama/llama3.1"
    assert s.max_tokens == 4096


def test_overrides_ignore_none(monkeypatch):
    monkeypatch.setenv("LITELLM_MODEL", "gpt-4o")
    # A CLI flag that wasn't passed comes through as None and must not clobber env.
    s = CoreSettings.from_env(model=None, max_tokens=2048)
    assert s.model == "gpt-4o"
    assert s.max_tokens == 2048


def test_subclass_extends_settings():
    from dataclasses import dataclass

    @dataclass
    class MySettings(CoreSettings):
        widgets: int = 7

    s = MySettings.from_env(model="gpt-4o", widgets=9)
    assert s.model == "gpt-4o"
    assert s.widgets == 9


def test_assistant_message_roundtrips_tool_calls():
    result = CompletionResult(
        text="working",
        tool_calls=[ToolCall(id="c1", name="record", arguments={"a": 1})],
        finish_reason="tool_calls",
    )
    msg = chat.assistant_message(result)
    assert msg["role"] == "assistant"
    assert msg["tool_calls"][0]["id"] == "c1"
    assert json.loads(msg["tool_calls"][0]["function"]["arguments"]) == {"a": 1}


def test_function_tool_shape():
    t = chat.function_tool("f", "does f", {"type": "object", "properties": {}})
    assert t["type"] == "function"
    assert t["function"]["name"] == "f"
    assert t["function"]["parameters"]["type"] == "object"
