"""CRM-automation settings: shared CoreSettings plus CRM/audit knobs."""

from __future__ import annotations

import os
from dataclasses import dataclass

from lumifie_core import CoreSettings


@dataclass
class CRMSettings(CoreSettings):
    """Core settings extended with the audit DB path and CRM source."""

    db_path: str = "crm_audit.db"
    source: str = "demo"
    rules_path: str = "config/rules.example.yaml"

    @classmethod
    def from_env(cls, **overrides):
        settings = super().from_env(**overrides)
        settings.db_path = os.getenv("CRM_DB_PATH", "crm_audit.db")
        settings.source = os.getenv("CRM_SOURCE", "demo")
        settings.rules_path = os.getenv("CRM_RULES_PATH", "config/rules.example.yaml")
        # apply explicit overrides last
        for key, value in overrides.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        return settings


__all__ = ["CRMSettings"]
