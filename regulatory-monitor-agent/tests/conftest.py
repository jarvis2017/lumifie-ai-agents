"""Fixtures and fakes for reg-monitor tests (no network, no API keys)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from lumifie_core import CompletionResult, ToolCall

from reg_monitor.config import MonitorSettings
from reg_monitor.models import BusinessProfile, Source, SourceType
from reg_monitor.schemas import ANALYZE_TOOL, PLAN_TOOL
from reg_monitor.sources import FeedItem, SearchResult

_USAGE = {"input_tokens": 300, "output_tokens": 120, "total_tokens": 420}

# Canned plan + impacts the fake provider returns.
CANNED_PLAN = {
    "search_queries": [
        "California food safety regulation 2026",
        "California restaurant minimum wage update",
    ],
    "source_focus": ["food safety", "minimum wage"],
    "rationale": "Focus on California wage and food-safety obligations.",
}

WAGE_URL = "https://example.gov/ca/min-wage-2026"
SAFETY_URL = "https://example.gov/ca/food-safety-2026"
FEED_URL = "https://example.gov/ca/feed-item-1"
IRRELEVANT_URL = "https://example.gov/unrelated/forestry"


def _impact(url: str, title: str, relevance: str = "high") -> dict[str, Any]:
    return {
        "url": url,
        "title": title,
        "plain_english": f"What {title} means for a California food-service business.",
        "relevance": relevance,
        "recommended_action": "Review payroll and update notices accordingly.",
    }


class FakeSearch:
    """Deterministic search backend; records queries and the after_date used."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.queries: list[str] = []
        self.after_dates: list[str | None] = []
        self._results = results

    def search(
        self, query: str, max_results: int = 5, after_date: str | None = None
    ) -> list[SearchResult]:
        self.queries.append(query)
        self.after_dates.append(after_date)
        if self._results is not None:
            return list(self._results)
        return [
            SearchResult(
                title="California minimum wage rises",
                url=WAGE_URL,
                snippet="The state raised the minimum wage for food-service workers.",
                date="2026-06-16",
            )
        ]


class FakeFeed:
    """Deterministic feed backend; records fetched urls."""

    def __init__(self, items: list[FeedItem] | None = None) -> None:
        self.urls: list[str] = []
        self._items = items

    def fetch(self, url: str) -> list[FeedItem]:
        self.urls.append(url)
        if self._items is not None:
            return list(self._items)
        return [
            FeedItem(
                title="New health inspection guidance",
                url=FEED_URL,
                summary="Updated inspection checklist for restaurants.",
                published="2026-06-17",
            )
        ]


class FakeProvider:
    """Tool-supporting provider: returns the plan, then impact statements.

    Routes by the tool name present in the request (PLAN_TOOL vs ANALYZE_TOOL),
    mirroring how BaseAgent.structured forces a single tool call.
    """

    supports_tools = True

    def __init__(self, model: str = "claude-opus-4-8", impacts: list[dict] | None = None) -> None:
        self.model = model
        self.calls = 0
        self.seen_tools: list[str] = []
        self._impacts = impacts if impacts is not None else [
            _impact(WAGE_URL, "the minimum wage increase", "high"),
            _impact(FEED_URL, "the health inspection guidance", "medium"),
        ]

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        self.calls += 1
        tools = kwargs.get("tools") or []
        names = {t["function"]["name"] for t in tools}
        if PLAN_TOOL in names:
            self.seen_tools.append(PLAN_TOOL)
            return CompletionResult(
                text=None,
                tool_calls=[ToolCall("p1", PLAN_TOOL, CANNED_PLAN)],
                finish_reason="tool_calls",
                usage=_USAGE,
            )
        if ANALYZE_TOOL in names:
            self.seen_tools.append(ANALYZE_TOOL)
            return CompletionResult(
                text=None,
                tool_calls=[ToolCall("a1", ANALYZE_TOOL, {"impacts": self._impacts})],
                finish_reason="tool_calls",
                usage=_USAGE,
            )
        return CompletionResult(text="{}", finish_reason="stop", usage=_USAGE)


class FakeJSONProvider:
    """Provider without tool support; returns JSON for plan then analysis."""

    supports_tools = False

    def __init__(self, model: str = "ollama/llama3.1") -> None:
        self.model = model
        self.calls = 0

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        self.calls += 1
        # First structured call is the plan, second is the analysis.
        if self.calls == 1:
            return CompletionResult(text=json.dumps(CANNED_PLAN), finish_reason="stop", usage=_USAGE)
        payload = {"impacts": [_impact(WAGE_URL, "the minimum wage increase", "high")]}
        return CompletionResult(text=json.dumps(payload), finish_reason="stop", usage=_USAGE)


@pytest.fixture
def profile() -> BusinessProfile:
    return BusinessProfile(
        industry="food service",
        location="California, USA",
        operational_keywords=["food safety", "labor law", "minimum wage"],
        business_description="A Bay Area fast-casual restaurant chain.",
    )


@pytest.fixture
def sources() -> list[Source]:
    return [
        Source(type=SourceType.GOV, value="https://example.gov/ca/labor", label="CA Labor"),
        Source(type=SourceType.RSS, value="https://example.gov/ca/rss.xml", label="CA News"),
    ]


@pytest.fixture
def fake_search() -> FakeSearch:
    return FakeSearch()


@pytest.fixture
def fake_feed() -> FakeFeed:
    return FakeFeed()


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def json_provider() -> FakeJSONProvider:
    return FakeJSONProvider()


@pytest.fixture
def settings() -> MonitorSettings:
    return MonitorSettings(
        model="claude-opus-4-8",
        lookback_days=7,
        max_queries=6,
        results_per_search=5,
        max_findings=40,
    )
