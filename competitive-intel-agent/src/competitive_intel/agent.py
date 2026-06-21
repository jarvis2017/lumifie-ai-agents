"""The competitive-intelligence agent.

Given a company and a market vertical, it autonomously researches competitors via
a ``web_search`` tool, records each competitor and threat, and finalizes an
executive brief. Models with native tool use run the full agentic loop; models
without it (e.g. Ollama) fall back to a fixed-query research pass plus a single
JSON-mode synthesis call.
"""

from __future__ import annotations

import json
from typing import Any

from lumifie_core import BaseAgent, LLMProvider, chat

from competitive_intel import tools as tool_mod
from competitive_intel.config import CompetitiveSettings
from competitive_intel.models import (
    Competitor,
    IntelReport,
    Threat,
    ThreatLevel,
)
from competitive_intel.search import SearchBackend, format_results

SYSTEM_PROMPT = """\
You are a competitive-intelligence analyst producing a briefing for an executive \
at the company under study. You are rigorous, source-driven, and concise.

Method:
- Use the web_search tool to find the company's real competitors and their \
positioning, pricing, target customers, and recent moves. Start broad, then dig \
into each serious competitor with focused queries.
- Record each competitor with record_competitor (cite a source_url when you can).
- Record material competitive threats with record_threat, each with a concrete, \
actionable recommendation for the company.
- Be skeptical of marketing language; infer pricing tiers and positioning from \
evidence. Mark pricing "Unknown" rather than guessing.
- When you have a solid picture of the landscape, call finalize_brief exactly once.
"""

_KICKOFF = (
    "Research the competitive landscape for {company} in the {vertical} market. "
    "Identify the most relevant competitors, their positioning and pricing, and the "
    "key threats to {company}. Then finalize the brief."
)


