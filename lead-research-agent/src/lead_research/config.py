"""Lead-research settings: shared CoreSettings plus research/ICP knobs."""

from __future__ import annotations

import os
from dataclasses import dataclass

from lumifie_core import CoreSettings, env_int


@dataclass
class LeadSettings(CoreSettings):
    icp_path: str | None = None
    region: str = "us-en"
    max_searches: int = 4
    results_per_search: int = 4
    jina_base: str = "https://r.jina.ai"
    max_page_chars: int = 6000

    @classmethod
    def from_env(cls, **overrides):
        settings = super().from_env(**overrides)
        settings.icp_path = os.getenv("LEAD_ICP_PATH") or None
        settings.region = os.getenv("LEAD_SEARCH_REGION", "us-en")
        settings.max_searches = env_int("LEAD_MAX_SEARCHES", 4)
        settings.results_per_search = env_int("LEAD_RESULTS_PER_SEARCH", 4)
        settings.jina_base = os.getenv("LEAD_JINA_BASE", "https://r.jina.ai")
        settings.max_page_chars = env_int("LEAD_MAX_PAGE_CHARS", 6000)
        for key, value in overrides.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        return settings


__all__ = ["LeadSettings"]
