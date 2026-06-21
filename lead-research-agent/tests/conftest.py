"""Fixtures and fakes for lead-research tests (no network, no API keys)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from lumifie_core import CompletionResult, ToolCall

from lead_research.backends import SearchResult
from lead_research.config import LeadSettings
from lead_research.icp import DEFAULT_ICP

_USAGE = {"input_tokens": 150, "output_tokens": 60, "total_tokens": 210}

# Canned structured outputs per sub-agent, keyed by tool name.
_OUTPUTS: dict[str, dict[str, Any]] = {
    "enrichment": {
        "company_name": "Acme Analytics",
        "industry": "B2B SaaS",
        "value_proposition": "Warehouse-native product analytics for mid-market teams.",
        "recent_news": ["Raised a $20M Series B", "Launched an AI insights feature"],
        "key_executives": [{"name": "Jane Doe", "title": "CEO"}],
        "summary": "Mid-market analytics vendor with fresh funding.",
    },
    "icp_score": {
        "fit_score": 82,
        "tier": "Strong",
        "reasoning": "B2B SaaS, 50-200 employees, VP Eng persona — matches the ICP well.",
        "matched_criteria": ["B2B SaaS", "mid-market size"],
        "gaps": ["pricing unclear"],
        "disqualified": False,
    },
    "outreach": {
        "email_subject": "Congrats on the Series B, Acme",
        "email_body": "Hi Jane — saw Acme just raised a $20M Series B...",
        "linkedin_message": "Hi Jane, congrats on the raise — would love to connect.",
        "personalization_signals": ["Series B raise", "AI insights launch"],
    },
}


def _which(system: str) -> str:
    if "research analyst" in system:
        return "enrichment"
    if "qualification" in system:
        return "icp_score"
    return "outreach"


class FakeToolProvider:
    supports_tools = True

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        name = kwargs["tool_choice"]["function"]["name"]
        return CompletionResult(
            text=None,
            tool_calls=[ToolCall(id=f"c{self.calls}", name=name, arguments=_OUTPUTS[name])],
            finish_reason="tool_calls",
            usage=_USAGE,
        )


class FakeJSONProvider:
    supports_tools = False

    def __init__(self, model: str = "ollama/llama3.1") -> None:
        self.model = model
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        key = _which(messages[0]["content"])
        return CompletionResult(text=json.dumps(_OUTPUTS[key]), finish_reason="stop", usage=_USAGE)


class FakeSearch:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        return [SearchResult(title="News", url="https://news.example.com/acme", snippet="Acme raised $20M.")]


class FakeReader:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def read(self, url: str) -> str:
        self.urls.append(url)
        return "Acme Analytics — warehouse-native product analytics for mid-market teams."


@pytest.fixture
def tool_provider() -> FakeToolProvider:
    return FakeToolProvider()


@pytest.fixture
def json_provider() -> FakeJSONProvider:
    return FakeJSONProvider()


@pytest.fixture
def fake_search() -> FakeSearch:
    return FakeSearch()


@pytest.fixture
def fake_reader() -> FakeReader:
    return FakeReader()


@pytest.fixture
def settings() -> LeadSettings:
    return LeadSettings(model="claude-opus-4-8", max_searches=2, results_per_search=2)


@pytest.fixture
def icp():
    return DEFAULT_ICP
