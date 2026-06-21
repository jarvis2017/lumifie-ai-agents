"""Source backends: web search (shared) and RSS/Atom feed fetching (local).

The web search backend is shared across the portfolio in ``lumifie_core.web``
(re-exported here). The feed backend is specific to this agent and stays local.
Both are injected into the agent and have deterministic fakes in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lumifie_core import logger
from lumifie_core.web import (
    DDGSearchBackend,
    SearchBackend,
    SearchResult,
)

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
