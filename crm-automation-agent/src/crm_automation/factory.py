"""Construct a ready-to-use CRM automation agent from settings.

Chooses the CRM client by ``source`` (demo / hubspot / airtable) and falls back
to the offline :class:`StubProvider` when no LLM credential is configured, so the
demo and tests run with zero setup.
"""

from __future__ import annotations

from lumifie_core import LLMProvider, logger
from lumifie_core.provider import missing_credential, resolve_model

from crm_automation.agent import CRMAutomationAgent
from crm_automation.approval import Approver, interactive_approval
from crm_automation.audit import AuditLog
from crm_automation.config import CRMSettings
from crm_automation.crm import AirtableClient, CRMClient, FakeCRMClient, HubSpotClient
from crm_automation.rules import load_rules
from crm_automation.stub import StubProvider


def build_client(source: str) -> CRMClient:
    """Return a CRM client for the requested source."""
    src = source.lower()
    if src == "demo":
        return FakeCRMClient()
    if src == "hubspot":
        return HubSpotClient()
    if src == "airtable":
        return AirtableClient()
    raise ValueError(f"Unknown source '{source}'. Use one of: demo, hubspot, airtable.")


def build_provider(settings: CRMSettings, *, force_stub: bool = False):
    """Return a real LLM provider, or the offline stub when no credential is set."""
    resolved = resolve_model(settings.model)
    if force_stub or missing_credential(resolved):
        if not force_stub:
            logger.warning(
                "No credential for '{}'; using the offline stub provider for email "
                "drafts. Set an API key (see .env.example) to use a real model.",
                resolved,
            )
        return StubProvider()
    return LLMProvider.from_settings(settings)


def build_agent(
    settings: CRMSettings,
    *,
    client: CRMClient | None = None,
    approver: Approver = interactive_approval,
    audit_log: AuditLog | None = None,
    force_stub: bool = False,
) -> CRMAutomationAgent:
    """Wire up a CRM automation agent ready to ``run()``."""
    provider = build_provider(settings, force_stub=force_stub)
    crm_client = client or build_client(settings.source)
    ruleset = load_rules(settings.rules_path)
    log = audit_log or AuditLog(settings.db_path)
    return CRMAutomationAgent(
        provider, settings, crm_client, ruleset, approver=approver, audit_log=log
    )


__all__ = ["build_agent", "build_client", "build_provider"]
