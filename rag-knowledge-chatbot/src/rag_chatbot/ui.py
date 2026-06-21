"""Optional Gradio UI for the RAG chatbot.

``gradio`` is an OPTIONAL extra (``uv pip install -e ".[ui]"``); this module is
imported lazily by the CLI's ``ui`` command, which errors gracefully if it is not
installed. Provides a simple page to upload documents and ask questions, showing
the answer with its citations.
"""

from __future__ import annotations

from rag_chatbot.chatbot import RagChatbot
from rag_chatbot.config import ChatbotSettings
from rag_chatbot.loaders import load_sources


def _format_answer(answer) -> str:  # type: ignore[no-untyped-def]
    lines = [answer.answer, "", f"_Confidence: {answer.confidence:.2f}_", ""]
    if answer.citations:
        lines.append("**Sources:**")
        for c in answer.citations:
            loc = c.source + (f", p.{c.page}" if c.page is not None else "")
            lines.append(f"- [{c.n}] {loc} (chunk {c.chunk}): {c.snippet}")
    return "\n".join(lines)


def launch_ui(
    chatbot: RagChatbot,
    settings: ChatbotSettings,
    *,
    host: str = "127.0.0.1",
    port: int = 7860,
) -> None:
    import gradio as gr  # noqa: PLC0415

    def do_ingest(files: list[str] | None, urls: str) -> str:
        specs: list[str] = list(files or [])
        specs += [u.strip() for u in (urls or "").splitlines() if u.strip()]
        if not specs:
            return "Nothing to ingest."
        chunks = load_sources(
            specs,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
            user_agent=settings.request_user_agent,
        )
        result = chatbot._store.add_documents(chunks)
        return (
            f"Ingested {len(result.sources)} source(s): {result.chunks_added} added, "
            f"{result.chunks_skipped} skipped, {result.total_in_store} total."
        )

    def do_ask(question: str) -> str:
        if not question.strip():
            return "Ask a question above."
        return _format_answer(chatbot.ask(question))

    with gr.Blocks(title="Lumifie RAG Knowledge Chatbot") as demo:
        gr.Markdown("# Lumifie RAG Knowledge Chatbot\nUpload documents, then ask questions.")
        with gr.Tab("Ingest"):
            files = gr.File(label="Documents", file_count="multiple", type="filepath")
            urls = gr.Textbox(label="URLs (one per line)", lines=3)
            ingest_btn = gr.Button("Ingest")
            ingest_out = gr.Markdown()
            ingest_btn.click(do_ingest, [files, urls], ingest_out)
        with gr.Tab("Ask"):
            q = gr.Textbox(label="Question")
            ask_btn = gr.Button("Ask")
            ask_out = gr.Markdown()
            ask_btn.click(do_ask, q, ask_out)

    demo.launch(server_name=host, server_port=port)


__all__ = ["launch_ui"]
