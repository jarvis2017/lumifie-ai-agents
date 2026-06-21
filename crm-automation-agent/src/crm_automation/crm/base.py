"""The CRM client protocol every backend implements.

Keeping read and action methods behind one ``Protocol`` lets the agent run
against HubSpot, Airtable, or an in-memory fake interchangeably — and lets the
test suite inject a fake so the whole pipeline runs offline.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from crm_automation.models import Contact, Deal


@runtime_checkable
class CRMClient(Protocol):
    """Read + action surface the agent depends on."""

    name: str

    # -- reads -------------------------------------------------------------
    def fetch_contacts(self) -> list[Contact]:
        """Return all contacts visible to this client."""
        ...

    def fetch_deals(self) -> list[Deal]:
        """Return all deals/opportunities visible to this client."""
        ...

    # -- actions (external mutations) -------------------------------------
    def update_deal_stage(self, deal_id: str, stage: str) -> str:
        """Move a deal to a new pipeline stage. Returns a human-readable result."""
        ...

    def create_task(self, subject: str, due: date | None, related_id: str | None) -> str:
        """Create a follow-up task. Returns a human-readable result."""
        ...

    def add_note(self, related_id: str, body: str) -> str:
        """Attach a note to a record. Returns a human-readable result."""
        ...


__all__ = ["CRMClient"]
