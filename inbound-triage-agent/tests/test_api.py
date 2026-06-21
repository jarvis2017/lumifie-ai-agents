"""Tests for the FastAPI webhook (async, offline stub agent)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from inbound_triage.api import create_app


@pytest.fixture
def client(agent):
    return TestClient(create_app(agent))


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_classifies_and_routes(client):
    payload = {
        "id": "wh_1",
        "sender": "lee@globex.com",
        "sender_name": "Lee",
        "subject": "Re: intro",
        "body": "Sounds interesting, I'd love a demo — send me a time.",
    }
    resp = client.post("/webhook/email", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "INTERESTED"
    assert data["action"] == "booking"
    assert data["booking"]["link"].endswith("ref=wh_1")


def test_webhook_objection_returns_rebuttal(client):
    payload = {
        "id": "wh_2",
        "sender": "ops@initech.com",
        "subject": "Re: intro",
        "body": "Too expensive and we already use a competitor.",
    }
    data = client.post("/webhook/email", json=payload).json()
    assert data["intent"] == "OBJECTION"
    assert data["action"] == "rebuttal"
    assert data["rebuttal"]["body"]


def test_webhook_validation_error(client):
    # Missing required fields -> 422 from FastAPI/Pydantic.
    assert client.post("/webhook/email", json={"subject": "x"}).status_code == 422
