"""Lead Research Agent — multi-agent (LangGraph) prospect research + outreach.

Lumifie Consulting. Given a target company URL, three sub-agents (Scraper/Enricher,
ICP Matcher, Copywriter) research the company via web search + Jina Reader, score it
against a configurable ICP, and draft personalized email + LinkedIn outreach. Built
on lumifie_core; multi-provider via litellm.
"""

from lead_research.models import (
    Enrichment,
    Executive,
    ICPScore,
    LeadReport,
    Outreach,
)

__version__ = "0.1.0"

__all__ = [
    "Enrichment",
    "Executive",
    "ICPScore",
    "LeadReport",
    "Outreach",
    "__version__",
]
