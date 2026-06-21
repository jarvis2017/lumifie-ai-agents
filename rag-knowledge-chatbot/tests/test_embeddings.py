"""Tests for embedding backends and the offline auto-fallback."""

from __future__ import annotations

import sys

from rag_chatbot.embeddings import HashingEmbedding, build_embedding


def test_hashing_embedding_is_deterministic_and_normalized():
    emb = HashingEmbedding()
    a = list(emb(["vacation policy days"])[0])
    b = list(emb(["vacation policy days"])[0])
    assert a == b  # deterministic
    norm = sum(x * x for x in a) ** 0.5
    assert abs(norm - 1.0) < 1e-5  # L2-normalized


def test_hashing_overlap_more_similar_than_disjoint():
    emb = HashingEmbedding()
    base, overlap, disjoint = emb(
        ["vacation days policy", "vacation days request", "shipping refund warranty"]
    )
    dot_overlap = sum(x * y for x, y in zip(base, overlap, strict=True))
    dot_disjoint = sum(x * y for x, y in zip(base, disjoint, strict=True))
    assert dot_overlap > dot_disjoint


def test_build_embedding_auto_falls_back_when_st_missing(monkeypatch):
    # With sentence-transformers unavailable, "auto" must fall back to hashing.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    backend = build_embedding("auto")
    assert isinstance(backend, HashingEmbedding)


def test_build_embedding_st_request_also_falls_back(monkeypatch):
    # Force sentence-transformers to be unavailable (regardless of whether it's
    # installed in this env) so the fallback path is exercised deterministically.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    backend = build_embedding("sentence-transformers")
    assert isinstance(backend, HashingEmbedding)
