"""The regulatory-monitor agent: a three-stage monitoring pipeline.

1. **Planner** (LLM, structured) — turns the business profile + sources into a
   :class:`MonitoringPlan`: search queries tuned to industry/location/keywords.
2. **Researcher** (deterministic) — runs each query through the injected
   ``SearchBackend`` with a recent-date constraint, and fetches each RSS/url
   source through the injected ``FeedBackend``, collecting & de-duping
   :class:`Finding` objects.
3. **Impact Analyst** (LLM, structured) — translates the relevant findings into
   plain-English :class:`ImpactStatement` objects tailored to this business,
   dropping clearly-irrelevant ones.

The agent then diffs the impacts against the previous run to surface what's new,
and assembles a :class:`Digest`. All external I/O (LLM, search, feeds, history)
is injected, so the whole pipeline runs offline in tests.
"""

from __future__ import annotations

from lumifie_core import BaseAgent, LLMProvider

from reg_monitor import schemas
from reg_monitor.config import MonitorSettings
from reg_monitor.diff import new_impacts
from reg_monitor.models import (
    BusinessProfile,
    Digest,
    Finding,
    ImpactStatement,
    MonitoringPlan,
    Relevance,
    Source,
    SourceType,
)
from reg_monitor.sources import FeedBackend, SearchBackend
from reg_monitor.utils import lookback_date

PLANNER_SYSTEM = (
    "You are a regulatory-monitoring strategist. Given a business profile and its "
    "regulatory sources, design a focused plan to surface RECENT regulatory change "
    "that affects this business. Produce search queries tuned to the industry, "
    "location, and operational keywords — each will be run with a recent-date "
    "constraint — plus which sources to focus on. Be specific and practical; favor "
    "queries naming the jurisdiction and the concrete obligation (e.g. licensing, "
    "wages, safety, reporting). Do not invent regulations."
)

ANALYST_SYSTEM = (
    "You are a regulatory analyst who translates dense regulatory news into plain "
    "English for a busy, non-technical business owner. For each finding, decide "
    "whether it actually matters to THIS business (its industry, location, and "
    "operations). Drop anything clearly irrelevant. For the rest, explain in plain "
    "English what it means for this specific business, rate its relevance "
    "(high/medium/low), and give one concrete recommended action. Never invent "
    "rules; ground every statement in the finding's content."
)


