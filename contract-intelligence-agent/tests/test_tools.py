"""Tests that the tool schemas are well-formed and match the models."""

from __future__ import annotations

from contract_intelligence import tools as tool_mod
from contract_intelligence.models import ClauseCategory, RiskLevel


def test_three_tools_defined():
    names = {t["name"] for t in tool_mod.tool_definitions()}
    assert names == {
        tool_mod.RECORD_CLAUSE,
        tool_mod.FLAG_RISK,
        tool_mod.FINALIZE_ANALYSIS,
    }


def test_tools_are_strict_and_closed():
    for tool in tool_mod.tool_definitions():
        schema = tool["input_schema"]
        assert tool["strict"] is True
        assert schema["additionalProperties"] is False
        # Strict tools require every property to be listed in `required`.
        assert set(schema["required"]) == set(schema["properties"])


def test_enums_in_schema_match_models():
    by_name = {t["name"]: t for t in tool_mod.tool_definitions()}
    clause_schema = by_name[tool_mod.RECORD_CLAUSE]["input_schema"]
    assert set(clause_schema["properties"]["category"]["enum"]) == {
        c.value for c in ClauseCategory
    }
    risk_schema = by_name[tool_mod.FLAG_RISK]["input_schema"]
    assert set(risk_schema["properties"]["severity"]["enum"]) == {
        r.value for r in RiskLevel
    }
