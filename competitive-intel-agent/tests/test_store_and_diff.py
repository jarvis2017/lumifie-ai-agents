"""Tests for SQLite persistence and run-over-run diffing."""

from __future__ import annotations

from competitive_intel.diff import diff_reports
from competitive_intel.models import (
    ChangeKind,
    Competitor,
    IntelReport,
    ThreatLevel,
)
from competitive_intel.store import IntelStore

T = ThreatLevel


def _report(level=T.MEDIUM, competitors=None, summary="s") -> IntelReport:
    return IntelReport(
        company="Acme",
        vertical="SaaS",
        model="claude-opus-4-8",
        overall_threat_level=level,
        market_summary="m",
        executive_summary=summary,
        competitors=competitors or [],
    )


def test_store_roundtrip_and_latest(tmp_path):
    db = tmp_path / "t.db"
    with IntelStore(db) as store:
        assert store.latest("Acme", "SaaS") is None
        store.save(_report(summary="first"))
        store.save(_report(summary="second"))
        latest = store.latest("Acme", "SaaS")
        assert latest is not None
        assert latest.executive_summary == "second"
        assert store.count("Acme", "SaaS") == 2
        # Case-insensitive keying.
        assert store.latest("acme", "saas") is not None


def test_store_isolates_by_company_vertical(tmp_path):
    with IntelStore(tmp_path / "t.db") as store:
        store.save(_report(summary="acme"))
        assert store.latest("Other", "SaaS") is None


def test_diff_no_previous_is_empty():
    assert diff_reports(None, _report()) == []


def test_diff_detects_new_dropped_pricing_positioning_and_threat():
    prev = _report(
        level=T.MEDIUM,
        competitors=[
            Competitor(name="Alpha", positioning="Cheap tool", pricing="$10/mo"),
            Competitor(name="Beta", positioning="Enterprise", pricing="Quote"),
        ],
    )
    curr = _report(
        level=T.HIGH,
        competitors=[
            Competitor(name="Alpha", positioning="Cheap tool", pricing="$15/mo"),  # pricing change
            Competitor(name="Gamma", positioning="Open source", pricing="Free"),    # new
            # Beta dropped
        ],
    )
    kinds = {c.kind for c in diff_reports(prev, curr)}
    assert ChangeKind.NEW_COMPETITOR in kinds
    assert ChangeKind.DROPPED_COMPETITOR in kinds
    assert ChangeKind.PRICING_CHANGE in kinds
    assert ChangeKind.OVERALL_THREAT_CHANGE in kinds


def test_diff_ignores_whitespace_only_pricing_change():
    prev = _report(competitors=[Competitor(name="Alpha", positioning="x", pricing="$10 / mo")])
    curr = _report(competitors=[Competitor(name="Alpha", positioning="x", pricing="$10  /  mo")])
    assert diff_reports(prev, curr) == []
