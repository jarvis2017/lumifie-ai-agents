"""SalesOpsOrchestrator — the supervisor's brain.

Owns the provider, config, persistence, I/O backends, and the human approval gate;
exposes the five LangGraph node methods and a single ``_gate_and_execute`` path that
EVERY external action flows through (so nothing fires without approval, and dry-run
executes nothing). ``run()`` invokes the checkpointed graph and assembles the result.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

from lumifie_core import LLMProvider, logger
from lumifie_core.web import ReaderBackend, SearchBackend

from sales_ops.approval import Approver, cli_approver
from sales_ops.backends import EmailSender, Mailbox
from sales_ops.config import SalesOpsConfig, SalesOpsSettings
from sales_ops.crm import CRMClient
from sales_ops.models import (
    ActionOutcome,
    ActionType,
    Decision,
    LeadStage,
    OutreachSequence,
    PipelineMetrics,
    PipelineReport,
    PipelineResult,
    ProposedAction,
    Reply,
    ReplyIntent,
    ScoredLead,
)
from sales_ops.state import SalesState
from sales_ops.store import SalesOpsStore
from sales_ops.subagents import CrmSync, Outreach, Prospector, ReplyHandler, Reporter
from sales_ops.supervisor import build_graph

_REPLY_NEEDS_SEND = {ReplyIntent.INTERESTED, ReplyIntent.OBJECTION}


class SalesOpsOrchestrator:
    """Coordinates the five sub-agents through the LangGraph supervisor."""

    def __init__(
        self,
        provider: LLMProvider,
        settings: SalesOpsSettings,
        config: SalesOpsConfig,
        *,
        store: SalesOpsStore,
        search: SearchBackend,
        reader: ReaderBackend,
        mailbox: Mailbox,
        emailer: EmailSender,
        crm_client: CRMClient,
        approver: Approver | None = None,
        dry_run: bool = False,
    ) -> None:
        self.provider = provider
        self.settings = settings
        self.config = config
        self.store = store
        self.search = search
        self.reader = reader
        self.mailbox = mailbox
        self.emailer = emailer
        self.crm_client = crm_client
        self.approver: Approver = approver or cli_approver
        self.dry_run = dry_run

        # Sub-agents share the provider/settings; we aggregate their token usage.
        self.prospector = Prospector(provider, settings)
        self.outreach = Outreach(provider, settings)
        self.reply_handler = ReplyHandler(provider, settings)
        self.crm_sync = CrmSync(crm_client)
        self.reporter = Reporter(provider, settings)
        self._subagents = [self.prospector, self.outreach, self.reply_handler, self.reporter]

        self._pipeline_id = ""

    # -- public API --------------------------------------------------------

    def run(self, pipeline_id: str | None = None) -> PipelineResult:
        pid = pipeline_id or f"pipe-{uuid.uuid4().hex[:12]}"
        self._pipeline_id = pid
        self.store.save_pipeline(pid, self.provider.model, self.dry_run)
        logger.bind(agent="sales-ops").info(
            "Pipeline {} starting (model={}, dry_run={}).", pid, self.provider.model, self.dry_run
        )

        graph = build_graph(self)
        initial: SalesState = {
            "pipeline_id": pid,
            "icp": self.config.icp.model_dump(),
            "max_leads": self.config.max_leads,
            "dry_run": self.dry_run,
            "actions": [],
            "trace": [],
        }
        final = graph.invoke(initial, config={"configurable": {"thread_id": pid}})
        return self._assemble(pid, final)

    # -- nodes -------------------------------------------------------------

    def prospect_node(self, state: SalesState) -> dict[str, Any]:
        leads = self.prospector.find(
            self.config.icp, state.get("max_leads", 5), self.search, self.reader
        )
        for lead in leads:
            self.store.upsert_lead(lead, self._pipeline_id)
        return {"leads": [lead.model_dump() for lead in leads], "prospected": True}

    def outreach_node(self, state: SalesState) -> dict[str, Any]:
        leads = [ScoredLead.model_validate(d) for d in state.get("leads", [])]
        sequences: list[OutreachSequence] = []
        outcomes: list[dict[str, Any]] = []
        for lead in leads:
            seq = self.outreach.craft(lead, self.config.outreach, self.config.icp)
            sequences.append(seq)
            first = seq.steps[0] if seq.steps else None
            action = ProposedAction(
                id=f"out-{lead.id}",
                type=ActionType.START_OUTREACH,
                lead_id=lead.id,
                summary=f"Start {len(seq.steps)}-step outreach to {lead.company}",
                rationale=f"ICP fit {lead.icp_fit} ({lead.tier})",
                requires_approval=True,
                payload={"to": lead.contact_email or "", "subject": first.subject if first else ""},
            )

            def _send(lead=lead, first=first) -> tuple[bool, str]:
                if not (lead.contact_email and first):
                    return False, "no email/step"
                ok = self.emailer.send(lead.contact_email, first.subject or "Hello", first.body)
                return ok, f"sent step 1 to {lead.contact_email}"

            outcome = self._gate_and_execute(action, _send)
            outcomes.append(outcome.model_dump())
            lead.stage = (
                LeadStage.CONTACTED
                if outcome.decision is Decision.EXECUTED
                else LeadStage.OUTREACH_DRAFTED
            )
        return {
            "sequences": [s.model_dump() for s in sequences],
            "leads": [lead.model_dump() for lead in leads],
            "outreached": True,
            "actions": outcomes,
        }

    def reply_node(self, state: SalesState) -> dict[str, Any]:
        leads_by_id = {
            lead["id"]: ScoredLead.model_validate(lead) for lead in state.get("leads", [])
        }
        replies: list[Reply] = []
        outcomes: list[dict[str, Any]] = []
        for raw in self.mailbox.fetch_replies():
            reply = self.reply_handler.classify(raw)
            replies.append(reply)
            lead = leads_by_id.get(reply.lead_id)
            if lead is not None:
                lead.stage = LeadStage.REPLIED
            if reply.intent in _REPLY_NEEDS_SEND:
                action = ProposedAction(
                    id=f"reply-{reply.lead_id}",
                    type=ActionType.SEND_REPLY,
                    lead_id=reply.lead_id,
                    summary=f"Reply to {reply.from_email} ({reply.intent.value})",
                    rationale=reply.suggested_action,
                    requires_approval=True,
                    payload={"to": reply.from_email},
                )

                def _send(reply=reply) -> tuple[bool, str]:
                    ok = self.emailer.send(
                        reply.from_email, f"Re: {reply.subject}", reply.suggested_action
                    )
                    return ok, f"replied to {reply.from_email}"

                outcomes.append(self._gate_and_execute(action, _send).model_dump())
                if reply.intent is ReplyIntent.INTERESTED and lead is not None:
                    lead.stage = LeadStage.QUALIFIED
        return {
            "replies": [r.model_dump() for r in replies],
            "leads": [lead.model_dump() for lead in leads_by_id.values()],
            "replies_checked": True,
            "actions": outcomes,
        }

    def crm_node(self, state: SalesState) -> dict[str, Any]:
        leads = [ScoredLead.model_validate(d) for d in state.get("leads", [])]
        outcomes: list[dict[str, Any]] = []
        for lead in leads:
            action = ProposedAction(
                id=f"crm-{lead.id}",
                type=ActionType.CRM_UPDATE,
                lead_id=lead.id,
                summary=f"Upsert {lead.company} to '{lead.stage.value}' in CRM",
                rationale=f"Keep CRM in sync (stage {lead.stage.value})",
                requires_approval=True,
                payload={"stage": lead.stage.value},
            )

            def _sync(lead=lead) -> tuple[bool, str]:
                ok = self.crm_sync.sync(lead, lead.stage.value)
                return ok, f"crm upsert {lead.company} -> {lead.stage.value}"

            outcome = self._gate_and_execute(action, _sync)
            outcomes.append(outcome.model_dump())
            self.store.upsert_lead(lead, self._pipeline_id)
        return {"crm_synced": True, "actions": outcomes}

    def report_node(self, state: SalesState) -> dict[str, Any]:
        leads = [ScoredLead.model_validate(d) for d in state.get("leads", [])]
        replies = [Reply.model_validate(d) for d in state.get("replies", [])]
        actions = [ActionOutcome.model_validate(d) for d in state.get("actions", [])]
        metrics = self._metrics(leads, replies, actions, state)
        stale = self.store.stale_deals(self.config.stale_after_days)

        data = self.reporter.summarize(
            metrics.model_dump_json(indent=2),
            json.dumps([s.model_dump() for s in stale], indent=2),
            json.dumps([lead.model_dump(mode="json") for lead in leads], indent=2),
        )
        report = PipelineReport(
            pipeline_id=self._pipeline_id,
            metrics=metrics,
            stale_deals=stale,
            recommended_next_actions=data.get("recommended_next_actions", []) or [],
            summary=data.get("summary", "") or self._fallback_summary(metrics),
        )
        return {"report": report.model_dump(mode="json"), "reported": True}

    # -- the single gated-execution path ----------------------------------

    def _gate_and_execute(
        self, action: ProposedAction, executor: Callable[[], tuple[bool, str]]
    ) -> ActionOutcome:
        if self.dry_run:
            outcome = ActionOutcome(
                action_id=action.id,
                type=action.type,
                lead_id=action.lead_id,
                decision=Decision.DRY_RUN,
                detail=f"[dry-run] would: {action.summary}",
                ok=True,
            )
        elif action.requires_approval and not self.approver(action):
            outcome = ActionOutcome(
                action_id=action.id,
                type=action.type,
                lead_id=action.lead_id,
                decision=Decision.DENIED,
                detail="denied at approval gate",
                ok=False,
            )
        else:
            try:
                ok, detail = executor()
                outcome = ActionOutcome(
                    action_id=action.id,
                    type=action.type,
                    lead_id=action.lead_id,
                    decision=Decision.EXECUTED if ok else Decision.FAILED,
                    detail=detail,
                    ok=ok,
                )
            except Exception as exc:  # noqa: BLE001 - never let one action crash the run
                outcome = ActionOutcome(
                    action_id=action.id,
                    type=action.type,
                    lead_id=action.lead_id,
                    decision=Decision.FAILED,
                    detail=f"error: {exc}",
                    ok=False,
                )
        self.store.record_action(self._pipeline_id, outcome)
        return outcome

    # -- assembly ----------------------------------------------------------

    def _metrics(
        self,
        leads: list[ScoredLead],
        replies: list[Reply],
        actions: list[ActionOutcome],
        state: SalesState,
    ) -> PipelineMetrics:
        by_stage: dict[str, int] = {}
        for lead in leads:
            by_stage[lead.stage.value] = by_stage.get(lead.stage.value, 0) + 1
        by_intent: dict[str, int] = {}
        for r in replies:
            by_intent[r.intent.value] = by_intent.get(r.intent.value, 0) + 1
        executed = sum(1 for a in actions if a.decision is Decision.EXECUTED)
        return PipelineMetrics(
            leads_prospected=len(leads),
            sequences_drafted=len(state.get("sequences", [])),
            replies_processed=len(replies),
            actions_proposed=len(actions),
            actions_executed=executed,
            by_stage=by_stage,
            by_reply_intent=by_intent,
        )

    @staticmethod
    def _fallback_summary(metrics: PipelineMetrics) -> str:
        return (
            f"{metrics.leads_prospected} leads prospected, {metrics.sequences_drafted} sequences "
            f"drafted, {metrics.actions_executed}/{metrics.actions_proposed} actions executed."
        )

    def _token_usage(self) -> dict[str, int]:
        total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        for sub in self._subagents:
            for k in total:
                total[k] += int(sub.token_usage.get(k, 0))
        return total

    def _assemble(self, pid: str, final: SalesState) -> PipelineResult:
        report = final.get("report")
        return PipelineResult(
            pipeline_id=pid,
            model=self.provider.model,
            dry_run=self.dry_run,
            leads=[ScoredLead.model_validate(d) for d in final.get("leads", [])],
            sequences=[OutreachSequence.model_validate(d) for d in final.get("sequences", [])],
            replies=[Reply.model_validate(d) for d in final.get("replies", [])],
            actions=[ActionOutcome.model_validate(d) for d in final.get("actions", [])],
            report=PipelineReport.model_validate(report) if report else None,
            token_usage=self._token_usage(),
        )


__all__ = ["SalesOpsOrchestrator"]
