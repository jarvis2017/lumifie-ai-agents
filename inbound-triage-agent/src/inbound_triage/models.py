"""Typed models and JSON schemas for inbound message triage."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    INTERESTED = "INTERESTED"
    OBJECTION = "OBJECTION"
    NOT_THE_RIGHT_PERSON = "NOT_THE_RIGHT_PERSON"
    OUT_OF_OFFICE = "OUT_OF_OFFICE"
    SPAM = "SPAM"


class Action(str, Enum):
    REBUTTAL = "rebuttal"
    BOOKING = "booking"
    EXTRACT_CONTACT = "extract_contact"
    SNOOZE = "snooze"
    DROP = "drop"


class InboundMessage(BaseModel):
    """An incoming email/message webhook payload."""

    id: str = Field(..., description="Provider message id.")
    sender: str = Field(..., description="Sender email address.")
    sender_name: str | None = None
    subject: str = ""
    body: str = Field(..., description="Message body (plain text).")
    received_at: datetime | None = None

    def as_text(self) -> str:
        who = f"{self.sender_name} <{self.sender}>" if self.sender_name else self.sender
        return f"From: {who}\nSubject: {self.subject}\n\n{self.body}"


class Classification(BaseModel):
    intent: Intent
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reasoning: str = ""


class RebuttalResult(BaseModel):
    body: str
    key_points: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list, description="Knowledge-base entries used.")


class BookingResult(BaseModel):
    link: str
    reply: str


class ContactExtraction(BaseModel):
    referred_name: str | None = None
    referred_title: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    note: str = ""


class TriageResult(BaseModel):
    """The full triage decision and the action taken for one message."""

    message_id: str
    intent: Intent
    confidence: float
    reasoning: str
    action: Action
    model: str
    rebuttal: RebuttalResult | None = None
    booking: BookingResult | None = None
    contact: ContactExtraction | None = None
    handled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    token_usage: dict[str, int] = Field(default_factory=dict)


# -- JSON schemas the model is asked to fill --------------------------------


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def classification_schema() -> dict[str, Any]:
    return _obj(
        {
            "intent": {"type": "string", "enum": [i.value for i in Intent]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
        },
        ["intent", "confidence", "reasoning"],
    )


def rebuttal_schema() -> dict[str, Any]:
    return _obj(
        {
            "body": {"type": "string", "description": "The rebuttal reply to send."},
            "key_points": {"type": "array", "items": {"type": "string"}},
        },
        ["body", "key_points"],
    )


def contact_schema() -> dict[str, Any]:
    return _obj(
        {
            "referred_name": {"type": ["string", "null"]},
            "referred_title": {"type": ["string", "null"]},
            "emails": {"type": "array", "items": {"type": "string"}},
            "phones": {"type": "array", "items": {"type": "string"}},
            "note": {"type": "string"},
        },
        ["referred_name", "referred_title", "emails", "phones", "note"],
    )


__all__ = [
    "Action",
    "BookingResult",
    "Classification",
    "ContactExtraction",
    "InboundMessage",
    "Intent",
    "RebuttalResult",
    "TriageResult",
    "classification_schema",
    "contact_schema",
    "rebuttal_schema",
]
