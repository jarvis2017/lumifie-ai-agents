"""Fixtures for RAG chatbot tests (offline hashing embedding + stub provider).

Everything here runs with NO network and NO API keys: the vector store uses the
deterministic hashing embedding and a per-test temporary Chroma path, and the
chatbot uses the rule-based stub provider.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag_chatbot.chatbot import RagChatbot
from rag_chatbot.config import ChatbotSettings
from rag_chatbot.embeddings import HashingEmbedding
from rag_chatbot.loaders import load_sources
from rag_chatbot.store import VectorStore
from rag_chatbot.stub import StubProvider

_ROOT = Path(__file__).resolve().parents[1]
_DEMO_FILES = [
    str(_ROOT / "data" / "company_faq.md"),
    str(_ROOT / "data" / "remote_work_policy.md"),
]


@pytest.fixture
def settings(tmp_path) -> ChatbotSettings:
    return ChatbotSettings(
        model="claude-opus-4-8",
        db_path=str(tmp_path / "chroma"),
        chunk_size=500,
        chunk_overlap=80,
        top_k=4,
        embedding="hashing",
    )


@pytest.fixture
def store(settings) -> VectorStore:
    return VectorStore(
        HashingEmbedding(),
        path=settings.db_path,
        collection=settings.collection,
        persistent=True,
    )


@pytest.fixture
def populated_store(store, settings) -> VectorStore:
    chunks = load_sources(
        _DEMO_FILES, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    store.add_documents(chunks)
    return store


@pytest.fixture
def chatbot(populated_store, settings) -> RagChatbot:
    return RagChatbot(StubProvider(), settings, populated_store)


@pytest.fixture
def demo_files() -> list[str]:
    return list(_DEMO_FILES)
