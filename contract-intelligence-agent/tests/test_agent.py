"""End-to-end tests of the agent loop against the scripted (no-network) client.

These exercise the real pipeline — PDF load → chunking → multi-step tool loop →
finalization → report — with a deterministic LLM stand-in.
"""

from __future__ import annotations

from contract_intelligence.agent import ContractIntelligenceAgent
from contract_intelligence.models import ContractReport, RiskLevel
from contract_intelligence.pdf_loader import load_contract
from contract_intelligence.report import render_json, render_markdown


def test_agent_runs_end_to_end(sample_pdf, scripted_client, settings):
    doc = load_contract(sample_pdf, max_chunk_chars=settings.max_chunk_chars)
    assert len(doc.chunks) > 1  # multi-chunk path is under test

    agent = ContractIntelligenceAgent(scripted_client, settings)
    report = agent.analyze(doc)

    assert isinstance(report, ContractReport)
    assert report.contract_name == doc.name
    assert report.page_count == doc.page_count
    assert report.overall_risk_level is RiskLevel.HIGH
    assert "indemnity" in report.executive_summary.lower()

    # One clause + one risk were emitted per chunk by the scripted client.
    assert len(report.clauses) == len(doc.chunks)
    assert len(report.risks) == len(doc.chunks)

    # Token usage was accumulated across every model call.
    assert report.token_usage.input_tokens > 0


def test_agent_is_multi_step(sample_pdf, scripted_client, settings):
    doc = load_contract(sample_pdf, max_chunk_chars=settings.max_chunk_chars)
    agent = ContractIntelligenceAgent(scripted_client, settings)
    agent.analyze(doc)
    # Two calls per chunk (extract, then acknowledge) plus one finalize call —
    # proves it is a loop, not a single prompt.
    assert scripted_client.calls == 2 * len(doc.chunks) + 1


def test_agent_output_renders(sample_pdf, scripted_client, settings):
    doc = load_contract(sample_pdf, max_chunk_chars=settings.max_chunk_chars)
    report = ContractIntelligenceAgent(scripted_client, settings).analyze(doc)

    md = render_markdown(report)
    assert "Uncapped client indemnification" in md

    import json

    data = json.loads(render_json(report))
    assert data["model"] == "claude-opus-4-8"


def test_finalize_deferred_until_all_chunks(scripted_client, settings):
    """The agent must not accept finalize during a mid-document chunk pass."""
    agent = ContractIntelligenceAgent(scripted_client, settings)
    # allow_finalize=False path returns finalized=False even if asked to finalize.
    _, finalized = agent._handle_tool_call(
        "finalize_analysis",
        {"overall_risk_level": "low", "executive_summary": "early"},
        allow_finalize=False,
    )
    assert finalized is False
    assert agent._final is None
