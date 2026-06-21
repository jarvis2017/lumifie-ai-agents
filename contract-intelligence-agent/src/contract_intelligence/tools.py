"""Anthropic tool definitions used by the agent for structured extraction.

The model is given three tools and drives its own analysis loop by calling them:

* ``record_clause`` — emit one extracted clause (called repeatedly).
* ``flag_risk``     — emit one identified risk (called repeatedly).
* ``finalize_analysis`` — signal completion with an overall assessment.

Schemas mirror the Pydantic models in ``models.py``. ``strict: true`` guarantees
the model's tool input validates exactly against the schema.
"""

from __future__ import annotations

from contract_intelligence.models import ClauseCategory, RiskLevel

_CLAUSE_CATEGORIES = [c.value for c in ClauseCategory]
_RISK_LEVELS = [r.value for r in RiskLevel]

RECORD_CLAUSE = "record_clause"
FLAG_RISK = "flag_risk"
FINALIZE_ANALYSIS = "finalize_analysis"


def tool_definitions() -> list[dict]:
    """Return the tool list to pass to ``messages.create(tools=...)``."""
    return [
        {
            "name": RECORD_CLAUSE,
            "description": (
                "Record a single key clause extracted from the contract. Call "
                "this once per distinct clause you find in the priority "
                "categories (payment terms, termination, IP ownership, "
                "liability, dispute resolution). Quote the contract verbatim in "
                "verbatim_excerpt — do not paraphrase there."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": _CLAUSE_CATEGORIES,
                        "description": "Which clause category this belongs to.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Short human-readable name for the clause.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Plain-language summary of what the clause says.",
                    },
                    "verbatim_excerpt": {
                        "type": "string",
                        "description": "Exact text quoted from the contract.",
                    },
                    "page": {
                        "type": ["integer", "null"],
                        "description": "1-indexed page number, or null if unknown.",
                    },
                },
                "required": ["category", "title", "summary", "verbatim_excerpt", "page"],
                "additionalProperties": False,
            },
        },
        {
            "name": FLAG_RISK,
            "description": (
                "Flag a potential risk, ambiguity, or unfavorable term. Call "
                "once per distinct risk. Always include a concrete, actionable "
                "recommendation to mitigate or renegotiate it."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": _RISK_LEVELS,
                        "description": "How serious the risk is.",
                    },
                    "category": {
                        "type": "string",
                        "enum": _CLAUSE_CATEGORIES,
                        "description": "Clause category the risk relates to.",
                    },
                    "title": {"type": "string", "description": "Short name for the risk."},
                    "description": {
                        "type": "string",
                        "description": "Why this is a risk and what could go wrong.",
                    },
                    "recommendation": {
                        "type": "string",
                        "description": "Concrete action to mitigate or renegotiate.",
                    },
                    "related_excerpt": {
                        "type": ["string", "null"],
                        "description": "Relevant contract text, or null.",
                    },
                },
                "required": [
                    "severity",
                    "category",
                    "title",
                    "description",
                    "recommendation",
                    "related_excerpt",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": FINALIZE_ANALYSIS,
            "description": (
                "Call exactly once, after you have recorded all clauses and "
                "risks for the entire contract, to finish the analysis with an "
                "overall risk rating and an executive summary."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "overall_risk_level": {
                        "type": "string",
                        "enum": _RISK_LEVELS,
                        "description": "Overall risk rating for the whole contract.",
                    },
                    "executive_summary": {
                        "type": "string",
                        "description": (
                            "2-5 sentence executive summary for a decision-maker: "
                            "what the contract is, the headline risks, and the "
                            "recommended posture."
                        ),
                    },
                },
                "required": ["overall_risk_level", "executive_summary"],
                "additionalProperties": False,
            },
        },
    ]
