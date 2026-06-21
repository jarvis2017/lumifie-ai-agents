"""FastAPI app exposing the triage pipeline as an async webhook.

The agent's model calls are synchronous (litellm), so the handler offloads them to
a threadpool to keep the event loop responsive under concurrent webhooks.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from inbound_triage.agent import InboundTriageAgent
from inbound_triage.models import InboundMessage, TriageResult


def create_app(agent: InboundTriageAgent) -> FastAPI:
    app = FastAPI(
        title="Lumifie Inbound Triage Agent",
        description="Classify inbound replies and route them (rebuttal / booking / contact).",
        version="0.1.0",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "model": agent.provider.model}

    @app.post("/webhook/email", response_model=TriageResult)
    async def webhook_email(message: InboundMessage) -> TriageResult:
        # Offload the blocking LLM/RAG work so the event loop stays free.
        return await run_in_threadpool(agent.triage, message)

    return app


def build_default_app() -> FastAPI:
    """App wired from environment settings — entry point for `uvicorn ...:app`."""
    from inbound_triage.config import TriageSettings  # noqa: PLC0415
    from inbound_triage.factory import build_agent  # noqa: PLC0415

    return create_app(build_agent(TriageSettings.from_env()))


__all__ = ["create_app", "build_default_app"]
