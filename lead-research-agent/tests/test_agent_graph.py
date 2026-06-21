"""End-to-end tests of the LangGraph lead-research pipeline (no network)."""

from __future__ import annotations

from lead_research.agent import LeadResearchAgent
from lead_research.models import LeadReport
from lead_research.report import render_json, render_markdown


def test_pipeline_runs_all_three_subagents(tool_provider, fake_search, fake_reader, settings, icp):
    agent = LeadResearchAgent(tool_provider, settings, icp, fake_search, fake_reader)
    report = agent.run("https://acme.com")

    assert isinstance(report, LeadReport)
    # Scraper read the page; matcher + copywriter ran.
    assert fake_reader.urls == ["https://acme.com"]
    assert fake_search.queries  # searches were issued
    assert tool_provider.calls == 3  # enrich + score + copy

    assert report.enrichment.company_name == "Acme Analytics"
    assert report.icp_score.fit_score == 82
    assert report.icp_score.tier == "Strong"
    assert report.outreach.email_subject.startswith("Congrats")
    assert report.token_usage["input_tokens"] > 0
    # Sources merged from page + search via the LangGraph reducer.
    assert "https://acme.com" in report.sources
    assert any("news.example.com" in s for s in report.sources)


def test_json_fallback_pipeline(json_provider, fake_search, fake_reader, settings, icp):
    agent = LeadResearchAgent(json_provider, settings, icp, fake_search, fake_reader)
    report = agent.run("https://acme.com")
    assert json_provider.calls == 3
    assert report.model == "ollama/llama3.1"
    assert report.icp_score.fit_score == 82
    assert report.enrichment.value_proposition.startswith("Warehouse-native")


def test_output_renders(tool_provider, fake_search, fake_reader, settings, icp):
    agent = LeadResearchAgent(tool_provider, settings, icp, fake_search, fake_reader)
    report = agent.run("https://acme.com")

    md = render_markdown(report)
    assert "# Lead Research — Acme Analytics" in md
    assert "## ICP Fit" in md
    assert "## Outreach" in md

    import json

    data = json.loads(render_json(report))
    assert data["icp_name"] == icp.name
    assert data["outreach"]["linkedin_message"]


def test_coerce_falls_back_on_garbage(tool_provider, fake_search, fake_reader, settings, icp):
    agent = LeadResearchAgent(tool_provider, settings, icp, fake_search, fake_reader)
    from lead_research.models import Enrichment

    fallback = Enrichment(company_name="x", value_proposition="y")
    assert agent._coerce(Enrichment, None, fallback) is fallback
    assert agent._coerce(Enrichment, {"bad": "data"}, fallback) is fallback
    good = agent._coerce(Enrichment, {"company_name": "Z", "value_proposition": "vp"}, fallback)
    assert good.company_name == "Z"
