"""JSON schemas for the two structured LLM stages (planner, impact analyst).

These are passed to :meth:`lumifie_core.BaseAgent.structured`, which uses them as
the parameters of a forced tool call (Claude / GPT-4o) or as the shape hint for
JSON-mode (Ollama). Outputs are validated with the Pydantic models afterwards.
"""

from __future__ import annotations

from typing import Any

from reg_monitor.models import Relevance

RELEVANCE_LEVELS = [r.value for r in Relevance]

PLAN_TOOL = "monitoring_plan"
ANALYZE_TOOL = "impact_analysis"


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def plan_schema() -> dict[str, Any]:
    """Schema for Stage 1 — the monitoring plan."""
    return _obj(
        {
            "search_queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Web search queries tuned to the business's industry, location, and "
                    "operational keywords, each intended to be run with a recent-date "
                    "constraint to surface new regulatory change."
                ),
            },
            "source_focus": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Which provided sources/topics to pay closest attention to.",
            },
            "rationale": {
                "type": "string",
                "description": "Brief explanation of the monitoring strategy.",
            },
        },
        ["search_queries", "source_focus", "rationale"],
    )


def analysis_schema() -> dict[str, Any]:
    """Schema for Stage 3 — a batch of impact statements.

    Findings judged irrelevant to the business are simply omitted from the array.
    """
    impact = _obj(
        {
            "url": {
                "type": "string",
                "description": "URL of the finding this impact statement is about.",
            },
            "title": {"type": "string"},
            "plain_english": {
                "type": "string",
                "description": (
                    "Plain-English explanation of what this regulatory item means for "
                    "THIS specific business (its industry, location, and operations)."
                ),
            },
            "relevance": {"type": "string", "enum": RELEVANCE_LEVELS},
            "recommended_action": {
                "type": "string",
                "description": "One concrete, actionable next step for the business owner.",
            },
        },
        ["url", "title", "plain_english", "relevance", "recommended_action"],
    )
    return _obj(
        {
            "impacts": {
                "type": "array",
                "items": impact,
                "description": (
                    "One entry per RELEVANT finding. Omit findings that are clearly "
                    "irrelevant to this business."
                ),
            }
        },
        ["impacts"],
    )


__all__ = [
    "ANALYZE_TOOL",
    "PLAN_TOOL",
    "RELEVANCE_LEVELS",
    "analysis_schema",
    "plan_schema",
]
