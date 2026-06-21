"""Inbound-triage settings: shared CoreSettings plus routing knobs."""

from __future__ import annotations

import os
from dataclasses import dataclass

from lumifie_core import CoreSettings, env_int


@dataclass
class TriageSettings(CoreSettings):
    booking_base_url: str = "https://cal.com/lumifie/intro"
    kb_path: str | None = None  # JSON rebuttal playbook; None = built-in
    rebuttal_top_k: int = 3

    @classmethod
    def from_env(cls, **overrides):
        settings = super().from_env(**overrides)
        settings.booking_base_url = os.getenv("TRIAGE_BOOKING_URL", "https://cal.com/lumifie/intro")
        settings.kb_path = os.getenv("TRIAGE_KB_PATH") or None
        settings.rebuttal_top_k = env_int("TRIAGE_REBUTTAL_TOP_K", 3)
        for key, value in overrides.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        return settings


__all__ = ["TriageSettings"]
