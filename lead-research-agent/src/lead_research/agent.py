"""The lead-research agent: a LangGraph pipeline of three sub-agents.

1. **Scraper/Enricher** — reads the company URL (Jina Reader) and web-searches for
   news and executives, then extracts a structured enrichment.
2. **ICP Matcher** — scores the company against a configurable JSON ideal-customer
   profile, with explicit reasoning.
3. **Copywriter** — drafts a personalized email + LinkedIn message from the live
   signals and the ICP fit.

All three are nodes in a LangGraph ``StateGraph``; every sub-agent returns a
Pydantic-validated structured object via ``lumifie_core`` (tool use where
supported, JSON-mode fallback otherwise).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from lumifie_core import BaseAgent, LLMProvider

from lead_research import models
from lead_research.backends import (
    ReaderBackend,
    SearchBackend,
    format_results,
)
from lead_research.config import LeadSettings
from lead_research.graph import build_graph
from lead_research.icp import ICPProfile
from lead_research.models import (
    Enrichment,
    ICPScore,
    LeadReport,
    Outreach,
)

SCRAPER_SYSTEM = (
    "You are a B2B research analyst. From a company's website and live web "
    "signals, extract an accurate, concise enrichment: what they sell and to whom "
    "(value proposition), recent news, and key executives. Do not invent facts; "
    "leave fields empty if the evidence is absent."
)
MATCHER_SYSTEM = (
    "You are a sales-qualification analyst. Score how well a company fits the "
    "given Ideal Customer Profile (ICP) from 0-100, assign a tier (Strong/"
    "Moderate/Weak), and explain your reasoning against the ICP's criteria. Set "
    "disqualified=true if the company matches any ICP disqualifier."
)
COPY_SYSTEM = (
    "You are an expert SDR copywriter. Using the enrichment and ICP fit, write a "
    "short, specific, non-salesy cold email (subject + body) and a LinkedIn "
    "connection message. Personalize using concrete live signals (recent news, "
    "the company's own value prop). No fluff, no false claims, under 130 words for "
    "the email body."
)


def _host(url: str) -> str:
    netloc = urlparse(url if "//" in url else f"//{url}").netloc or url
    return netloc.replace("www.", "").strip("/") or url


class LeadResearchAgent(BaseAgent):
    name = "lead-research"
    description = "Researches a target company and drafts personalized outreach."

    def __init__(
        self,
        provider: LLMProvider,
        settings: LeadSettings,
        icp: ICPProfile,
        search_backend: SearchBackend,
        reader_backend: ReaderBackend,
    ) -> None:
        super().__init__(provider, settings)
        self.settings: LeadSettings = settings
        self._icp = icp
        self._search = search_backend
        self._reader = reader_backend

    # -- public API --------------------------------------------------------

    def run(self, company_url: str) -> LeadReport:  # type: ignore[override]
        self.log.info("Researching lead {} with {}", company_url, self.provider.model)
        graph = build_graph(self)
        final: dict[str, Any] = graph.invoke(
            {"company_url": company_url, "icp": self._icp.model_dump(), "sources": []}
        )
        return self._build_report(company_url, final)

    # -- sub-agent nodes ---------------------------------------------------

    def scrape_node(self, state: dict[str, Any]) -> dict[str, Any]:
        url = state["company_url"]
        host = _host(url)
        page = self._reader.read(url)

        search_urls: list[str] = []
        blocks: list[str] = []
        queries = [f"{host} company news 2026", f"{host} leadership team executives"]
        for q in queries[: self.settings.max_searches]:
            results = self._search.search(q, max_results=self.settings.results_per_search)
            search_urls.extend(r.url for r in results if r.url)
            blocks.append(f"Query: {q}\n{format_results(results)}")

        prompt = (
            f"Target company URL: {url}\n\n"
            f"--- Website content (may be truncated) ---\n"
            f"{page[: self.settings.max_page_chars] or '(could not read page)'}\n\n"
            f"--- Live web signals ---\n" + "\n\n".join(blocks)
        )
        data = self.structured(
            system=SCRAPER_SYSTEM,
            prompt=prompt,
            schema=models.enrichment_schema(),
            tool_name="enrichment",
        )
        self.log.info("Enriched {}", data.get("company_name", host))
        sources = [url, *dict.fromkeys(search_urls)]
        return {"enrichment": data, "sources": sources}

    def match_node(self, state: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            f"Ideal Customer Profile:\n{self._icp.as_prompt()}\n\n"
            f"Company enrichment:\n{state.get('enrichment', {})}\n\n"
            "Score this company against the ICP."
        )
        data = self.structured(
            system=MATCHER_SYSTEM,
            prompt=prompt,
            schema=models.icp_score_schema(),
            tool_name="icp_score",
        )
        self.log.info("ICP fit: {} ({})", data.get("fit_score"), data.get("tier"))
        return {"icp_score": data}

    def copy_node(self, state: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            f"Company enrichment:\n{state.get('enrichment', {})}\n\n"
            f"ICP fit:\n{state.get('icp_score', {})}\n\n"
            f"Value props to emphasize: {self._icp.value_props_to_emphasize}\n\n"
            "Write the personalized email and LinkedIn message."
        )
        data = self.structured(
            system=COPY_SYSTEM,
            prompt=prompt,
            schema=models.outreach_schema(),
            tool_name="outreach",
        )
        self.log.info("Drafted outreach.")
        return {"outreach": data}

    # -- assembly ----------------------------------------------------------

    def _build_report(self, company_url: str, final: dict[str, Any]) -> LeadReport:
        enrichment = self._coerce(
            Enrichment, final.get("enrichment"),
            Enrichment(company_name=_host(company_url), value_proposition="Unknown"),
        )
        icp_score = self._coerce(
            ICPScore, final.get("icp_score"),
            ICPScore(fit_score=0, tier="Unknown", reasoning="Scoring unavailable."),
        )
        outreach = self._coerce(
            Outreach, final.get("outreach"),
            Outreach(email_subject="", email_body="", linkedin_message=""),
        )
        sources = list(dict.fromkeys(final.get("sources", [])))
        return LeadReport(
            company_url=company_url,
            model=self.provider.model,
            icp_name=self._icp.name,
            enrichment=enrichment,
            icp_score=icp_score,
            outreach=outreach,
            sources=sources,
            token_usage=dict(self.token_usage),
        )

    def _coerce(self, model_cls, payload, fallback):
        if not payload:
            return fallback
        try:
            return model_cls.model_validate(payload)
        except Exception as exc:
            self.log.warning("Invalid {} output: {}", model_cls.__name__, exc)
            return fallback


__all__ = ["LeadResearchAgent"]
