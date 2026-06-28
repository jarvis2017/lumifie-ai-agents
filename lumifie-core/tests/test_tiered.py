"""Tests for the two-tier LLM façade (offline; fake providers)."""

from __future__ import annotations

from typing import Any

import pytest

from lumifie_core import TieredLLM
from lumifie_core.provider import CompletionResult, resolve_model


class _FakeProvider:
    supports_tools = True

    def __init__(self, label: str) -> None:
        self.model = label
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return CompletionResult(
            text=f"{self.model}:reply",
            usage={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        )


def _tiered():
    return TieredLLM(quality=_FakeProvider("quality"), fast=_FakeProvider("fast"))


def test_alias_resolution_for_tiers():
    assert resolve_model("fast") == "openrouter/google/gemini-2.0-flash-exp:free"
    assert resolve_model("llama-free") == "openrouter/meta-llama/llama-3.1-8b-instruct:free"
    assert resolve_model("claude") == "claude-opus-4-8"


def test_call_routes_to_correct_tier():
    llm = _tiered()
    assert llm.call("hi", tier="quality") == "quality:reply"
    assert llm.call("hi", tier="fast") == "fast:reply"
    assert llm.quality.calls and not llm.fast.calls[1:]  # both used appropriately


def test_default_tier_is_fast():
    llm = _tiered()
    assert llm.call("hi") == "fast:reply"


def test_system_prompt_is_prepended():
    llm = _tiered()
    llm.call("question", tier="quality", system="be terse")
    msgs = llm.quality.calls[0]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == "be terse"
    assert msgs[-1]["content"] == "question"


def test_usage_tracked_per_tier():
    llm = _tiered()
    llm.call("a", tier="quality")
    llm.call("b", tier="fast")
    llm.call("c", tier="fast")
    assert llm.usage["quality"]["total_tokens"] == 7
    assert llm.usage["fast"]["total_tokens"] == 14
    assert llm.total_usage()["total_tokens"] == 21


def test_invalid_tier_raises():
    with pytest.raises(ValueError, match="tier"):
        _tiered().call("x", tier="medium")


def test_openrouter_missing_credential(monkeypatch):
    from lumifie_core.provider import missing_credential

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert missing_credential("openrouter/google/gemini-2.0-flash-exp:free") == "OPENROUTER_API_KEY"
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    assert missing_credential("openrouter/google/gemini-2.0-flash-exp:free") is None


def test_nvidia_override_routes_quality_to_nvidia(monkeypatch):
    from lumifie_core.tiered import NVIDIA_BUILD_BASE, NVIDIA_QUALITY_MODEL

    monkeypatch.setenv("NVIDIA_BUILD_API", "nv-secret")
    llm = TieredLLM(quality_model="claude-opus-4-8", fast=_FakeProvider("fast"))
    assert llm.quality.model == NVIDIA_QUALITY_MODEL
    assert llm.quality.api_base == NVIDIA_BUILD_BASE
    assert llm.quality.api_key == "nv-secret"


def test_no_nvidia_override_uses_default_quality(monkeypatch):
    monkeypatch.delenv("NVIDIA_BUILD_API", raising=False)
    llm = TieredLLM(quality_model="claude-opus-4-8", fast=_FakeProvider("fast"))
    assert llm.quality.model == "claude-opus-4-8"
    assert llm.quality.api_base is None


def test_api_base_and_key_forwarded_to_completion():
    from lumifie_core.provider import LLMProvider

    seen: dict[str, Any] = {}

    def fake_completion(**kwargs):
        seen.update(kwargs)

        class _R:
            choices = [type("C", (), {"message": type("M", (), {"content": "ok", "tool_calls": []}),
                                      "finish_reason": "stop"})]
            usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})

        return _R()

    p = LLMProvider("openai/meta/llama-3.3-70b-instruct", api_base="https://x/v1", api_key="k",
                    completion_fn=fake_completion)
    p.complete([{"role": "user", "content": "hi"}])
    assert seen["api_base"] == "https://x/v1"
    assert seen["api_key"] == "k"
