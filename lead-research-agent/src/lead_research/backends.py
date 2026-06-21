"""Live-signal backends: web search and a URL reader (Jina Reader).

Both are behind small protocols so the real network backends can be swapped for
fakes in tests. The Scraper/Enricher sub-agent uses these to gather live signals.
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


@runtime_checkable
class ReaderBackend(Protocol):
    def read(self, url: str) -> str: ...


class DDGSearchBackend:
    """DuckDuckGo search (no API key) via the ``ddgs`` package."""

    def __init__(self, region: str = "us-en") -> None:
        self.region = region

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            from ddgs import DDGS  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install 'ddgs' for live search: uv pip install ddgs") from exc
        out: list[SearchResult] = []
        try:
            with DDGS() as ddgs:
                for row in ddgs.text(query, region=self.region, max_results=max_results):
                    out.append(
                        SearchResult(
                            title=row.get("title", ""),
                            url=row.get("href", "") or row.get("url", ""),
                            snippet=row.get("body", "") or row.get("snippet", ""),
                        )
                    )
        except Exception as exc:
            logger.warning("Search failed for '{}': {}", query, exc)
        return out


class JinaReader:
    """Fetch readable page content via Jina Reader (https://r.jina.ai/<url>).

    No API key required for basic use. Returns markdown-ish text, truncated to
    ``max_chars``. Returns "" on failure so the pipeline degrades gracefully.
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


def format_results(results: list[SearchResult]) -> str:
    if not results:
        return "(no results)"
    return "\n".join(f"- {r.title} — {r.snippet} ({r.url})" for r in results)


__all__ = [
    "SearchResult",
    "SearchBackend",
    "ReaderBackend",
    "DDGSearchBackend",
    "JinaReader",
    "format_results",
]
