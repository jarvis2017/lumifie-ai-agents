"""Minimal Airtable REST client for writing records.

Graceful and injectable: the HTTP call is swappable (``post_fn``) so callers stay
offline-testable, and every failure is logged and swallowed (returns ``None``) so a
CRM hiccup never breaks an agent pipeline. Reads ``AIRTABLE_API_KEY`` /
``AIRTABLE_BASE_ID`` from the environment via :meth:`from_env`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from lumifie_core.logging import logger

_API_ROOT = "https://api.airtable.com/v0"

# Exact field names of the shared "Outreach" table in the Lumifie CRM base.
OUTREACH_TABLE = "Outreach"

PostFn = Callable[[str, dict[str, Any]], tuple[int, Any]]  # (url, payload) -> (status, json)


class AirtableClient:
    """Writes records to an Airtable base."""

    def __init__(
        self,
        api_key: str,
        base_id: str,
        *,
        timeout: int = 20,
        post_fn: PostFn | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_id = base_id
        self.timeout = timeout
        self._post_fn = post_fn

    @classmethod
    def from_env(cls) -> AirtableClient | None:
        """Build from ``AIRTABLE_API_KEY`` + ``AIRTABLE_BASE_ID``; ``None`` if unset."""
        key = os.getenv("AIRTABLE_API_KEY")
        base = os.getenv("AIRTABLE_BASE_ID")
        if not (key and base):
            return None
        return cls(key, base)

    def create_record(
        self, table: str, fields: dict[str, Any], *, typecast: bool = True
    ) -> str | None:
        """Create one record; return its id, or ``None`` on any failure (logged)."""
        url = f"{_API_ROOT}/{self.base_id}/{quote(table)}"
        payload = {"fields": _drop_empty(fields), "typecast": typecast}
        try:
            status, data = self._post(url, payload)
        except Exception as exc:  # noqa: BLE001 - never break the pipeline on CRM errors
            logger.warning("Airtable create error: {}", exc)
            return None
        if status and status < 300:
            return (data or {}).get("id")
        logger.warning("Airtable create failed ({}): {}", status, str(data)[:200])
        return None

    def _post(self, url: str, payload: dict[str, Any]) -> tuple[int, Any]:
        if self._post_fn is not None:
            return self._post_fn(url, payload)
        import httpx  # noqa: PLC0415

        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            data = None
        return resp.status_code, data


def build_outreach_fields(
    *,
    company_name: str,
    website: str | None = None,
    contact_name: str | None = None,
    contact_title: str | None = None,
    linkedin_url: str | None = None,
    email: str | None = None,
    outreach_type: str | None = None,        # "Agency Subcontract" | "Direct Client"
    status: str = "Not Contacted",
    fit_score: int | None = None,
    pain_point: str | None = None,           # -> "Pain Point / Why Them"
    linkedin_dm: str | None = None,
    email_draft: str | None = None,
    date_found: str | None = None,           # ISO date (YYYY-MM-DD)
    date_contacted: str | None = None,
    follow_up_date: str | None = None,
    notes: str | None = None,
    agent_source: str | None = None,
) -> dict[str, Any]:
    """Map agent data to the exact field names of the CRM "Outreach" table."""
    return {
        "Company Name": company_name,
        "Website": website,
        "Contact Name": contact_name,
        "Contact Title": contact_title,
        "LinkedIn URL": linkedin_url,
        "Email": email,
        "Outreach Type": outreach_type,
        "Status": status,
        "Fit Score": fit_score,
        "Pain Point / Why Them": pain_point,
        "LinkedIn DM Draft": linkedin_dm,
        "Email Draft": email_draft,
        "Date Found": date_found,
        "Date Contacted": date_contacted,
        "Follow Up Date": follow_up_date,
        "Notes": notes,
        "Agent Source": agent_source,
    }


def _drop_empty(fields: dict[str, Any]) -> dict[str, Any]:
    """Drop None/empty values so Airtable doesn't reject unset typed fields."""
    return {k: v for k, v in fields.items() if v not in (None, "")}


__all__ = ["AirtableClient", "build_outreach_fields", "OUTREACH_TABLE"]
