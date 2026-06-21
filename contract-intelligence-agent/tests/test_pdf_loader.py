"""Tests for PDF ingestion and chunking."""

from __future__ import annotations

import pytest

from contract_intelligence.pdf_loader import PDFLoadError, load_contract


def test_load_sample_contract(sample_pdf):
    doc = load_contract(sample_pdf, max_chunk_chars=100_000)
    assert doc.page_count >= 1
    assert "Master Services Agreement" in doc.full_text
    # Whole document fits in one chunk at a large chunk size.
    assert len(doc.chunks) == 1


def test_chunking_splits_large_documents(sample_pdf):
    doc = load_contract(sample_pdf, max_chunk_chars=600)
    assert len(doc.chunks) > 1
    # Page boundaries are preserved and labeled.
    assert all("[Page" in chunk.text for chunk in doc.chunks)
    # Chunks cover a contiguous, non-overlapping page range.
    assert doc.chunks[0].start_page == 1
    assert doc.chunks[-1].end_page == doc.page_count


def test_missing_file_raises():
    with pytest.raises(PDFLoadError):
        load_contract("/no/such/file.pdf")


def test_non_pdf_suffix_raises(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("hello")
    with pytest.raises(PDFLoadError):
        load_contract(p)
