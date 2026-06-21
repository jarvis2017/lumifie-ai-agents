"""Tests for the shared web backends (search + Jina reader)."""

from __future__ import annotations

import pytest

from lumifie_core.web import (
    DDGSearchBackend,
    JinaReader,
    ReaderBackend,
    SearchBackend,
    SearchResult,
    format_results,
)


def test_search_result_defaults():
    r = SearchResult(title="t", url="u", snippet="s")
    assert r.date is None


def test_protocols_are_structural():
    class FakeSearch:
        def search(self, query, max_results=5, after_date=None):
            return [SearchResult("t", "u", "s")]

    class FakeReader:
        def read(self, url):
            return "text"

    assert isinstance(FakeSearch(), SearchBackend)
    assert isinstance(FakeReader(), ReaderBackend)


def test_format_results():
    rs = [SearchResult("Title", "https://x", "snippet")]
    assert format_results([]) == "(no results)"
    assert format_results([], query="q") == 'No results for "q".'
    out = format_results(rs, query="q")
    assert out.startswith('Results for "q":')
    assert "https://x" in out


def test_ddg_search_raises_without_ddgs(monkeypatch):
    # Block the lazy `import ddgs` regardless of whether it's installed in this venv.
    monkeypatch.setitem(__import__("sys").modules, "ddgs", None)
    with pytest.raises(RuntimeError, match="ddgs"):
        DDGSearchBackend().search("anything")


def test_jina_reader_degrades_to_empty_on_failure(monkeypatch):
    import httpx

    def boom(*args, **kwargs):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "get", boom)
    assert JinaReader().read("https://example.com") == ""
