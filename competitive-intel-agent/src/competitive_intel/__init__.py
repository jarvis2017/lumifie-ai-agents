"""Competitive Intelligence Agent — autonomous competitor research and briefing.

Lumifie Consulting. Researches competitors via web search, synthesizes
positioning/pricing/threats, diffs against prior runs (SQLite), and emits an
executive brief in Markdown and JSON. Built on lumifie_core.
"""

from competitive_intel.models import (
    Change,
    Competitor,
    IntelReport,
    Threat,
    ThreatLevel,
)

__version__ = "0.1.0"

__all__ = [
    "Change",
    "Competitor",
    "IntelReport",
    "Threat",
    "ThreatLevel",
    "__version__",
]
