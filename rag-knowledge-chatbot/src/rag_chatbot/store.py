"""Persistent Chroma vector store with incremental, deduplicated ingestion.

Backed by ``chromadb.PersistentClient(path)`` so ingestion is INCREMENTAL —
adding new documents does not rebuild the index, and the store survives across
runs. Chunk ids are stable hashes of ``source + chunk content``
(:func:`rag_chatbot.loaders.chunk_id`), so re-ingesting the same content is
deduplicated: ids already present are skipped rather than re-embedded.

The embedding backend is injected, so tests use the offline hashing embedding
while production can use sentence-transformers.
"""

from __future__ import annotations

from chromadb.api.types import EmbeddingFunction
from lumifie_core import logger

from rag_chatbot.models import Chunk, IngestResult, Retrieved, SourceType


def distance_to_similarity(distance: float) -> float:
    """Map a Chroma distance (lower = closer, >= 0) to a [0, 1] similarity.

    Uses ``1 / (1 + distance)``: distance 0 → similarity 1.0, and similarity
    decays smoothly toward 0 as distance grows. Documented and reused for the
    chatbot's confidence score.
    """
    if distance < 0:
        distance = 0.0
    return 1.0 / (1.0 + distance)


class VectorStore:
    """A persistent Chroma collection of document chunks."""

    def __init__(
        self,
        embedding: EmbeddingFunction,
        *,
        path: str = "./chroma_rag",
        collection: str = "documents",
        persistent: bool = True,
    ) -> None:
        import chromadb  # noqa: PLC0415

        self._client = (
            chromadb.PersistentClient(path=path)
            if persistent
            else chromadb.EphemeralClient()
        )
        self._col = self._client.get_or_create_collection(
            collection, embedding_function=embedding
        )

    def count(self) -> int:
        return self._col.count()

    def add_documents(self, chunks: list[Chunk]) -> IngestResult:
        """Add chunks, skipping any whose id is already present (dedup)."""
        sources = list(dict.fromkeys(c.source for c in chunks))
        if not chunks:
            return IngestResult(sources=sources, total_in_store=self.count())

        # De-duplicate within the batch first (same id can recur across pages).
        unique: dict[str, Chunk] = {}
        for c in chunks:
            unique.setdefault(c.id, c)

        existing = self._existing_ids(list(unique.keys()))
        to_add = [c for cid, c in unique.items() if cid not in existing]
        skipped = len(unique) - len(to_add)

        if to_add:
            self._col.add(
                ids=[c.id for c in to_add],
                documents=[c.text for c in to_add],
                metadatas=[c.metadata() for c in to_add],
            )
        logger.info(
            "Ingest: {} added, {} skipped (already present); {} total.",
            len(to_add), skipped, self.count(),
        )
        return IngestResult(
            sources=sources,
            chunks_added=len(to_add),
            chunks_skipped=skipped,
            total_in_store=self.count(),
        )

    def query(self, text: str, top_k: int = 4) -> list[Retrieved]:
        """Return the ``top_k`` most relevant chunks with distance + similarity."""
        n = min(top_k, self.count())
        if n <= 0:
            return []
        res = self._col.query(
            query_texts=[text],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        ids = (res.get("ids") or [[]])[0]

        out: list[Retrieved] = []
        for cid, doc, meta, dist in zip(ids, docs, metas, dists, strict=False):
            meta = meta or {}
            chunk = Chunk(
                id=cid,
                text=doc,
                source=meta.get("source", "unknown"),
                source_type=SourceType(meta.get("source_type", "text")),
                chunk_index=int(meta.get("chunk_index", 0)),
                page=meta.get("page"),
            )
            distance = float(dist)
            out.append(
                Retrieved(
                    chunk=chunk,
                    distance=distance,
                    similarity=distance_to_similarity(distance),
                )
            )
        return out

    def _existing_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        got = self._col.get(ids=ids, include=[])
        return set(got.get("ids") or [])


__all__ = ["VectorStore", "distance_to_similarity"]
