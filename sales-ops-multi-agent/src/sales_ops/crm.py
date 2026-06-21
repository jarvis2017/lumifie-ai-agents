"""CRM Sync backends: HubSpot / Airtable (real, httpx) + a Fake for offline runs."""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from lumifie_core import logger

from sales_ops.config import CRMConfig
from sales_ops.models import ScoredLead


@runtime_checkable
class CRMClient(Protocol):
    def upsert_lead(self, lead: ScoredLead, stage: str) -> bool: ...


class FakeCRMClient:
    """Records upserts instead of calling a real CRM (demo + tests)."""

    def __init__(self) -> None:
        self.upserts: list[dict[str, str]] = []

    def upsert_lead(self, lead: ScoredLead, stage: str) -> bool:
        self.upserts.append({"lead_id": lead.id, "company": lead.company, "stage": stage})
        logger.info("[fake-crm] upsert {} -> {}", lead.company, stage)
        return True


class HubSpotClient:  # pragma: no cover - network/credentials
    """Minimal HubSpot contacts upsert via the v3 CRM API (token from env)."""

    def __init__(self, token: str) -> None:
        self.token = token

    def upsert_lead(self, lead: ScoredLead, stage: str) -> bool:
        import httpx  # noqa: PLC0415

        props = {
            "email": lead.contact_email or "",
            "company": lead.company,
            "lifecyclestage": stage,
            "hs_lead_status": lead.tier,
        }
        try:
            r = httpx.post(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"properties": props},
                timeout=30,
            )
            return r.status_code < 300
        except Exception as exc:
            logger.warning("HubSpot upsert failed: {}", exc)
            return False


class AirtableClient:  # pragma: no cover - network/credentials
    """Minimal Airtable row create (api key + base/table from env)."""

    def __init__(self, api_key: str, base_id: str, table: str) -> None:
        self.api_key, self.base_id, self.table = api_key, base_id, table

    def upsert_lead(self, lead: ScoredLead, stage: str) -> bool:
        import httpx  # noqa: PLC0415

        fields = {"Company": lead.company, "Email": lead.contact_email or "", "Stage": stage}
        try:
            r = httpx.post(
                f"https://api.airtable.com/v0/{self.base_id}/{self.table}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"fields": fields},
                timeout=30,
            )
            return r.status_code < 300
        except Exception as exc:
            logger.warning("Airtable upsert failed: {}", exc)
            return False


def build_crm_client(config: CRMConfig) -> CRMClient:
    """Resolve the configured CRM; fall back to the Fake when creds are absent."""
    provider = (config.provider or "none").lower()
    if provider == "hubspot":
        token = os.getenv("HUBSPOT_TOKEN")
        if token:
            return HubSpotClient(token)
        logger.warning("HUBSPOT_TOKEN not set; using FakeCRMClient.")
    elif provider == "airtable":
        api_key = os.getenv("AIRTABLE_API_KEY")
        base_id = os.getenv("AIRTABLE_BASE_ID")
        table = os.getenv("AIRTABLE_TABLE", "Leads")
        if api_key and base_id:
            return AirtableClient(api_key, base_id, table)
        logger.warning("Airtable creds not set; using FakeCRMClient.")
    return FakeCRMClient()


__all__ = ["CRMClient", "FakeCRMClient", "HubSpotClient", "AirtableClient", "build_crm_client"]