class CompetitiveIntelAgent(BaseAgent):
    name = "competitive-intel"
    description = "Researches competitors and produces an executive intel brief."

    def __init__(
        self,
        provider: LLMProvider,
        settings: CompetitiveSettings,
        search_backend: SearchBackend,
    ) -> None:
        super().__init__(provider, settings)
        self.settings: CompetitiveSettings = settings
        self._search = search_backend
        self._tools = tool_mod.tool_definitions()
        self._competitors: list[Competitor] = []
        self._threats: list[Threat] = []
        self._sources: list[str] = []
        self._searches = 0
        self._final: dict[str, Any] | None = None

    # -- public API --------------------------------------------------------

    def run(self, company: str, vertical: str) -> IntelReport:  # type: ignore[override]
        self.log.info("Researching {} in '{}' with {}", company, vertical, self.provider.model)
        if self.provider.supports_tools:
            self._research_with_tools(company, vertical)
        else:
            self._research_with_json(company, vertical)
        return self._build_report(company, vertical)

    # -- tool-use path -----------------------------------------------------

    def _research_with_tools(self, company: str, vertical: str) -> None:
        messages: list[dict[str, Any]] = [
            chat.system(SYSTEM_PROMPT),
            chat.user(_KICKOFF.format(company=company, vertical=vertical)),
        ]
        for _ in range(self.settings.max_iterations):
            result = self.complete(messages, tools=self._tools, tool_choice="auto")
            messages.append(chat.assistant_message(result))
            if not result.tool_calls:
                break
            done = False
            for call in result.tool_calls:
                text, finalized = self._handle_tool_call(call.name, call.arguments)
                messages.append(chat.tool_result(call.id, text))
                done = done or finalized
            if done:
                return
        if self._final is None:
            self.log.warning("Research loop ended without finalize; synthesizing from state.")

    def _handle_tool_call(self, name: str, payload: dict[str, Any]) -> tuple[str, bool]:
        if name == tool_mod.WEB_SEARCH:
            return self._run_search(payload), False
        if name == tool_mod.RECORD_COMPETITOR:
            return self._add_competitor(payload), False
        if name == tool_mod.RECORD_THREAT:
            return self._add_threat(payload), False
        if name == tool_mod.FINALIZE_BRIEF:
            self._final = payload
            self.log.info("Brief finalized: overall threat {}", payload.get("overall_threat_level"))
            return "Brief finalized.", True
        self.log.warning("Unknown tool call: {}", name)
        return f"Unknown tool: {name}", False

    def _run_search(self, payload: dict[str, Any]) -> str:
        if self._searches >= self.settings.max_searches:
            return (
                "Search budget exhausted. Record any remaining findings and call "
                "finalize_brief now."
            )
        self._searches += 1
        query = str(payload.get("query", "")).strip()
        if not query:
            return "Empty query ignored."
        n = payload.get("max_results") or self.settings.results_per_search
        results = self._search.search(query, max_results=int(n))
        for r in results:
            self._add_source(r.url)
        return format_results(query, results)

    # -- JSON-mode fallback path ------------------------------------------

    def _research_with_json(self, company: str, vertical: str) -> None:
        self.log.warning(
            "Model '{}' lacks tool use; running fixed-query research + JSON synthesis.",
            self.provider.model,
        )
        queries = [
            f"{company} competitors",
            f"top {vertical} companies",
            f"{vertical} pricing comparison",
            f"{company} alternatives",
        ][: self.settings.max_searches]

        blocks: list[str] = []
        for q in queries:
            self._searches += 1
            results = self._search.search(q, max_results=self.settings.results_per_search)
            for r in results:
                self._add_source(r.url)
            blocks.append(format_results(q, results))
        evidence = "\n\n".join(blocks) or "No web results were available."

        prompt = (
            f"Company under study: {company}\nMarket vertical: {vertical}\n\n"
            f"Web research:\n{evidence}\n\n{tool_mod.json_synthesis_hint()}"
        )
        result = self.complete(
            [chat.system(SYSTEM_PROMPT), chat.user(prompt)],
            response_format={"type": "json_object"},
        )
        data = self._parse_json(result.text)
        for raw in data.get("competitors", []) or []:
            self._add_competitor(raw)
        for raw in data.get("threats", []) or []:
            self._add_threat(raw)
        if data:
            self._final = {
                "overall_threat_level": data.get("overall_threat_level", "medium"),
                "market_summary": data.get("market_summary", ""),
                "executive_summary": data.get("executive_summary", ""),
            }

    # -- state helpers -----------------------------------------------------

    def _add_competitor(self, payload: dict[str, Any]) -> str:
        if len(self._competitors) >= self.settings.max_competitors:
            return "Competitor limit reached; not recorded."
        try:
            competitor = Competitor.model_validate(payload)
        except Exception as exc:
            self.log.warning("Discarding malformed competitor: {}", exc)
            return "Competitor rejected: invalid fields."
        # De-duplicate by name.
        if competitor.name.strip().lower() in {c.name.strip().lower() for c in self._competitors}:
            return "Competitor already recorded."
        self._competitors.append(competitor)
        if competitor.source_url:
            self._add_source(competitor.source_url)
        self.log.info("Competitor: {}", competitor.name)
        return "Competitor recorded."

    def _add_threat(self, payload: dict[str, Any]) -> str:
        try:
            threat = Threat.model_validate(payload)
        except Exception as exc:
            self.log.warning("Discarding malformed threat: {}", exc)
            return "Threat rejected: invalid fields."
        self._threats.append(threat)
        self.log.info("Threat [{}] {}", threat.severity.label, threat.description[:60])
        return "Threat recorded."

    def _add_source(self, url: str | None) -> None:
        if url and url not in self._sources:
            self._sources.append(url)

    @staticmethod
    def _parse_json(text: str | None) -> dict[str, Any]:
        if not text:
            return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    # -- report assembly ---------------------------------------------------

    def _build_report(self, company: str, vertical: str) -> IntelReport:
        if self._final is not None:
            overall = self._coerce_level(self._final.get("overall_threat_level"))
            market = self._final.get("market_summary") or "No market summary produced."
            summary = self._final.get("executive_summary") or self._fallback_summary()
        else:
            overall = self._derive_overall_threat()
            market = "No market summary produced."
            summary = self._fallback_summary()

        return IntelReport(
            company=company,
            vertical=vertical,
            model=self.provider.model,
            overall_threat_level=overall,
            market_summary=market,
            executive_summary=summary,
            competitors=list(self._competitors),
            threats=list(self._threats),
            sources=list(self._sources),
            token_usage=dict(self.token_usage),
        )

    def _derive_overall_threat(self) -> ThreatLevel:
        if not self._threats:
            return ThreatLevel.LOW
        return max((t.severity for t in self._threats), key=lambda s: s.rank)

    @staticmethod
    def _coerce_level(value: Any) -> ThreatLevel:
        try:
            return ThreatLevel(value)
        except (ValueError, TypeError):
            return ThreatLevel.MEDIUM

    def _fallback_summary(self) -> str:
        return (
            f"Identified {len(self._competitors)} competitor(s) and "
            f"{len(self._threats)} threat(s). See details below."
        )


__all__ = ["CompetitiveIntelAgent", "SYSTEM_PROMPT"]
