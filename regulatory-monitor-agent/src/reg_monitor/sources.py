"""Source backends: web search and feed fetching.

The agent depends only on the :class:`SearchBackend` and :class:`FeedBackend`
protocols, so the real DuckDuckGo / RSS backends can be swapped for deterministic
fakes in tests (no network, no API keys). Both are injected into the agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lumifie_core import logger

# -- web search -----------------------------------------------------------


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


class DDGSearchBackend:
    """DuckDuckGo backend (no API key). Uses the ``ddgs`` package.

    When ``after_date`` (YYYY-MM-DD) is given it is appended to the query as an
    ``after:`` constraint so results skew to recent regulatory change.
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


# -- feeds (RSS / Atom) ---------------------------------------------------


@dataclass(slots=True)
class FeedItem:
    title: str
    url: str
    summary: str
    published: str | None = None


@runtime_checkable
class FeedBackend(Protocol):
    def fetch(self, url: str) -> list[FeedItem]: ...


class RSSFeedBackend:
    """RSS/Atom backend using the ``feedparser`` package."""

    def __init__(self, max_items: int = 20) -> None:
        self.max_items = max_items

    def fetch(self, url: str) -> list[FeedItem]:
        try:
            import feedparser  # noqa: PLC0415 - optional, lazy import
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'feedparser' package is required to read RSS feeds. "
                "Install with: uv pip install feedparser"
            ) from exc

        items: list[FeedItem] = []
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[: self.max_items]:
                items.append(
                    FeedItem(
                        title=getattr(entry, "title", "") or "",
                        url=getattr(entry, "link", "") or "",
                        summary=getattr(entry, "summary", "") or "",
                        published=getattr(entry, "published", None)
                        or getattr(entry, "updated", None),
                    )
                )
        except Exception as exc:  # malformed feed / network — degrade gracefully
            logger.warning("Feed fetch failed for '{}': {}", url, exc)
        return items


def format_results(query: str, results: list[SearchResult]) -> str:
    """Render search results as text (used for logging/debugging)."""
    if not results:
        return f'No results for "{query}".'
    lines = [f'Results for "{query}":']
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title}\n   {r.url}\n   {r.snippet}")
    return "\n".join(lines)


__all__ = [
    "DDGSearchBackend",
    "FeedBackend",
    "FeedItem",
    "RSSFeedBackend",
    "SearchBackend",
    "SearchResult",
    "format_results",
]
