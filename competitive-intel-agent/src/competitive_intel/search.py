"""Web search backend for the competitive-intel agent.

The backend implementation is shared across the portfolio in ``lumifie_core.web``
(re-exported here so existing imports keep working). Only the agent-specific text
formatting lives locally.
"""

from __future__ import annotations

from lumifie_core.web import (
    DDGSearchBackend,
    SearchBackend,
    SearchResult,
)


def format_results(query: str, results: list[SearchResult]) -> str:
    """Render search results as text to hand back to the model."""
    if not results:
        return f'No results for "{query}".'
    lines = [f'Results for "{query}":']
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title}\n   {r.url}\n   {r.snippet}")
    return "\n".join(lines)


__all__ = ["SearchBackend", "SearchResult", "DDGSearchBackend", "format_results"]
