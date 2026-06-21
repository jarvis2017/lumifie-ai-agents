"""CLI for the RAG knowledge chatbot.

Subcommands:
  * ``ingest <paths-or-urls...>`` — add documents to the vector store.
  * ``ask "question"``            — answer a question with citations.
  * ``serve``                     — run the FastAPI server.
  * ``demo``                      — ingest the bundled demo dataset, then answer.
  * ``ui``                        — launch the optional Gradio app (extra ``[ui]``).

With no API key the offline stub provider is used automatically, so `demo` and
`ask` work instantly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lumifie_core import configure_logging, logger

from rag_chatbot import __version__
from rag_chatbot.config import ChatbotSettings
from rag_chatbot.factory import build_chatbot, build_store
from rag_chatbot.loaders import load_sources
from rag_chatbot.models import Answer

# data/ lives at the agent root (src/rag_chatbot/cli.py -> parents[2]).
_ROOT = Path(__file__).resolve().parents[2]
_DEMO_FILES = [
    str(_ROOT / "data" / "company_faq.md"),
    str(_ROOT / "data" / "remote_work_policy.md"),
]
_DEMO_QUESTION = "How many vacation days do employees get and how do I request them?"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rag-chatbot",
        description="Answer questions over your documents with inline source citations.",
    )
    p.add_argument("--model", default=None, help="Model alias/id (or LITELLM_MODEL).")
    p.add_argument("--db", default=None, help="Chroma persistence path.")
    p.add_argument("--top-k", type=int, default=None, help="Chunks retrieved per question.")
    p.add_argument("--offline", action="store_true", help="Force the offline stub provider.")
    p.add_argument("--log-level", default=None)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command")

    sp_ingest = sub.add_parser("ingest", help="Ingest local paths and/or URLs.")
    sp_ingest.add_argument("sources", nargs="+", help="File paths or http(s) URLs.")

    sp_ask = sub.add_parser("ask", help="Ask a question.")
    sp_ask.add_argument("question", help="The question to answer.")

    sp_serve = sub.add_parser("serve", help="Run the FastAPI server.")
    sp_serve.add_argument("--host", default="127.0.0.1")
    sp_serve.add_argument("--port", type=int, default=8000)

    sp_demo = sub.add_parser("demo", help="Ingest the bundled demo dataset and answer.")
    sp_demo.add_argument("question", nargs="?", default=_DEMO_QUESTION, help="Optional question.")

    sp_ui = sub.add_parser("ui", help="Launch the optional Gradio UI (extra: [ui]).")
    sp_ui.add_argument("--host", default="127.0.0.1")
    sp_ui.add_argument("--port", type=int, default=7860)

    return p


def _settings(args: argparse.Namespace) -> ChatbotSettings:
    return ChatbotSettings.from_env(
        model=args.model,
        log_level=args.log_level,
        db_path=args.db,
        top_k=args.top_k,
    )


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = _settings(args)
    configure_logging(settings.log_level)

    if args.command == "ingest":
        return _cmd_ingest(args, settings)
    if args.command == "ask":
        return _cmd_ask(args, settings)
    if args.command == "serve":
        return _cmd_serve(args, settings)
    if args.command == "demo":
        return _cmd_demo(args, settings)
    if args.command == "ui":
        return _cmd_ui(args, settings)

    build_parser().print_help()
    return 0


# -- commands ---------------------------------------------------------------


def _cmd_ingest(args: argparse.Namespace, settings: ChatbotSettings) -> int:
    store = build_store(settings)
    try:
        chunks = load_sources(
            args.sources,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
            user_agent=settings.request_user_agent,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Ingestion failed: {}", exc)
        return 1
    result = store.add_documents(chunks)
    print(
        f"Ingested {len(result.sources)} source(s): "
        f"{result.chunks_added} chunk(s) added, {result.chunks_skipped} skipped, "
        f"{result.total_in_store} total in store."
    )
    return 0


def _cmd_ask(args: argparse.Namespace, settings: ChatbotSettings) -> int:
    chatbot = build_chatbot(settings, force_stub=args.offline)
    answer = chatbot.ask(args.question)
    _print_answer(answer)
    return 0


def _cmd_serve(args: argparse.Namespace, settings: ChatbotSettings) -> int:
    try:
        import uvicorn  # noqa: PLC0415
    except ImportError:
        logger.error("uvicorn is required to serve: uv pip install uvicorn")
        return 2
    from rag_chatbot.api import create_app  # noqa: PLC0415

    chatbot = build_chatbot(settings, force_stub=args.offline)
    logger.info(
        "Serving RAG chatbot on http://{}:{} (model: {})",
        args.host, args.port, chatbot.provider.model,
    )
    uvicorn.run(create_app(chatbot), host=args.host, port=args.port)
    return 0


def _cmd_demo(args: argparse.Namespace, settings: ChatbotSettings) -> int:
    chatbot = build_chatbot(settings, force_stub=args.offline)
    try:
        chunks = load_sources(
            _DEMO_FILES,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not load demo dataset: {}", exc)
        return 1
    result = chatbot._store.add_documents(chunks)
    logger.info(
        "Demo dataset ready: {} chunk(s) added, {} total.",
        result.chunks_added, result.total_in_store,
    )
    print(f'\nQ: {args.question}\n')
    _print_answer(chatbot.ask(args.question))
    return 0


def _cmd_ui(args: argparse.Namespace, settings: ChatbotSettings) -> int:
    from rag_chatbot.ui import launch_ui  # noqa: PLC0415

    chatbot = build_chatbot(settings, force_stub=args.offline)
    try:
        # gradio is imported lazily inside launch_ui; catch its absence here.
        launch_ui(chatbot, settings, host=args.host, port=args.port)
    except ImportError:
        logger.error(
            "Gradio is not installed. Install the UI extra: uv pip install -e \".[ui]\""
        )
        return 2
    return 0


def _print_answer(answer: Answer) -> None:
    print("=" * 70)
    print(f"model     : {answer.model}")
    print(f"confidence: {answer.confidence:.2f}")
    print("-" * 70)
    print(answer.answer)
    if answer.citations:
        print("\nSources:")
        for c in answer.citations:
            loc = c.source + (f", p.{c.page}" if c.page is not None else "")
            print(f"  [{c.n}] {loc} (chunk {c.chunk})")
            print(f"      {c.snippet}")
    print("=" * 70)


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
