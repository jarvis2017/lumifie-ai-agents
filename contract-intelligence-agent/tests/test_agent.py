"""End-to-end tests of the agent loop against fake providers (no network).

Exercises the real pipeline — PDF load → chunking → multi-step tool loop /
JSON-mode fallback → finalization → report — with deterministic LLM stand-ins.
"""

from __future__ import annotations

import json

from contract_intelligence.agent import ContractIntelligenceAgent
from contract_intelligence.models import ContractReport, RiskLevel
from contract_intelligence.pdf_loader import load_contract
from contract_intelligence.report import render_json, render_markdown


def test_tool_path_runs_end_to_end(sample_pdf, tool_provider, settings):
    doc = load_contract(sample_pdf, max_chunk_chars=settings.max_chunk_chars)
    assert len(doc.chunks) > 1  # multi-chunk path under test

    report = ContractIntelligenceAgent(tool_provider, settings).analyze(doc)

    assert isinstance(report, ContractReport)
    assert report.contract_name == doc.name
    assert report.overall_risk_level is RiskLevel.HIGH
    assert "indemnity" in report.executive_summary.lower()
    assert len(report.clauses) == len(doc.chunks)
    assert len(report.risks) == len(doc.chunks)
    assert report.token_usage.input_tokens > 0


def test_tool_path_is_multi_step(sample_pdf, tool_provider, settings):
    doc = load_contract(sample_pdf, max_chunk_chars=settings.max_chunk_chars)
    ContractIntelligenceAgent(tool_provider, settings).analyze(doc)
    # Two calls per chunk (extract, then acknowledge) + one finalize call.
    assert tool_provider.calls == 2 * len(doc.chunks) + 1


def test_json_fallback_path(sample_pdf, json_provider, settings):
    doc = load_contract(sample_pdf, max_chunk_chars=settings.max_chunk_chars)
    agent = ContractIntelligenceAgent(json_provider, settings)
    report = agent.analyze(doc)

    # One extraction call per chunk + one finalize call (no tool loop).
    assert json_provider.calls == len(doc.chunks) + 1
    assert report.overall_risk_level is RiskLevel.MEDIUM
    assert len(report.clauses) == len(doc.chunks)
    assert report.model == "ollama/llama3.1"


def test_output_renders(sample_pdf, tool_provider, settings):
    doc = load_contract(sample_pdf, max_chunk_chars=settings.max_chunk_chars)
    report = ContractIntelligenceAgent(tool_provider, settings).analyze(doc)

    md = render_markdown(report)
    assert "Uncapped client indemnification" in md
    data = json.loads(render_json(report))
    assert data["model"] == "claude-opus-4-8"


def test_finalize_deferred_during_chunk_pass(tool_provider, settings):
    agent = ContractIntelligenceAgent(tool_provider, settings)
    _, finalized = agent._handle_tool_call(
        "finalize_analysis",
        {"overall_risk_level": "low", "executive_summary": "early"},
        allow_finalize=False,
    )
    assert finalized is False
    assert agent._final is None
