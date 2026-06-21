"""Function tools (OpenAI/litellm format) and JSON-fallback schema hints."""

from __future__ import annotations

from typing import Any

from lumifie_core import chat

from competitive_intel.models import ThreatLevel

LEVELS = [t.value for t in ThreatLevel]

WEB_SEARCH = "web_search"
RECORD_COMPETITOR = "record_competitor"
RECORD_THREAT = "record_threat"
FINALIZE_BRIEF = "finalize_brief"


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def tool_definitions() -> list[dict[str, Any]]:
    return [
        chat.function_tool(
            WEB_SEARCH,
            "Search the web for competitor information (names, positioning, pricing, "
            "recent moves). Use focused queries and call repeatedly to dig in.",
            _obj(
                {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {
                        "type": ["integer", "null"],
                        "description": "Max results (default 5).",
                    },
                },
                ["query", "max_results"],
            ),
        ),
        chat.function_tool(
            RECORD_COMPETITOR,
            "Record one competitor you have researched. Cite a source_url when possible.",
            _obj(
                {
                    "name": {"type": "string"},
                    "positioning": {"type": "string", "description": "How they position."},
                    "pricing": {"type": "string", "description": "Pricing summary, or 'Unknown'."},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                    "source_url": {"type": ["string", "null"]},
                },
                ["name", "positioning", "pricing", "strengths", "weaknesses", "source_url"],
            ),
        ),
        chat.function_tool(
            RECORD_THREAT,
            "Record one competitive threat with an actionable recommendation.",
            _obj(
                {
                    "severity": {"type": "string", "enum": LEVELS},
                    "competitor": {"type": ["string", "null"]},
                    "description": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                ["severity", "competitor", "description", "recommendation"],
            ),
        ),
        chat.function_tool(
            FINALIZE_BRIEF,
            "Call exactly once when research is complete to finish the brief.",
            _obj(
                {
                    "overall_threat_level": {"type": "string", "enum": LEVELS},
                    "market_summary": {"type": "string", "description": "State of the market."},
                    "executive_summary": {"type": "string", "description": "2-5 sentence summary."},
                },
                ["overall_threat_level", "market_summary", "executive_summary"],
            ),
        ),
    ]


def json_synthesis_hint() -> str:
    return (
        "Respond with a single JSON object with keys: "
        '"competitors" (array of {"name","positioning","pricing","strengths" (array), '
        '"weaknesses" (array),"source_url" (string or null)}), '
        '"threats" (array of {"severity" (one of '
        f"{LEVELS}"
        '),"competitor" (string or null),"description","recommendation"}), '
        f'"overall_threat_level" (one of {LEVELS}), "market_summary", "executive_summary". '
        "Output only the JSON object."
    )
