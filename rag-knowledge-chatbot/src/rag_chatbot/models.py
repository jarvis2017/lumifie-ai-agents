"""Typed models and JSON schemas for the RAG chatbot."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    TEXT = "text"
    URL = "url"


class Chunk(BaseModel):
    """A single chunk of an ingested document with provenance metadata."""

    id: str = Field(..., description="Stable id = hash(source + chunk content).")
    text: str
    source: str = Field(..., description="Source name (filename or URL).")
    source_type: SourceType
    chunk_index: int = Field(..., ge=0, description="Position of the chunk in its source.")
    page: int | None = Field(None, description="1-based page number (PDF only).")

    def metadata(self) -> dict[str, Any]:
        """Chroma-safe metadata (no None values; Chroma rejects them)."""
        meta: dict[str, Any] = {
            "source": self.source,
            "source_type": self.source_type.value,
            "chunk_index": self.chunk_index,
        }
        if self.page is not None:
            meta["page"] = self.page
        return meta


class Retrieved(BaseModel):
    """A chunk returned from the vector store with its similarity score."""

    chunk: Chunk
    distance: float = Field(..., description="Chroma distance (lower = closer).")
    similarity: float = Field(..., ge=0.0, le=1.0, description="1 / (1 + distance).")


class Citation(BaseModel):
    """A numbered citation tying an answer back to a retrieved source."""

    n: int = Field(..., ge=1, description="Citation number used inline as [n].")
    source: str
    page: int | None = None
    chunk: int = Field(..., ge=0, description="Chunk index within the source.")
    snippet: str = Field(..., description="Short excerpt of the cited chunk.")


class Answer(BaseModel):
    """The chatbot's cited answer to one question."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    used_sources: list[str] = Field(default_factory=list)
    model: str = ""
    question: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    answered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestResult(BaseModel):
    """Outcome of an ingestion run."""

    sources: list[str] = Field(default_factory=list)
    chunks_added: int = 0
    chunks_skipped: int = 0  # already-present duplicates
    total_in_store: int = 0


# -- JSON schema the model is asked to fill for the answer -------------------


def answer_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The answer, citing sources inline as [1], [2].",
            },
            "cited": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "The citation numbers actually used in the answer.",
            },
        },
        "required": ["answer", "cited"],
        "additionalProperties": False,
    }


__all__ = [
    "Answer",
    "Chunk",
    "Citation",
    "IngestResult",
    "Retrieved",
    "SourceType",
    "answer_schema",
]
