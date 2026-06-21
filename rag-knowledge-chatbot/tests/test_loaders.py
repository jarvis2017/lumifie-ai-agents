"""Tests for document loaders and chunking."""

from __future__ import annotations

from rag_chatbot.loaders import chunk_id, chunk_text, is_url, load_source, load_sources
from rag_chatbot.models import SourceType


def test_chunking_overlap_and_no_truncation():
    text = "abcdefghij" * 30  # 300 chars
    chunks = chunk_text(
        text, source="t.txt", source_type=SourceType.TEXT, chunk_size=100, overlap=20
    )
    assert len(chunks) >= 3
    # Every character of the source appears somewhere (no silent truncation).
    joined = "".join(c.text for c in chunks)
    assert set(text) <= set(joined)
    assert all(len(c.text) <= 100 for c in chunks)
    # Chunk indices are sequential.
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_ids_are_stable_and_content_addressed():
    a = chunk_id("doc.md", "hello world")
    b = chunk_id("doc.md", "hello world")
    c = chunk_id("other.md", "hello world")
    assert a == b
    assert a != c  # same text, different source -> different id


def test_load_markdown_file(demo_files):
    chunks = load_source(demo_files[0], chunk_size=400, overlap=50)
    assert chunks
    assert chunks[0].source_type is SourceType.MARKDOWN
    assert chunks[0].source.endswith("company_faq.md")
    assert chunks[0].page is None


def test_load_txt_file(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("Plain text content here for ingestion.", encoding="utf-8")
    chunks = load_source(str(p), chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].source_type is SourceType.TEXT


def test_unsupported_extension_raises(tmp_path):
    p = tmp_path / "data.xyz"
    p.write_text("x", encoding="utf-8")
    try:
        load_source(str(p), chunk_size=100, overlap=10)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Unsupported" in str(exc)


def test_url_loading_with_injected_fetch():
    html = "<html><body><h1>Title</h1><p>Hello world paragraph.</p>" \
           "<script>ignore()</script></body></html>"

    def fake_fetch(url: str, ua: str) -> str:
        assert url.startswith("http")
        return html

    chunks = load_source(
        "https://example.com/page",
        chunk_size=500,
        overlap=50,
        fetch_fn=fake_fetch,
    )
    assert chunks
    assert chunks[0].source_type is SourceType.URL
    text = chunks[0].text
    assert "Hello world paragraph." in text
    assert "ignore" not in text  # script stripped


def test_is_url():
    assert is_url("https://x.com")
    assert is_url("http://x.com")
    assert not is_url("/local/path.md")


def test_load_sources_combines(demo_files):
    chunks = load_sources(demo_files, chunk_size=500, overlap=80)
    sources = {c.source for c in chunks}
    assert len(sources) == 2
