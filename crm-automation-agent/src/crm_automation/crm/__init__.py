"""CRM client implementations behind a single injectable protocol.

The agent only ever talks to a :class:`CRMClient`. We ship three:

* :class:`FakeCRMClient` — in-memory, seeded with realistic sample data; powers
  the offline ``--source demo`` and the entire test suite (no network/keys).
* :class:`HubSpotClient` — real HubSpot CRM v3 over ``httpx``.
* :class:`AirtableClient` — real Airtable REST API over ``httpx``.
"""

from __future__ import annotations

from crm_automation.crm.airtable import AirtableClient
from crm_automation.crm.base import CRMClient
from crm_automation.crm.fake import FakeCRMClient, seed_records
from crm_automation.crm.hubspot import HubSpotClient

__all__ = [
    "AirtableClient",
    "CRMClient",
    "FakeCRMClient",
    "HubSpotClient",
    "seed_records",
]
