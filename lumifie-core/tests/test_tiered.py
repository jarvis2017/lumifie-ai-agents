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
