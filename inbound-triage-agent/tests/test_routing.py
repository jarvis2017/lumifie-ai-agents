"""End-to-end routing tests over the bundled mock payload (offline stub)."""

from __future__ import annotations

from inbound_triage.models import Action, Intent


def test_interested_routes_to_booking(agent, mock_messages):
    result = agent.triage(mock_messages["msg_interested_01"])
    assert result.intent is Intent.INTERESTED
    assert result.action is Action.BOOKING
    assert result.booking is not None
    assert "ref=msg_interested_01" in result.booking.link
    assert result.booking.reply


def test_objection_routes_to_rag_rebuttal(agent, mock_messages):
    result = agent.triage(mock_messages["msg_objection_01"])
    assert result.intent is Intent.OBJECTION
    assert result.action is Action.REBUTTAL
    assert result.rebuttal is not None
    assert result.rebuttal.body
    # RAG retrieved at least one playbook entry from the Chroma KB.
    assert result.rebuttal.sources


def test_wrong_person_routes_to_contact_extraction(agent, mock_messages):
    result = agent.triage(mock_messages["msg_wrongperson_01"])
    assert result.intent is Intent.NOT_THE_RIGHT_PERSON
    assert result.action is Action.EXTRACT_CONTACT
    assert result.contact is not None
    assert "jordan.mills@vertexlabs.com" in result.contact.emails
    assert any("415" in p for p in result.contact.phones)
    assert result.contact.referred_name == "Jordan Mills"


def test_out_of_office_snoozes(agent, mock_messages):
    result = agent.triage(mock_messages["msg_ooo_01"])
    assert result.intent is Intent.OUT_OF_OFFICE
    assert result.action is Action.SNOOZE
    assert result.rebuttal is None and result.booking is None


def test_spam_dropped(agent, mock_messages):
    result = agent.triage(mock_messages["msg_spam_01"])
    assert result.intent is Intent.SPAM
    assert result.action is Action.DROP


def test_all_mock_messages_triage(agent, mock_messages):
    # Every bundled message produces a valid result with a concrete action.
    for msg in mock_messages.values():
        result = agent.triage(msg)
        assert result.message_id == msg.id
        assert result.action in set(Action)
        assert isinstance(result.token_usage, dict)
