"""RAG knowledge base for objection rebuttals, backed by Chroma.

Uses a deterministic, dependency-free hashing embedding so retrieval works fully
offline (no model downloads, reproducible across processes). Swap in a real
embedding function for production-grade semantic recall.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from lumifie_core import logger


class HashingEmbedding(EmbeddingFunction):
    """Deterministic bag-of-words hashing embedding (offline, reproducible)."""

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        out: list[list[float]] = []
        for doc in input:
            vec = [0.0] * self._dim
            for tok in doc.lower().split():
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % self._dim] += 1.0
            out.append(vec)
        return out

    @staticmethod
    def name() -> str:
        return "lumifie-hashing"

    def get_config(self) -> dict[str, Any]:
        return {"dim": self._dim}

    @classmethod
    def build_from_config(cls, config: dict[str, Any]) -> HashingEmbedding:
        return cls(**config)


# Default rebuttal playbook (used if no JSON file is supplied).
DEFAULT_REBUTTALS: list[dict[str, str]] = [
    {
        "id": "price",
        "objection": "too expensive / over budget / price is high",
        "rebuttal": "Frame around ROI and payback period, not sticker price. Offer a "
        "right-sized starter tier or a pilot, and quantify the cost of the status quo.",
    },
    {
        "id": "incumbent",
        "objection": "already use a competitor / have a solution",
        "rebuttal": "Acknowledge the incumbent, then differentiate on the specific gap "
        "they feel. Propose a low-risk side-by-side trial rather than a rip-and-replace.",
    },
    {
        "id": "timing",
        "objection": "not the right time / circle back next quarter",
        "rebuttal": "Respect the timing, anchor a concrete future touchpoint, and share a "
        "small piece of value now (benchmark, teardown) to stay top of mind.",
    },
    {
        "id": "no_need",
        "objection": "don't see the need / not a priority",
        "rebuttal": "Surface the cost of inaction with a relevant peer example, and ask a "
        "diagnostic question that reframes the problem in their terms.",
    },
    {
        "id": "trust",
        "objection": "never heard of you / are you legit / security concerns",
        "rebuttal": "Lead with proof: comparable customers, security posture, and a "
        "no-commitment way to verify (references, trial, documentation).",
    },
]


class RebuttalKnowledgeBase:
    """Chroma collection of objection→rebuttal entries with offline retrieval."""

    def __init__(self, entries: list[dict[str, str]] | None = None) -> None:
        self._client = chromadb.EphemeralClient()
        self._col = self._client.get_or_create_collection(
            "objection_rebuttals", embedding_function=HashingEmbedding()
        )
        self._by_id: dict[str, dict[str, str]] = {}
        self.add(entries if entries is not None else DEFAULT_REBUTTALS)

    def add(self, entries: list[dict[str, str]]) -> None:
        if not entries:
            return
        ids = [e["id"] for e in entries]
        docs = [f"{e['objection']} :: {e['rebuttal']}" for e in entries]
        self._col.add(ids=ids, documents=docs)
        for e in entries:
            self._by_id[e["id"]] = e
        logger.info("Rebuttal KB loaded with {} entr(y/ies).", len(self._by_id))

    def retrieve(self, query: str, k: int = 3) -> list[dict[str, str]]:
        if not self._by_id:
            return []
        res = self._col.query(query_texts=[query], n_results=min(k, len(self._by_id)))
        ids = (res.get("ids") or [[]])[0]
        return [self._by_id[i] for i in ids if i in self._by_id]


def load_rebuttals(path: str | Path | None) -> list[dict[str, str]]:
    if not path:
        return DEFAULT_REBUTTALS
    return json.loads(Path(path).read_text(encoding="utf-8"))


__all__ = ["RebuttalKnowledgeBase", "HashingEmbedding", "DEFAULT_REBUTTALS", "load_rebuttals"]
