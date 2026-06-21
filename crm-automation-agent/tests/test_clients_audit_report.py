"""Tests for the fake CRM client, audit store, report rendering, and stub."""

from __future__ import annotations

from datetime import date

from crm_automation.audit import AuditLog
from crm_automation.crm.base import CRMClient
from crm_automation.crm.fake import FakeCRMClient, seed_records
from crm_automation.models import (
    ActionType,
    AuditEntry,
    Decision,
    ProposedAction,
    RunSummary,
    TriggerType,
)
from crm_automation.report import render_json, render_markdown
from crm_automation.stub import StubProvider


def test_fake_client_satisfies_protocol_and_seeds_data():
    client = FakeCRMClient()
    assert isinstance(client, CRMClient)
    assert client.fetch_contacts()
    assert client.fetch_deals()


def test_fake_client_records_mutations():
    client = FakeCRMClient()
    deal_id = client.fetch_deals()[0].id
    client.update_deal_stage(deal_id, "Closed Won")
    client.create_task("Call back", date(2030, 1, 1), deal_id)
    client.add_note(deal_id, "Spoke with buyer.")
    assert client.stage_updates == [(deal_id, "Closed Won")]
    assert client.tasks[0]["subject"] == "Call back"
    assert client.notes[0][0] == deal_id


def test_seed_records_are_trigger_rich():
    contacts, deals = seed_records()
    assert len(contacts) >= 3
    assert len(deals) >= 4


def test_audit_log_roundtrip(tmp_path):
    db = tmp_path / "a.db"
    entry = AuditEntry(
        rule_name="r", trigger_type=TriggerType.DEAL_STALE,
        action_type=ActionType.FLAG_FOR_REVIEW, target_id="d-1",
        params={"k": "v"}, decision=Decision.PROPOSED, result="ok",
    )
    with AuditLog(db) as log:
        saved = log.record(entry)
        assert saved.id is not None
        assert log.count() == 1
        rows = log.all_entries()
        assert rows[0].params == {"k": "v"}
        assert rows[0].decision == Decision.PROPOSED
        assert log.by_decision(Decision.PROPOSED)
        assert log.by_decision(Decision.EXECUTED) == []


def _summary() -> RunSummary:
    proposed = ProposedAction(
        type=ActionType.CREATE_TASK, target_id="d-1", params={"subject": "Call"},
        rule_name="Task rule", rationale="overdue", trigger_type=TriggerType.FOLLOW_UP_OVERDUE,
    )
    audit = AuditEntry(
        rule_name="Task rule", trigger_type=TriggerType.FOLLOW_UP_OVERDUE,
        action_type=ActionType.CREATE_TASK, target_id="d-1", params={"subject": "Call"},
        decision=Decision.EXECUTED, result="Task created.",
    )
    return RunSummary(
        source="demo", model="claude-opus-4-8", dry_run=False,
        contacts_scanned=3, deals_scanned=4,
        proposed=[proposed], audit=[audit],
    )


def test_render_json_and_markdown():
    summary = _summary()
    js = render_json(summary)
    assert '"source": "demo"' in js
    md = render_markdown(summary)
    assert "# CRM Automation Run" in md
    assert "Task rule" in md
    assert "Triggers Detected" in md
    assert "Proposed Actions & Decisions" in md


def test_stub_provider_returns_email_draft():
    provider = StubProvider()
    result = provider.complete(
        [{"role": "user", "content": "Draft for d-2001"}],
        tool_choice={"type": "function", "function": {"name": "email_draft"}},
    )
    assert result.tool_calls
    args = result.tool_calls[0].arguments
    assert args["subject"] and args["body"]
