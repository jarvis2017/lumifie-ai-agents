"""Unit tests: store/stale-deals, sub-agents, config loading."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sales_ops.config import DEFAULT_CONFIG, SalesOpsConfig, load_config
from sales_ops.demo import DemoReader, DemoSearch
from sales_ops.models import LeadStage, Reply, ReplyIntent, ScoredLead
from sales_ops.store import SalesOpsStore
from sales_ops.stub import StubProvider
from sales_ops.subagents import Outreach, Prospector, ReplyHandler


def _settings():
    from sales_ops.config import SalesOpsSettings

    return SalesOpsSettings(model="claude-opus-4-8")


def test_store_stale_deals(tmp_path):
    store = SalesOpsStore(tmp_path / "s.db")
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    recent = datetime.now(UTC).isoformat()
    store.upsert_lead(ScoredLead(id="a", company="StaleCo", stage=LeadStage.CONTACTED), "p", last_seen=old)
    store.upsert_lead(ScoredLead(id="b", company="FreshCo", stage=LeadStage.CONTACTED), "p", last_seen=recent)
    store.upsert_lead(ScoredLead(id="c", company="WonCo", stage=LeadStage.QUALIFIED), "p", last_seen=old)

    stale = store.stale_deals(stale_after_days=14)
    ids = {d.lead_id for d in stale}
    assert "a" in ids          # old + non-terminal -> stale
    assert "b" not in ids      # recent
    assert "c" not in ids      # terminal stage excluded
    store.close()


def test_prospector_scores_and_ranks():
    leads = Prospector(StubProvider(), _settings()).find(
        DEFAULT_CONFIG.icp, max_leads=2, search=DemoSearch(), reader=DemoReader()
    )
    assert len(leads) == 2                       # capped to max_leads
    assert [lead.rank for lead in leads] == [1, 2]
    assert leads[0].icp_fit >= leads[1].icp_fit  # ranked by fit desc


def test_outreach_builds_sequence():
    lead = ScoredLead(id="lead-1", company="Acme", icp_fit=88, tier="A")
    seq = Outreach(StubProvider(), _settings()).craft(lead, DEFAULT_CONFIG.outreach, DEFAULT_CONFIG.icp)
    assert seq.lead_id == "lead-1"
    assert seq.steps and seq.steps[0].channel in ("email", "linkedin")


def test_reply_handler_classifies_objection_and_interest():
    rh = ReplyHandler(StubProvider(), _settings())
    objection = rh.classify(Reply(lead_id="x", from_email="a@b.com", body="too expensive, we already use a competitor"))
    assert objection.intent is ReplyIntent.OBJECTION
    interested = rh.classify(Reply(lead_id="y", from_email="c@d.com", body="interested, can we book a demo?"))
    assert interested.intent is ReplyIntent.INTERESTED


def test_load_config_default_and_file(tmp_path):
    assert load_config(None) is DEFAULT_CONFIG
    p = tmp_path / "c.yaml"
    p.write_text("max_leads: 9\napproval:\n  channel: auto\nicp:\n  industries: ['healthtech']\n")
    cfg = load_config(p)
    assert isinstance(cfg, SalesOpsConfig)
    assert cfg.max_leads == 9
    assert cfg.approval.channel == "auto"
    assert cfg.icp.industries == ["healthtech"]
