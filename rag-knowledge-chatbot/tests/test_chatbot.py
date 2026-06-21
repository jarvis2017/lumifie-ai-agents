"""Tests for the RAG chatbot: citations, confidence, and the no-context path."""

from __future__ import annotations

from lumifie_core import CompletionResult, ToolCall

from rag_chatbot.chatbot import NO_CONTEXT_MESSAGE, RagChatbot
from rag_chatbot.embeddings import HashingEmbedding
from rag_chatbot.store import VectorStore


class FakeProvider:
    """A fake LLM provider that echoes a fixed cited answer (offline, no network)."""

    supports_tools = True
    model = "fake:test"

    def __init__(self, answer: str = "Employees accrue 20 days of vacation [1].",
                 cited: list[int] | None = None) -> None:
        self._answer = answer
        self._cited = cited if cited is not None else [1]

    def complete(self, messages, **kwargs):
        return CompletionResult(
            text=None,
            tool_calls=[
                ToolCall(
                    id="t",
                    name="answer",
                    arguments={"answer": self._answer, "cited": self._cited},
                )
            ],
            finish_reason="tool_calls",
            usage={"input_tokens": 5, "output_tokens": 7, "total_tokens": 12},
        )


def test_stub_answer_cites_sources(chatbot):
    answer = chatbot.ask("How many vacation days do employees get?")
    assert answer.answer
    assert answer.citations
    assert answer.confidence > 0.0
    assert answer.used_sources
    # Citation references a real demo source.
    assert any("policy" in c.source.lower() or "faq" in c.source.lower() for c in answer.citations)


def test_confidence_in_range(chatbot):
    answer = chatbot.ask("What is the warranty on power tools?")
    assert 0.0 <= answer.confidence <= 1.0


def test_citation_points_at_correct_source(populated_store, settings):
    bot = RagChatbot(FakeProvider(), settings, populated_store)
    answer = bot.ask("How many vacation days do employees accrue per year?")
    assert answer.citations
    c = answer.citations[0]
    assert c.n == 1
    assert c.snippet
    assert c.source  # has a real source name
    # token usage tracked through BaseAgent.complete
    assert answer.token_usage["total_tokens"] == 12


def test_no_relevant_chunks_returns_low_confidence(settings, tmp_path):
    empty = VectorStore(
        HashingEmbedding(), path=str(tmp_path / "empty"), collection="documents"
    )
    bot = RagChatbot(FakeProvider(), settings, empty)
    answer = bot.ask("anything at all")
    assert answer.answer == NO_CONTEXT_MESSAGE
    assert answer.confidence == 0.0
    assert answer.citations == []


def test_model_declines_forces_low_confidence(populated_store, settings):
    bot = RagChatbot(
        FakeProvider(answer=NO_CONTEXT_MESSAGE, cited=[]), settings, populated_store
    )
    answer = bot.ask("What is the airspeed velocity of an unladen swallow?")
    assert answer.answer == NO_CONTEXT_MESSAGE
    assert answer.confidence == 0.1


def test_inline_citation_parsed_when_model_omits_cited(populated_store, settings):
    # Model reports no 'cited' list but uses [2] inline -> parsed from text.
    bot = RagChatbot(
        FakeProvider(answer="See the policy [2].", cited=[]), settings, populated_store
    )
    answer = bot.ask("How do I request vacation?")
    assert answer.citations
    assert any(c.n == 2 for c in answer.citations)
