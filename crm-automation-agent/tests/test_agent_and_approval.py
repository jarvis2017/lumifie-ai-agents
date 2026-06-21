"""End-to-end agent tests: approval gate, dry-run, audit persistence."""

from __future__ import annotations

from crm_automation.agent import CRMAutomationAgent
from crm_automation.approval import auto_approve, auto_deny
from crm_automation.audit import AuditLog
from crm_automation.models import ActionType, Decision


def _agent(provider, settings, client, ruleset, approver, audit_log):
    return CRMAutomationAgent(
        provider, settings, client, ruleset, approver=approver, audit_log=audit_log
    )


def test_dry_run_executes_nothing_but_audits_proposals(
    email_provider, settings, fake_client, ruleset
):
    audit = AuditLog(settings.db_path)
    agent = _agent(email_provider, settings, fake_client, ruleset, auto_approve, audit)
    summary = agent.run(dry_run=True)
    audit.close()

    assert summary.proposed, "expected proposed actions on the seeded demo data"
    # Nothing executed; everything is 'proposed'.
    assert all(a.decision == Decision.PROPOSED for a in summary.audit)
    # No external mutations happened.
    assert fake_client.stage_updates == []
    assert fake_client.tasks == []
    # The LLM was never called for drafts in dry-run.
    assert email_provider.calls == 0
    # Proposals were persisted.
    persisted = AuditLog(settings.db_path)
    assert persisted.count() == len(summary.audit)
    persisted.close()


def test_auto_approve_executes_external_actions_and_audits(
    email_provider, settings, fake_client, ruleset
):
    audit = AuditLog(settings.db_path)
    agent = _agent(email_provider, settings, fake_client, ruleset, auto_approve, audit)
    summary = agent.run(dry_run=False)
    audit.close()

    executed = summary.executed()
    assert executed, "expected executed actions under auto-approve"
    # The overdue-follow-up rule creates a task via the client.
    assert fake_client.tasks, "create_task should have fired through the client"
    task_entries = [a for a in executed if a.action_type == ActionType.CREATE_TASK]
    assert task_entries and task_entries[0].decision == Decision.EXECUTED
    # Email drafts executed too (drafted, flagged for review, never sent).
    draft_entries = [a for a in executed if a.action_type == ActionType.DRAFT_FOLLOW_UP_EMAIL]
    assert draft_entries
    assert draft_entries[0].params.get("draft_body")
    assert email_provider.calls >= 1


def test_auto_deny_skips_external_actions(email_provider, settings, fake_client, ruleset):
    audit = AuditLog(settings.db_path)
    agent = _agent(email_provider, settings, fake_client, ruleset, auto_deny, audit)
    summary = agent.run(dry_run=False)
    audit.close()

    # External mutations are denied -> no client side effects.
    assert fake_client.stage_updates == []
    assert fake_client.tasks == []
    denied = summary.by_decision(Decision.DENIED)
    assert denied, "external actions should be denied at the gate"
    assert all(a.action_type in (ActionType.CREATE_TASK, ActionType.UPDATE_DEAL_STAGE) for a in denied)
    # Non-external actions (drafts/flags) still execute despite the deny-all gate.
    assert summary.by_decision(Decision.EXECUTED)


def test_audit_rows_persist_and_are_queryable(email_provider, settings, fake_client, ruleset):
    audit = AuditLog(settings.db_path)
    agent = _agent(email_provider, settings, fake_client, ruleset, auto_approve, audit)
    summary = agent.run(dry_run=False)
    audit.close()

    reopened = AuditLog(settings.db_path)
    rows = reopened.all_entries()
    assert len(rows) == len(summary.audit)
    executed_rows = reopened.by_decision(Decision.EXECUTED)
    assert all(r.id is not None for r in rows)
    assert len(executed_rows) == len(summary.executed())
    reopened.close()


def test_token_usage_tracked_for_email_drafts(email_provider, settings, fake_client, ruleset):
    audit = AuditLog(settings.db_path)
    agent = _agent(email_provider, settings, fake_client, ruleset, auto_approve, audit)
    summary = agent.run(dry_run=False)
    audit.close()
    assert summary.token_usage["total_tokens"] > 0
