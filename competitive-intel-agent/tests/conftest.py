"""Fixtures and fakes for competitive-intel tests (no network, no API keys)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from lumifie_core import CompletionResult, ToolCall

from competitive_intel.config import CompetitiveSettings
from competitive_intel.search import SearchResult

_USAGE = {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280}


class FakeSearch:
    """Deterministic search backend that records queries."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        return [
            SearchResult(
                title=f"Result for {query}",
                url=f"https://example.com/{len(self.queries)}",
                snippet="Competitor X offers a self-serve tier at $20/mo.",
            )
        ]


class FakeToolProvider:
    """Provider with tool support: searches twice, records, then finalizes."""

    supports_tools = True

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self.calls = 0
        self._uid = 0

    def _id(self) -> str:
        self._uid += 1
        return f"call_{self._uid}"

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        self.calls += 1
        # Turn 1: search. Turn 2 (after tool results): record + finalize.
        if self.calls == 1:
            tcs = [ToolCall(self._id(), "web_search", {"query": "competitors", "max_results": 3})]
            return CompletionResult(text=None, tool_calls=tcs, finish_reason="tool_calls", usage=_USAGE)
        if self.calls == 2:
            tcs = [
                ToolCall(
                    self._id(),
                    "record_competitor",
                    {
                        "name": "Competitor X",
                        "positioning": "Self-serve analytics",
                        "pricing": "$20/mo",
                        "strengths": ["price"],
                        "weaknesses": ["depth"],
                        "source_url": "https://example.com/x",
                    },
                ),
                ToolCall(
                    self._id(),
                    "record_threat",
                    {
                        "severity": "high",
                        "competitor": "Competitor X",
                        "description": "Aggressive pricing.",
                        "recommendation": "Differentiate on support.",
                    },
                ),
                ToolCall(
                    self._id(),
                    "finalize_brief",
                    {
                        "overall_threat_level": "high",
                        "market_summary": "Competitive low end.",
                        "executive_summary": "One aggressive challenger on price.",
                    },
                ),
            ]
            return CompletionResult(text=None, tool_calls=tcs, finish_reason="tool_calls", usage=_USAGE)
        return CompletionResult(text="done", finish_reason="stop", usage=_USAGE)


class FakeJSONProvider:
    """Provider without tool support; returns a synthesis JSON object."""

    supports_tools = False

    def __init__(self, model: str = "ollama/llama3.1") -> None:
        self.model = model
        self.calls = 0

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        self.calls += 1
        payload = {
            "competitors": [
                {
                    "name": "Competitor Y",
                    "positioning": "Enterprise analytics",
                    "pricing": "Quote-based",
                    "strengths": ["brand"],
                    "weaknesses": ["price"],
                    "source_url": None,
                }
            ],
            "threats": [
                {
                    "severity": "medium",
                    "competitor": "Competitor Y",
                    "description": "Strong brand.",
                    "recommendation": "Compete on time-to-value.",
                }
            ],
            "overall_threat_level": "medium",
            "market_summary": "Two-tier market.",
            "executive_summary": "Manageable competition.",
        }
        return CompletionResult(text=json.dumps(payload), finish_reason="stop", usage=_USAGE)


@pytest.fixture
def fake_search() -> FakeSearch:
    return FakeSearch()


@pytest.fixture
def tool_provider() -> FakeToolProvider:
    return FakeToolProvider()


@pytest.fixture
def json_provider() -> FakeJSONProvider:
    return FakeJSONProvider()


@pytest.fixture
def settings() -> CompetitiveSettings:
    return CompetitiveSettings(
        model="claude-opus-4-8",
        max_searches=5,
        max_competitors=8,
        max_iterations=8,
        results_per_search=3,
    )
