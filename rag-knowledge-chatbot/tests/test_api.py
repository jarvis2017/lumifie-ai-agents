"""Tests for the FastAPI app (async, offline stub agent + hashing embedding)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rag_chatbot.api import create_app


@pytest.fixture
def client(chatbot):
    return TestClient(create_app(chatbot))


def test_health(client, chatbot):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["chunks"] > 0  # demo dataset already ingested in the fixture


def test_ask_returns_cited_answer(client):
    resp = client.post("/ask", json={"question": "How many vacation days do employees get?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
    assert data["citations"]
    assert 0.0 <= data["confidence"] <= 1.0


def test_ingest_endpoint_adds_and_dedups(client, tmp_path):
    doc = tmp_path / "newdoc.md"
    doc.write_text("Northwind ships internationally to the EU and Canada.", encoding="utf-8")

    first = client.post("/ingest", json={"paths": [str(doc)]}).json()
    assert first["chunks_added"] >= 1

    # Re-ingesting the same doc adds nothing new (dedup).
    second = client.post("/ingest", json={"paths": [str(doc)]}).json()
    assert second["chunks_added"] == 0
    assert second["chunks_skipped"] >= 1


def test_ask_validation_error(client):
    assert client.post("/ask", json={}).status_code == 422
