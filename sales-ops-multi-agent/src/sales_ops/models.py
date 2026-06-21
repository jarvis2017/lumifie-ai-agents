"""Pydantic models for every entity and state transition in the sales pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class LeadStage(str, Enum):
    PROSPECTED = "prospected"
    OUTREACH_DRAFTED = "outreach_drafted"
    CONTACTED = "contacted"
    REPLIED = "replied"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"


class ActionType(str, Enum):
    START_OUTREACH = "start_outreach"  # external: begin an outreach sequence / send email
    SEND_REPLY = "send_reply"  # external: reply to a prospect
    CRM_UPDATE = "crm_update"  # external: write to HubSpot/Airtable
    FLAG_REVIEW = "flag_review"  # internal: surface for a human, no external call


class ReplyIntent(str, Enum):
    INTERESTED = "interested"
    OBJECTION = "objection"
    NOT_NOW = "not_now"
    WRONG_PERSON = "wrong_person"
    UNSUBSCRIBE = "unsubscribe"
    NONE = "none"


class Decision(str, Enum):
    DRY_RUN = "dry_run"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


# -- entities ----------------------------------------------------------------


class Lead(BaseModel):
    id: str
    company: str
    domain: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    title: str | None = None
    source_url: str | None = None
    signals: list[str] = Field(default_factory=list)


class ScoredLead(Lead):
    icp_fit: int = Field(0, ge=0, le=100)
    tier: str = "Unknown"
    reasoning: str = ""
    rank: int = 0
    stage: LeadStage = LeadStage.PROSPECTED


class OutreachStep(BaseModel):
    channel: str = Field(..., description="'email' or 'linkedin'")
    day: int = Field(0, ge=0, description="Day offset in the sequence.")
    subject: str | None = None
    body: str


class OutreachSequence(BaseModel):
    lead_id: str
    steps: list[OutreachStep] = Field(default_factory=list)
    personalization_signals: list[str] = Field(default_factory=list)


class Reply(BaseModel):
    lead_id: str
    from_email: str
    subject: str = ""
    body: str = ""
    intent: ReplyIntent = ReplyIntent.NONE
    suggested_action: str = ""


class ProposedAction(BaseModel):
    id: str
    type: ActionType
    lead_id: str
    summary: str
    rationale: str = ""
    requires_approval: bool = True
    payload: dict = Field(default_factory=dict)


class ActionOutcome(BaseModel):
    action_id: str
    type: ActionType
    lead_id: str
    decision: Decision
    detail: str = ""
    ok: bool = True


class StaleDeal(BaseModel):
    lead_id: str
    company: str
    stage: str
    days_stale: int


class PipelineMetrics(BaseModel):
    leads_prospected: int = 0
    sequences_drafted: int = 0
    replies_processed: int = 0
    actions_proposed: int = 0
    actions_executed: int = 0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_reply_intent: dict[str, int] = Field(default_factory=dict)


class PipelineReport(BaseModel):
    pipeline_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metrics: PipelineMetrics
    stale_deals: list[StaleDeal] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    summary: str = ""


class PipelineResult(BaseModel):
    """The complete, durable result of one pipeline run — the top-level artifact."""

    pipeline_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model: str
    dry_run: bool
    leads: list[ScoredLead] = Field(default_factory=list)
    sequences: list[OutreachSequence] = Field(default_factory=list)
    replies: list[Reply] = Field(default_factory=list)
    actions: list[ActionOutcome] = Field(default_factory=list)
    report: PipelineReport | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)


__all__ = [
    "ActionOutcome",
    "ActionType",
    "Decision",
    "Lead",
    "LeadStage",
    "OutreachSequence",
    "OutreachStep",
    "PipelineMetrics",
    "PipelineReport",
    "PipelineResult",
    "ProposedAction",
    "Reply",
    "ReplyIntent",
    "ScoredLead",
    "StaleDeal",
]
