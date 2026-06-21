"""FastAPI backend exposing the RAG chatbot.

Endpoints:
  * ``POST /ingest`` — ingest local paths and/or URLs into the vector store.
  * ``POST /ask``    — ask a question, get a cited :class:`Answer`.
  * ``GET  /health`` — liveness + the active model and chunk count.

The agent's model calls and Chroma I/O are synchronous, so handlers offload them
to a threadpool to keep the event loop responsive.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from rag_chatbot.chatbot import RagChatbot
from rag_chatbot.loaders import load_sources
from rag_chatbot.models import Answer, IngestResult


class IngestRequest(BaseModel):
    paths: list[str] = Field(default_factory=list, description="Local file paths.")
    urls: list[str] = Field(default_factory=list, description="http(s) URLs.")


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None


def create_app(chatbot: RagChatbot) -> FastAPI:
    app = FastAPI(
        title="Lumifie RAG Knowledge Chatbot",
        description="Answer questions over uploaded documents with inline source citations.",
        version="0.1.0",
    )
    settings = chatbot.settings

    @app.get("/health")
    async def health() -> dict[str, object]:
        count = await run_in_threadpool(chatbot._store.count)
        return {"status": "ok", "model": chatbot.provider.model, "chunks": count}

    @app.post("/ingest", response_model=IngestResult)
    async def ingest(req: IngestRequest) -> IngestResult:
        specs = [*req.paths, *req.urls]

        def _do() -> IngestResult:
            chunks = load_sources(
                specs,
                chunk_size=settings.chunk_size,
                overlap=settings.chunk_overlap,
                user_agent=settings.request_user_agent,
            )
            return chatbot._store.add_documents(chunks)

        return await run_in_threadpool(_do)

    @app.post("/ask", response_model=Answer)
    async def ask(req: AskRequest) -> Answer:
        return await run_in_threadpool(chatbot.ask, req.question, top_k=req.top_k)

    return app


def build_default_app() -> FastAPI:
    """App wired from environment settings — entry point for `uvicorn ...:app`."""
    from rag_chatbot.config import ChatbotSettings  # noqa: PLC0415
    from rag_chatbot.factory import build_chatbot  # noqa: PLC0415

    return create_app(build_chatbot(ChatbotSettings.from_env()))


__all__ = ["create_app", "build_default_app", "IngestRequest", "AskRequest"]
