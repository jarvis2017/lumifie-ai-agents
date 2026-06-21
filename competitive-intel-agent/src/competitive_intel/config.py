"""Competitive-intel settings: shared CoreSettings plus research/storage knobs."""

from __future__ import annotations

from dataclasses import dataclass

from lumifie_core import CoreSettings, env_int


@dataclass
class CompetitiveSettings(CoreSettings):
    """Core settings extended with research limits and the SQLite path."""

    db_path: str = "competitive_intel.db"
    region: str = "us-en"
    max_searches: int = 8
    max_competitors: int = 8
    max_iterations: int = 14
    results_per_search: int = 5

    @classmethod
    def from_env(cls, **overrides):
        import os

        settings = super().from_env(**overrides)
        settings.db_path = os.getenv("CI_DB_PATH", "competitive_intel.db")
        settings.region = os.getenv("CI_SEARCH_REGION", "us-en")
        settings.max_searches = env_int("CI_MAX_SEARCHES", 8)
        settings.max_competitors = env_int("CI_MAX_COMPETITORS", 8)
        settings.max_iterations = env_int("CI_MAX_ITERS", 14)
        settings.results_per_search = env_int("CI_RESULTS_PER_SEARCH", 5)
        # apply explicit overrides last
        for key, value in overrides.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        return settings


__all__ = ["CompetitiveSettings"]
