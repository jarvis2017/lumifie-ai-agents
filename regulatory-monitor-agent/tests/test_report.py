"""Tests for the Markdown + JSON report rendering and the example config."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import SAFETY_URL, WAGE_URL, _impact

from reg_monitor.loader import load_config
from reg_monitor.models import (
    BusinessProfile,
    Digest,
    ImpactStatement,
    MonitoringPlan,
)
from reg_monitor.report import render_json, render_markdown


def _imp(url: str, title: str, rel: str = "high") -> ImpactStatement:
    return ImpactStatement.model_validate(_impact(url, title, rel))


def _digest(*, baseline: bool, new: list[ImpactStatement], impacts: list[ImpactStatement]) -> Digest:
    return Digest(
        profile=BusinessProfile(
            industry="food service",
            location="California, USA",
            operational_keywords=["food safety", "minimum wage"],
        ),
        model="claude-opus-4-8",
        lookback_days=7,
        plan=MonitoringPlan(search_queries=["q1"], source_focus=["food safety"], rationale="r"),
        impacts=impacts,
        new_impacts=new,
        sources_checked=["search: q1", "rss: CA News"],
        is_baseline=baseline,
        token_usage={"input_tokens": 1000, "output_tokens": 200, "total_tokens": 1200},
    )


def test_markdown_has_new_and_watchlist_sections():
    wage = _imp(WAGE_URL, "Wage increase", "high")
    safety = _imp(SAFETY_URL, "Safety rule", "medium")
    md = render_markdown(_digest(baseline=False, new=[safety], impacts=[wage, safety]))
    assert "# Regulatory Digest" in md
    assert "🆕 New This Week" in md
    assert "Full Watchlist" in md
    assert "Sources Checked" in md
    assert "Safety rule" in md  # the new item appears in the new section
    assert "last 7 day(s)" in md


def test_markdown_baseline_note():
    wage = _imp(WAGE_URL, "Wage increase", "high")
    md = render_markdown(_digest(baseline=True, new=[wage], impacts=[wage]))
    assert "baseline run" in md.lower()


def test_markdown_no_new_message():
    wage = _imp(WAGE_URL, "Wage increase", "high")
    md = render_markdown(_digest(baseline=False, new=[], impacts=[wage]))
    assert "No new regulatory changes" in md


def test_new_section_sorted_by_relevance():
    low = _imp(WAGE_URL, "Low item", "low")
    high = _imp(SAFETY_URL, "High item", "high")
    md = render_markdown(_digest(baseline=False, new=[low, high], impacts=[low, high]))
    # High-relevance item must render before the low one in the New section.
    assert md.index("High item") < md.index("Low item")


def test_json_mirrors_markdown_structure():
    wage = _imp(WAGE_URL, "Wage increase", "high")
    safety = _imp(SAFETY_URL, "Safety rule", "medium")
    payload = json.loads(render_json(_digest(baseline=False, new=[safety], impacts=[wage, safety])))
    assert payload["business"]["industry"] == "food service"
    assert payload["lookback_days"] == 7
    assert [i["url"] for i in payload["new_this_week"]] == [SAFETY_URL]
    assert len(payload["full_watchlist"]) == 2
    assert payload["sources_checked"]
    # Watchlist sorted by relevance (high before medium).
    assert payload["full_watchlist"][0]["relevance"] == "high"


def test_example_config_loads_and_is_realistic():
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "profile.example.json"
    cfg = load_config(cfg_path)
    assert cfg.profile.industry
    assert cfg.profile.operational_keywords
    assert len(cfg.sources) >= 2
    types = {s.type.value for s in cfg.sources}
    assert "rss" in types  # at least one RSS feed
