"""End-to-end tests of the research agent against fakes (no network)."""

from __future__ import annotations

from competitive_intel.agent import CompetitiveIntelAgent
from competitive_intel.models import IntelReport, ThreatLevel


def test_tool_path_runs_end_to_end(tool_provider, fake_search, settings):
    agent = CompetitiveIntelAgent(tool_provider, settings, fake_search)
    report = agent.run("Acme", "project management SaaS")

    assert isinstance(report, IntelReport)
    assert report.company == "Acme"
    assert report.overall_threat_level is ThreatLevel.HIGH
    assert len(report.competitors) == 1
    assert report.competitors[0].name == "Competitor X"
    assert len(report.threats) == 1
    # The agent actually performed a search and captured the source.
    assert fake_search.queries == ["competitors"]
    assert any("example.com" in s for s in report.sources)
    assert report.token_usage["input_tokens"] > 0


def test_tool_path_is_agentic_loop(tool_provider, fake_search, settings):
    CompetitiveIntelAgent(tool_provider, settings, fake_search).run("Acme", "SaaS")
    # search turn + record/finalize turn = at least 2 model calls.
    assert tool_provider.calls >= 2


def test_json_fallback_runs_fixed_queries(json_provider, fake_search, settings):
    agent = CompetitiveIntelAgent(json_provider, settings, fake_search)
    report = agent.run("Acme", "SaaS")

    # Fixed-query research pass ran several searches, then ONE synthesis call.
    assert len(fake_search.queries) >= 1
    assert json_provider.calls == 1
    assert report.overall_threat_level is ThreatLevel.MEDIUM
    assert report.competitors[0].name == "Competitor Y"
    assert report.model == "ollama/llama3.1"


def test_search_budget_is_capped(tool_provider, fake_search):
    from competitive_intel.config import CompetitiveSettings

    tight = CompetitiveSettings(model="claude-opus-4-8", max_searches=0, max_iterations=4)
    agent = CompetitiveIntelAgent(tool_provider, tight, fake_search)
    # With a zero search budget, the web_search tool refuses without calling search.
    text, finalized = agent._handle_tool_call("web_search", {"query": "x"})
    assert "budget" in text.lower()
    assert fake_search.queries == []
    assert finalized is False


def test_competitor_dedup_and_cap(tool_provider, fake_search, settings):
    agent = CompetitiveIntelAgent(tool_provider, settings, fake_search)
    payload = {
        "name": "Dup",
        "positioning": "p",
        "pricing": "Unknown",
        "strengths": [],
        "weaknesses": [],
        "source_url": None,
    }
    assert agent._add_competitor(payload) == "Competitor recorded."
    assert agent._add_competitor(payload) == "Competitor already recorded."
    assert len(agent._competitors) == 1
