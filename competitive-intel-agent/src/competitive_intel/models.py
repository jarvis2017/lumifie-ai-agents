"""Typed models for competitive-intelligence briefs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ThreatLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]

    @property
    def label(self) -> str:
        return self.value.title()


class Competitor(BaseModel):
    name: str
    positioning: str = Field(..., description="How the competitor positions itself.")
    pricing: str = Field("Unknown", description="Pricing summary, or 'Unknown'.")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    source_url: str | None = None

    model_config = {"use_enum_values": False}


class Threat(BaseModel):
    severity: ThreatLevel
    competitor: str | None = Field(default=None, description="Competitor the threat comes from.")
    description: str
    recommendation: str

    model_config = {"use_enum_values": False}


class IntelReport(BaseModel):
    """One competitive-intelligence run for a (company, vertical)."""

    company: str
    vertical: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model: str
    overall_threat_level: ThreatLevel
    market_summary: str
    executive_summary: str
    competitors: list[Competitor] = Field(default_factory=list)
    threats: list[Threat] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)

    model_config = {"use_enum_values": False}

    def threats_by_severity(self) -> list[Threat]:
        return sorted(self.threats, key=lambda t: t.severity.rank, reverse=True)

    def competitor_names(self) -> set[str]:
        return {c.name.strip().lower() for c in self.competitors}


class ChangeKind(str, Enum):
    NEW_COMPETITOR = "new_competitor"
    DROPPED_COMPETITOR = "dropped_competitor"
    PRICING_CHANGE = "pricing_change"
    POSITIONING_CHANGE = "positioning_change"
    OVERALL_THREAT_CHANGE = "overall_threat_change"


class Change(BaseModel):
    """A single delta between this run and the previous run."""

    kind: ChangeKind
    competitor: str | None = None
    summary: str
    before: str | None = None
    after: str | None = None

    model_config = {"use_enum_values": False}


__all__ = [
    "Change",
    "ChangeKind",
    "Competitor",
    "IntelReport",
    "Threat",
    "ThreatLevel",
]
