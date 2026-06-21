"""Real HubSpot CRM client (v3 REST API) over httpx.

Reads its token from ``HUBSPOT_TOKEN``. Network access is only attempted when
this client is actually used (``--source hubspot``); the demo and tests use the
in-memory :class:`~crm_automation.crm.fake.FakeCRMClient` instead, so nothing
here runs offline.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import Any

import httpx
from lumifie_core import logger

from crm_automation.models import Contact, Deal

_BASE = "https://api.hubapi.com"
_CONTACT_PROPS = ["email", "firstname", "lastname", "phone", "company", "lastmodifieddate"]
_DEAL_PROPS = [
    "dealname",
    "dealstage",
    "amount",
    "hubspot_owner_id",
    "notes_last_updated",
    "createdate",
    "closedate",
]


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class HubSpotClient:
    """Minimal HubSpot CRM client covering the agent's read + action surface."""

    name = "hubspot"

    def __init__(self, token: str | None = None, *, client: httpx.Client | None = None) -> None:
        token = token or os.getenv("HUBSPOT_TOKEN")
        if not token:
            raise RuntimeError("HUBSPOT_TOKEN is not set; cannot use the HubSpot source.")
        self._client = client or httpx.Client(
            base_url=_BASE,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30.0,
        )

    # -- reads -------------------------------------------------------------
    def fetch_contacts(self) -> list[Contact]:
        data = self._get("/crm/v3/objects/contacts", {"properties": ",".join(_CONTACT_PROPS)})
        contacts: list[Contact] = []
        for row in data.get("results", []):
            p = row.get("properties", {})
            name = " ".join(x for x in (p.get("firstname"), p.get("lastname")) if x) or None
            contacts.append(
                Contact(
                    id=str(row.get("id")),
                    email=p.get("email"),
                    name=name,
                    fields={"company": p.get("company") or "", "phone": p.get("phone") or ""},
                    created_at=_parse_dt(row.get("createdAt")),
                    last_contacted=_parse_dt(p.get("lastmodifieddate")),
                )
            )
        return contacts

    def fetch_deals(self) -> list[Deal]:
        data = self._get("/crm/v3/objects/deals", {"properties": ",".join(_DEAL_PROPS)})
        deals: list[Deal] = []
        for row in data.get("results", []):
            p = row.get("properties", {})
            deals.append(
                Deal(
                    id=str(row.get("id")),
                    name=p.get("dealname") or "(unnamed deal)",
                    stage=p.get("dealstage") or "unknown",
                    amount=_to_float(p.get("amount")),
                    last_activity_at=_parse_dt(p.get("notes_last_updated")),
                    created_at=_parse_dt(p.get("createdate")),
                    owner=p.get("hubspot_owner_id"),
                    next_follow_up=_parse_date(p.get("closedate")),
                )
            )
        return deals

    # -- actions -----------------------------------------------------------
    def update_deal_stage(self, deal_id: str, stage: str) -> str:
        self._patch(f"/crm/v3/objects/deals/{deal_id}", {"properties": {"dealstage": stage}})
        return f"HubSpot deal {deal_id} moved to stage '{stage}'."

    def create_task(self, subject: str, due: date | None, related_id: str | None) -> str:
        props: dict[str, Any] = {"hs_task_subject": subject, "hs_task_status": "NOT_STARTED"}
        if due:
            props["hs_timestamp"] = f"{due.isoformat()}T09:00:00Z"
        body: dict[str, Any] = {"properties": props}
        if related_id:
            body["associations"] = [
                {
                    "to": {"id": related_id},
                    "types": [
                        {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}
                    ],
                }
            ]
        self._post("/crm/v3/objects/tasks", body)
        return f"HubSpot task created: '{subject}'."

    def add_note(self, related_id: str, body: str) -> str:
        self._post(
            "/crm/v3/objects/notes",
            {
                "properties": {
                    "hs_note_body": body,
                    "hs_timestamp": datetime.now(UTC).isoformat(),
                },
                "associations": [
                    {
                        "to": {"id": related_id},
                        "types": [
                            {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}
                        ],
                    }
                ],
            },
        )
        return f"HubSpot note added to {related_id}."

    # -- http helpers ------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.patch(path, json=body)
        resp.raise_for_status()
        return resp.json()


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        logger.warning("Could not parse amount '{}' as float.", value)
        return None


def _parse_date(value: Any) -> date | None:
    dt = _parse_dt(value)
    return dt.date() if dt else None


__all__ = ["HubSpotClient"]
