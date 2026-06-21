"""The RAG chatbot agent: retrieve, build cited context, answer with citations.

Pipeline for one question:
  1. Retrieve the top-k most relevant chunks from the vector store.
  2. Build a numbered context block ([1], [2], …), one entry per chunk, carrying
     the source name and (for PDFs) the page number.
  3. Ask the LLM to answer USING ONLY that context, citing inline as [n].
  4. Return a typed :class:`Answer` with citations, used sources, and a
     confidence derived from retrieval similarity.

If retrieval finds nothing, the agent answers "I don't have enough information to
answer that." with low confidence — it never fabricates.

Structured output goes through ``lumifie_core.BaseAgent.structured`` (native tool
use where supported, JSON-mode fallback otherwise), so any litellm model works;
with no API key the offline :class:`rag_chatbot.stub.StubProvider` composes the
answer from the retrieved chunks.
"""

from __future__ import annotations

from lumifie_core import BaseAgent, LLMProvider

from rag_chatbot.config import ChatbotSettings
from rag_chatbot.models import Answer, Citation, Retrieved, answer_schema
from rag_chatbot.store import VectorStore

NO_CONTEXT_MESSAGE = "I don't have enough information to answer that."

ANSWER_SYSTEM = (
    "You are a precise knowledge assistant for a business. Answer the question "
    "USING ONLY the numbered context passages provided. Cite every claim inline "
    "with the passage number in square brackets, e.g. [1] or [2][3]. Do NOT use "
    "any outside knowledge. If the context does not contain the answer, reply "
    f'exactly: "{NO_CONTEXT_MESSAGE}". Keep the answer concise and factual.'
)

_SNIPPET_CHARS = 240


def _snippet(text: str, limit: int = _SNIPPET_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


class RagChatbot(BaseAgent):
    name = "rag-knowledge-chatbot"
    description = "Answers questions over uploaded documents, citing exact sources."

    def __init__(
        self,
        provider: LLMProvider,
        settings: ChatbotSettings,
        store: VectorStore,
    ) -> None:
        super().__init__(provider, settings)
        self.settings: ChatbotSettings = settings
        self._store = store

    # -- public API --------------------------------------------------------

    def run(self, question: str, *, top_k: int | None = None) -> Answer:  # type: ignore[override]
        return self.ask(question, top_k=top_k)

    def ask(self, question: str, *, top_k: int | None = None) -> Answer:
        k = top_k or self.settings.top_k
        hits = self._store.query(question, top_k=k)
        self.log.info("Retrieved {} chunk(s) for question.", len(hits))

        if not hits:
            return Answer(
                answer=NO_CONTEXT_MESSAGE,
                citations=[],
                confidence=0.0,
                used_sources=[],
                model=self.provider.model,
                question=question,
                token_usage=dict(self.token_usage),
            )

        context = self._build_context(hits)
        prompt = (
            f"Question: {question}\n\n"
            f"Numbered context passages:\n{context}\n\n"
            "Answer the question using only these passages, citing inline as [n]."
        )
        data = self.structured(
            system=ANSWER_SYSTEM,
            prompt=prompt,
            schema=answer_schema(),
            tool_name="answer",
        )
        answer_text = (data.get("answer") or "").strip() or NO_CONTEXT_MESSAGE
        cited_ns = self._cited_numbers(data.get("cited"), answer_text, len(hits))

        citations = [self._citation(n, hits[n - 1]) for n in cited_ns]
        used_sources = list(dict.fromkeys(c.source for c in citations))
        confidence = self._confidence(hits, answered=answer_text != NO_CONTEXT_MESSAGE)

        return Answer(
            answer=answer_text,
            citations=citations,
            confidence=confidence,
            used_sources=used_sources,
            model=self.provider.model,
            question=question,
            token_usage=dict(self.token_usage),
        )

    # -- helpers -----------------------------------------------------------

    def _build_context(self, hits: list[Retrieved]) -> str:
        lines: list[str] = []
        for i, hit in enumerate(hits, start=1):
            c = hit.chunk
            loc = f"{c.source}" + (f", p.{c.page}" if c.page is not None else "")
            lines.append(f"[{i}] (source: {loc})\n{c.text}")
        return "\n\n".join(lines)

    def _cited_numbers(
        self, raw: object, answer_text: str, n_hits: int
    ) -> list[int]:
        """Pick which passages to attach as citations.

        Prefer the numbers the model reported; otherwise parse [n] tokens out of
        the answer text. Keep only valid, in-range numbers, de-duplicated and
        ordered. If the model cited nothing but produced a real answer, fall back
        to citing the top hit so an answer is never uncited.
        """
        candidates: list[int] = []
        if isinstance(raw, list):
            for x in raw:
                try:
                    candidates.append(int(x))
                except (TypeError, ValueError):
                    continue
        if not candidates:
            candidates = self._parse_inline_citations(answer_text)

        seen: list[int] = []
        for n in candidates:
            if 1 <= n <= n_hits and n not in seen:
                seen.append(n)
        if not seen and answer_text != NO_CONTEXT_MESSAGE:
            seen = [1]
        return seen

    @staticmethod
    def _parse_inline_citations(text: str) -> list[int]:
        import re  # noqa: PLC0415

        return [int(m) for m in re.findall(r"\[(\d+)\]", text)]

    def _citation(self, n: int, hit: Retrieved) -> Citation:
        c = hit.chunk
        return Citation(
            n=n,
            source=c.source,
            page=c.page,
            chunk=c.chunk_index,
            snippet=_snippet(c.text),
        )

    def _confidence(self, hits: list[Retrieved], *, answered: bool) -> float:
        """Confidence from retrieval similarity of the top hits.

        We average the similarity of up to the top-3 retrieved passages (each
        similarity = 1 / (1 + chroma_distance), see ``store.distance_to_similarity``).
        If the model declined to answer, confidence is forced low (0.1) regardless
        of retrieval, since the context did not actually answer the question.
        """
        if not answered:
            return 0.1
        top = hits[:3]
        return round(sum(h.similarity for h in top) / len(top), 4)


__all__ = ["RagChatbot", "NO_CONTEXT_MESSAGE"]
