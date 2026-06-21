"""Tests for models and report rendering."""

from __future__ import annotations

import json

from competitive_intel.diff import diff_reports
from competitive_intel.models import (
    Change,
    ChangeKind,
    Competitor,
    IntelReport,
    Threat,
    ThreatLevel,
)
from competitive_intel.report import render_json, render_markdown

T = ThreatLevel


def _report() -> IntelReport:
    return IntelReport(
        company="Acme",
        vertical="SaaS",
        model="claude-opus-4-8",
        overall_threat_level=T.HIGH,
        market_summary="Consolidating market.",
        executive_summary="Rising pressure from a new entrant.",
        competitors=[
            Competitor(name="Alpha", positioning="Leader", pricing="$50k/yr", strengths=["brand"]),
        ],
        threats=[
            Threat(severity=T.LOW, competitor="Alpha", description="minor", recommendation="watch"),
            Threat(severity=T.CRITICAL, competitor="Beta", description="major", recommendation="act"),
        ],
        sources=["https://example.com/a"],
        token_usage={"input_tokens": 100, "output_tokens": 20},
    )


def test_threats_sorted_most_severe_first():
    ordered = _report().threats_by_severity()
    assert [t.severity for t in ordered] == [T.CRITICAL, T.LOW]


def test_render_json_includes_report_and_changes():
    report = _report()
    changes = [Change(kind=ChangeKind.NEW_COMPETITOR, competitor="Beta", summary="new")]
    data = json.loads(render_json(report, changes))
    assert data["report"]["company"] == "Acme"
    assert data["report"]["overall_threat_level"] == "high"
    assert len(data["changes"]) == 1
    assert data["changes"][0]["kind"] == "new_competitor"


def test_render_markdown_sections_and_ordering():
    md = render_markdown(_report(), [])
    assert "# Competitive Intelligence Brief — Acme" in md
    assert "## What Changed Since Last Run" in md
    assert "baseline" in md  # no changes -> baseline note
    assert "## Competitors" in md
    assert "| Competitor |" in md
    # Critical threat appears before the low one.
    assert md.index("major") < md.index("minor")


def test_render_markdown_shows_change_log():
    prev = IntelReport(
        company="Acme", vertical="SaaS", model="claude-opus-4-8",
        overall_threat_level=T.LOW, market_summary="m", executive_summary="s",
        competitors=[Competitor(name="Alpha", positioning="Leader", pricing="$40k/yr")],
    )
    curr = _report()
    changes = diff_reports(prev, curr)
    md = render_markdown(curr, changes)
    assert "baseline" not in md
    assert "pricing change" in md or "overall threat change" in md
