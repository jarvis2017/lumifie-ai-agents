"""Regulatory-monitor settings: shared CoreSettings plus monitoring knobs."""

from __future__ import annotations

import os
from dataclasses import dataclass

from lumifie_core import CoreSettings, env_int


@dataclass
class MonitorSettings(CoreSettings):
    """Core settings extended with monitoring limits and the SQLite path."""

    db_path: str = "reg_monitor.db"
    region: str = "us-en"
    lookback_days: int = 7
    max_queries: int = 6
    results_per_search: int = 5
    max_findings: int = 40

    @classmethod
    def from_env(cls, **overrides):
        settings = super().from_env(**overrides)
        settings.db_path = os.getenv("RM_DB_PATH", "reg_monitor.db")
        settings.region = os.getenv("RM_SEARCH_REGION", "us-en")
        settings.lookback_days = env_int("RM_LOOKBACK_DAYS", 7)
        settings.max_queries = env_int("RM_MAX_QUERIES", 6)
        settings.results_per_search = env_int("RM_RESULTS_PER_SEARCH", 5)
        settings.max_findings = env_int("RM_MAX_FINDINGS", 40)
        # apply explicit overrides last (None values are ignored)
        for key, value in overrides.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        return settings


__all__ = ["MonitorSettings"]
