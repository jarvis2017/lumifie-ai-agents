"""Fixtures for inbound-triage tests (offline stub provider, in-memory Chroma)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inbound_triage.agent import InboundTriageAgent
from inbound_triage.config import TriageSettings
from inbound_triage.knowledge import RebuttalKnowledgeBase
from inbound_triage.models import InboundMessage
from inbound_triage.stub import StubProvider

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> TriageSettings:
    return TriageSettings(model="claude-opus-4-8")


@pytest.fixture
def agent(settings) -> InboundTriageAgent:
    return InboundTriageAgent(StubProvider(), settings, RebuttalKnowledgeBase())


@pytest.fixture
def mock_messages() -> dict[str, InboundMessage]:
    raw = json.loads((_ROOT / "data" / "mock_email.json").read_text())
    return {m["id"]: InboundMessage.model_validate(m) for m in raw}
