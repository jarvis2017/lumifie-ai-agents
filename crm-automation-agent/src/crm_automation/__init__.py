"""CRM Automation Agent — human-gated CRM monitoring and actions.

Lumifie Consulting. Connects to HubSpot or Airtable, monitors for trigger
conditions (new leads, stale deals, overdue follow-ups, missing fields), and
takes autonomous-but-human-gated actions per a YAML rules file — drafting
follow-up emails, updating deal stages, creating tasks, flagging for review —
auditing everything to SQLite. Built on lumifie_core.
"""

from crm_automation.models import (
    ActionType,
    AuditEntry,
    Contact,
    Deal,
    Decision,
    ProposedAction,
    RunSummary,
    Trigger,
    TriggerType,
)

__version__ = "0.1.0"

__all__ = [
    "ActionType",
    "AuditEntry",
    "Contact",
    "Deal",
    "Decision",
    "ProposedAction",
    "RunSummary",
    "Trigger",
    "TriggerType",
    "__version__",
]
