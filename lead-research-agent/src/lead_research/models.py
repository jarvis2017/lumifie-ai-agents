"""Typed models and JSON schemas for the lead-research pipeline.

Every sub-agent returns a structured object validated against these Pydantic
models; the matching JSON schemas are what the LLM is asked to fill (via tool use
or JSON mode through ``lumifie_core``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Executive(BaseModel):
    name: str
    title: str = "Unknown"


class Enrichment(BaseModel):
    """Output of the Scraper/Enricher sub-agent."""

    company_name: str
    industry: str | None = None
    value_proposition: str = Field(..., description="What the company sells and to whom.")
    recent_news: list[str] = Field(default_factory=list)
    key_executives: list[Executive] = Field(default_factory=list)
    summary: str = Field("", description="One-paragraph synthesis for downstream agents.")


class ICPScore(BaseModel):
    """Output of the ICP Matcher sub-agent."""

    fit_score: int = Field(..., ge=0, le=100, description="0-100 fit against the ICP.")
    tier: str = Field(..., description="Strong / Moderate / Weak (or A/B/C).")
    reasoning: str = Field(..., description="Why this score, referencing ICP criteria.")
    matched_criteria: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    disqualified: bool = False


class Outreach(BaseModel):
    """Output of the Copywriter sub-agent."""

    email_subject: str
    email_body: str
    linkedin_message: str
    personalization_signals: list[str] = Field(
        default_factory=list, description="Live signals the copy is built on."
    )


class LeadReport(BaseModel):
    """The complete lead-research result for one target company."""

    company_url: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model: str
    icp_name: str
    enrichment: Enrichment
    icp_score: ICPScore
    outreach: Outreach
    sources: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)


# -- JSON schemas the LLM is asked to fill (flat, provider-friendly) ---------


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def enrichment_schema() -> dict[str, Any]:
    return _obj(
        {
            "company_name": {"type": "string"},
            "industry": {"type": ["string", "null"]},
            "value_proposition": {"type": "string"},
            "recent_news": {"type": "array", "items": {"type": "string"}},
            "key_executives": {
                "type": "array",
                "items": _obj(
                    {"name": {"type": "string"}, "title": {"type": "string"}},
                    ["name", "title"],
                ),
            },
            "summary": {"type": "string"},
        },
        ["company_name", "value_proposition", "recent_news", "key_executives", "summary"],
    )


def icp_score_schema() -> dict[str, Any]:
    return _obj(
        {
            "fit_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "tier": {"type": "string"},
            "reasoning": {"type": "string"},
            "matched_criteria": {"type": "array", "items": {"type": "string"}},
            "gaps": {"type": "array", "items": {"type": "string"}},
            "disqualified": {"type": "boolean"},
        },
        ["fit_score", "tier", "reasoning", "matched_criteria", "gaps", "disqualified"],
    )


def outreach_schema() -> dict[str, Any]:
    return _obj(
        {
            "email_subject": {"type": "string"},
            "email_body": {"type": "string"},
            "linkedin_message": {"type": "string"},
            "personalization_signals": {"type": "array", "items": {"type": "string"}},
        },
        ["email_subject", "email_body", "linkedin_message", "personalization_signals"],
    )


__all__ = [
    "Enrichment",
    "Executive",
    "ICPScore",
    "LeadReport",
    "Outreach",
    "enrichment_schema",
    "icp_score_schema",
    "outreach_schema",
]
