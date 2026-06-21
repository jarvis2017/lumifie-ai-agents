"""Sales-Ops Multi-Agent — a LangGraph supervisor orchestrating the B2B sales cycle.

Lumifie Consulting. A supervisor routes between five specialized sub-agents
(Prospector, Outreach, Reply Handler, CRM Sync, Reporter) end to end, with a human
approval gate before every external action, full pipeline memory via LangGraph
checkpointing, and SQLite persistence. Built on lumifie_core; multi-provider via litellm.
"""

from sales_ops.models import (
    ActionOutcome,
    ActionType,
    PipelineReport,
    PipelineResult,
    ScoredLead,
)

__version__ = "0.1.0"

__all__ = [
    "ActionOutcome",
    "ActionType",
    "PipelineReport",
    "PipelineResult",
    "ScoredLead",
    "__version__",
]
