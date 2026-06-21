"""rag-knowledge-chatbot settings: shared CoreSettings plus RAG knobs."""

from __future__ import annotations

import os
from dataclasses import dataclass

from lumifie_core import CoreSettings, env_int


@dataclass
class ChatbotSettings(CoreSettings):
    """Provider-agnostic settings plus ingestion/retrieval knobs."""

    db_path: str = "./chroma_rag"  # Chroma PersistentClient directory
    collection: str = "documents"
    chunk_size: int = 1000  # characters per chunk
    chunk_overlap: int = 150  # character overlap between consecutive chunks
    top_k: int = 4  # chunks retrieved per question
    embedding: str = "auto"  # "auto" | "sentence-transformers" | "hashing"
    st_model: str = "all-MiniLM-L6-v2"  # sentence-transformers model id
    request_user_agent: str = "lumifie-rag-chatbot/0.1"  # for URL fetches

    @classmethod
    def from_env(cls, **overrides):
        settings = super().from_env(**overrides)
        settings.db_path = os.getenv("RAG_DB_PATH", "./chroma_rag")
        settings.collection = os.getenv("RAG_COLLECTION", "documents")
        settings.chunk_size = env_int("RAG_CHUNK_SIZE", 1000)
        settings.chunk_overlap = env_int("RAG_CHUNK_OVERLAP", 150)
        settings.top_k = env_int("RAG_TOP_K", 4)
        settings.embedding = os.getenv("RAG_EMBEDDING", "auto")
        settings.st_model = os.getenv("RAG_ST_MODEL", "all-MiniLM-L6-v2")
        settings.request_user_agent = os.getenv(
            "RAG_USER_AGENT", "lumifie-rag-chatbot/0.1"
        )
        for key, value in overrides.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        return settings


__all__ = ["ChatbotSettings"]
