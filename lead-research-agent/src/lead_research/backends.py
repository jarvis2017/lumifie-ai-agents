"""Live-signal backends for lead research: web search + a URL reader.

The backend implementations are shared in ``lumifie_core.web`` (re-exported here
so existing imports keep working); only agent-specific formatting lives locally.
"""

from __future__ import annotations

from lumifie_core.web import (
    DDGSearchBackend,
    JinaReader,
    ReaderBackend,
    SearchBackend,
    SearchResult,
)


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
