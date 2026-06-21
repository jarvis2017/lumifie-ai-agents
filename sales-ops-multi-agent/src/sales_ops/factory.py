"""Build a fully-wired orchestrator from settings + config (offline-friendly)."""

from __future__ import annotations

from lumifie_core import LLMProvider, logger
from lumifie_core.provider import missing_credential, resolve_model
from lumifie_core.web import DDGSearchBackend, JinaReader

from sales_ops.agent import SalesOpsOrchestrator
from sales_ops.approval import auto_approve, build_approver
from sales_ops.backends import FakeEmailSender, FakeMailbox
from sales_ops.config import SalesOpsConfig, SalesOpsSettings
from sales_ops.crm import FakeCRMClient, build_crm_client
from sales_ops.demo import DemoReader, DemoSearch, demo_replies
from sales_ops.store import SalesOpsStore


def build_orchestrator(
    settings: SalesOpsSettings,
    config: SalesOpsConfig,
    *,
    dry_run: bool = False,
    demo: bool = False,
    force_stub: bool = False,
) -> SalesOpsOrchestrator:
    resolved = resolve_model(settings.model)
    if force_stub or missing_credential(resolved):
        from sales_ops.stub import StubProvider  # noqa: PLC0415

        if not force_stub:
            logger.warning("No credential for '{}'; using offline stub provider.", resolved)
        provider = StubProvider()
    else:
        provider = LLMProvider.from_settings(settings)

    store = SalesOpsStore(settings.db_path)

    if demo:
        search, reader = DemoSearch(), DemoReader()
        mailbox, emailer, crm = FakeMailbox(demo_replies()), FakeEmailSender(), FakeCRMClient()
        approver = auto_approve  # demo is non-interactive; approvals auto-granted
    else:
        search = DDGSearchBackend(region="us-en")
        reader = JinaReader()
        mailbox = FakeMailbox()  # real IMAP/provider inbox is a deploy-time integration
        emailer = FakeEmailSender()  # swap SMTPEmailSender / provider in production
        crm = build_crm_client(config.crm)
        approver = build_approver(config.approval)

    return SalesOpsOrchestrator(
        provider,
        settings,
        config,
        store=store,
        search=search,
        reader=reader,
        mailbox=mailbox,
        emailer=emailer,
        crm_client=crm,
        approver=approver,
        dry_run=dry_run,
    )


__all__ = ["build_orchestrator"]
