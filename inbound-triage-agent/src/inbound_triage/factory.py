"""Construct a ready-to-use triage agent from settings.

Falls back to the offline :class:`StubProvider` when no credential is configured,
so the demo and webhook run with zero setup.
"""

from __future__ import annotations

from lumifie_core import LLMProvider, logger
from lumifie_core.provider import missing_credential, resolve_model

from inbound_triage.agent import InboundTriageAgent
from inbound_triage.config import TriageSettings
from inbound_triage.knowledge import RebuttalKnowledgeBase, load_rebuttals
from inbound_triage.stub import StubProvider


def build_agent(settings: TriageSettings, *, force_stub: bool = False) -> InboundTriageAgent:
    resolved = resolve_model(settings.model)
    if force_stub or missing_credential(resolved):
        if not force_stub:
            logger.warning(
                "No credential for '{}'; using the offline rule-based stub provider. "
                "Set an API key (see .env.example) to use a real model.",
                resolved,
            )
        provider: LLMProvider | StubProvider = StubProvider()
    else:
        provider = LLMProvider.from_settings(settings)

    kb = RebuttalKnowledgeBase(load_rebuttals(settings.kb_path))
    return InboundTriageAgent(provider, settings, kb)


__all__ = ["build_agent"]
