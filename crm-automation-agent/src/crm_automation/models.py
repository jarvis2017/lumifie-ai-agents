"""Typed models for the CRM automation agent.

These describe the records pulled from a CRM (contacts, deals), the trigger
conditions detected in them, the actions the agent proposes, and the audit and
run-summary records produced as it works. Everything is Pydantic so inputs are
validated at the boundary and outputs serialize cleanly to JSON.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    """The conditions the agent watches for across CRM records."""

    NEW_LEAD = "new_lead"
    DEAL_STALE = "deal_stale"
    FOLLOW_UP_OVERDUE = "follow_up_overdue"
    MISSING_FIELDS = "missing_fields"


class ActionType(str, Enum):
    """The actions a rule can take in response to a trigger."""

    DRAFT_FOLLOW_UP_EMAIL = "draft_follow_up_email"
    UPDATE_DEAL_STAGE = "update_deal_stage"
    CREATE_TASK = "create_task"
    FLAG_FOR_REVIEW = "flag_for_review"


class Decision(str, Enum):
    """The lifecycle state of a proposed action in the audit log."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTED = "executed"
    SKIPPED = "skipped"
    FAILED = "failed"


# External mutations require a human approval gate; everything else does not.
EXTERNAL_MUTATIONS: frozenset[ActionType] = frozenset(
    {ActionType.UPDATE_DEAL_STAGE, ActionType.CREATE_TASK}
)


class Contact(BaseModel):
    """A CRM contact (a person)."""

    id: str
    email: str | None = None
    name: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    last_contacted: datetime | None = None
    created_at: datetime | None = None
    # Populated by MISSING_FIELDS detection; not part of the source record.
    missing_required: list[str] = Field(default_factory=list)

    def display(self) -> str:
        return self.name or self.email or self.id


class Deal(BaseModel):
    """A CRM deal / opportunity."""

    id: str
    name: str
    stage: str
    amount: float | None = None
    last_activity_at: datetime | None = None
    created_at: datetime | None = None
    owner: str | None = None
    next_follow_up: date | None = None


class Trigger(BaseModel):
    """A detected condition tying a trigger type to a specific record."""

    type: TriggerType
    target_id: str
    detail: str
    # Lightweight context for actions/rendering (e.g. days stale, missing fields).
    context: dict[str, Any] = Field(default_factory=dict)


class ProposedAction(BaseModel):
    """An action the agent proposes in response to a matched trigger."""

    type: ActionType
    target_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    rule_name: str
    rationale: str
    trigger_type: TriggerType

    @property
    def requires_approval(self) -> bool:
        """External mutations require a human approval gate."""
        return self.type in EXTERNAL_MUTATIONS


class AuditEntry(BaseModel):
    """One row of the audit trail."""

    id: int | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rule_name: str
    trigger_type: TriggerType
    action_type: ActionType
    target_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    decision: Decision
    result: str = ""


class RunSummary(BaseModel):
    """Summary of a single end-to-end run."""

    source: str
    model: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dry_run: bool = False
    contacts_scanned: int = 0
    deals_scanned: int = 0
    triggers: list[Trigger] = Field(default_factory=list)
    proposed: list[ProposedAction] = Field(default_factory=list)
    audit: list[AuditEntry] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)

    def executed(self) -> list[AuditEntry]:
        return [a for a in self.audit if a.decision == Decision.EXECUTED]

    def by_decision(self, decision: Decision) -> list[AuditEntry]:
        return [a for a in self.audit if a.decision == decision]


__all__ = [
    "ActionType",
    "AuditEntry",
    "Contact",
    "Deal",
    "Decision",
    "EXTERNAL_MUTATIONS",
    "ProposedAction",
    "RunSummary",
    "Trigger",
    "TriggerType",
]
