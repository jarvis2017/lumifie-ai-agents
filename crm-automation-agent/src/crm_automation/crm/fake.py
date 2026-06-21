"""In-memory CRM client seeded with realistic data.

Powers the offline ``--source demo`` (runs immediately, no credentials) and the
entire test suite. The seed data is hand-built so that each trigger condition —
new lead, stale deal, overdue follow-up, missing fields — fires against the
example rules, making the demo a faithful end-to-end illustration.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from crm_automation.models import Contact, Deal


def _days_ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def seed_records() -> tuple[list[Contact], list[Deal]]:
    """Return a realistic, trigger-rich set of contacts and deals."""
    today = datetime.now(UTC).date()
    contacts = [
        # Brand-new lead created today, missing phone + company -> NEW_LEAD + MISSING_FIELDS.
        Contact(
            id="c-1001",
            email="dana@brightpath.io",
            name="Dana Okoro",
            fields={"company": "", "phone": ""},
            created_at=_days_ago(0),
            last_contacted=None,
        ),
        # Established contact, fully populated, contacted recently -> no trigger.
        Contact(
            id="c-1002",
            email="marcus@vantage.co",
            name="Marcus Vael",
            fields={"company": "Vantage Co", "phone": "+1-555-0142"},
            created_at=_days_ago(120),
            last_contacted=_days_ago(3),
        ),
        # Older contact missing a phone number -> MISSING_FIELDS only.
        Contact(
            id="c-1003",
            email="priya@nimbus-labs.com",
            name="Priya Nair",
            fields={"company": "Nimbus Labs", "phone": ""},
            created_at=_days_ago(45),
            last_contacted=_days_ago(20),
        ),
    ]
    deals = [
        # Stale: no activity for 40 days -> DEAL_STALE.
        Deal(
            id="d-2001",
            name="BrightPath — Platform license",
            stage="Proposal Sent",
            amount=48000.0,
            last_activity_at=_days_ago(40),
            created_at=_days_ago(70),
            owner="Joe Stanton",
            next_follow_up=None,
        ),
        # Overdue follow-up scheduled in the past -> FOLLOW_UP_OVERDUE.
        Deal(
            id="d-2002",
            name="Vantage — Annual renewal",
            stage="Negotiation",
            amount=120000.0,
            last_activity_at=_days_ago(5),
            created_at=_days_ago(200),
            owner="Joe Stanton",
            next_follow_up=today - timedelta(days=4),
        ),
        # Brand-new deal created today -> NEW_LEAD; activity is fresh so not stale.
        Deal(
            id="d-2003",
            name="Nimbus Labs — Pilot",
            stage="Qualification",
            amount=15000.0,
            last_activity_at=_days_ago(0),
            created_at=_days_ago(0),
            owner="Joe Stanton",
            next_follow_up=today + timedelta(days=7),
        ),
        # Healthy deal: recent activity, future follow-up -> no trigger.
        Deal(
            id="d-2004",
            name="Vantage — Add-on seats",
            stage="Negotiation",
            amount=9000.0,
            last_activity_at=_days_ago(2),
            created_at=_days_ago(30),
            owner="Joe Stanton",
            next_follow_up=today + timedelta(days=3),
        ),
    ]
    return contacts, deals


class FakeCRMClient:
    """Deterministic, in-memory stand-in for a real CRM."""

    name = "demo"

    def __init__(
        self,
        contacts: list[Contact] | None = None,
        deals: list[Deal] | None = None,
    ) -> None:
        if contacts is None and deals is None:
            contacts, deals = seed_records()
        self._contacts = list(contacts or [])
        self._deals = {d.id: d for d in (deals or [])}
        # Recorded mutations, so tests (and the demo) can assert side effects.
        self.stage_updates: list[tuple[str, str]] = []
        self.tasks: list[dict[str, object]] = []
        self.notes: list[tuple[str, str]] = []

    # -- reads -------------------------------------------------------------
    def fetch_contacts(self) -> list[Contact]:
        return [c.model_copy(deep=True) for c in self._contacts]

    def fetch_deals(self) -> list[Deal]:
        return [d.model_copy(deep=True) for d in self._deals.values()]

    # -- actions -----------------------------------------------------------
    def update_deal_stage(self, deal_id: str, stage: str) -> str:
        if deal_id not in self._deals:
            raise KeyError(f"Unknown deal: {deal_id}")
        old = self._deals[deal_id].stage
        self._deals[deal_id].stage = stage
        self.stage_updates.append((deal_id, stage))
        return f"Deal {deal_id} moved from '{old}' to '{stage}'."

    def create_task(self, subject: str, due: date | None, related_id: str | None) -> str:
        task = {"subject": subject, "due": due, "related_id": related_id}
        self.tasks.append(task)
        due_str = due.isoformat() if due else "no due date"
        return f"Task created: '{subject}' (due {due_str}) on {related_id or 'unlinked'}."

    def add_note(self, related_id: str, body: str) -> str:
        self.notes.append((related_id, body))
        return f"Note added to {related_id} ({len(body)} chars)."


__all__ = ["FakeCRMClient", "seed_records"]
