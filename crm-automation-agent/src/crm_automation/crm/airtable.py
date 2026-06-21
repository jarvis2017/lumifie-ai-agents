"""Real Airtable client (REST API) over httpx.

Reads ``AIRTABLE_API_KEY`` and ``AIRTABLE_BASE_ID``; table names default to
``Contacts`` / ``Deals`` and are overridable via env. Network is only attempted
when this client is actually used (``--source airtable``); the demo and tests use
the in-memory fake instead.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from lumifie_core import logger

from crm_automation.models import Contact, Deal

_BASE = "https://api.airtable.com/v0"


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class AirtableClient:
    """Minimal Airtable client covering the agent's read + action surface."""

    name = "airtable"

    def __init__(
        self,
        api_key: str | None = None,
        base_id: str | None = None,
        *,
        contacts_table: str | None = None,
        deals_table: str | None = None,
        client: Any | None = None,
    ) -> None:
        api_key = api_key or os.getenv("AIRTABLE_API_KEY")
        base_id = base_id or os.getenv("AIRTABLE_BASE_ID")
        if not api_key or not base_id:
            raise RuntimeError(
                "AIRTABLE_API_KEY and AIRTABLE_BASE_ID must be set to use the Airtable source."
            )
        self._base_id = base_id
        self._contacts_table = contacts_table or os.getenv("AIRTABLE_CONTACTS_TABLE", "Contacts")
        self._deals_table = deals_table or os.getenv("AIRTABLE_DEALS_TABLE", "Deals")
        if client is None:
            import httpx  # noqa: PLC0415 - only needed for live use

            client = httpx.Client(
                base_url=f"{_BASE}/{base_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0,
            )
        self._client = client

    # -- reads -------------------------------------------------------------
    def fetch_contacts(self) -> list[Contact]:
        contacts: list[Contact] = []
        for rec in self._list(self._contacts_table):
            f = rec.get("fields", {})
            contacts.append(
                Contact(
                    id=str(rec.get("id")),
                    email=f.get("Email"),
                    name=f.get("Name"),
                    fields={"company": f.get("Company") or "", "phone": f.get("Phone") or ""},
                    created_at=_parse_dt(rec.get("createdTime")),
                    last_contacted=_parse_dt(f.get("Last Contacted")),
                )
            )
        return contacts

    def fetch_deals(self) -> list[Deal]:
        deals: list[Deal] = []
        for rec in self._list(self._deals_table):
            f = rec.get("fields", {})
            deals.append(
                Deal(
                    id=str(rec.get("id")),
                    name=f.get("Name") or "(unnamed deal)",
                    stage=f.get("Stage") or "unknown",
                    amount=_to_float(f.get("Amount")),
                    last_activity_at=_parse_dt(f.get("Last Activity")),
                    created_at=_parse_dt(rec.get("createdTime")),
                    owner=f.get("Owner"),
                    next_follow_up=_parse_date(f.get("Next Follow Up")),
                )
            )
        return deals

    # -- actions -----------------------------------------------------------
    def update_deal_stage(self, deal_id: str, stage: str) -> str:
        self._patch(self._deals_table, deal_id, {"Stage": stage})
        return f"Airtable deal {deal_id} moved to stage '{stage}'."

    def create_task(self, subject: str, due: date | None, related_id: str | None) -> str:
        table = os.getenv("AIRTABLE_TASKS_TABLE", "Tasks")
        fields: dict[str, Any] = {"Subject": subject}
        if due:
            fields["Due"] = due.isoformat()
        if related_id:
            fields["Related"] = [related_id]
        self._create(table, fields)
        return f"Airtable task created: '{subject}'."

    def add_note(self, related_id: str, body: str) -> str:
        self._patch(self._deals_table, related_id, {"Notes": body})
        return f"Airtable note added to {related_id}."

    # -- http helpers ------------------------------------------------------
    def _list(self, table: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            params = {"offset": offset} if offset else {}
            resp = self._client.get(f"/{table}", params=params)
            resp.raise_for_status()
            data = resp.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        return records

    def _patch(self, table: str, record_id: str, fields: dict[str, Any]) -> None:
        resp = self._client.patch(f"/{table}/{record_id}", json={"fields": fields})
        resp.raise_for_status()

    def _create(self, table: str, fields: dict[str, Any]) -> None:
        resp = self._client.post(f"/{table}", json={"fields": fields})
        resp.raise_for_status()


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        logger.warning("Could not parse amount '{}' as float.", value)
        return None


__all__ = ["AirtableClient"]
