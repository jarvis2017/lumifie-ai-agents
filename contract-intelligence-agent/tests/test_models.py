"""Unit tests for the typed data models."""

from __future__ import annotations

from contract_intelligence.models import (
    Clause,
    ClauseCategory,
    ContractReport,
    Risk,
    RiskLevel,
    TokenUsage,
)


def test_risk_level_rank_orders_severity():
    assert RiskLevel.LOW.rank < RiskLevel.MEDIUM.rank < RiskLevel.HIGH.rank < RiskLevel.CRITICAL.rank


def test_category_label_is_human_readable():
    assert ClauseCategory.IP_OWNERSHIP.label == "Ip Ownership"
    assert ClauseCategory.PAYMENT_TERMS.label == "Payment Terms"


def _report_with(risks, clauses=None):
    return ContractReport(
        contract_name="x.pdf",
        page_count=1,
        model="claude-opus-4-8",
        overall_risk_level=RiskLevel.MEDIUM,
        executive_summary="s",
        clauses=clauses or [],
        risks=risks,
    )


def test_risks_by_severity_sorts_most_severe_first():
    risks = [
        Risk(severity=RiskLevel.LOW, category=ClauseCategory.OTHER, title="a", description="d", recommendation="r"),
        Risk(severity=RiskLevel.CRITICAL, category=ClauseCategory.LIABILITY, title="b", description="d", recommendation="r"),
        Risk(severity=RiskLevel.MEDIUM, category=ClauseCategory.PAYMENT_TERMS, title="c", description="d", recommendation="r"),
    ]
    ordered = _report_with(risks).risks_by_severity()
    assert [r.severity for r in ordered] == [RiskLevel.CRITICAL, RiskLevel.MEDIUM, RiskLevel.LOW]


def test_clauses_grouped_by_category():
    clauses = [
        Clause(category=ClauseCategory.PAYMENT_TERMS, title="t1", summary="s", verbatim_excerpt="e"),
        Clause(category=ClauseCategory.PAYMENT_TERMS, title="t2", summary="s", verbatim_excerpt="e"),
        Clause(category=ClauseCategory.TERMINATION, title="t3", summary="s", verbatim_excerpt="e"),
    ]
    grouped = _report_with([], clauses).clauses_by_category()
    assert len(grouped[ClauseCategory.PAYMENT_TERMS]) == 2
    assert len(grouped[ClauseCategory.TERMINATION]) == 1


def test_token_usage_accumulates_duck_typed_usage():
    from types import SimpleNamespace

    usage = TokenUsage()
    usage.add(SimpleNamespace(input_tokens=10, output_tokens=5))
    usage.add(SimpleNamespace(input_tokens=3, output_tokens=2, cache_read_input_tokens=7))
    assert usage.input_tokens == 13
    assert usage.output_tokens == 7
    assert usage.cache_read_input_tokens == 7


def test_clause_accepts_string_enum_value():
    # Tool inputs arrive as strings; the model must coerce them.
    clause = Clause.model_validate(
        {"category": "liability", "title": "t", "summary": "s", "verbatim_excerpt": "e", "page": 2}
    )
    assert clause.category is ClauseCategory.LIABILITY
    assert clause.page == 2
