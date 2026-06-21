"""End-to-end pipeline tests: supervisor routing, execution, dry-run, approval gate."""

from __future__ import annotations

from langgraph.graph import END

from sales_ops.approval import RecordingApprover
from sales_ops.models import Decision, LeadStage
from sales_ops.report import render_json, render_markdown
from sales_ops.state import CRM, OUTREACH, PROSPECT, REPLY, REPORT
from sales_ops.supervisor import route


def test_supervisor_routes_in_order():
    assert route({}) == PROSPECT
    assert route({"prospected": True}) == OUTREACH
    assert route({"prospected": True, "outreached": True}) == REPLY
    assert route({"prospected": True, "outreached": True, "replies_checked": True}) == CRM
    s = {"prospected": True, "outreached": True, "replies_checked": True, "crm_synced": True}
    assert route(s) == REPORT
    assert route({**s, "reported": True}) == END


def test_pipeline_runs_end_to_end(make_orch):
    orch, emailer, crm, store = make_orch(dry_run=False)
    result = orch.run("pipe-test")

    # All five stages contributed.
    assert len(result.leads) == 3
    assert result.sequences and result.sequences[0].steps
    assert len(result.replies) == 2
    assert result.report is not None

    # External actions actually executed through the fakes.
    assert emailer.sent, "outreach/reply emails should have been sent"
    assert crm.upserts, "CRM upserts should have happened"
    assert any(a.decision is Decision.EXECUTED for a in result.actions)

    # The interested reply (lead-1) advanced to QUALIFIED.
    assert any(lead.stage is LeadStage.QUALIFIED for lead in result.leads)

    # Everything was audited to SQLite.
    assert store.action_count("pipe-test") > 0


def test_dry_run_executes_nothing(make_orch):
    orch, emailer, crm, store = make_orch(dry_run=True)
    result = orch.run("pipe-dry")

    assert emailer.sent == []
    assert crm.upserts == []
    assert result.actions  # proposals exist
    assert all(a.decision is Decision.DRY_RUN for a in result.actions)
    # Proposals are still audited so you can see what *would* happen.
    assert store.action_count("pipe-dry") == len(result.actions)


def test_approval_gate_blocks_external_actions(make_orch):
    approver = RecordingApprover(decision=False)
    orch, emailer, crm, store = make_orch(dry_run=False, approver=approver)
    result = orch.run("pipe-deny")

    assert approver.seen, "the gate must be consulted for external actions"
    assert emailer.sent == []
    assert crm.upserts == []
    assert all(a.decision is Decision.DENIED for a in result.actions)


def test_approval_gate_allows_when_approved(make_orch):
    approver = RecordingApprover(decision=True)
    orch, emailer, crm, _ = make_orch(dry_run=False, approver=approver)
    result = orch.run("pipe-allow")
    assert approver.seen
    assert emailer.sent and crm.upserts
    assert any(a.decision is Decision.EXECUTED for a in result.actions)


def test_output_renders(make_orch):
    orch, *_ = make_orch(dry_run=True)
    result = orch.run("pipe-render")
    md = render_markdown(result)
    assert "# Sales Pipeline Briefing" in md
    assert "## Leads" in md
    assert "## Action Log" in md

    import json

    data = json.loads(render_json(result))
    assert data["pipeline_id"] == "pipe-render"
    assert data["report"]["metrics"]["leads_prospected"] == 3
