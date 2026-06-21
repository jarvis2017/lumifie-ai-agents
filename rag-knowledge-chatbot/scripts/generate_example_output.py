"""Produce the committed example cited Q&A in examples/.

Runs the real pipeline over the bundled demo dataset using the offline hashing
embedding and the offline stub provider (no key/network), so the example reflects
actual agent behavior.

    python scripts/generate_example_output.py
"""

from __future__ import annotations

import json
from pathlib import Path

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
_QUESTIONS = [
    "How many vacation days do employees get and how do I request them?",
    "What is the return and refund policy?",
    "How many days per week must I be in the office?",
]


def main() -> None:
    # Smaller chunks than the default so the demo answer pinpoints the exact
    # passage with the offline (lexical) hashing embedding.
    settings = ChatbotSettings(model="claude-opus-4-8", chunk_size=450, chunk_overlap=80)
    store = VectorStore(HashingEmbedding(), collection="example", persistent=False)
    chunks = load_sources(
        _DEMO_FILES, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    store.add_documents(chunks)
    chatbot = RagChatbot(StubProvider(), settings, store)

    answers = [chatbot.ask(q) for q in _QUESTIONS]

    out_dir = _ROOT / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "example_answer.json").write_text(
        json.dumps([a.model_dump(mode="json") for a in answers], indent=2),
        encoding="utf-8",
    )

    lines = [
        "# RAG Knowledge Chatbot — example cited Q&A",
        "",
        "_Answers over the bundled demo dataset (company FAQ + remote-work policy), "
        "produced offline with the hashing embedding and the rule-based stub provider._",
        "",
    ]
    for a in answers:
        lines.append(f"## Q: {a.question}")
        lines.append("")
        lines.append(f"{a.answer}")
        lines.append("")
        lines.append(f"_Confidence: {a.confidence:.2f} | sources: {', '.join(a.used_sources) or '—'}_")
        lines.append("")
        if a.citations:
            lines.append("**Citations:**")
            for c in a.citations:
                loc = c.source + (f", p.{c.page}" if c.page is not None else "")
                lines.append(f"- [{c.n}] {loc} (chunk {c.chunk}): {c.snippet}")
            lines.append("")
    (out_dir / "example_answer.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote examples/example_answer.json and .md ({len(answers)} answers)")


if __name__ == "__main__":
    main()
