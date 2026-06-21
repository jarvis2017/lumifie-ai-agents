"""Tests for trigger detection and the YAML rules engine."""

from __future__ import annotations

from crm_automation import triggers as trig
from crm_automation.models import ActionType, TriggerType
from crm_automation.rules import evaluate, load_rules


def test_detect_new_leads_for_contacts_and_deals(sample_contacts, sample_deals):
    found = trig.detect_new_leads(sample_contacts, sample_deals, within_days=1)
    ids = {t.target_id for t in found}
    assert ids == {"c-new", "d-new"}
    assert all(t.type == TriggerType.NEW_LEAD for t in found)


def test_detect_stale_deals(sample_deals):
    found = trig.detect_stale_deals(sample_deals, days=30)
    assert [t.target_id for t in found] == ["d-stale"]
    assert found[0].context["days_stale"] >= 50


def test_detect_stale_deals_threshold_is_configurable(sample_deals):
    # With a 60-day window, the 50-day-stale deal no longer triggers.
    assert trig.detect_stale_deals(sample_deals, days=60) == []


def test_detect_overdue_follow_ups(sample_deals):
    found = trig.detect_overdue_follow_ups(sample_deals)
    assert [t.target_id for t in found] == ["d-overdue"]
    assert found[0].context["days_overdue"] == 3


def test_detect_missing_fields(sample_contacts):
    found = trig.detect_missing_fields(sample_contacts, required_fields=["company", "phone"])
    assert [t.target_id for t in found] == ["c-new"]
    assert set(found[0].context["missing"]) == {"company", "phone"}


def test_load_rules_parses_example_yaml():
    rs = load_rules("config/rules.example.yaml")
    names = [r.name for r in rs.rules]
    assert "Welcome new leads" in names
    assert all(r.enabled for r in rs.enabled_rules())
    # Spot-check trigger/action typing.
    welcome = next(r for r in rs.rules if r.name == "Welcome new leads")
    assert welcome.trigger.type == TriggerType.NEW_LEAD
    assert welcome.action.type == ActionType.DRAFT_FOLLOW_UP_EMAIL


def test_evaluate_matches_rules_to_actions(ruleset, sample_contacts, sample_deals):
    triggers, proposed = evaluate(ruleset, sample_contacts, sample_deals)
    types = {p.type for p in proposed}
    # Each rule's action should be represented given the seeded triggers.
    assert ActionType.DRAFT_FOLLOW_UP_EMAIL in types  # new lead + stale deal
    assert ActionType.CREATE_TASK in types            # overdue follow-up
    assert ActionType.FLAG_FOR_REVIEW in types        # missing fields
    # Every proposed action carries its rule + rationale.
    assert all(p.rule_name and p.rationale for p in proposed)
    assert len(triggers) >= 4
