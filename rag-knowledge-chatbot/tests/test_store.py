"""Tests for the vector store: incremental ingestion, dedup, and retrieval."""

from __future__ import annotations

from rag_chatbot.embeddings import HashingEmbedding, build_embedding
from rag_chatbot.loaders import load_source, load_sources
from rag_chatbot.store import VectorStore, distance_to_similarity


def test_distance_to_similarity_in_range():
    assert distance_to_similarity(0.0) == 1.0
    assert 0.0 < distance_to_similarity(5.0) < 1.0
    assert distance_to_similarity(-1.0) == 1.0  # clamped


def test_reingest_does_not_duplicate(store, settings, demo_files):
    chunks = load_sources(
        demo_files, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    first = store.add_documents(chunks)
    assert first.chunks_added > 0
    assert first.chunks_skipped == 0
    count_after_first = store.count()

    # Re-ingest the exact same content -> everything skipped, no growth.
    second = store.add_documents(chunks)
    assert second.chunks_added == 0
    assert second.chunks_skipped == first.chunks_added
    assert store.count() == count_after_first


def test_new_document_adds_chunks_incrementally(store, settings, demo_files, tmp_path):
    chunks = load_source(
        demo_files[0], chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    store.add_documents(chunks)
    base = store.count()
    assert base > 0

    extra = tmp_path / "extra.md"
    extra.write_text("Northwind also sells branded safety goggles in bulk.", encoding="utf-8")
    new_chunks = load_source(
        str(extra), chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    result = store.add_documents(new_chunks)
    assert result.chunks_added == len(new_chunks)
    assert store.count() == base + len(new_chunks)


def test_query_returns_relevant_chunk(populated_store):
    hits = populated_store.query("how many vacation days do employees accrue", top_k=4)
    assert hits
    combined = " ".join(h.chunk.text.lower() for h in hits)
    assert "vacation" in combined
    # Distances/similarities are sane.
    assert all(0.0 <= h.similarity <= 1.0 for h in hits)


def test_query_empty_store_returns_nothing(store):
    assert store.query("anything", top_k=3) == []


def test_persistence_across_instances(settings, demo_files):
    s1 = VectorStore(HashingEmbedding(), path=settings.db_path, collection="documents")
    chunks = load_sources(
        demo_files, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    s1.add_documents(chunks)
    count = s1.count()

    # New client at the same path sees the persisted data (incremental store).
    s2 = VectorStore(HashingEmbedding(), path=settings.db_path, collection="documents")
    assert s2.count() == count


def test_build_embedding_hashing_explicit():
    assert isinstance(build_embedding("hashing"), HashingEmbedding)
