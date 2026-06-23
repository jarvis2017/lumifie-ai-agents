"""Tests for the Airtable client (offline; injected post_fn)."""

from __future__ import annotations

from typing import Any

from lumifie_core import AirtableClient, build_outreach_fields


class _Recorder:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, payload: dict[str, Any]):
        self.calls.append((url, payload))
        return self.status, {"id": "recABC", "fields": payload["fields"]}


def test_create_record_posts_and_returns_id():
    rec = _Recorder()
    client = AirtableClient("key", "appBASE", post_fn=rec)
    rid = client.create_record("Outreach", {"Company Name": "Acme", "Fit Score": 9})
    assert rid == "recABC"
    url, payload = rec.calls[0]
    assert url == "https://api.airtable.com/v0/appBASE/Outreach"
    assert payload["typecast"] is True
    assert payload["fields"] == {"Company Name": "Acme", "Fit Score": 9}


def test_table_name_is_url_encoded():
    rec = _Recorder()
    AirtableClient("k", "appB", post_fn=rec).create_record("My Table", {"Company Name": "X"})
    assert rec.calls[0][0].endswith("/appB/My%20Table")


def test_failure_status_returns_none():
    rec = _Recorder(status=422)
    assert AirtableClient("k", "appB", post_fn=rec).create_record("Outreach", {"Company Name": "X"}) is None


def test_exception_is_swallowed():
    def boom(url, payload):
        raise RuntimeError("network down")

    assert AirtableClient("k", "appB", post_fn=boom).create_record("Outreach", {"Company Name": "X"}) is None


def test_from_env(monkeypatch):
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    monkeypatch.delenv("AIRTABLE_BASE_ID", raising=False)
    assert AirtableClient.from_env() is None
    monkeypatch.setenv("AIRTABLE_API_KEY", "k")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appB")
    client = AirtableClient.from_env()
    assert client is not None and client.base_id == "appB"


def test_build_outreach_fields_maps_names_and_drops_empty():
    fields = build_outreach_fields(
        company_name="Acme", website="https://acme.com", outreach_type="Direct Client",
        fit_score=8, pain_point="manual reporting", agent_source="lead-gen",
        contact_name=None,  # dropped
    )
    assert fields["Company Name"] == "Acme"
    assert fields["Outreach Type"] == "Direct Client"
    assert fields["Pain Point / Why Them"] == "manual reporting"
    assert fields["Agent Source"] == "lead-gen"
    # None/empty values are dropped at create time.
    rec = _Recorder()
    AirtableClient("k", "appB", post_fn=rec).create_record("Outreach", fields)
    assert "Contact Name" not in rec.calls[0][1]["fields"]
