"""The CRM automation agent.

Orchestrates the full pipeline: fetch records from a CRM client, detect trigger
conditions, match them against the YAML rules, propose actions, gate each
external mutation behind the human approval callback, execute approved actions
via the client (or the LLM, for email drafts), and audit everything.

The LLM is used only for email drafts (via :meth:`BaseAgent.structured`); all
control flow is deterministic and fully testable offline with fakes.
"""

from __future__ import annotations

from lumifie_core import BaseAgent, LLMProvider

from crm_automation.actions import ActionExecutor
from crm_automation.approval import Approver, interactive_approval
from crm_automation.audit import AuditLog, record_run
from crm_automation.config import CRMSettings
from crm_automation.crm.base import CRMClient
from crm_automation.models import (
    AuditEntry,
    Decision,
    ProposedAction,
    RunSummary,
)
from crm_automation.rules import RuleSet, evaluate


class CRMAutomationAgent(BaseAgent):
    name = "crm-automation"
    description = "Monitors a CRM for trigger conditions and takes human-gated actions."

    def __init__(
        self,
        provider: LLMProvider,
        settings: CRMSettings,
        client: CRMClient,
        ruleset: RuleSet,
        *,
        approver: Approver = interactive_approval,
        audit_log: AuditLog | None = None,
    ) -> None:
        super().__init__(provider, settings)
        self.settings: CRMSettings = settings
        self._client = client
        self._ruleset = ruleset
        self._approver = approver
        self._audit = audit_log
        self._executor = ActionExecutor(client, self)

    def run(self, *, dry_run: bool = False) -> RunSummary:  # type: ignore[override]
        """Execute one full monitoring + action cycle."""
        self.log.info(
            "Running CRM automation against '{}' (dry_run={}) with {}",
            self._client.name, dry_run, self.provider.model,
        )
        contacts = self._client.fetch_contacts()
        deals = self._client.fetch_deals()
        triggers, proposed = evaluate(self._ruleset, contacts, deals)
        self.log.info(
            "Scanned {} contact(s), {} deal(s); {} trigger(s), {} proposed action(s).",
            len(contacts), len(deals), len(triggers), len(proposed),
        )

        summary = RunSummary(
            source=self._client.name,
            model=self.provider.model,
            dry_run=dry_run,
            contacts_scanned=len(contacts),
            deals_scanned=len(deals),
            triggers=triggers,
            proposed=proposed,
        )

        for action in proposed:
            summary.audit.append(self._process(action, dry_run))

        summary.token_usage = dict(self.token_usage)

        if self._audit is not None:
            record_run(self._audit, summary)

        self.log.info(
            "Run complete: {} executed, {} skipped, {} failed.",
            len(summary.by_decision(Decision.EXECUTED)),
            len(summary.by_decision(Decision.SKIPPED)) + len(summary.by_decision(Decision.DENIED)),
            len(summary.by_decision(Decision.FAILED)),
        )
        return summary

    # -- per-action handling ----------------------------------------------

    def _process(self, action: ProposedAction, dry_run: bool) -> AuditEntry:
        # Dry run: propose + audit only. Nothing executes, no prompt.
        if dry_run:
            return self._entry(action, Decision.PROPOSED, "Dry run: proposed only, not executed.")

        # External mutations require approval; drafts/flags never mutate externally.
        if action.requires_approval:
            try:
                approved = self._approver(action)
            except Exception as exc:  # noqa: BLE001 - a failing approver denies safely
                self.log.warning("Approval callback failed; denying: {}", exc)
                approved = False
            if not approved:
                return self._entry(action, Decision.DENIED, "Denied at approval gate; skipped.")

        try:
            result = self._executor.execute(action)
        except Exception as exc:  # noqa: BLE001 - audit the failure, keep going
            self.log.warning("Action {} failed: {}", action.type.value, exc)
            return self._entry(action, Decision.FAILED, f"Failed: {exc}")
        return self._entry(action, Decision.EXECUTED, result)

    def _entry(self, action: ProposedAction, decision: Decision, result: str) -> AuditEntry:
        return AuditEntry(
            rule_name=action.rule_name,
            trigger_type=action.trigger_type,
            action_type=action.type,
            target_id=action.target_id,
            params=action.params,
            decision=decision,
            result=result,
        )


__all__ = ["CRMAutomationAgent"]
