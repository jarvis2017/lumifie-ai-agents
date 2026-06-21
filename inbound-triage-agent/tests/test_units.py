"""Unit tests for contact extraction and the RAG knowledge base."""

from __future__ import annotations

from inbound_triage.contacts import extract_emails, extract_phones
from inbound_triage.knowledge import RebuttalKnowledgeBase


def test_extract_emails():
    text = "Reach jordan.mills@vertexlabs.com or sales@acme.co, not bad@@x."
    emails = extract_emails(text)
    assert "jordan.mills@vertexlabs.com" in emails
    assert "sales@acme.co" in emails


def test_extract_phones():
    assert any("415" in p for p in extract_phones("call 415-555-0142 today"))
    assert extract_phones("no digits here") == []


def test_kb_retrieves_relevant_rebuttal():
    kb = RebuttalKnowledgeBase()
    hits = kb.retrieve("this is way too expensive and over our budget", k=2)
    assert hits
    assert any(h["id"] == "price" for h in hits)


def test_kb_custom_entries():
    kb = RebuttalKnowledgeBase(
        [{"id": "x", "objection": "security worries", "rebuttal": "share SOC2"}]
    )
    hits = kb.retrieve("we have security concerns", k=1)
    assert hits[0]["id"] == "x"
