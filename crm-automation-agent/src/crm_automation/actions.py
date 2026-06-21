"""Execute a proposed action.

The executor maps each :class:`ProposedAction` to a concrete effect:

* ``draft_follow_up_email`` — asks the LLM (via the agent) for a draft; the draft
  is a *draft only*, stored and flagged for review. It never sends anything.
* ``update_deal_stage`` / ``create_task`` — external mutations via the CRM client
  (these only run once the approval gate has approved them; the agent gates them
  before calling here).
* ``flag_for_review`` — no external call; purely audited.

Every path returns a human-readable result string for the audit trail.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from crm_automation.crm.base import CRMClient
from crm_automation.models import ActionType, ProposedAction

if TYPE_CHECKING:  # avoid a circular import at runtime
    from crm_automation.agent import CRMAutomationAgent


class EmailDraft(BaseModel):
    """Structured email draft returned by the LLM (validated with Pydantic)."""

    subject: str = Field(..., description="Concise, specific subject line.")
    body: str = Field(..., description="The full email body, ready for a human to review.")


_EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string", "description": "Concise, specific subject line."},
        "body": {"type": "string", "description": "Full email body for human review."},
    },
    "required": ["subject", "body"],
}

_EMAIL_SYSTEM = (
    "You are a sales rep's assistant drafting a short, warm, professional follow-up "
    "email. Keep it under 150 words, specific, and low-pressure. Never invent facts "
    "about the customer. Output a subject and a body only."
)


class ActionExecutor:
    """Carries out proposed actions against a CRM client and the LLM."""

    def __init__(self, client: CRMClient, agent: CRMAutomationAgent) -> None:
        self._client = client
        self._agent = agent

    def execute(self, action: ProposedAction) -> str:
        if action.type == ActionType.DRAFT_FOLLOW_UP_EMAIL:
            return self._draft_email(action)
        if action.type == ActionType.UPDATE_DEAL_STAGE:
            return self._update_stage(action)
        if action.type == ActionType.CREATE_TASK:
            return self._create_task(action)
        if action.type == ActionType.FLAG_FOR_REVIEW:
            return self._flag(action)
        raise ValueError(f"Unknown action type: {action.type}")

    # -- handlers ----------------------------------------------------------

    def _draft_email(self, action: ProposedAction) -> str:
        context = action.params.get("trigger_detail", "")
        prompt = (
            f"Draft a follow-up email for CRM record {action.target_id}.\n"
            f"Context: {context}\n"
            f"Tone/intent: {action.params.get('intent', 'reconnect and offer help')}."
        )
        data = self._agent.structured(
            system=_EMAIL_SYSTEM, prompt=prompt, schema=_EMAIL_SCHEMA, tool_name="email_draft"
        )
        try:
            draft = EmailDraft.model_validate(data)
        except Exception:  # noqa: BLE001 - fall back to a safe placeholder draft
            draft = EmailDraft(
                subject="Following up",
                body="Hi — just circling back on our conversation. Happy to help however I can.",
            )
        # Store the draft on the action so it surfaces in the run summary/audit.
        action.params["draft_subject"] = draft.subject
        action.params["draft_body"] = draft.body
        # A draft never sends; flag it for human review.
        return f"Drafted follow-up email (FLAGGED FOR REVIEW, not sent): '{draft.subject}'."

    def _update_stage(self, action: ProposedAction) -> str:
        stage = str(action.params.get("stage", "")).strip()
        if not stage:
            raise ValueError("update_deal_stage requires a 'stage' param.")
        return self._client.update_deal_stage(action.target_id, stage)

    def _create_task(self, action: ProposedAction) -> str:
        subject = str(action.params.get("subject", "Follow up")).strip()
        due = _parse_due(action.params.get("due"), action.params.get("due_in_days"))
        return self._client.create_task(subject, due, action.target_id)

    def _flag(self, action: ProposedAction) -> str:
        reason = action.params.get("reason") or action.rationale
        return f"Flagged for review: {reason}"


def _parse_due(due: object, due_in_days: object) -> date | None:
    if isinstance(due, str) and due.strip():
        try:
            return date.fromisoformat(due[:10])
        except ValueError:
            return None
    if due_in_days is not None:
        from datetime import timedelta

        try:
            return (datetime.now().date() + timedelta(days=int(due_in_days)))
        except (TypeError, ValueError):
            return None
    return None


__all__ = ["ActionExecutor", "EmailDraft"]
