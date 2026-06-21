"""Shared web backends: search and a URL reader (Jina Reader).

Agents depend only on the :class:`SearchBackend` / :class:`ReaderBackend`
protocols, so the real network backends can be swapped for fakes in tests. The
heavy/optional libraries (``ddgs``, ``httpx``) are imported lazily inside the
methods, so importing this module is cheap and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lumifie_core.logging import logger


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    date: str | None = None


@runtime_checkable
class SearchBackend(Protocol):
    def search(
        self, query: str, max_results: int = 5, after_date: str | None = None
    ) -> list[SearchResult]: ...


@runtime_checkable
class ReaderBackend(Protocol):
    def read(self, url: str) -> str: ...


class DDGSearchBackend:
    """DuckDuckGo backend (no API key) via the ``ddgs`` package.

    When ``after_date`` (YYYY-MM-DD) is given it is appended to the query as an
    ``after:`` constraint to skew toward recent results.
    """

    def __init__(self, region: str = "us-en", safesearch: str = "moderate") -> None:
        self.region = region
        self.safesearch = safesearch

    def search(
        self, query: str, max_results: int = 5, after_date: str | None = None
    ) -> list[SearchResult]:
        try:
            from ddgs import DDGS  # noqa: PLC0415 - optional, lazy import
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'ddgs' package is required for live web search. "
                "Install with: uv pip install ddgs"
            ) from exc

        full_query = f"{query} after:{after_date}" if after_date else query
        results: list[SearchResult] = []
        try:
            with DDGS() as ddgs:
                for row in ddgs.text(
                    full_query,
                    region=self.region,
                    safesearch=self.safesearch,
                    max_results=max_results,
                ):
                    results.append(
                        SearchResult(
                            title=row.get("title", ""),
                            url=row.get("href", "") or row.get("url", ""),
                            snippet=row.get("body", "") or row.get("snippet", ""),
                            date=row.get("date") or None,
                        )
                    )
        except Exception as exc:  # network/ratelimit — degrade gracefully
            logger.warning("Web search failed for '{}': {}", full_query, exc)
        return results


class JinaReader:
    """Fetch readable page content via Jina Reader (https://r.jina.ai/<url>).

    Returns markdown-ish text truncated to ``max_chars``; returns "" on failure so
    callers degrade gracefully.
    """

    def __init__(self, base: str = "https://r.jina.ai", max_chars: int = 6000) -> None:
        self.base = base.rstrip("/")
        self.max_chars = max_chars

    def read(self, url: str) -> str:
        try:
            import httpx  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install 'httpx' for the reader: uv pip install httpx") from exc
        target = f"{self.base}/{url}"
        try:
            resp = httpx.get(
                target,
                headers={"X-Return-Format": "markdown", "Accept": "text/plain"},
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text[: self.max_chars]
        except Exception as exc:
            logger.warning("Reader failed for '{}': {}", url, exc)
            return ""


def format_results(results: list[SearchResult], query: str | None = None) -> str:
    """Render results as a numbered text block, optionally with a query header."""
    if not results:
        return f'No results for "{query}".' if query else "(no results)"
    lines = [f'Results for "{query}":'] if query else []
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title}\n   {r.url}\n   {r.snippet}")
    return "\n".join(lines)


__all__ = [
    "SearchResult",
    "SearchBackend",
    "ReaderBackend",
    "DDGSearchBackend",
    "JinaReader",
    "format_results",
]
