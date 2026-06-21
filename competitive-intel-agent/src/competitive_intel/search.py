"""Web search backends.

The agent depends only on the :class:`SearchBackend` protocol, so the real
DuckDuckGo backend can be swapped for a fake in tests (no network).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lumifie_core import logger


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@runtime_checkable
class SearchBackend(Protocol):
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class DDGSearchBackend:
    """DuckDuckGo backend (no API key). Uses the ``ddgs`` package."""

    def __init__(self, region: str = "us-en", safesearch: str = "moderate") -> None:
        self.region = region
        self.safesearch = safesearch

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            from ddgs import DDGS  # noqa: PLC0415 - optional, lazy import
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'ddgs' package is required for live web search. "
                "Install with: uv pip install ddgs"
            ) from exc

        results: list[SearchResult] = []
        try:
            with DDGS() as ddgs:
                for row in ddgs.text(
                    query,
                    region=self.region,
                    safesearch=self.safesearch,
                    max_results=max_results,
                ):
                    results.append(
                        SearchResult(
                            title=row.get("title", ""),
                            url=row.get("href", "") or row.get("url", ""),
                            snippet=row.get("body", "") or row.get("snippet", ""),
                        )
                    )
        except Exception as exc:  # network/ratelimit — degrade gracefully
            logger.warning("Web search failed for '{}': {}", query, exc)
        return results


def format_results(query: str, results: list[SearchResult]) -> str:
    """Render search results as text to hand back to the model."""
    if not results:
        return f'No results for "{query}".'
    lines = [f'Results for "{query}":']
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title}\n   {r.url}\n   {r.snippet}")
    return "\n".join(lines)


__all__ = ["SearchBackend", "SearchResult", "DDGSearchBackend", "format_results"]
