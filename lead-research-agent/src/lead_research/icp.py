"""Ideal Customer Profile (ICP): configurable via JSON, with a sensible default."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class ICPProfile(BaseModel):
    """A configurable ideal-customer profile the matcher scores against."""

    name: str = "Default ICP"
    target_industries: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    target_personas: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    disqualifiers: list[str] = Field(default_factory=list)
    value_props_to_emphasize: list[str] = Field(default_factory=list)

    def as_prompt(self) -> str:
        """Render the ICP as a compact block for the matcher/copywriter prompts."""
        return json.dumps(self.model_dump(), indent=2)


DEFAULT_ICP = ICPProfile(
    name="B2B SaaS — mid-market",
    target_industries=["SaaS", "B2B software", "fintech", "developer tools"],
    company_sizes=["50-200 employees", "200-1000 employees"],
    target_personas=["VP Engineering", "Head of Product", "CTO", "VP Marketing"],
    pain_points=[
        "manual, repetitive workflows",
        "slow time-to-insight",
        "tooling that does not scale with headcount",
    ],
    disqualifiers=["pre-revenue", "fewer than 10 employees", "consumer-only"],
    value_props_to_emphasize=[
        "fast time-to-value",
        "automation of repetitive work",
        "integrates with existing stack",
    ],
)


def load_icp(path: str | Path | None) -> ICPProfile:
    """Load an ICP from a JSON file, or return the built-in default."""
    if not path:
        return DEFAULT_ICP
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ICPProfile.model_validate(data)


__all__ = ["ICPProfile", "DEFAULT_ICP", "load_icp"]
