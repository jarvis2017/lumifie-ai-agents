"""Deterministic demo backends so `--source demo` runs the whole pipeline offline."""

from __future__ import annotations

from lumifie_core.web import SearchResult

from sales_ops.models import Reply


class DemoSearch:
    """Returns seeded 'companies' matching the stub leads, recording queries."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5, after_date: str | None = None):
        self.queries.append(query)
        return [
            SearchResult(
                "Acme Analytics — warehouse-native analytics",
                "https://acme-analytics.com",
                "Series B SaaS scaling fast.",
            ),
            SearchResult(
                "Globex Data", "https://globexdata.io", "Product analytics; manual reporting pain."
            ),
            SearchResult("Initech Cloud", "https://initech.cloud", "Legacy tooling, mid-market."),
        ][:max_results]


class DemoReader:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def read(self, url: str) -> str:
        self.urls.append(url)
        return f"Company page for {url}: B2B SaaS, scaling team, manual workflows mentioned."


def demo_replies() -> list[Reply]:
    """Two inbound replies to triage (one interested, one objection)."""
    return [
        Reply(
            lead_id="lead-1",
            from_email="jane@acme-analytics.com",
            subject="Re: A quick idea for your team",
            body="This is interesting — I'd love a quick demo. Can you send a time next week?",
        ),
        Reply(
            lead_id="lead-2",
            from_email="sam@globexdata.io",
            subject="Re: A quick idea for your team",
            body="Honestly this looks too expensive and we already use a competitor right now.",
        ),
    ]


__all__ = ["DemoSearch", "DemoReader", "demo_replies"]
