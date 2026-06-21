"""Typed models for the regulatory-monitor pipeline.

The pipeline flows: a :class:`BusinessProfile` plus a list of :class:`Source` →
a :class:`MonitoringPlan` (Stage 1) → raw :class:`Finding` objects (Stage 2) →
:class:`ImpactStatement` objects (Stage 3) → a :class:`Digest` that the report
module renders. Everything here is JSON-serializable so runs can be stored in
SQLite and diffed run-over-run.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    URL = "url"
    RSS = "rss"
    GOV = "gov"


class Relevance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {"low": 0, "medium": 1, "high": 2}[self.value]

    @property
    def label(self) -> str:
        return self.value.title()


# -- inputs ---------------------------------------------------------------


class BusinessProfile(BaseModel):
    """The business whose regulatory exposure we monitor."""

    industry: str
    location: str
    operational_keywords: list[str] = Field(default_factory=list)
    business_description: str | None = None

    def slug(self) -> str:
        from reg_monitor.utils import slugify

        return f"{slugify(self.industry)}_{slugify(self.location)}"

    def key(self) -> str:
        """Stable history key: industry + location, normalized."""
        return f"{self.industry.strip().lower()}|{self.location.strip().lower()}"

    def hash(self) -> str:
        """Short stable hash of the profile identity (industry + location)."""
        return hashlib.sha256(self.key().encode("utf-8")).hexdigest()[:12]


class Source(BaseModel):
    """A regulatory source to monitor (a gov page, generic URL, or RSS feed)."""

    type: SourceType
    value: str
    label: str | None = None

    model_config = {"use_enum_values": False}

    def display(self) -> str:
        return self.label or self.value


class MonitoringConfig(BaseModel):
    """A profile + its sources, loaded from one JSON file."""

    profile: BusinessProfile
    sources: list[Source] = Field(default_factory=list)


# -- Stage 1: plan --------------------------------------------------------


class MonitoringPlan(BaseModel):
    """Stage 1 output — how to search for recent regulatory change."""

    search_queries: list[str] = Field(default_factory=list)
    source_focus: list[str] = Field(default_factory=list)
    rationale: str = ""


# -- Stage 2: findings ----------------------------------------------------


class Finding(BaseModel):
    """A raw, unanalyzed item collected from a search or feed."""

    title: str
    url: str
    source: str = Field(..., description="Label of the originating source/query.")
    date: str | None = None
    raw_summary: str = ""

    def fingerprint(self) -> str:
        """Identity used for diffing — the normalized URL (or title fallback)."""
        basis = (self.url or self.title).strip().lower().rstrip("/")
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


# -- Stage 3: impact ------------------------------------------------------


class ImpactStatement(BaseModel):
    """Stage 3 output — one finding translated into plain-English impact."""

    title: str
    url: str
    plain_english: str
    relevance: Relevance
    recommended_action: str
    date: str | None = None

    model_config = {"use_enum_values": False}

    def fingerprint(self) -> str:
        basis = (self.url or self.title).strip().lower().rstrip("/")
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


# -- the digest -----------------------------------------------------------


class Digest(BaseModel):
    """One full monitoring run for a (industry, location) business profile."""

    profile: BusinessProfile
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model: str
    lookback_days: int
    plan: MonitoringPlan
    impacts: list[ImpactStatement] = Field(default_factory=list)
    new_impacts: list[ImpactStatement] = Field(default_factory=list)
    sources_checked: list[str] = Field(default_factory=list)
    is_baseline: bool = True
    token_usage: dict[str, int] = Field(default_factory=dict)

    model_config = {"use_enum_values": False}

    def impacts_by_relevance(self) -> list[ImpactStatement]:
        return sorted(self.impacts, key=lambda i: i.relevance.rank, reverse=True)

    def new_by_relevance(self) -> list[ImpactStatement]:
        return sorted(self.new_impacts, key=lambda i: i.relevance.rank, reverse=True)


__all__ = [
    "BusinessProfile",
    "Digest",
    "Finding",
    "ImpactStatement",
    "MonitoringConfig",
    "MonitoringPlan",
    "Relevance",
    "Source",
    "SourceType",
]
