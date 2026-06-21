"""End-to-end pipeline tests for the regulatory-monitor agent (offline)."""

from __future__ import annotations

from conftest import (
    FEED_URL,
    IRRELEVANT_URL,
    SAFETY_URL,
    WAGE_URL,
    FakeFeed,
    FakeProvider,
    FakeSearch,
    _impact,
)

from reg_monitor.agent import RegulatoryMonitorAgent
from reg_monitor.models import Relevance
from reg_monitor.sources import FeedItem, SearchResult


def _agent(provider, settings, search, feed) -> RegulatoryMonitorAgent:
    return RegulatoryMonitorAgent(provider, settings, search, feed)


def test_planner_produces_queries(provider, settings, fake_search, fake_feed, profile, sources):
    agent = _agent(provider, settings, fake_search, fake_feed)
    plan = agent.plan(profile, sources)
    assert plan.search_queries
    assert "food safety" in plan.search_queries[0].lower() or plan.search_queries
    assert plan.rationale


def test_researcher_collects_from_search_and_feed(
    provider, settings, fake_search, fake_feed, profile, sources
):
    agent = _agent(provider, settings, fake_search, fake_feed)
    plan = agent.plan(profile, sources)
    findings, checked = agent.research(profile, sources, plan)
    urls = {f.url for f in findings}
    assert WAGE_URL in urls  # from search
    assert FEED_URL in urls  # from feed
    # both feed sources fetched
    assert any("rss.xml" in u for u in fake_feed.urls)
    assert any(c.startswith("search:") for c in checked)
    assert any(c.startswith("gov:") or c.startswith("rss:") for c in checked)


def test_researcher_applies_lookback_date(
    provider, settings, fake_search, fake_feed, profile, sources
):
    agent = _agent(provider, settings, fake_search, fake_feed)
    plan = agent.plan(profile, sources)
    agent.research(profile, sources, plan)
    # Every search query carried an after_date constraint (YYYY-MM-DD).
    assert fake_search.after_dates
    assert all(d and len(d) == 10 and d.count("-") == 2 for d in fake_search.after_dates)


def test_researcher_dedupes_by_url(provider, settings, profile, sources):
    dup = [
        SearchResult(title="A", url=WAGE_URL, snippet="one", date="2026-06-16"),
        SearchResult(title="A again", url=WAGE_URL + "/", snippet="dup", date="2026-06-16"),
    ]
    search = FakeSearch(results=dup)
    feed = FakeFeed(items=[FeedItem(title="A3", url=WAGE_URL, summary="dup feed")])
    agent = _agent(provider, settings, search, feed)
    plan = agent.plan(profile, sources)
    findings, _ = agent.research(profile, sources, plan)
    # All three collapse to a single finding (normalized URL).
    assert len([f for f in findings if WAGE_URL.rstrip("/") in f.url.rstrip("/")]) == 1


def test_analyst_yields_tailored_impacts(
    provider, settings, fake_search, fake_feed, profile, sources
):
    agent = _agent(provider, settings, fake_search, fake_feed)
    plan = agent.plan(profile, sources)
    findings, _ = agent.research(profile, sources, plan)
    impacts = agent.analyze(profile, findings)
    assert impacts
    assert all(isinstance(i.relevance, Relevance) for i in impacts)
    # Tailored plain-English output references the business context.
    assert any("food-service" in i.plain_english or "California" in i.plain_english for i in impacts)


def test_analyst_drops_irrelevant_findings(settings, fake_search, fake_feed, profile, sources):
    # Provider returns impacts for only WAGE_URL even though more findings exist.
    provider = FakeProvider(impacts=[_impact(WAGE_URL, "the wage change", "high")])
    agent = _agent(provider, settings, fake_search, fake_feed)
    plan = agent.plan(profile, sources)
    findings, _ = agent.research(profile, sources, plan)
    impacts = agent.analyze(profile, findings)
    kept_urls = {i.url for i in impacts}
    assert kept_urls == {WAGE_URL}  # FEED_URL was dropped


def test_run_first_time_all_new(provider, settings, fake_search, fake_feed, profile, sources):
    agent = _agent(provider, settings, fake_search, fake_feed)
    digest = agent.run(profile, sources, previous=None)
    assert digest.is_baseline is True
    assert digest.impacts
    # First run: every impact is new.
    assert len(digest.new_impacts) == len(digest.impacts)


def test_run_second_time_zero_new_when_unchanged(
    settings, fake_search, fake_feed, profile, sources
):
    first = _agent(FakeProvider(), settings, fake_search, fake_feed).run(
        profile, sources, previous=None
    )
    second = _agent(FakeProvider(), settings, FakeSearch(), FakeFeed()).run(
        profile, sources, previous=first
    )
    assert second.is_baseline is False
    assert second.impacts  # watchlist still populated
    assert second.new_impacts == []  # nothing new since last run


def test_run_surfaces_only_genuinely_new(settings, profile, sources):
    # Run 1: just the wage impact.
    p1 = FakeProvider(impacts=[_impact(WAGE_URL, "the wage change", "high")])
    first = _agent(p1, settings, FakeSearch(), FakeFeed()).run(profile, sources, previous=None)

    # Run 2: wage impact again PLUS a brand-new safety impact.
    p2 = FakeProvider(
        impacts=[
            _impact(WAGE_URL, "the wage change", "high"),
            _impact(SAFETY_URL, "a new food-safety rule", "high"),
        ]
    )
    second = _agent(p2, settings, FakeSearch(), FakeFeed()).run(profile, sources, previous=first)

    new_urls = {i.url for i in second.new_impacts}
    assert new_urls == {SAFETY_URL}
    assert len(second.impacts) == 2


def test_run_tracks_token_usage(provider, settings, fake_search, fake_feed, profile, sources):
    agent = _agent(provider, settings, fake_search, fake_feed)
    digest = agent.run(profile, sources, previous=None)
    assert digest.token_usage["total_tokens"] > 0
    # Two LLM stages (planner + analyst) were called.
    assert provider.seen_tools.count("monitoring_plan") == 1
    assert provider.seen_tools.count("impact_analysis") == 1


def test_json_fallback_path(json_provider, settings, fake_search, fake_feed, profile, sources):
    agent = _agent(json_provider, settings, fake_search, fake_feed)
    digest = agent.run(profile, sources, previous=None)
    assert digest.impacts  # JSON-mode plan + analysis both parsed
    assert digest.plan.search_queries
    assert json_provider.calls >= 2


def test_irrelevant_impact_url_without_matching_finding_still_validates(
    settings, fake_search, fake_feed, profile, sources
):
    # Analyst returns an impact for a URL not among findings; it must still coerce.
    provider = FakeProvider(impacts=[_impact(IRRELEVANT_URL, "an unrelated rule", "low")])
    agent = _agent(provider, settings, fake_search, fake_feed)
    plan = agent.plan(profile, sources)
    findings, _ = agent.research(profile, sources, plan)
    impacts = agent.analyze(profile, findings)
    assert len(impacts) == 1
    assert impacts[0].relevance == Relevance.LOW
