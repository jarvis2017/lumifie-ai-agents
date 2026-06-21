"""Tool definitions (OpenAI/litellm function format) and JSON-fallback schemas.

The agent gives the model three function tools and drives its own loop:

* ``record_clause`` — emit one extracted clause (called repeatedly)
* ``flag_risk``     — emit one identified risk (called repeatedly)
* ``finalize_analysis`` — signal completion with an overall assessment

For models without tool support (e.g. Ollama), the same fields are requested via
JSON mode using the schema descriptions in :func:`json_extraction_hint` and
:func:`json_finalize_hint`.
"""

from __future__ import annotations

from typing import Any

from lumifie_core import chat

from contract_intelligence.models import ClauseCategory, RiskLevel

CATEGORIES = [c.value for c in ClauseCategory]
LEVELS = [r.value for r in RiskLevel]

RECORD_CLAUSE = "record_clause"
FLAG_RISK = "flag_risk"
FINALIZE_ANALYSIS = "finalize_analysis"

_CLAUSE_PROPS = {
    "category": {"type": "string", "enum": CATEGORIES, "description": "Clause category."},
    "title": {"type": "string", "description": "Short human-readable name."},
    "summary": {"type": "string", "description": "Plain-language summary."},
    "verbatim_excerpt": {"type": "string", "description": "Exact text quoted from the contract."},
    "page": {"type": ["integer", "null"], "description": "1-indexed page, or null."},
}

_RISK_PROPS = {
    "severity": {"type": "string", "enum": LEVELS, "description": "Risk severity."},
    "category": {"type": "string", "enum": CATEGORIES, "description": "Related clause category."},
    "title": {"type": "string", "description": "Short name for the risk."},
    "description": {"type": "string", "description": "Why this is a risk."},
    "recommendation": {"type": "string", "description": "Concrete mitigation/renegotiation."},
    "related_excerpt": {"type": ["string", "null"], "description": "Relevant text, or null."},
}

_FINALIZE_PROPS = {
    "overall_risk_level": {"type": "string", "enum": LEVELS, "description": "Overall rating."},
    "executive_summary": {"type": "string", "description": "2-5 sentence executive summary."},
}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def tool_definitions() -> list[dict[str, Any]]:
    """Return the function tools to pass to the provider."""
    return [
        chat.function_tool(
            RECORD_CLAUSE,
            "Record one key clause extracted from the contract. Quote the contract "
            "verbatim in verbatim_excerpt; do not paraphrase there.",
            _obj(_CLAUSE_PROPS),
        ),
        chat.function_tool(
            FLAG_RISK,
            "Flag one potential risk, ambiguity, or unfavorable term, with an "
            "actionable recommendation.",
            _obj(_RISK_PROPS),
        ),
        chat.function_tool(
            FINALIZE_ANALYSIS,
            "Call exactly once, after all clauses and risks are recorded, to finish "
            "with an overall risk rating and executive summary.",
            _obj(_FINALIZE_PROPS),
        ),
    ]


def json_extraction_hint() -> str:
    """Instruction appended in JSON-mode (no-tools) extraction per section."""
    return (
        "Respond with a single JSON object with exactly two keys: "
        '"clauses" and "risks". '
        f'Each clause is {{"category" (one of {CATEGORIES}), "title", "summary", '
        '"verbatim_excerpt", "page" (integer or null)}}. '
        f'Each risk is {{"severity" (one of {LEVELS}), "category" (one of {CATEGORIES}), '
        '"title", "description", "recommendation", "related_excerpt" (string or null)}}. '
        "Return empty arrays if a section has none. Output only the JSON object."
    )


def json_finalize_hint() -> str:
    """Instruction for the JSON-mode finalize step."""
    return (
        "Respond with a single JSON object with exactly two keys: "
        f'"overall_risk_level" (one of {LEVELS}) and "executive_summary" (2-5 sentences). '
        "Output only the JSON object."
    )
