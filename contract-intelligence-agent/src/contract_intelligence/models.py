"""Typed data models for contract analysis.

These Pydantic models are the single source of truth for the shape of the
agent's output. The tool schemas the model is asked to fill (see ``tools.py``)
are derived to match these models, and the JSON report is a serialization of
:class:`ContractReport`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ClauseCategory(str, Enum):
    """The clause categories the agent is responsible for extracting."""

    PAYMENT_TERMS = "payment_terms"
    TERMINATION = "termination"
    IP_OWNERSHIP = "ip_ownership"
    LIABILITY = "liability"
    DISPUTE_RESOLUTION = "dispute_resolution"
    OTHER = "other"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class RiskLevel(str, Enum):
    """Severity scale for flagged risks and the overall assessment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return order[self.value]

    @property
    def label(self) -> str:
        return self.value.title()


class Clause(BaseModel):
    """A single extracted contract clause."""

    category: ClauseCategory
    title: str = Field(..., description="Short human-readable name for the clause.")
    summary: str = Field(..., description="Plain-language summary of what the clause says.")
    verbatim_excerpt: str = Field(
        ...,
        description="Exact text quoted from the contract supporting the summary.",
    )
    page: int | None = Field(
        default=None, description="1-indexed page the clause was found on, if known."
    )

    model_config = {"use_enum_values": False}


class Risk(BaseModel):
    """A potential risk identified in the contract."""

    severity: RiskLevel
    category: ClauseCategory
    title: str = Field(..., description="Short name for the risk.")
    description: str = Field(..., description="Why this is a risk and what could go wrong.")
    recommendation: str = Field(
        ..., description="Concrete action to mitigate or renegotiate the risk."
    )
    related_excerpt: str | None = Field(
        default=None, description="Contract text the risk relates to, if applicable."
    )

    model_config = {"use_enum_values": False}


class TokenUsage(BaseModel):
    """Aggregate token usage across all agent steps, for cost transparency."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(self, usage: object) -> None:
        """Accumulate a single response's ``usage`` object (duck-typed)."""
        self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        self.cache_read_input_tokens += int(
            getattr(usage, "cache_read_input_tokens", 0) or 0
        )
        self.cache_creation_input_tokens += int(
            getattr(usage, "cache_creation_input_tokens", 0) or 0
        )


class ContractReport(BaseModel):
    """The complete analysis output for one contract."""

    contract_name: str
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    page_count: int
    model: str
    overall_risk_level: RiskLevel
    executive_summary: str
    clauses: list[Clause] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    model_config = {"use_enum_values": False}

    def risks_by_severity(self) -> list[Risk]:
        """Risks sorted most-severe first."""
        return sorted(self.risks, key=lambda r: r.severity.rank, reverse=True)

    def clauses_by_category(self) -> dict[ClauseCategory, list[Clause]]:
        grouped: dict[ClauseCategory, list[Clause]] = {}
        for clause in self.clauses:
            grouped.setdefault(clause.category, []).append(clause)
        return grouped
