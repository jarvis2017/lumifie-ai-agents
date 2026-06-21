"""The five specialized sub-agents the supervisor orchestrates.

Each is a thin, focused ``BaseAgent`` that does one job and returns Pydantic-
validated output via ``BaseAgent.structured`` (tool use where supported, JSON-mode
fallback otherwise). They share the orchestrator's provider/settings; the
orchestrator aggregates their token usage.
"""

from __future__ import annotations

import json
from typing import Any

from lumifie_core import BaseAgent
from lumifie_core.web import ReaderBackend, SearchBackend

from sales_ops.config import ICP, OutreachConfig
from sales_ops.crm import CRMClient
from sales_ops.models import (
    LeadStage,
    OutreachSequence,
    Reply,
    ReplyIntent,
    ScoredLead,
)

_LEVELS = [i.value for i in ReplyIntent]


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def scored_leads_schema() -> dict[str, Any]:
    lead = _obj(
        {
            "company": {"type": "string"},
            "domain": {"type": ["string", "null"]},
            "contact_name": {"type": ["string", "null"]},
            "contact_email": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "source_url": {"type": ["string", "null"]},
            "signals": {"type": "array", "items": {"type": "string"}},
            "icp_fit": {"type": "integer", "minimum": 0, "maximum": 100},
            "tier": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        ["company", "icp_fit", "tier", "reasoning", "signals"],
    )
    return _obj({"leads": {"type": "array", "items": lead}}, ["leads"])


def outreach_schema() -> dict[str, Any]:
    step = _obj(
        {
            "channel": {"type": "string", "enum": ["email", "linkedin"]},
            "day": {"type": "integer", "minimum": 0},
            "subject": {"type": ["string", "null"]},
            "body": {"type": "string"},
        },
        ["channel", "day", "subject", "body"],
    )
    return _obj(
        {
            "steps": {"type": "array", "items": step},
            "personalization_signals": {"type": "array", "items": {"type": "string"}},
        },
        ["steps", "personalization_signals"],
    )


def reply_schema() -> dict[str, Any]:
    return _obj(
        {
            "intent": {"type": "string", "enum": _LEVELS},
            "suggested_action": {"type": "string"},
        },
        ["intent", "suggested_action"],
    )


def report_schema() -> dict[str, Any]:
    return _obj(
        {
            "recommended_next_actions": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
        ["recommended_next_actions", "summary"],
    )


# -- 1. Prospector -----------------------------------------------------------

PROSPECTOR_SYSTEM = (
    "You are a B2B prospecting analyst. From candidate companies found via web "
    "search, score each against the Ideal Customer Profile (0-100), assign a tier "
    "(A/B/C), and explain why. Only include plausible, real-looking leads."
)


class Prospector(BaseAgent):
    name = "prospector"
    description = "Finds, enriches, scores and ranks leads against the ICP."

    def run(self, *args: Any, **kwargs: Any) -> list[ScoredLead]:  # type: ignore[override]
        return self.find(*args, **kwargs)

    def find(
        self, icp: ICP, max_leads: int, search: SearchBackend, reader: ReaderBackend
    ) -> list[ScoredLead]:
        queries = self._queries(icp)
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for q in queries[:3]:
            for r in search.search(q, max_results=5):
                key = (r.url or r.title).lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                candidates.append({"title": r.title, "url": r.url, "snippet": r.snippet})
            if len(candidates) >= max_leads * 3:
                break

        enriched = []
        for c in candidates[:max_leads]:
            page = reader.read(c["url"]) if c.get("url") else ""
            enriched.append({**c, "page_excerpt": page[:600]})

        cand_json = json.dumps(candidates[: max_leads * 3], indent=2)
        enr_json = json.dumps(enriched, indent=2)
        prompt = (
            f"Ideal Customer Profile:\n{icp.as_prompt()}\n\n"
            f"Candidate companies (web search):\n{cand_json}\n\n"
            f"Enriched page excerpts:\n{enr_json}\n\n"
            f"Return up to {max_leads} best-fit, ranked leads."
        )
        data = self.structured(
            system=PROSPECTOR_SYSTEM,
            prompt=prompt,
            schema=scored_leads_schema(),
            tool_name="scored_leads",
        )
        leads: list[ScoredLead] = []
        for i, raw in enumerate(data.get("leads", []) or []):
            raw = {
                **raw,
                "id": raw.get("id") or f"lead-{i + 1}",
                "stage": LeadStage.PROSPECTED.value,
            }
            try:
                leads.append(ScoredLead.model_validate(raw))
            except Exception as exc:
                self.log.warning("Discarding malformed lead: {}", exc)
        leads.sort(key=lambda lead: lead.icp_fit, reverse=True)
        leads = leads[:max_leads]
        for rank, lead in enumerate(leads, start=1):
            lead.rank = rank
        self.log.info("Prospected {} lead(s).", len(leads))
        return leads

    @staticmethod
    def _queries(icp: ICP) -> list[str]:
        out: list[str] = []
        for ind in icp.industries[:2]:
            kw = icp.keywords[0] if icp.keywords else ""
            out.append(f"{ind} companies {kw}".strip())
        if icp.personas:
            out.append(f"{icp.industries[0] if icp.industries else 'B2B'} {icp.personas[0]}")
        return out or ["B2B SaaS companies"]


# -- 2. Outreach -------------------------------------------------------------

OUTREACH_SYSTEM = (
    "You are an expert SDR copywriter. Write a short multi-step outreach sequence "
    "(email + LinkedIn) personalized to the lead's signals and the ICP's value "
    "props. Specific, non-salesy, no false claims; email bodies under 130 words."
)


class Outreach(BaseAgent):
    name = "outreach"
    description = "Crafts hyper-personalized multi-step outreach sequences."

    def run(self, *args: Any, **kwargs: Any) -> OutreachSequence:  # type: ignore[override]
        return self.craft(*args, **kwargs)

    def craft(self, lead: ScoredLead, cfg: OutreachConfig, icp: ICP) -> OutreachSequence:
        prompt = (
            f"Lead:\n{lead.model_dump_json(indent=2)}\n\n"
            f"Value props to emphasize: {icp.value_props}\n"
            f"Tone: {cfg.tone}. Channels: {cfg.channels}. Steps: {cfg.num_steps}.\n\n"
            "Write the sequence using the lead's concrete signals."
        )
        data = self.structured(
            system=OUTREACH_SYSTEM,
            prompt=prompt,
            schema=outreach_schema(),
            tool_name="outreach_sequence",
        )
        try:
            seq = OutreachSequence.model_validate({**data, "lead_id": lead.id})
        except Exception as exc:
            self.log.warning("Malformed sequence for {}: {}", lead.id, exc)
            seq = OutreachSequence(lead_id=lead.id)
        return seq


# -- 3. Reply Handler --------------------------------------------------------

REPLY_SYSTEM = (
    "You triage replies to sales outreach. Classify intent as one of "
    f"{_LEVELS} and suggest the single best next action in one sentence."
)


class ReplyHandler(BaseAgent):
    name = "reply-handler"
    description = "Classifies inbound replies and recommends routing."

    def run(self, *args: Any, **kwargs: Any) -> Reply:  # type: ignore[override]
        return self.classify(*args, **kwargs)

    def classify(self, reply: Reply) -> Reply:
        prompt = f"From: {reply.from_email}\nSubject: {reply.subject}\n\n{reply.body}"
        data = self.structured(
            system=REPLY_SYSTEM,
            prompt=prompt,
            schema=reply_schema(),
            tool_name="reply_classification",
        )
        try:
            reply.intent = ReplyIntent(data.get("intent", "none"))
        except (ValueError, TypeError):
            reply.intent = ReplyIntent.NONE
        reply.suggested_action = data.get("suggested_action", "")
        return reply


# -- 4. CRM Sync (no LLM) ----------------------------------------------------


class CrmSync:
    name = "crm-sync"

    def __init__(self, client: CRMClient) -> None:
        self.client = client

    def sync(self, lead: ScoredLead, stage: str) -> bool:
        return self.client.upsert_lead(lead, stage)


# -- 5. Reporter -------------------------------------------------------------

REPORTER_SYSTEM = (
    "You are a sales-ops analyst. Given pipeline metrics, stale deals, and the "
    "leads worked, write a crisp daily pipeline summary and the top recommended "
    "next actions for the team."
)


class Reporter(BaseAgent):
    name = "reporter"
    description = "Generates the daily pipeline summary and recommendations."

    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        return self.summarize(*args, **kwargs)

    def summarize(self, metrics_json: str, stale_json: str, leads_json: str) -> dict[str, Any]:
        prompt = (
            f"Metrics:\n{metrics_json}\n\nStale deals:\n{stale_json}\n\n"
            f"Leads worked:\n{leads_json}\n\nWrite the summary and recommended next actions."
        )
        return self.structured(
            system=REPORTER_SYSTEM,
            prompt=prompt,
            schema=report_schema(),
            tool_name="pipeline_report",
        )


__all__ = ["Prospector", "Outreach", "ReplyHandler", "CrmSync", "Reporter"]