class RegulatoryMonitorAgent(BaseAgent):
    name = "regulatory-monitor"
    description = (
        "Monitors regulatory sources for a business and emits a plain-English "
        "weekly digest of new changes."
    )

    def __init__(
        self,
        provider: LLMProvider,
        settings: MonitorSettings,
        search_backend: SearchBackend,
        feed_backend: FeedBackend,
    ) -> None:
        super().__init__(provider, settings)
        self.settings: MonitorSettings = settings
        self._search = search_backend
        self._feed = feed_backend

    # -- public API --------------------------------------------------------

    def run(  # type: ignore[override]
        self,
        profile: BusinessProfile,
        sources: list[Source],
        *,
        previous: Digest | None = None,
    ) -> Digest:
        self.log.info(
            "Monitoring {} in {} ({} source(s)) with {}",
            profile.industry,
            profile.location,
            len(sources),
            self.provider.model,
        )
        plan = self.plan(profile, sources)
        findings, sources_checked = self.research(profile, sources, plan)
        impacts = self.analyze(profile, findings)
        new = new_impacts(previous, impacts)
        return Digest(
            profile=profile,
            model=self.provider.model,
            lookback_days=self.settings.lookback_days,
            plan=plan,
            impacts=impacts,
            new_impacts=new,
            sources_checked=sources_checked,
            is_baseline=previous is None,
            token_usage=dict(self.token_usage),
        )

    # -- Stage 1: planner --------------------------------------------------

    def plan(self, profile: BusinessProfile, sources: list[Source]) -> MonitoringPlan:
        source_lines = "\n".join(f"- [{s.type.value}] {s.display()}" for s in sources) or "(none)"
        prompt = (
            f"Business profile:\n"
            f"- Industry: {profile.industry}\n"
            f"- Location: {profile.location}\n"
            f"- Operational keywords: {', '.join(profile.operational_keywords) or '(none)'}\n"
            f"- Description: {profile.business_description or '(none)'}\n\n"
            f"Regulatory sources to monitor:\n{source_lines}\n\n"
            f"Produce up to {self.settings.max_queries} search queries plus source focus "
            f"and a short rationale."
        )
        data = self.structured(
            system=PLANNER_SYSTEM,
            prompt=prompt,
            schema=schemas.plan_schema(),
            tool_name=schemas.PLAN_TOOL,
        )
        try:
            plan = MonitoringPlan.model_validate(data)
        except Exception as exc:  # malformed plan — fall back to keyword queries
            self.log.warning("Malformed plan ({}); using keyword fallback.", exc)
            plan = self._fallback_plan(profile)
        if not plan.search_queries:
            plan.search_queries = self._fallback_plan(profile).search_queries
        plan.search_queries = plan.search_queries[: self.settings.max_queries]
        self.log.info("Plan: {} query(ies).", len(plan.search_queries))
        return plan

    def _fallback_plan(self, profile: BusinessProfile) -> MonitoringPlan:
        kws = profile.operational_keywords or [profile.industry]
        queries = [
            f"{kw} regulation {profile.location} {profile.industry}".strip() for kw in kws
        ]
        return MonitoringPlan(
            search_queries=queries,
            source_focus=[s for s in profile.operational_keywords],
            rationale="Keyword-derived fallback plan.",
        )

    # -- Stage 2: researcher ----------------------------------------------

    def research(
        self,
        profile: BusinessProfile,
        sources: list[Source],
        plan: MonitoringPlan,
    ) -> tuple[list[Finding], list[str]]:
        after = lookback_date(self.settings.lookback_days)
        findings: list[Finding] = []
        sources_checked: list[str] = []

        # Search queries from the plan, each with the recent-date constraint.
        for query in plan.search_queries:
            sources_checked.append(f"search: {query}")
            results = self._search.search(
                query, max_results=self.settings.results_per_search, after_date=after
            )
            for r in results:
                findings.append(
                    Finding(
                        title=r.title or r.url,
                        url=r.url,
                        source=f"search: {query}",
                        date=r.date,
                        raw_summary=r.snippet,
                    )
                )

        # RSS / url / gov sources via the feed backend.
        for src in sources:
            label = src.display()
            sources_checked.append(f"{src.type.value}: {label}")
            for item in self._feed.fetch(src.value):
                findings.append(
                    Finding(
                        title=item.title or item.url,
                        url=item.url,
                        source=f"{src.type.value}: {label}",
                        date=item.published,
                        raw_summary=item.summary,
                    )
                )

        deduped = self._dedupe(findings)[: self.settings.max_findings]
        self.log.info(
            "Collected {} finding(s) ({} after dedupe) from {} source(s).",
            len(findings),
            len(deduped),
            len(sources_checked),
        )
        return deduped, sources_checked

    @staticmethod
    def _dedupe(findings: list[Finding]) -> list[Finding]:
        seen: set[str] = set()
        out: list[Finding] = []
        for f in findings:
            fp = f.fingerprint()
            if fp in seen:
                continue
            seen.add(fp)
            out.append(f)
        return out

    # -- Stage 3: impact analyst ------------------------------------------

    def analyze(
        self, profile: BusinessProfile, findings: list[Finding]
    ) -> list[ImpactStatement]:
        if not findings:
            self.log.info("No findings to analyze.")
            return []

        finding_block = "\n\n".join(
            f"[{i + 1}] {f.title}\nURL: {f.url}\nSource: {f.source}\n"
            f"Date: {f.date or 'unknown'}\nSummary: {f.raw_summary or '(none)'}"
            for i, f in enumerate(findings)
        )
        prompt = (
            f"Business profile:\n"
            f"- Industry: {profile.industry}\n"
            f"- Location: {profile.location}\n"
            f"- Operational keywords: {', '.join(profile.operational_keywords) or '(none)'}\n"
            f"- Description: {profile.business_description or '(none)'}\n\n"
            f"Findings to assess:\n{finding_block}\n\n"
            f"Return one impact statement per RELEVANT finding (omit irrelevant ones). "
            f"Use each finding's exact URL."
        )
        data = self.structured(
            system=ANALYST_SYSTEM,
            prompt=prompt,
            schema=schemas.analysis_schema(),
            tool_name=schemas.ANALYZE_TOOL,
        )
        impacts = self._coerce_impacts(data.get("impacts", []), findings)
        self.log.info("Analyst kept {} of {} finding(s).", len(impacts), len(findings))
        return impacts

    def _coerce_impacts(
        self, raw: list[dict], findings: list[Finding]
    ) -> list[ImpactStatement]:
        by_url = {f.url.strip().lower().rstrip("/"): f for f in findings if f.url}
        out: list[ImpactStatement] = []
        seen: set[str] = set()
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            payload = dict(item)
            url = str(payload.get("url", "")).strip()
            match = by_url.get(url.lower().rstrip("/"))
            # Backfill title/date from the matched finding when missing.
            if match:
                payload.setdefault("title", match.title)
                payload.setdefault("date", match.date)
            try:
                payload["relevance"] = Relevance(str(payload.get("relevance", "medium")))
            except (ValueError, TypeError):
                payload["relevance"] = Relevance.MEDIUM
            try:
                impact = ImpactStatement.model_validate(payload)
            except Exception as exc:
                self.log.warning("Discarding malformed impact: {}", exc)
                continue
            fp = impact.fingerprint()
            if fp in seen:
                continue
            seen.add(fp)
            out.append(impact)
        return out


_ = SourceType  # re-exported for callers building sources programmatically

__all__ = ["RegulatoryMonitorAgent", "PLANNER_SYSTEM", "ANALYST_SYSTEM"]
