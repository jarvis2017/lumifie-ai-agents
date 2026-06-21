"""Tests that the function-tool schemas are well-formed and match the models."""

from __future__ import annotations

from contract_intelligence import tools as tool_mod
from contract_intelligence.models import ClauseCategory, RiskLevel


def _by_name() -> dict[str, dict]:
    return {t["function"]["name"]: t for t in tool_mod.tool_definitions()}


def test_three_function_tools_defined():
    tools = tool_mod.tool_definitions()
    assert all(t["type"] == "function" for t in tools)
    assert set(_by_name()) == {
        tool_mod.RECORD_CLAUSE,
        tool_mod.FLAG_RISK,
        tool_mod.FINALIZE_ANALYSIS,
    }


def test_schemas_are_closed_and_required():
    for tool in tool_mod.tool_definitions():
        params = tool["function"]["parameters"]
        assert params["type"] == "object"
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])


def test_enums_match_models():
    tools = _by_name()
    clause = tools[tool_mod.RECORD_CLAUSE]["function"]["parameters"]
    assert set(clause["properties"]["category"]["enum"]) == {c.value for c in ClauseCategory}
    risk = tools[tool_mod.FLAG_RISK]["function"]["parameters"]
    assert set(risk["properties"]["severity"]["enum"]) == {r.value for r in RiskLevel}


def test_json_hints_mention_keys():
    assert '"clauses"' in tool_mod.json_extraction_hint()
    assert '"risks"' in tool_mod.json_extraction_hint()
    assert "overall_risk_level" in tool_mod.json_finalize_hint()
