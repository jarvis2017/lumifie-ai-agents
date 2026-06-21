"""Tests for JSON and markdown rendering."""

from __future__ import annotations

import json

from contract_intelligence.models import (
    Clause,
    ClauseCategory,
    ContractReport,
    Risk,
    RiskLevel,
)
from contract_intelligence.report import render_json, render_markdown


def _sample_report() -> ContractReport:
    return ContractReport(
        contract_name="acme_msa.pdf",
        page_count=3,
        model="claude-opus-4-8",
        overall_risk_level=RiskLevel.HIGH,
        executive_summary="A vendor-favorable agreement with notable risks.",
        clauses=[
            Clause(
                category=ClauseCategory.PAYMENT_TERMS,
                title="Net-15 payment",
                summary="Invoices due in 15 days.",
                verbatim_excerpt="due and payable within fifteen (15) days",
                page=2,
            )
        ],
        risks=[
            Risk(
                severity=RiskLevel.CRITICAL,
                category=ClauseCategory.LIABILITY,
                title="Uncapped indemnity",
                description="Client indemnity is unlimited.",
                recommendation="Add a liability cap.",
                related_excerpt="shall be unlimited",
            ),
            Risk(
                severity=RiskLevel.LOW,
                category=ClauseCategory.PAYMENT_TERMS,
                title="Short payment window",
                description="15 days is tight.",
                recommendation="Negotiate net-30.",
            ),
        ],
    )


def test_render_json_is_valid_and_roundtrips():
    report = _sample_report()
    raw = render_json(report)
    data = json.loads(raw)
    assert data["contract_name"] == "acme_msa.pdf"
    assert data["overall_risk_level"] == "high"
    assert len(data["risks"]) == 2
    # Round-trips back into the model.
    restored = ContractReport.model_validate(data)
    assert restored.overall_risk_level is RiskLevel.HIGH


def test_render_markdown_has_sections_and_orders_risks():
    md = render_markdown(_sample_report())
    assert "# Contract Analysis — acme_msa.pdf" in md
    assert "## Executive Summary" in md
    assert "## Risk Register" in md
    assert "## Key Clauses" in md
    # Critical risk must appear before the low risk.
    assert md.index("Uncapped indemnity") < md.index("Short payment window")
    assert "not legal advice" in md


def test_render_markdown_handles_empty_report():
    empty = ContractReport(
        contract_name="empty.pdf",
        page_count=1,
        model="claude-opus-4-8",
        overall_risk_level=RiskLevel.LOW,
        executive_summary="Nothing notable.",
    )
    md = render_markdown(empty)
    assert "No risks were identified" in md
    assert "No clauses were extracted" in md
