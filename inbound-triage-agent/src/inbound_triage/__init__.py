"""Inbound Triage Agent — FastAPI pipeline that classifies and routes inbound replies.

Lumifie Consulting. Receives email/message webhooks, classifies intent
(INTERESTED / OBJECTION / NOT_THE_RIGHT_PERSON / OUT_OF_OFFICE / SPAM), and routes:
objections → RAG rebuttal (Chroma), interested → booking link, wrong person → contact
extraction. Built on lumifie_core; multi-provider via litellm.
"""

from inbound_triage.models import (
    Action,
    Classification,
    InboundMessage,
    Intent,
    TriageResult,
)

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Classification",
    "InboundMessage",
    "Intent",
    "TriageResult",
    "__version__",
]
