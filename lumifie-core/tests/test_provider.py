"""Tests for the litellm-backed provider abstraction."""

from __future__ import annotations

import litellm
import pytest
from conftest import RecordingCompletion, make_response

from lumifie_core.provider import (
    LLMProvider,
    model_supports_tools,
    resolve_model,
)


def test_alias_resolution():
    assert resolve_model("claude") == "claude-opus-4-8"
    assert resolve_model(None) == "claude-opus-4-8"
    assert resolve_model("gpt-4o") == "gpt-4o"
    assert resolve_model("ollama/llama3.1") == "ollama/llama3.1"


def test_tool_capability_detection():
    assert model_supports_tools("claude-opus-4-8") is True
    assert model_supports_tools("gpt-4o") is True
    assert model_supports_tools("ollama/llama3.1") is False
    assert model_supports_tools("ollama_chat/qwen2.5") is False


def test_complete_normalizes_text_and_usage():
    fake = RecordingCompletion([make_response(content="hello", prompt_tokens=12, completion_tokens=3)])
    provider = LLMProvider("gpt-4o", completion_fn=fake)
    result = provider.complete([{"role": "user", "content": "hi"}])
    assert result.text == "hello"
    assert result.finish_reason == "stop"
    assert result.usage == {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}


def test_complete_parses_tool_calls():
    fake = RecordingCompletion(
        [
            make_response(
                tool_calls=[{"id": "call_1", "name": "do_thing", "arguments": '{"x": 1, "y": "z"}'}],
                finish_reason="tool_calls",
            )
        ]
    )
    provider = LLMProvider("claude", completion_fn=fake)
    result = provider.complete([{"role": "user", "content": "go"}], tools=[{"type": "function"}])
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.id == "call_1"
    assert tc.name == "do_thing"
    assert tc.arguments == {"x": 1, "y": "z"}
    # Tools were forwarded because the model supports them.
    assert "tools" in fake.calls[0]
    assert fake.calls[0]["tool_choice"] == "auto"


def test_tools_dropped_for_non_tool_models():
    fake = RecordingCompletion([make_response(content='{"ok": true}')])
    provider = LLMProvider("ollama/llama3.1", completion_fn=fake)
    assert provider.supports_tools is False
    provider.complete(
        [{"role": "user", "content": "extract"}],
        tools=[{"type": "function"}],
        response_format={"type": "json_object"},
    )
    # tools are NOT forwarded; response_format is.
    assert "tools" not in fake.calls[0]
    assert fake.calls[0]["response_format"] == {"type": "json_object"}


def test_malformed_tool_arguments_become_empty_dict():
    fake = RecordingCompletion(
        [make_response(tool_calls=[{"id": "c", "name": "f", "arguments": "not json"}])]
    )
    provider = LLMProvider("gpt-4o", completion_fn=fake)
    result = provider.complete([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
    assert result.tool_calls[0].arguments == {}


def test_retries_then_succeeds():
    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise litellm.exceptions.RateLimitError("slow down", model="gpt-4o", llm_provider="openai")
        return make_response(content="recovered")

    provider = LLMProvider("gpt-4o", max_retries=5, completion_fn=flaky)
    result = provider.complete([{"role": "user", "content": "hi"}])
    assert result.text == "recovered"
    assert calls["n"] == 3


def test_temperature_only_sent_when_set():
    fake = RecordingCompletion([make_response(content="ok"), make_response(content="ok")])
    LLMProvider("gpt-4o", completion_fn=fake).complete([{"role": "user", "content": "a"}])
    assert "temperature" not in fake.calls[0]

    fake2 = RecordingCompletion([make_response(content="ok")])
    LLMProvider("gpt-4o", temperature=0.5, completion_fn=fake2).complete(
        [{"role": "user", "content": "a"}]
    )
    assert fake2.calls[0]["temperature"] == 0.5


def test_bad_request_is_not_retried():
    calls = {"n": 0}

    def bad(**kwargs):
        calls["n"] += 1
        raise litellm.exceptions.BadRequestError("nope", model="gpt-4o", llm_provider="openai")

    provider = LLMProvider("gpt-4o", max_retries=5, completion_fn=bad)
    with pytest.raises(litellm.exceptions.BadRequestError):
        provider.complete([{"role": "user", "content": "x"}])
    assert calls["n"] == 1
