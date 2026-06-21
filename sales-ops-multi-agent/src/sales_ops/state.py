"""LangGraph state for the sales-ops pipeline.

The supervisor reads the routing flags to decide which sub-agent runs next; each
sub-agent node sets its flag when done so the supervisor advances. ``actions`` and
``trace`` use additive reducers so contributions from each node merge.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SalesState(TypedDict, total=False):
    pipeline_id: str
    icp: dict[str, Any]
    max_leads: int
    dry_run: bool

    # working set
    leads: list[dict[str, Any]]  # ScoredLead dicts
    sequences: list[dict[str, Any]]  # OutreachSequence dicts
    replies: list[dict[str, Any]]  # Reply dicts
    actions: Annotated[list[dict[str, Any]], operator.add]  # ActionOutcome dicts
    report: dict[str, Any] | None

    # routing flags (supervisor advances when each becomes True)
    prospected: bool
    outreached: bool
    replies_checked: bool
    crm_synced: bool
    reported: bool

    trace: Annotated[list[str], operator.add]


# Node names (also used as supervisor routing targets).
PROSPECT = "prospector"
OUTREACH = "outreach"
REPLY = "reply_handler"
CRM = "crm_sync"
REPORT = "reporter"

__all__ = ["SalesState", "PROSPECT", "OUTREACH", "REPLY", "CRM", "REPORT"]
