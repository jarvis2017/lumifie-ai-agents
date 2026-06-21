"""Configuration: YAML business config + shared CoreSettings runtime settings.

Everything a non-technical operator tunes (ICP, approval channel, CRM target,
outreach style) lives in a YAML file (see config/sales_ops.example.yaml). Runtime
plumbing (model, db path) comes from CoreSettings/env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from lumifie_core import CoreSettings
from pydantic import BaseModel, Field


class ICP(BaseModel):
    industries: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    personas: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    disqualifiers: list[str] = Field(default_factory=list)
    value_props: list[str] = Field(default_factory=list)

    def as_prompt(self) -> str:
        import json

        return json.dumps(self.model_dump(), indent=2)


class ApprovalConfig(BaseModel):
    # cli (default), auto (no prompt), deny (block all), or telegram.
    channel: str = "cli"
    telegram_chat_id: str | None = None  # bot token comes from TELEGRAM_BOT_TOKEN env


class CRMConfig(BaseModel):
    provider: str = "none"  # none | hubspot | airtable


class OutreachConfig(BaseModel):
    tone: str = "concise, friendly, specific; no fluff"
    num_steps: int = 2
    channels: list[str] = Field(default_factory=lambda: ["email", "linkedin"])


class SalesOpsConfig(BaseModel):
    icp: ICP = Field(default_factory=ICP)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    crm: CRMConfig = Field(default_factory=CRMConfig)
    outreach: OutreachConfig = Field(default_factory=OutreachConfig)
    max_leads: int = 5
    stale_after_days: int = 14


DEFAULT_CONFIG = SalesOpsConfig(
    icp=ICP(
        industries=["B2B SaaS", "developer tools", "fintech"],
        company_sizes=["50-200 employees", "200-1000 employees"],
        personas=["VP Engineering", "Head of Product", "CTO"],
        keywords=["manual workflows", "scaling", "automation"],
        disqualifiers=["pre-revenue", "fewer than 10 employees"],
        value_props=["fast time-to-value", "automation of repetitive work"],
    )
)


def load_config(path: str | Path | None) -> SalesOpsConfig:
    """Load the YAML business config, or return the built-in default."""
    if not path:
        return DEFAULT_CONFIG
    import yaml  # noqa: PLC0415 - lazy

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return SalesOpsConfig.model_validate(data)


@dataclass
class SalesOpsSettings(CoreSettings):
    config_path: str | None = None
    db_path: str = "sales_ops.db"

    @classmethod
    def from_env(cls, **overrides):
        settings = super().from_env(**overrides)
        settings.config_path = os.getenv("SALESOPS_CONFIG") or None
        settings.db_path = os.getenv("SALESOPS_DB", "sales_ops.db")
        for key, value in overrides.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        return settings


__all__ = [
    "ICP",
    "ApprovalConfig",
    "CRMConfig",
    "OutreachConfig",
    "SalesOpsConfig",
    "SalesOpsSettings",
    "DEFAULT_CONFIG",
    "load_config",
]
