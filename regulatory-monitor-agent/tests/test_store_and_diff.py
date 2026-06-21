"""Tests for SQLite history, the new-detection diff, and config loading."""

from __future__ import annotations

import json

import pytest
from conftest import SAFETY_URL, WAGE_URL, _impact

from reg_monitor.diff import new_impacts, seen_fingerprints
from reg_monitor.loader import load_config
from reg_monitor.models import (
    BusinessProfile,
    Digest,
    ImpactStatement,
    MonitoringPlan,
    Relevance,
)
from reg_monitor.store import MonitorStore


def _digest(profile: BusinessProfile, impacts: list[ImpactStatement]) -> Digest:
    return Digest(
        profile=profile,
        model="claude-opus-4-8",
        lookback_days=7,
        plan=MonitoringPlan(search_queries=["q"], rationale="r"),
        impacts=impacts,
        new_impacts=impacts,
        sources_checked=["search: q"],
    )


def _imp(url: str, rel: str = "high") -> ImpactStatement:
    return ImpactStatement.model_validate(_impact(url, "title", rel))


def test_store_roundtrip_and_latest(tmp_path, profile):
    db = tmp_path / "rm.db"
    store = MonitorStore(db)
    assert store.count(profile) == 0
    assert store.latest(profile) is None

    d = _digest(profile, [_imp(WAGE_URL)])
    store.save(d)
    assert store.count(profile) == 1

    got = store.latest(profile)
    assert got is not None
    assert got.impacts[0].url == WAGE_URL
    store.close()


def test_store_latest_returns_most_recent(tmp_path, profile):
    store = MonitorStore(tmp_path / "rm.db")
    store.save(_digest(profile, [_imp(WAGE_URL)]))
    store.save(_digest(profile, [_imp(WAGE_URL), _imp(SAFETY_URL)]))
    latest = store.latest(profile)
    assert len(latest.impacts) == 2
    store.close()


def test_store_keyed_by_profile(tmp_path, profile):
    other = BusinessProfile(industry="retail", location="Texas, USA")
    store = MonitorStore(tmp_path / "rm.db")
    store.save(_digest(profile, [_imp(WAGE_URL)]))
    assert store.latest(other) is None  # different profile -> no history
    assert store.count(other) == 0
    store.close()


def test_diff_no_previous_all_new():
    current = [_imp(WAGE_URL), _imp(SAFETY_URL)]
    new = new_impacts(None, current)
    assert len(new) == 2


def test_diff_detects_only_new(profile):
    prev = _digest(profile, [_imp(WAGE_URL)])
    current = [_imp(WAGE_URL), _imp(SAFETY_URL)]
    new = new_impacts(prev, current)
    assert [i.url for i in new] == [SAFETY_URL]


def test_diff_zero_new_when_unchanged(profile):
    prev = _digest(profile, [_imp(WAGE_URL), _imp(SAFETY_URL)])
    current = [_imp(WAGE_URL), _imp(SAFETY_URL)]
    assert new_impacts(prev, current) == []


def test_diff_normalizes_trailing_slash(profile):
    prev = _digest(profile, [_imp(WAGE_URL)])
    current = [_imp(WAGE_URL + "/")]  # same item, trailing slash
    assert new_impacts(prev, current) == []


def test_seen_fingerprints(profile):
    prev = _digest(profile, [_imp(WAGE_URL)])
    fps = seen_fingerprints(prev)
    assert len(fps) == 1
    assert seen_fingerprints(None) == set()


def test_profile_hash_stable_and_distinct():
    a = BusinessProfile(industry="Food Service", location="California, USA")
    b = BusinessProfile(industry="food service", location="california, usa")
    c = BusinessProfile(industry="retail", location="California, USA")
    assert a.hash() == b.hash()  # case-insensitive
    assert a.hash() != c.hash()


def test_load_config_valid(tmp_path):
    raw = {
        "profile": {
            "industry": "food service",
            "location": "California, USA",
            "operational_keywords": ["food safety"],
        },
        "sources": [{"type": "rss", "value": "https://x/rss.xml", "label": "X"}],
    }
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    cfg = load_config(p)
    assert cfg.profile.industry == "food service"
    assert cfg.sources[0].type.value == "rss"


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.json")


def test_load_config_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)


def test_relevance_rank_ordering():
    assert Relevance.HIGH.rank > Relevance.MEDIUM.rank > Relevance.LOW.rank
