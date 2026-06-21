"""Fixtures for sales-ops tests: offline stub provider + demo backends, no network."""

from __future__ import annotations

import pytest

from sales_ops.agent import SalesOpsOrchestrator
from sales_ops.approval import auto_approve
from sales_ops.backends import FakeEmailSender, FakeMailbox
from sales_ops.config import DEFAULT_CONFIG, SalesOpsSettings
from sales_ops.crm import FakeCRMClient
from sales_ops.demo import DemoReader, DemoSearch, demo_replies
from sales_ops.store import SalesOpsStore
from sales_ops.stub import StubProvider


@pytest.fixture
def settings(tmp_path) -> SalesOpsSettings:
    return SalesOpsSettings(model="claude-opus-4-8", db_path=str(tmp_path / "sales.db"))


@pytest.fixture
def make_orch(settings):
    """Factory returning (orchestrator, emailer, crm, store) wired with fakes."""
    created: list[SalesOpsOrchestrator] = []

    def _make(*, dry_run: bool = False, approver=None):
        store = SalesOpsStore(settings.db_path)
        emailer = FakeEmailSender()
        crm = FakeCRMClient()
        orch = SalesOpsOrchestrator(
            StubProvider(), settings, DEFAULT_CONFIG,
            store=store, search=DemoSearch(), reader=DemoReader(),
            mailbox=FakeMailbox(demo_replies()), emailer=emailer, crm_client=crm,
            approver=approver or auto_approve, dry_run=dry_run,
        )
        created.append(orch)
        return orch, emailer, crm, store

    yield _make
    for o in created:
        o.store.close()
