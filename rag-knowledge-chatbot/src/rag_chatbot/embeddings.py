"""Embedding backends for the vector store.

Two interchangeable backends, both implementing Chroma's ``EmbeddingFunction``:

* :class:`HashingEmbedding` — a deterministic, dependency-free md5 bag-of-words
  embedding. Works fully offline, reproducibly across processes, and is what the
  tests use. No model download, no torch.
* :class:`SentenceTransformerEmbedding` — production default, wraps
  ``sentence-transformers`` (``all-MiniLM-L6-v2`` by default) for real semantic
  recall. ``sentence-transformers`` is an OPTIONAL extra (``pip install -e
  ".[st]"``) so torch is never pulled into dev/CI.

:func:`build_embedding` resolves a backend from settings and **auto-falls back**
to the hashing backend (with a logged warning) when sentence-transformers or its
model is unavailable, so ingestion/querying never hard-fail on a missing model.
"""

from __future__ import annotations

import hashlib
from typing import Any

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from lumifie_core import logger


class HashingEmbedding(EmbeddingFunction):
    """Deterministic bag-of-words hashing embedding (offline, reproducible).

    Tokens are lower-cased and hashed into a fixed-width vector; the vector is
    L2-normalized so retrieval ranks by term overlap (cosine-like) rather than by
    document length. A larger ``dim`` reduces hash collisions for sharper recall.
    """

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        out: list[list[float]] = []
        for doc in input:
            vec = [0.0] * self._dim
            for tok in self._tokens(doc):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % self._dim] += 1.0
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out

    @staticmethod
    def _tokens(doc: str) -> list[str]:
        import re  # noqa: PLC0415

        # Split on non-alphanumerics so "vacation." and "vacation" match, and
        # drop very short tokens that add noise.
        return [t for t in re.split(r"[^a-z0-9]+", doc.lower()) if len(t) > 1]

    @staticmethod
    def name() -> str:
        return "lumifie-hashing"

    def get_config(self) -> dict[str, Any]:
        return {"dim": self._dim}

    @classmethod
    def build_from_config(cls, config: dict[str, Any]) -> HashingEmbedding:
        return cls(**config)


class SentenceTransformerEmbedding(EmbeddingFunction):
    """Semantic embedding via ``sentence-transformers`` (production default).

    Imports the heavy dependency lazily so the package imports cleanly without the
    ``[st]`` extra installed; a missing dependency or model raises here and the
    caller (:func:`build_embedding`) falls back to hashing.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        vectors = self._model.encode(
            list(input), convert_to_numpy=True, normalize_embeddings=True
        )
        return [v.tolist() for v in vectors]

    @staticmethod
    def name() -> str:
        return "lumifie-sentence-transformer"

    def get_config(self) -> dict[str, Any]:
        return {"model_name": self._model_name}

    @classmethod
    def build_from_config(cls, config: dict[str, Any]) -> SentenceTransformerEmbedding:
        return cls(**config)


def build_embedding(kind: str = "auto", st_model: str = "all-MiniLM-L6-v2") -> EmbeddingFunction:
    """Resolve an embedding backend, auto-falling back to hashing offline.

    ``kind``:
      * ``"hashing"`` — always the offline hashing backend.
      * ``"sentence-transformers"`` — require the real backend (still falls back
        with a warning if it cannot load, so callers never crash).
      * ``"auto"`` (default) — try sentence-transformers, fall back to hashing.
    """
    if kind == "hashing":
        return HashingEmbedding()

    try:
        backend = SentenceTransformerEmbedding(st_model)
        logger.info("Using sentence-transformers embedding ({}).", st_model)
        return backend
    except Exception as exc:  # noqa: BLE001 — any import/model error -> fall back
        logger.warning(
            "sentence-transformers unavailable ({}); falling back to the offline "
            "hashing embedding. Install with: uv pip install -e \".[st]\".",
            exc,
        )
        return HashingEmbedding()


__all__ = [
    "HashingEmbedding",
    "SentenceTransformerEmbedding",
    "build_embedding",
]
