"""Fixtures and fakes for CRM automation tests (no network, no API keys)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from lumifie_core import CompletionResult, ToolCall

from crm_automation.config import CRMSettings
from crm_automation.crm.fake import FakeCRMClient
from crm_automation.models import Contact, Deal
from crm_automation.rules import RuleSet, load_rules

_USAGE = {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160}


def _days_ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


class FakeEmailProvider:
    """Provider with tool support; always returns a structured email draft."""

    supports_tools = True
    model = "claude-opus-4-8"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        self.calls += 1
        args = {"subject": "Following up", "body": "Hi — just checking in. Happy to help."}
        name = (kwargs.get("tool_choice") or {}).get("function", {}).get("name", "email_draft")
        return CompletionResult(
            text=None,
            tool_calls=[ToolCall(id=f"c{self.calls}", name=name, arguments=args)],
            finish_reason="tool_calls",
            usage=_USAGE,
        )


@pytest.fixture
def email_provider() -> FakeEmailProvider:
    return FakeEmailProvider()


@pytest.fixture
def fake_client() -> FakeCRMClient:
    return FakeCRMClient()


@pytest.fixture
def sample_contacts() -> list[Contact]:
    return [
        Contact(id="c-new", email="new@x.io", name="New Lead", fields={"company": "", "phone": ""}, created_at=_days_ago(0)),
        Contact(id="c-old", email="old@x.io", name="Old Friend", fields={"company": "X", "phone": "1"}, created_at=_days_ago(90), last_contacted=_days_ago(2)),
    ]


@pytest.fixture
def sample_deals() -> list[Deal]:
    today = datetime.now(UTC).date()
    return [
        Deal(id="d-stale", name="Stale Deal", stage="Proposal", amount=1000.0, last_activity_at=_days_ago(50), created_at=_days_ago(90)),
        Deal(id="d-overdue", name="Overdue Deal", stage="Negotiation", last_activity_at=_days_ago(2), created_at=_days_ago(60), next_follow_up=today - timedelta(days=3)),
        Deal(id="d-new", name="New Deal", stage="Qualification", created_at=_days_ago(0), last_activity_at=_days_ago(0), next_follow_up=today + timedelta(days=5)),
    ]


@pytest.fixture
def settings(tmp_path) -> CRMSettings:
    return CRMSettings(
        model="claude-opus-4-8",
        source="demo",
        db_path=str(tmp_path / "audit.db"),
        rules_path="config/rules.example.yaml",
    )


@pytest.fixture
def ruleset() -> RuleSet:
    return load_rules("config/rules.example.yaml")
