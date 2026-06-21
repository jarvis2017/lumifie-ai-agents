"""Construct a ready-to-use RAG chatbot from settings.

Wires the embedding backend (auto sentence-transformers → hashing fallback), the
persistent Chroma store, and the LLM provider. Falls back to the offline
:class:`StubProvider` when no credential is configured, so the demo and API run
with zero setup.
"""

from __future__ import annotations

from lumifie_core import LLMProvider, logger
from lumifie_core.provider import missing_credential, resolve_model

from rag_chatbot.chatbot import RagChatbot
from rag_chatbot.config import ChatbotSettings
from rag_chatbot.embeddings import build_embedding
from rag_chatbot.store import VectorStore
from rag_chatbot.stub import StubProvider


def build_store(settings: ChatbotSettings, *, persistent: bool = True) -> VectorStore:
    embedding = build_embedding(settings.embedding, settings.st_model)
    return VectorStore(
        embedding,
        path=settings.db_path,
        collection=settings.collection,
        persistent=persistent,
    )


def build_chatbot(
    settings: ChatbotSettings,
    *,
    store: VectorStore | None = None,
    force_stub: bool = False,
    persistent: bool = True,
) -> RagChatbot:
    resolved = resolve_model(settings.model)
    if force_stub or missing_credential(resolved):
        if not force_stub:
            logger.warning(
                "No credential for '{}'; using the offline rule-based stub provider. "
                "Set an API key (see .env.example) to use a real model.",
                resolved,
            )
        provider: LLMProvider | StubProvider = StubProvider()
    else:
        provider = LLMProvider.from_settings(settings)

    if store is None:
        store = build_store(settings, persistent=persistent)
    return RagChatbot(provider, settings, store)


__all__ = ["build_chatbot", "build_store"]
